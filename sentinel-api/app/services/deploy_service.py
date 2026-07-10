"""Deployment service.

Handles container deployments via docker compose, including:
- Triggering deployments (pull + recreate)
- Rolling back to a previous image
- Verifying GitHub webhook signatures (HMAC-SHA256)
"""
from __future__ import annotations

import asyncio
import base64
import hashlib
import hmac
import json
import logging
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.deployment import Deployment
from app.models.project import Project
from app.services.deploy_contracts import (
    compare_runtime_services,
    extract_intended_services,
    is_custom_deploy_config,
    normalize_deploy_config,
    validate_bundle_path,
)
from app.services.docker_service import list_compose_project_containers
from app.services.image_utils import (
    apply_env_assignment,
    apply_image_tag,
    compose_env_file_path,
    find_image_tag_env_vars,
    split_image_ref,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Webhook verification
# ---------------------------------------------------------------------------

def verify_webhook(secret: str, payload: bytes, signature: str) -> bool:
    """Verify a GitHub-style HMAC-SHA256 webhook signature.

    Args:
        secret: The shared webhook secret.
        payload: Raw request body bytes.
        signature: Value of the ``X-Hub-Signature-256`` header (``sha256=...``).

    Returns:
        True if the signature is valid.
    """
    if not signature or not secret:
        return False

    if signature.startswith("sha256="):
        signature = signature[7:]

    expected = hmac.new(
        secret.encode("utf-8"),
        payload,
        hashlib.sha256,
    ).hexdigest()

    return hmac.compare_digest(expected, signature)


# ---------------------------------------------------------------------------
# Deployment helpers
# ---------------------------------------------------------------------------

async def _run_command(cmd: list[str], cwd: str | None = None) -> tuple[int, str]:
    """Run a shell command asynchronously and return (returncode, combined output)."""
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
        cwd=cwd,
    )
    stdout, _ = await proc.communicate()
    output = stdout.decode("utf-8", errors="replace") if stdout else ""
    return proc.returncode or 0, output


def _parse_compose_config_json(output: str) -> tuple[dict[str, Any], str | None]:
    """Parse Docker Compose JSON output, tolerating warning lines before JSON."""
    stripped = output.lstrip()
    if stripped.startswith("{") or stripped.startswith("["):
        return json.loads(stripped), None

    object_index = output.find("{")
    array_index = output.find("[")
    candidates = [idx for idx in (object_index, array_index) if idx >= 0]
    if not candidates:
        raise json.JSONDecodeError("No JSON object found", output, 0)

    start = min(candidates)
    prefix = output[:start].strip()
    return json.loads(output[start:].lstrip()), prefix or None


async def _health_check(project: Project) -> bool:
    """Run a basic HTTP health check against the project's health endpoint.

    Returns True if the endpoint responds with a 2xx status within 30 seconds.
    """
    if not project.health_endpoint or not project.domain:
        # No health endpoint configured - assume healthy
        return True

    url = f"https://{project.domain}{project.health_endpoint}"
    import httpx

    for attempt in range(6):  # 6 attempts, 5s apart = 30s total
        try:
            async with httpx.AsyncClient(timeout=5.0, verify=False) as client:
                resp = await client.get(url)
                if 200 <= resp.status_code < 300:
                    logger.info("Health check passed for %s (attempt %d)", project.name, attempt + 1)
                    return True
        except Exception:
            pass
        if attempt < 5:
            await asyncio.sleep(5)

    logger.warning("Health check failed for %s after 6 attempts", project.name)
    return False


async def _ghcr_login(logs: list[str]) -> None:
    """Login to GHCR using configured credentials. Skips if not configured."""
    from app.config import settings
    from app.services.instance_config import get_effective
    if not settings.ghcr_token:
        return

    ghcr_user = get_effective("ghcr_user") or settings.ghcr_user

    logs.append("=== GHCR login ===")
    proc = await asyncio.create_subprocess_exec(
        "docker", "login", "ghcr.io",
        "-u", ghcr_user,
        "--password-stdin",
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
    )
    stdout, _ = await proc.communicate(input=settings.ghcr_token.encode())
    output = stdout.decode("utf-8", errors="replace") if stdout else ""
    if proc.returncode == 0:
        logs.append("GHCR login successful")
    else:
        logs.append(f"GHCR login failed: {output}")


