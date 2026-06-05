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
from pathlib import Path
from typing import Any, Optional

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.deployment import Deployment
from app.models.project import Project
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


async def _apply_requested_image(
    project: Project,
    image_tag: str,
    all_logs: list[str],
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
    if project.ghcr_image:
        base, _ = split_image_ref(project.ghcr_image)
    elif project.github_repo:
        from app.services.wizard_service import _ghcr_image
        base = _ghcr_image(project.github_repo)
    else:
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

    if count == 0:
        tag_env_vars = find_image_tag_env_vars(original)
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
            return str(env_path), env_original, project.ghcr_image, project.ghcr_image, False

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

    path.write_text(new_text)
    all_logs.append(
        f"Rewrote {count} image line(s) in {path.name} -> {base}:{image_tag}"
    )
    return str(path), original, project.ghcr_image, f"{base}:{image_tag}", True


async def _assert_compose_references_tag(
    compose_prefix: list[str],
    compose_dir: str,
    image_tag: str,
    all_logs: list[str],
) -> None:
    """Fail a tagged deploy if rendered compose images never use the tag."""
    rc, output = await _run_command(compose_prefix + ["config", "--images"], cwd=compose_dir)
    all_logs.append("=== docker compose config --images ===")
    all_logs.append(output)
    if rc != 0:
        raise RuntimeError(f"docker compose config --images failed (rc={rc})")

    images = [line.strip() for line in output.splitlines() if line.strip()]
    ghcr_images = [image for image in images if image.startswith("ghcr.io/")]
    if ghcr_images and not any(f":{image_tag}" in image for image in ghcr_images):
        raise RuntimeError(
            "rendered compose images do not reference requested tag "
            f"{image_tag}; refusing to deploy the currently pinned image set"
        )


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
    compose_prefix = ["docker", "compose"]
    if project.compose_file:
        compose_prefix += ["-f", project.compose_file]
    all_logs: list[str] = []

    # Bound before the try so the except can always reference them, even if
    # _apply_requested_image raises (it does file I/O).
    rewrote_path = backup_text = prev_pin = new_pin = None
    pin_changed = False

    try:
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
                project, image_tag, all_logs
            )
            if rewrote_path is not None and pin_changed:
                project.ghcr_image = new_pin
                await db.flush()
                await db.refresh(project, ["updated_at"])  # MissingGreenlet guard
                all_logs.append(f"Updated project pin: ghcr_image -> {new_pin}")
            if rewrote_path is not None:
                await _assert_compose_references_tag(
                    compose_prefix, compose_dir, image_tag, all_logs
                )
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

        all_logs.append("Health check PASSED")
        deployment.status = "success"

    except Exception as exc:
        logger.error("Deployment failed for %s: %s", project.name, exc)
        all_logs.append(f"ERROR: {exc}")

        # True rollback: restore the original compose file + pin BEFORE the
        # fallback `up -d` so it actually reverts the containers. Wrapped so a
        # restore error can never block status="failed".
        try:
            if rewrote_path is not None and backup_text is not None:
                Path(rewrote_path).write_text(backup_text)
                all_logs.append(f"Restored original compose file ({Path(rewrote_path).name})")
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
            rc, output = await _run_command(compose_prefix + ["up", "-d"], cwd=compose_dir)
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
    compose_prefix = ["docker", "compose"]
    if project.compose_file:
        compose_prefix += ["-f", project.compose_file]
    all_logs: list[str] = [f"Rolling back to deployment {target_deployment.id} (tag: {target_deployment.image_tag})"]

    # Bound before the try so the except can always reference them.
    rewrote_path = backup_text = prev_pin = new_pin = None
    pin_changed = False

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
                project, target_deployment.image_tag, all_logs
            )
            if rewrote_path is not None and pin_changed:
                project.ghcr_image = new_pin
                await db.flush()
                await db.refresh(project, ["updated_at"])  # MissingGreenlet guard
                all_logs.append(f"Updated project pin: ghcr_image -> {new_pin}")
            if rewrote_path is not None:
                await _assert_compose_references_tag(
                    compose_prefix,
                    compose_dir,
                    target_deployment.image_tag,
                    all_logs,
                )

        await _ghcr_login(all_logs)

        all_logs.append("=== docker compose pull ===")
        rc, output = await _run_command(compose_prefix + ["pull"], cwd=compose_dir)
        all_logs.append(output)

        all_logs.append("=== docker compose up -d ===")
        rc, output = await _run_command(compose_prefix + ["up", "-d"], cwd=compose_dir)
        all_logs.append(output)
        if rc != 0:
            raise RuntimeError(f"docker compose up -d failed during rollback (rc={rc})")

        all_logs.append("Rollback completed")
        deployment.status = "success"

    except Exception as exc:
        logger.error("Rollback failed for %s: %s", project.name, exc)
        all_logs.append(f"ERROR: {exc}")

        # Restore the original compose file + pin so a failed rollback leaves
        # the project exactly as it was.
        try:
            if rewrote_path is not None and backup_text is not None:
                Path(rewrote_path).write_text(backup_text)
                all_logs.append(f"Restored original compose file ({Path(rewrote_path).name})")
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
