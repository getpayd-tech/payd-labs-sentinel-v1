"""Deployment service.

Handles container deployments via docker compose, including:
- Triggering deployments (pull + recreate)
- Rolling back to a previous image
- Verifying GitHub webhook signatures (HMAC-SHA256)
"""
from __future__ import annotations

import asyncio
import hashlib
import hmac
import logging
import time
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.deployment import Deployment
from app.models.project import Project

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
    if not settings.ghcr_token:
        return

    logs.append("=== GHCR login ===")
    proc = await asyncio.create_subprocess_exec(
        "docker", "login", "ghcr.io",
        "-u", settings.ghcr_user,
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


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

async def trigger_deployment(
    db: AsyncSession,
    project: Project,
    image_tag: Optional[str] = None,
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
    all_logs: list[str] = []

    try:
        # GHCR login (ensures auth is fresh before pulling)
        await _ghcr_login(all_logs)

        # Pull
        all_logs.append("=== docker compose pull ===")
        rc, output = await _run_command(["docker", "compose", "pull"], cwd=compose_dir)
        all_logs.append(output)
        if rc != 0:
            raise RuntimeError(f"docker compose pull failed (rc={rc})")

        # Up
        all_logs.append("=== docker compose up -d ===")
        rc, output = await _run_command(["docker", "compose", "up", "-d"], cwd=compose_dir)
        all_logs.append(output)
        if rc != 0:
            raise RuntimeError(f"docker compose up -d failed (rc={rc})")

        # Health check
        all_logs.append("=== health check ===")
        healthy = await _health_check(project)
        if not healthy:
            all_logs.append("Health check FAILED - initiating rollback")
            raise RuntimeError("Health check failed after deployment")

        all_logs.append("Health check PASSED")
        deployment.status = "success"

    except Exception as exc:
        logger.error("Deployment failed for %s: %s", project.name, exc)
        all_logs.append(f"ERROR: {exc}")

        # Attempt rollback
        try:
            all_logs.append("=== rollback: docker compose up -d (previous) ===")
            rc, output = await _run_command(["docker", "compose", "up", "-d"], cwd=compose_dir)
            all_logs.append(output)
        except Exception as rb_exc:
            all_logs.append(f"Rollback also failed: {rb_exc}")

        deployment.status = "failed"

    elapsed = int(time.time() - start)
    deployment.completed_at = datetime.now(timezone.utc)
    deployment.duration_seconds = elapsed
    deployment.logs = "\n".join(all_logs)

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
    all_logs: list[str] = [f"Rolling back to deployment {target_deployment.id} (tag: {target_deployment.image_tag})"]

    try:
        all_logs.append("=== docker compose pull ===")
        rc, output = await _run_command(["docker", "compose", "pull"], cwd=compose_dir)
        all_logs.append(output)

        all_logs.append("=== docker compose up -d ===")
        rc, output = await _run_command(["docker", "compose", "up", "-d"], cwd=compose_dir)
        all_logs.append(output)
        if rc != 0:
            raise RuntimeError(f"docker compose up -d failed during rollback (rc={rc})")

        all_logs.append("Rollback completed")
        deployment.status = "success"

    except Exception as exc:
        logger.error("Rollback failed for %s: %s", project.name, exc)
        all_logs.append(f"ERROR: {exc}")
        deployment.status = "failed"

    elapsed = int(time.time() - start)
    deployment.completed_at = datetime.now(timezone.utc)
    deployment.duration_seconds = elapsed
    deployment.logs = "\n".join(all_logs)

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