def _resolve_compose_file(project: Project) -> Path | None:
    """Locate the on-disk compose file Sentinel runs ``docker compose`` against.

    Mirrors the directory/-f conventions used by ``trigger_deployment``.
    Returns None if no compose file exists (caller logs + skips the rewrite;
    Docker itself will then fail loudly at pull/up if it is truly missing).
    """
    compose_dir = Path(project.compose_path or f"/apps/{project.name}")
    if project.compose_file:
        cf = Path(project.compose_file)
        path = cf if cf.is_absolute() else compose_dir / cf
        return path if path.exists() else None
    for name in ("docker-compose.yml", "docker-compose.yaml"):
        path = compose_dir / name
        if path.exists():
            return path
    return None


def _base_image_for_project(project: Project) -> str | None:
    """Return the generated deploy base image for legacy Sentinel projects."""
    if project.ghcr_image:
        base, _ = split_image_ref(project.ghcr_image)
        return base
    if project.github_repo:
        from app.services.wizard_service import _ghcr_image
        return _ghcr_image(project.github_repo)
    return None


def _snapshot_file(path: Path) -> dict[str, Any]:
    """Capture a file before Sentinel mutates it."""
    return {
        "path": str(path),
        "existed": path.exists(),
        "content": path.read_bytes() if path.exists() else None,
    }


def _remember_snapshot(snapshots: list[dict[str, Any]], path: Path) -> None:
    """Record one file snapshot once."""
    if any(item["path"] == str(path) for item in snapshots):
        return
    snapshots.append(_snapshot_file(path))


def _restore_snapshots(snapshots: list[dict[str, Any]], all_logs: list[str]) -> None:
    """Restore all captured files in reverse mutation order."""
    for snapshot in reversed(snapshots):
        path = Path(snapshot["path"])
        if snapshot["existed"]:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(snapshot["content"] or b"")
            all_logs.append(f"Restored {path}")
        elif path.exists():
            path.unlink()
            all_logs.append(f"Removed new deploy file {path}")


def _bundle_file_bytes(file_entry: dict[str, Any]) -> bytes:
    """Decode one webhook compose-bundle file entry."""
    encoding = file_entry.get("encoding") or "utf-8"
    content = file_entry.get("content")
    if content is None:
        raise ValueError("compose bundle file is missing content")
    if encoding == "base64":
        return base64.b64decode(content)
    if encoding != "utf-8":
        raise ValueError(f"unsupported compose bundle encoding: {encoding}")
    return str(content).encode("utf-8")


def _apply_compose_bundle(
    project: Project,
    compose_bundle: dict[str, Any] | None,
    snapshots: list[dict[str, Any]],
    all_logs: list[str],
) -> None:
    """Persist a signed project-owned compose bundle under the project directory."""
    deploy_config = normalize_deploy_config(project.deploy_config)
    if deploy_config["compose_source"] == "webhook_bundle" and not compose_bundle:
        raise RuntimeError("project requires a compose_bundle webhook payload")
    if not compose_bundle:
        return

    files = compose_bundle.get("files") or []
    if not files:
        raise RuntimeError("compose_bundle must include at least one file")

    root = Path(project.compose_path or f"/apps/{project.name}")
    written: list[str] = []
    for file_entry in files:
        rel_path = validate_bundle_path(str(file_entry.get("path") or ""))
        dest = root / rel_path
        _remember_snapshot(snapshots, dest)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(_bundle_file_bytes(file_entry))
        written.append(rel_path)

    all_logs.append(
        f"Applied compose bundle ({len(written)} file(s)): {', '.join(written[:8])}"
        + (" ..." if len(written) > 8 else "")
    )


