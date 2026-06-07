"""Unit tests for custom compose deployment contract helpers."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.deploy_contracts import (  # noqa: E402
    compare_runtime_services,
    extract_intended_services,
    normalize_deploy_config,
    validate_bundle_path,
)


DEPLOY_CONFIG = normalize_deploy_config(
    {
        "compose_source": "webhook_bundle",
        "image_tag_variables": ["CONNECT_IMAGE_TAG"],
        "project_image_prefixes": ["ghcr.io/getpayd-tech/fixture-"],
        "edge_service": "fixture",
        "artifact_contract": {"static": "packaged in edge image"},
    }
)


def _rendered(edge_image="ghcr.io/getpayd-tech/fixture-edge:abc123"):
    return {
        "name": "fixture",
        "services": {
            "app": {
                "image": "ghcr.io/getpayd-tech/fixture-app:abc123",
                "restart": "unless-stopped",
            },
            "migrations": {
                "image": "ghcr.io/getpayd-tech/fixture-app:abc123",
                "restart": "no",
            },
            "fixture": {
                "image": edge_image,
                "restart": "unless-stopped",
            },
            "redis": {
                "image": "redis:7-alpine",
                "restart": "unless-stopped",
            },
        },
    }


def test_validate_bundle_path_accepts_project_relative_files():
    assert validate_bundle_path("deploy/sentinel/docker-compose.yml") == "deploy/sentinel/docker-compose.yml"


def test_validate_bundle_path_rejects_unsafe_paths():
    for path in ("/tmp/docker-compose.yml", "../docker-compose.yml", "deploy/.env"):
        try:
            validate_bundle_path(path)
        except ValueError:
            pass
        else:
            raise AssertionError(f"expected {path} to be rejected")


def test_extract_intended_services_includes_custom_edge_and_one_shot():
    intended = extract_intended_services(_rendered(), DEPLOY_CONFIG, "abc123")
    assert intended["errors"] == []
    assert intended["managed_count"] == 3
    assert sorted(intended["services"]) == ["app", "fixture", "migrations"]
    assert intended["services"]["fixture"]["image"] == "ghcr.io/getpayd-tech/fixture-edge:abc123"
    assert intended["services"]["migrations"]["one_shot"] is True


def test_extract_intended_services_fails_when_edge_is_generic_caddy():
    intended = extract_intended_services(_rendered("caddy:2-alpine"), DEPLOY_CONFIG, "abc123")
    assert "edge service fixture image caddy:2-alpine is not a managed project image" in intended["errors"]


def test_extract_intended_services_fails_when_managed_image_uses_old_tag():
    intended = extract_intended_services(
        _rendered("ghcr.io/getpayd-tech/fixture-edge:old"),
        DEPLOY_CONFIG,
        "abc123",
    )
    assert any("fixture" in err and "abc123" in err for err in intended["errors"])


def test_compare_runtime_services_detects_stale_edge_image():
    intended = extract_intended_services(_rendered(), DEPLOY_CONFIG, "abc123")["services"]
    runtime = {
        "app": {
            "container": "fixture-app-1",
            "status": "running",
            "health": "healthy",
            "image": "ghcr.io/getpayd-tech/fixture-app:abc123",
            "image_id": "sha256:app",
        },
        "migrations": {
            "container": "fixture-migrations-1",
            "status": "exited",
            "exit_code": 0,
            "image": "ghcr.io/getpayd-tech/fixture-app:abc123",
            "image_id": "sha256:app",
        },
        "fixture": {
            "container": "fixture-fixture-1",
            "status": "running",
            "health": None,
            "image": "caddy:2-alpine",
            "image_id": "sha256:caddy",
        },
    }
    result = compare_runtime_services(intended, runtime)
    assert result["ok"] is False
    assert any("fixture" in err and "image mismatch" in err for err in result["errors"])


def test_compare_runtime_services_accepts_matching_stack():
    intended = extract_intended_services(_rendered(), DEPLOY_CONFIG, "abc123")["services"]
    runtime = {
        "app": {
            "container": "fixture-app-1",
            "status": "running",
            "health": "healthy",
            "image": "ghcr.io/getpayd-tech/fixture-app:abc123",
            "image_id": "sha256:app",
        },
        "migrations": {
            "container": "fixture-migrations-1",
            "status": "exited",
            "exit_code": 0,
            "image": "ghcr.io/getpayd-tech/fixture-app:abc123",
            "image_id": "sha256:app",
        },
        "fixture": {
            "container": "fixture-fixture-1",
            "status": "running",
            "health": None,
            "image": "ghcr.io/getpayd-tech/fixture-edge:abc123",
            "image_id": "sha256:edge",
        },
    }
    assert compare_runtime_services(intended, runtime)["ok"] is True


if __name__ == "__main__":
    fns = sorted(
        (n, f) for n, f in globals().items() if n.startswith("test_") and callable(f)
    )
    failed = 0
    for name, fn in fns:
        try:
            fn()
            print(f"PASS {name}")
        except AssertionError as e:
            failed += 1
            print(f"FAIL {name}: {e!r}")
        except Exception as e:  # noqa: BLE001
            failed += 1
            print(f"ERROR {name}: {type(e).__name__}: {e}")
    print(f"\n{len(fns) - failed}/{len(fns)} passed")
    sys.exit(1 if failed else 0)
