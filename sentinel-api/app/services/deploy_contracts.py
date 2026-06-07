"""Pure helpers for custom compose deployment contracts."""
from __future__ import annotations

from pathlib import PurePosixPath
from typing import Any

from app.services.image_utils import split_image_ref


def normalize_deploy_config(raw: dict[str, Any] | None) -> dict[str, Any]:
    """Return a predictable deploy-config shape from a project JSON field."""
    raw = raw or {}
    return {
        "compose_source": raw.get("compose_source") or "sentinel",
        "image_tag_variables": list(raw.get("image_tag_variables") or []),
        "project_image_prefixes": list(raw.get("project_image_prefixes") or []),
        "edge_service": raw.get("edge_service") or None,
        "artifact_contract": raw.get("artifact_contract"),
    }


def is_custom_deploy_config(config: dict[str, Any]) -> bool:
    """Return True when a project opted into custom compose deploy semantics."""
    return bool(
        config.get("compose_source") != "sentinel"
        or config.get("image_tag_variables")
        or config.get("project_image_prefixes")
        or config.get("edge_service")
    )


def validate_bundle_path(path: str) -> str:
    """Validate a webhook bundle path and return its normalized POSIX form."""
    candidate = PurePosixPath(path)
    if not path or path.strip() != path:
        raise ValueError("bundle path must be non-empty and trimmed")
    if candidate.is_absolute():
        raise ValueError(f"bundle path must be relative: {path}")
    if any(part in ("", ".", "..") for part in candidate.parts):
        raise ValueError(f"bundle path contains an unsafe segment: {path}")
    if candidate.name == ".env":
        raise ValueError(f"bundle path may not replace dotenv secrets: {path}")
    return candidate.as_posix()


def default_project_image_names(base_image: str | None) -> set[str]:
    """Return Sentinel's generated single/blended image names."""
    if not base_image:
        return set()
    return {base_image, f"{base_image}-api", f"{base_image}-ui"}


def image_matches_prefix(image: str, prefixes: list[str]) -> bool:
    """Return True when an image reference belongs to any configured prefix."""
    name, _tag = split_image_ref(image)
    return any(name.startswith(prefix) or image.startswith(prefix) for prefix in prefixes)


def image_uses_tag(image: str, image_tag: str) -> bool:
    """Return True if an image reference resolves to the requested tag/digest."""
    if image_tag.startswith("sha256:"):
        return image.endswith(f"@{image_tag}") or image.endswith(f"@sha256:{image_tag.removeprefix('sha256:')}")
    if "@sha256:" in image:
        return False
    _name, tag = split_image_ref(image)
    return tag == image_tag


def extract_intended_services(
    rendered_config: dict[str, Any],
    deploy_config: dict[str, Any],
    image_tag: str | None,
    *,
    default_base_image: str | None = None,
) -> dict[str, Any]:
    """Build the intended service/image map from rendered compose JSON."""
    services = rendered_config.get("services") or {}
    prefixes = list(deploy_config.get("project_image_prefixes") or [])
    edge_service = deploy_config.get("edge_service")
    default_names = default_project_image_names(default_base_image)
    intended: dict[str, dict[str, Any]] = {}
    errors: list[str] = []

    for service_name, service_def in services.items():
        image = service_def.get("image")
        if not isinstance(image, str) or not image:
            continue

        image_name, tag = split_image_ref(image)
        managed = image_matches_prefix(image, prefixes) if prefixes else image_name in default_names
        if not managed:
            continue

        restart = service_def.get("restart")
        one_shot = restart in ("no", "none", False)
        if image_tag and not image_uses_tag(image, image_tag):
            errors.append(
                f"service {service_name} image {image} does not use requested tag/digest {image_tag}"
            )

        intended[service_name] = {
            "service": service_name,
            "image": image,
            "image_name": image_name,
            "tag": tag,
            "one_shot": one_shot,
        }

    if edge_service:
        edge_def = services.get(edge_service)
        if edge_def is None:
            errors.append(f"edge service {edge_service} is not present in rendered compose")
        elif edge_service not in intended:
            edge_image = edge_def.get("image")
            errors.append(
                f"edge service {edge_service} image {edge_image or '-'} is not a managed project image"
            )

    if is_custom_deploy_config(deploy_config) and not intended:
        errors.append("rendered compose has no managed project images")

    return {
        "compose_project_name": rendered_config.get("name"),
        "services": intended,
        "errors": errors,
        "managed_count": len(intended),
    }


def compare_runtime_services(
    intended_services: dict[str, dict[str, Any]],
    runtime_services: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    """Compare intended compose services to live Docker containers."""
    results: dict[str, dict[str, Any]] = {}
    errors: list[str] = []

    for service_name, intended in intended_services.items():
        runtime = runtime_services.get(service_name)
        if runtime is None:
            errors.append(f"service {service_name} has no live compose container")
            results[service_name] = {"status": "missing", "expected_image": intended["image"]}
            continue

        service_errors: list[str] = []
        if runtime.get("image") != intended["image"]:
            service_errors.append(
                f"image mismatch expected {intended['image']} got {runtime.get('image') or '-'}"
            )

        state = runtime.get("status")
        exit_code = runtime.get("exit_code")
        if intended.get("one_shot"):
            if state not in ("exited", "running") or (state == "exited" and exit_code not in (0, None)):
                service_errors.append(f"one-shot state is {state} exit={exit_code}")
        elif state != "running":
            service_errors.append(f"container state is {state}")

        if runtime.get("health") == "unhealthy":
            service_errors.append("container health is unhealthy")

        if service_errors:
            errors.extend(f"service {service_name}: {err}" for err in service_errors)

        results[service_name] = {
            "status": "failed" if service_errors else "matched",
            "expected_image": intended["image"],
            "actual_image": runtime.get("image"),
            "image_id": runtime.get("image_id"),
            "container": runtime.get("container"),
            "state": state,
            "health": runtime.get("health"),
            "exit_code": exit_code,
            "errors": service_errors,
        }

    return {"ok": not errors, "errors": errors, "services": results}