async def _render_compose_config(
    compose_prefix: list[str],
    compose_dir: str,
    all_logs: list[str],
) -> dict[str, Any]:
    """Render Docker Compose config as JSON for deterministic assertions."""
    rc, output = await _run_command(
        compose_prefix + ["config", "--format", "json"],
        cwd=compose_dir,
    )
    all_logs.append("=== docker compose config --format json ===")
    if rc != 0:
        all_logs.append(output)
        raise RuntimeError(f"docker compose config --format json failed (rc={rc})")
    try:
        rendered, warning_prefix = _parse_compose_config_json(output)
    except json.JSONDecodeError as exc:
        all_logs.append(output[:4000])
        raise RuntimeError(f"docker compose config did not return JSON: {exc}") from exc
    if warning_prefix:
        all_logs.append(f"Ignored docker compose config warning prefix: {warning_prefix[:500]}")
    services = rendered.get("services") or {}
    all_logs.append(f"Rendered compose project {rendered.get('name') or '-'} with {len(services)} service(s)")
    return rendered


def _compose_project_name(project: Project, rendered_config: dict[str, Any] | None) -> str:
    """Return the Compose project name Docker labels will use."""
    if rendered_config and rendered_config.get("name"):
        return str(rendered_config["name"])
    return project.name


async def _build_intended_map(
    project: Project,
    rendered_config: dict[str, Any],
    image_tag: str | None,
) -> dict[str, Any]:
    """Build and validate the intended managed service image map."""
    deploy_config = normalize_deploy_config(project.deploy_config)
    intended = extract_intended_services(
        rendered_config,
        deploy_config,
        image_tag,
        default_base_image=_base_image_for_project(project),
    )
    if intended["errors"]:
        raise RuntimeError("; ".join(intended["errors"]))
    return intended


async def _assert_live_services(
    project: Project,
    intended: dict[str, Any],
    all_logs: list[str],
) -> dict[str, Any]:
    """Assert live Docker containers match the intended compose image map."""
    services = intended.get("services") or {}
    if not services:
        return {"ok": True, "services": {}, "errors": []}

    compose_project = intended.get("compose_project_name") or project.name
    runtime = await asyncio.to_thread(list_compose_project_containers, compose_project)
    result = compare_runtime_services(services, runtime)
    all_logs.append("=== service image assertions ===")
    all_logs.append(json.dumps(result, sort_keys=True))
    if not result["ok"]:
        raise RuntimeError("service image assertions failed: " + "; ".join(result["errors"]))
    return result


