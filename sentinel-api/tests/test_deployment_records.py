"""Unit tests for deployment history recording helpers."""
import asyncio
import os
import sys
from types import SimpleNamespace

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from app.services.deploy_service import record_external_deployment  # noqa: E402
except ModuleNotFoundError as exc:  # pragma: no cover - local lightweight runner
    record_external_deployment = None
    MISSING_IMPORT = exc
else:
    MISSING_IMPORT = None


class FakeSession:
    def __init__(self):
        self.added = None
        self.flushes = 0

    def add(self, item):
        self.added = item

    async def flush(self):
        self.flushes += 1


def test_record_external_deployment_writes_success_without_compose_side_effects():
    if record_external_deployment is None:
        print(f"SKIP deployment service deps unavailable: {MISSING_IMPORT}")
        return

    db = FakeSession()
    project = SimpleNamespace(
        id="project-1",
        name="sentinel",
        ghcr_image="ghcr.io/getpayd-tech/sentinel-api:previous",
    )

    dep = asyncio.run(
        record_external_deployment(
            db,
            project,
            image_tag="abc123",
            triggered_by="benaiah-ke",
            deploy_metadata={"source": "github_actions_ssh_deploy"},
        )
    )

    assert db.added is dep
    assert db.flushes == 1
    assert dep.project_id == "project-1"
    assert dep.trigger == "webhook"
    assert dep.image_tag == "abc123"
    assert dep.previous_image_tag == "ghcr.io/getpayd-tech/sentinel-api:previous"
    assert dep.status == "success"
    assert dep.duration_seconds == 0
    assert dep.deploy_metadata["record_only"] is True
    assert dep.deploy_metadata["external_metadata"]["source"] == "github_actions_ssh_deploy"
    assert "no compose action" in dep.logs


def test_record_external_deployment_rejects_unknown_status():
    if record_external_deployment is None:
        print(f"SKIP deployment service deps unavailable: {MISSING_IMPORT}")
        return

    db = FakeSession()
    project = SimpleNamespace(id="project-1", name="sentinel", ghcr_image=None)

    try:
        asyncio.run(record_external_deployment(db, project, status="pending"))
    except ValueError as exc:
        assert "success or failed" in str(exc)
    else:
        raise AssertionError("expected invalid record status to fail")


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