async def _apply_requested_image(
    project: Project,
    image_tag: str,
    all_logs: list[str],
    snapshots: list[dict[str, Any]],
) -> tuple[str | None, str | None, str | None, str | None, bool]:
    """Apply a requested image tag to the project's compose deployment inputs.

    Returns ``(path, original_text, previous_pin, new_pin, pin_changed)`` on a
    successful compose or env rewrite, or ``(None, None, None, None, False)``
    if no rewrite was performed (a clear WARNING is appended to ``all_logs`` in
    that case).

    Does NOT touch the DB and does NOT raise on missing-file / 0-match - the
    caller decides what to do with the result.
    """
    # 1. Derive the base image (tag stripped). The base must come from the
    #    pinned image, never the project name (e.g. pandastarz-email-worker's
    #    image is the backend image).
    base = _base_image_for_project(project)
    if not base:
        all_logs.append(
            "WARNING: cannot determine base image (no ghcr_image / github_repo)"
            " - skipping compose image rewrite; deploying the current pinned image"
        )
        return None, None, None, None, False

    # 2. Locate the compose file.
    path = _resolve_compose_file(project)
    if path is None:
        all_logs.append(
            f"WARNING: compose file not found under "
            f"{project.compose_path or f'/apps/{project.name}'} - skipping image rewrite"
        )
        return None, None, None, None, False

    # 3. Rewrite matching image line(s).
    original = path.read_text()
    new_text, count = apply_image_tag(original, base, image_tag)
    deploy_config = normalize_deploy_config(project.deploy_config)
    detected_tag_env_vars = find_image_tag_env_vars(original)
    configured_tag_env_vars = deploy_config.get("image_tag_variables") or []
    tag_env_vars: list[str] = []

    if configured_tag_env_vars:
        missing = [key for key in configured_tag_env_vars if key not in detected_tag_env_vars]
        if missing:
            raise RuntimeError(
                "configured compose tag variable(s) not referenced by image lines: "
                + ", ".join(missing)
            )
        tag_env_vars = configured_tag_env_vars
    elif count == 0:
        tag_env_vars = detected_tag_env_vars

    if tag_env_vars:
        # Docker Compose resolves the implicit .env from the compose
        # project directory. With `docker compose -f subdir/file.yml`,
        # that is the compose file's directory, not necessarily
        # project.compose_path.
        env_path = compose_env_file_path(path)
        env_original = env_path.read_text() if env_path.exists() else ""
        env_text = env_original
        for key in tag_env_vars:
            env_text, _ = apply_env_assignment(env_text, key, image_tag)
        _remember_snapshot(snapshots, env_path)
        env_path.parent.mkdir(parents=True, exist_ok=True)
        env_path.write_text(env_text)
        display_path = env_path.name
        try:
            display_path = str(env_path.relative_to(Path(project.compose_path or f"/apps/{project.name}")))
        except ValueError:
            pass
        all_logs.append(
            f"Updated compose tag env var(s) {', '.join(tag_env_vars)} "
            f"in {display_path} -> {image_tag}"
        )
        if count == 0:
            return str(env_path), env_original, project.ghcr_image, project.ghcr_image, False

    if count == 0:
        all_logs.append(
            f"WARNING: no image lines in {path.name} matched base '{base}' "
            f"(matched 0) - NOT rewriting; deploying the current pinned image. "
            f"Check project.ghcr_image or configure a compose *IMAGE_TAG env var."
        )
        return None, None, None, None, False

    if project.project_type == "blended" and count < 2:
        all_logs.append(
            f"WARNING: blended project but only {count} image line(s) matched "
            f"base '{base}' - the other service may be left on a stale image"
        )

    _remember_snapshot(snapshots, path)
    path.write_text(new_text)
    all_logs.append(
        f"Rewrote {count} image line(s) in {path.name} -> {base}:{image_tag}"
    )
    return str(path), original, project.ghcr_image, f"{base}:{image_tag}", True


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

async def trigger_deployment(
    db: AsyncSession,
    project: Project,
    image_tag: Optional[str] = None,
    compose_bundle: Optional[dict[str, Any]] = None,
    triggered_by: str = "manual",
    trigger_type: str = "manual",
) -> Deployment:
    """Trigger a deployment for a project.

    1. Record the deployment as ``in_progress``.
    2. Run ``docker compose pull`` in the project's compose directory.
    3. Run ``docker compose up -d`` to recreate containers.
    4. Run a health check.
    5. On failure, attempt automatic rollback.

    Returns the completed Deployment record.
    """
    start = time.time()

    deployment = Deployment(
        project_id=project.id,
        trigger=trigger_type,
        image_tag=image_tag or "latest",
        previous_image_tag=project.ghcr_image,
        status="in_progress",
        triggered_by=triggered_by,
    )
    db.add(deployment)
    await db.flush()

    compose_dir = project.compose_path or f"/apps/{project.name}"
    compose_prefix = ["docker", "compose"]
    if project.compose_file:
        compose_prefix += ["-f", project.compose_file]
    all_logs: list[str] = []
    deploy_config = normalize_deploy_config(project.deploy_config)
    deploy_metadata: dict[str, Any] = {
        "deploy_config": deploy_config,
        "compose_bundle": None,
        "effective_compose": None,
        "intended_services": None,
        "runtime_assertions": None,
        "rollback": {},
    }

    # Bound before the try so the except can always reference them, even if
    # _apply_requested_image raises (it does file I/O).
    rewrote_path = backup_text = prev_pin = new_pin = None
    pin_changed = False
    snapshots: list[dict[str, Any]] = []
    intended: dict[str, Any] | None = None
    previous_intended: dict[str, Any] | None = None

    try:
        if is_custom_deploy_config(deploy_config):
            try:
                previous_rendered = await _render_compose_config(compose_prefix, compose_dir, all_logs)
                previous_intended = await _build_intended_map(project, previous_rendered, None)
                previous_intended["compose_project_name"] = _compose_project_name(project, previous_rendered)
            except Exception as previous_exc:
                all_logs.append(f"WARNING: could not capture previous intended image map: {previous_exc}")

        _apply_compose_bundle(project, compose_bundle, snapshots, all_logs)
        if compose_bundle:
            deploy_metadata["compose_bundle"] = {
                "source": compose_bundle.get("source"),
                "file_count": len(compose_bundle.get("files") or []),
            }

        # Apply the requested image tag to the on-disk compose file so the
        # containers actually move to it. Keys off the raw function arg -
        # deployment.image_tag is always truthy via `or "latest"`.
        if image_tag:
            (
                rewrote_path,
                backup_text,
                prev_pin,
                new_pin,
                pin_changed,
            ) = await _apply_requested_image(
                project, image_tag, all_logs, snapshots
            )
            if rewrote_path is not None and pin_changed:
                project.ghcr_image = new_pin
                await db.flush()
                await db.refresh(project, ["updated_at"])  # MissingGreenlet guard
                all_logs.append(f"Updated project pin: ghcr_image -> {new_pin}")
            if rewrote_path is not None or is_custom_deploy_config(deploy_config):
                rendered = await _render_compose_config(compose_prefix, compose_dir, all_logs)
                intended = await _build_intended_map(project, rendered, image_tag)
                intended["compose_project_name"] = _compose_project_name(project, rendered)
                deploy_metadata["effective_compose"] = {
                    "name": intended["compose_project_name"],
                    "managed_count": intended["managed_count"],
                    "services": list((rendered.get("services") or {}).keys()),
                }
                deploy_metadata["intended_services"] = intended["services"]
        elif is_custom_deploy_config(deploy_config):
            rendered = await _render_compose_config(compose_prefix, compose_dir, all_logs)
            intended = await _build_intended_map(project, rendered, None)
            intended["compose_project_name"] = _compose_project_name(project, rendered)
            deploy_metadata["effective_compose"] = {
                "name": intended["compose_project_name"],
                "managed_count": intended["managed_count"],
                "services": list((rendered.get("services") or {}).keys()),
            }
            deploy_metadata["intended_services"] = intended["services"]
        # No explicit tag -> intentionally no rewrite: restart on the current
        # pinned image; never regress a SHA pin down to :latest.

        # GHCR login (ensures auth is fresh before pulling)
        await _ghcr_login(all_logs)

        # Pull
        all_logs.append("=== docker compose pull ===")
        rc, output = await _run_command(compose_prefix + ["pull"], cwd=compose_dir)
        all_logs.append(output)
        if rc != 0:
            raise RuntimeError(f"docker compose pull failed (rc={rc})")

        # Up
        all_logs.append("=== docker compose up -d ===")
        rc, output = await _run_command(compose_prefix + ["up", "-d"], cwd=compose_dir)
        all_logs.append(output)
        if rc != 0:
            raise RuntimeError(f"docker compose up -d failed (rc={rc})")

        # Health check
        all_logs.append("=== health check ===")
        healthy = await _health_check(project)
        if not healthy:
            all_logs.append("Health check FAILED - initiating rollback")
            raise RuntimeError("Health check failed after deployment")

        if intended is not None:
            deploy_metadata["runtime_assertions"] = await _assert_live_services(
                project, intended, all_logs
            )

        all_logs.append("Health check PASSED")
        deployment.status = "success"

    except Exception as exc:
        logger.error("Deployment failed for %s: %s", project.name, exc)
        all_logs.append(f"ERROR: {exc}")
        deploy_metadata["failure"] = str(exc)

        # True rollback: restore the original compose file + pin BEFORE the
        # fallback `up -d` so it actually reverts the containers. Wrapped so a
        # restore error can never block status="failed".
        try:
            _restore_snapshots(snapshots, all_logs)
            if pin_changed and prev_pin is not None:
                project.ghcr_image = prev_pin
                await db.flush()
                await db.refresh(project, ["updated_at"])  # MissingGreenlet guard
                all_logs.append(f"Reverted project pin: ghcr_image -> {prev_pin}")
        except Exception as restore_exc:
            all_logs.append(f"WARNING: failed to restore compose/pin: {restore_exc}")

        # Fallback (now meaningful): re-pull + recreate on the previous image.
        try:
            all_logs.append("=== rollback: docker compose pull + up -d (previous) ===")
            rc, output = await _run_command(compose_prefix + ["pull"], cwd=compose_dir)
            all_logs.append(output)
            if rc != 0:
                raise RuntimeError(f"rollback docker compose pull failed (rc={rc})")
            rc, output = await _run_command(compose_prefix + ["up", "-d"], cwd=compose_dir)
            all_logs.append(output)
            if rc != 0:
                raise RuntimeError(f"rollback docker compose up -d failed (rc={rc})")
            if previous_intended is not None:
                deploy_metadata["rollback"]["runtime_assertions"] = await _assert_live_services(
                    project,
                    previous_intended,
                    all_logs,
                )
        except Exception as rb_exc:
            all_logs.append(f"Rollback also failed: {rb_exc}")
            deploy_metadata["rollback"]["failure"] = str(rb_exc)

        deployment.status = "failed"

    elapsed = int(time.time() - start)
    deployment.completed_at = datetime.now(timezone.utc)
    deployment.duration_seconds = elapsed
    deployment.logs = "\n".join(all_logs)
    deployment.deploy_metadata = deploy_metadata

    await db.flush()
    return deployment


async def record_external_deployment(
    db: AsyncSession,
    project: Project,
    image_tag: Optional[str] = None,
    triggered_by: str = "webhook",
    trigger_type: str = "webhook",
    status: str = "success",
    logs: Optional[str] = None,
    deploy_metadata: Optional[dict[str, Any]] = None,
) -> Deployment:
    """Record a deployment completed outside Sentinel's docker-compose runner.

    This is for Sentinel itself and similar stacks where an external deploy
    path is authoritative, but the normal status table should still reflect
    the latest verified rollout.
    """
    if status not in {"success", "failed"}:
        raise ValueError("recorded deployment status must be success or failed")

    now = datetime.now(timezone.utc)
    tag = image_tag or "latest"
    metadata = {
        "record_only": True,
        "source": "external",
        "external_metadata": deploy_metadata or {},
    }
    deployment = Deployment(
        project_id=project.id,
        trigger=trigger_type,
        image_tag=tag,
        previous_image_tag=project.ghcr_image,
        status=status,
        started_at=now,
        completed_at=now,
        duration_seconds=0,
        logs=logs or f"Recorded external deployment for {project.name} at tag {tag}; no compose action was run by Sentinel.",
        deploy_metadata=metadata,
        triggered_by=triggered_by,
    )
    db.add(deployment)
    await db.flush()
    return deployment


async def rollback_deployment(
    db: AsyncSession,
    project: Project,
    target_deployment: Deployment,
    triggered_by: str = "manual",
) -> Deployment:
    """Roll back a project to the state of a previous deployment.

    Creates a new deployment record with trigger="rollback".
    """
    start = time.time()

    deployment = Deployment(
        project_id=project.id,
        trigger="rollback",
        image_tag=target_deployment.image_tag,
        previous_image_tag=project.ghcr_image,
        status="in_progress",
        triggered_by=triggered_by,
    )
    db.add(deployment)
    await db.flush()

    compose_dir = project.compose_path or f"/apps/{project.name}"
    compose_prefix = ["docker", "compose"]
    if project.compose_file:
        compose_prefix += ["-f", project.compose_file]
    all_logs: list[str] = [f"Rolling back to deployment {target_deployment.id} (tag: {target_deployment.image_tag})"]
    deploy_config = normalize_deploy_config(project.deploy_config)
    deploy_metadata: dict[str, Any] = {
        "deploy_config": deploy_config,
        "rollback_to": target_deployment.id,
        "effective_compose": None,
        "intended_services": None,
        "runtime_assertions": None,
    }

    # Bound before the try so the except can always reference them.
    rewrote_path = backup_text = prev_pin = new_pin = None
    pin_changed = False
    snapshots: list[dict[str, Any]] = []
    intended: dict[str, Any] | None = None

    try:
        # Move the on-disk compose file to the target deployment's image tag so
        # the rollback actually changes the running containers.
        if target_deployment.image_tag:
            (
                rewrote_path,
                backup_text,
                prev_pin,
                new_pin,
                pin_changed,
            ) = await _apply_requested_image(
                project, target_deployment.image_tag, all_logs, snapshots
            )
            if rewrote_path is not None and pin_changed:
                project.ghcr_image = new_pin
                await db.flush()
                await db.refresh(project, ["updated_at"])  # MissingGreenlet guard
                all_logs.append(f"Updated project pin: ghcr_image -> {new_pin}")
            if rewrote_path is not None or is_custom_deploy_config(deploy_config):
                rendered = await _render_compose_config(compose_prefix, compose_dir, all_logs)
                intended = await _build_intended_map(project, rendered, target_deployment.image_tag)
                intended["compose_project_name"] = _compose_project_name(project, rendered)
                deploy_metadata["effective_compose"] = {
                    "name": intended["compose_project_name"],
                    "managed_count": intended["managed_count"],
                    "services": list((rendered.get("services") or {}).keys()),
                }
                deploy_metadata["intended_services"] = intended["services"]

        await _ghcr_login(all_logs)

        all_logs.append("=== docker compose pull ===")
        rc, output = await _run_command(compose_prefix + ["pull"], cwd=compose_dir)
        all_logs.append(output)

        all_logs.append("=== docker compose up -d ===")
        rc, output = await _run_command(compose_prefix + ["up", "-d"], cwd=compose_dir)
        all_logs.append(output)
        if rc != 0:
            raise RuntimeError(f"docker compose up -d failed during rollback (rc={rc})")

        if intended is not None:
            deploy_metadata["runtime_assertions"] = await _assert_live_services(
                project, intended, all_logs
            )

        all_logs.append("Rollback completed")
        deployment.status = "success"

    except Exception as exc:
        logger.error("Rollback failed for %s: %s", project.name, exc)
        all_logs.append(f"ERROR: {exc}")
        deploy_metadata["failure"] = str(exc)

        # Restore the original compose file + pin so a failed rollback leaves
        # the project exactly as it was.
        try:
            _restore_snapshots(snapshots, all_logs)
            if pin_changed and prev_pin is not None:
                project.ghcr_image = prev_pin
                await db.flush()
                await db.refresh(project, ["updated_at"])  # MissingGreenlet guard
                all_logs.append(f"Reverted project pin: ghcr_image -> {prev_pin}")
        except Exception as restore_exc:
            all_logs.append(f"WARNING: failed to restore compose/pin: {restore_exc}")

        deployment.status = "failed"

    elapsed = int(time.time() - start)
    deployment.completed_at = datetime.now(timezone.utc)
    deployment.duration_seconds = elapsed
    deployment.logs = "\n".join(all_logs)
    deployment.deploy_metadata = deploy_metadata

    await db.flush()
    return deployment


async def list_deployments(
    db: AsyncSession,
    project_id: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
) -> dict[str, Any]:
    """Return paginated deployment records, newest first."""
    base = select(Deployment)
    count_base = select(func.count()).select_from(Deployment)

    if project_id:
        base = base.where(Deployment.project_id == project_id)
        count_base = count_base.where(Deployment.project_id == project_id)

    total_result = await db.execute(count_base)
    total = total_result.scalar() or 0

    q = (
        base
        .order_by(Deployment.started_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    result = await db.execute(q)
    items = list(result.scalars().all())

    return {"items": items, "total": total, "page": page, "page_size": page_size}


async def get_deployment(db: AsyncSession, deployment_id: str) -> Deployment | None:
    """Fetch a single deployment by ID."""
    result = await db.execute(select(Deployment).where(Deployment.id == deployment_id))
    return result.scalar_one_or_none()
