"""Deploy wizard orchestration service.

Handles the full project provisioning flow end-to-end:
1. Create project record in DB
2. Generate docker-compose file from template
3. Write .env file
4. Add Caddy domain route (with custom path routing)
5. Reload Caddy
6. Optionally create PostgreSQL database
7. Pull Docker images (first deploy)
8. Start containers
9. Health check verification
"""
from __future__ import annotations

import asyncio
import logging
import secrets
import string
from pathlib import Path
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.project import Project
from app.services.caddy_service import add_domain, reload_caddy, _build_block

logger = logging.getLogger(__name__)

APPS_DIR = Path("/apps")
TEMPLATES_DIR = Path(__file__).parent.parent / "templates"
SERVER_IP = "46.101.240.141"


# ---------------------------------------------------------------------------
# Type defaults
# ---------------------------------------------------------------------------

TYPE_DEFAULTS: dict[str, dict[str, Any]] = {
    "fastapi": {
        "port": 8000,
        "health_endpoint": "/health",
        "suggested_env": ["DATABASE_URL", "SECRET_KEY", "REDIS_URL", "APP_ENV", "CORS_ORIGINS"],
        "description": "Python FastAPI backend with health checks",
        "container_count": 1,
        "default_routes": [],
    },
    "vue": {
        "port": 80,
        "health_endpoint": "",
        "suggested_env": [],
        "description": "Vue/Vite SPA served by Caddy",
        "container_count": 1,
        "default_routes": [],
    },
    "blended": {
        "port": 8000,
        "health_endpoint": "/health",
        "suggested_env": ["DATABASE_URL", "SECRET_KEY", "REDIS_URL", "APP_ENV", "CORS_ORIGINS"],
        "description": "FastAPI backend + Vue frontend (two containers)",
        "container_count": 2,
        "default_routes": [],
    },
    "nuxt": {
        "port": 3000,
        "health_endpoint": "/api/health",
        "suggested_env": ["NUXT_PUBLIC_API_BASE", "DATABASE_URL", "SECRET_KEY"],
        "description": "Nuxt 3 SSR application",
        "container_count": 1,
        "default_routes": [],
    },
    "laravel": {
        "port": 8000,
        "health_endpoint": "/health",
        "suggested_env": ["APP_KEY", "APP_ENV", "DB_CONNECTION", "DB_HOST", "DB_PORT", "DB_DATABASE", "DB_USERNAME", "DB_PASSWORD", "REDIS_HOST"],
        "description": "Laravel PHP application",
        "container_count": 1,
        "default_routes": [],
    },
}


def get_type_defaults(project_type: str) -> dict[str, Any]:
    """Return default config values for a project type."""
    defaults = TYPE_DEFAULTS.get(project_type, TYPE_DEFAULTS["fastapi"]).copy()
    # default_routes are generated dynamically based on project name, so leave empty here
    return defaults


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _generate_webhook_secret() -> str:
    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(32))


def _ghcr_image(github_repo: str, suffix: str = "") -> str:
    # Strip common URL prefixes users might paste
    clean = github_repo.strip()
    for prefix in ("https://github.com/", "http://github.com/", "github.com/"):
        if clean.lower().startswith(prefix):
            clean = clean[len(prefix):]
            break
    # Remove trailing .git
    if clean.endswith(".git"):
        clean = clean[:-4]
    # Remove trailing slashes
    clean = clean.strip("/")

    parts = clean.split("/")
    org = parts[0] if len(parts) > 1 else "getpayd-tech"
    repo = parts[-1]
    name = f"ghcr.io/{org}/{repo}"
    if suffix:
        name += f"-{suffix}"
    return name


def _auto_routes(name: str, project_type: str) -> list[dict[str, str]]:
    """Generate default Caddy proxy targets from project type."""
    defaults = TYPE_DEFAULTS.get(project_type, TYPE_DEFAULTS["fastapi"])
    if project_type == "blended":
        return [
            {"path_prefix": "/api", "upstream": f"{name}-api:8000"},
            {"path_prefix": "/", "upstream": f"{name}-ui:80"},
        ]
    elif project_type == "vue":
        return [{"path_prefix": "/", "upstream": f"{name}:80"}]
    elif project_type == "nuxt":
        return [{"path_prefix": "/", "upstream": f"{name}:3000"}]
    else:
        return [{"path_prefix": "/", "upstream": f"{name}:{defaults['port']}"}]


async def _run_compose(compose_file: str, project_dir: str, command: list[str]) -> tuple[int, str]:
    """Run a docker compose command using the Docker SDK.

    The docker CLI may not be installed in the sentinel-api container,
    but the Docker socket is mounted. We use subprocess with the full
    path or fallback to Docker SDK for compose operations.
    """
    # Try docker compose via subprocess first (works if docker CLI is installed)
    try:
        proc = await asyncio.create_subprocess_exec(
            "docker", "compose", "-f", compose_file, *command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
            cwd=project_dir,
        )
        stdout, _ = await proc.communicate()
        output = stdout.decode("utf-8", errors="replace") if stdout else ""
        return proc.returncode or 0, output
    except FileNotFoundError:
        # docker CLI not available - try docker-compose
        try:
            proc = await asyncio.create_subprocess_exec(
                "docker-compose", "-f", compose_file, *command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
                cwd=project_dir,
            )
            stdout, _ = await proc.communicate()
            output = stdout.decode("utf-8", errors="replace") if stdout else ""
            return proc.returncode or 0, output
        except FileNotFoundError:
            return 1, "Neither 'docker compose' nor 'docker-compose' found in container. Install docker CLI or mount it."


# ---------------------------------------------------------------------------
# Artifact generation
# ---------------------------------------------------------------------------

def generate_compose(
    name: str,
    project_type: str,
    github_repo: str,
    health_endpoint: str = "/health",
) -> str:
    """Generate docker-compose content from a template."""
    defaults = get_type_defaults(project_type)
    template_file = TEMPLATES_DIR / "compose" / f"{project_type}.yml"
    if not template_file.exists():
        template_file = TEMPLATES_DIR / "compose" / "fastapi.yml"

    template = template_file.read_text()
    ghcr = _ghcr_image(github_repo)

    replacements = {
        "{PROJECT_NAME}": name,
        "{GHCR_IMAGE}": ghcr,
        "{GHCR_IMAGE_API}": _ghcr_image(github_repo, "api"),
        "{GHCR_IMAGE_UI}": _ghcr_image(github_repo, "ui"),
        "{PORT}": str(defaults["port"]),
        "{HEALTH_ENDPOINT}": health_endpoint or defaults["health_endpoint"],
    }

    content = template
    for placeholder, value in replacements.items():
        content = content.replace(placeholder, value)
    return content


def generate_caddyfile_block(
    domain: str,
    name: str,
    project_type: str,
    tls_mode: str = "auto",
    custom_routes: list[dict[str, str]] | None = None,
) -> str:
    """Generate a Caddyfile block. Uses custom_routes if provided, else auto-generates."""
    if custom_routes:
        targets = [{"path_prefix": r["path"], "upstream": r["upstream"]} for r in custom_routes]
    else:
        targets = _auto_routes(name, project_type)
    return _build_block(domain, targets, tls_mode=tls_mode)


def generate_workflow(
    name: str,
    display_name: str,
    project_type: str,
    github_repo: str,
) -> str:
    """Generate GitHub Actions workflow content."""
    if project_type == "blended":
        template_file = TEMPLATES_DIR / "workflow" / "deploy-blended.yml"
    else:
        template_file = TEMPLATES_DIR / "workflow" / "deploy.yml"

    template = template_file.read_text()
    ghcr = _ghcr_image(github_repo)

    replacements = {
        "{PROJECT_NAME}": name,
        "{DISPLAY_NAME}": display_name,
        "{GHCR_IMAGE}": ghcr,
        "{GHCR_IMAGE_API}": _ghcr_image(github_repo, "api"),
        "{GHCR_IMAGE_UI}": _ghcr_image(github_repo, "ui"),
        "{BUILD_CONTEXT}": ".",
    }

    content = template
    for placeholder, value in replacements.items():
        content = content.replace(placeholder, value)
    return content


# ---------------------------------------------------------------------------
# Preview (no side effects)
# ---------------------------------------------------------------------------

def preview_artifacts(
    name: str,
    display_name: str,
    project_type: str,
    github_repo: str,
    domain: str,
    tls_mode: str = "auto",
    health_endpoint: str = "/health",
    custom_routes: list[dict[str, str]] | None = None,
) -> dict[str, str]:
    """Generate all artifacts as strings without writing to disk."""
    return {
        "compose": generate_compose(name, project_type, github_repo, health_endpoint),
        "caddyfile": generate_caddyfile_block(domain, name, project_type, tls_mode, custom_routes) if domain else "",
        "workflow": generate_workflow(name, display_name, project_type, github_repo),
    }


# ---------------------------------------------------------------------------
# Execute (full provisioning with side effects)
# ---------------------------------------------------------------------------

async def execute_wizard(
    db: AsyncSession,
    name: str,
    display_name: str,
    project_type: str,
    github_repo: str,
    domain: str,
    tls_mode: str = "auto",
    create_db: bool = False,
    database_name: str | None = None,
    env_vars: dict[str, str] | None = None,
    health_endpoint: str = "/health",
    compose_filename: str = "docker-compose.yml",
    custom_routes: list[dict[str, str]] | None = None,
    first_deploy: bool = True,
) -> dict[str, Any]:
    """Execute the full wizard end-to-end."""
    steps: list[dict[str, Any]] = []
    webhook_secret = _generate_webhook_secret()
    defaults = get_type_defaults(project_type)
    project_dir = APPS_DIR / name

    # Step 1: Create or update project record
    try:
        ghcr = _ghcr_image(github_repo)
        container_names = (
            {f"{name}-api": f"{name}-api", f"{name}-ui": f"{name}-ui"}
            if project_type == "blended"
            else {name: name}
        )

        # Check if project already exists (from scan or previous attempt)
        from sqlalchemy import select
        existing_result = await db.execute(select(Project).where(Project.name == name))
        project = existing_result.scalar_one_or_none()

        if project:
            # Update existing record
            project.display_name = display_name
            project.project_type = project_type
            project.github_repo = github_repo
            project.ghcr_image = ghcr
            project.domain = domain
            project.compose_path = str(project_dir)
            project.container_names = container_names
            project.health_endpoint = health_endpoint or defaults["health_endpoint"]
            project.database_name = database_name if create_db else None
            project.status = "active"
            webhook_secret = project.webhook_secret or webhook_secret
            await db.flush()
            steps.append({"step": 1, "name": "Update project record", "status": "complete", "message": f"Project '{display_name}' updated (already existed)"})
        else:
            project = Project(
                name=name,
                display_name=display_name,
                project_type=project_type,
                github_repo=github_repo,
                ghcr_image=ghcr,
                domain=domain,
                compose_path=str(project_dir),
                container_names=container_names,
                health_endpoint=health_endpoint or defaults["health_endpoint"],
                webhook_secret=webhook_secret,
                database_name=database_name if create_db else None,
                status="active",
            )
            db.add(project)
            await db.flush()
            steps.append({"step": 1, "name": "Create project record", "status": "complete", "message": f"Project '{display_name}' registered"})

        # Commit early so the DB isn't locked during slow docker operations
        await db.commit()
    except Exception as exc:
        try:
            await db.rollback()
        except Exception:
            pass
        steps.append({"step": 1, "name": "Create project record", "status": "error", "message": str(exc)})
        return _build_response("", "", steps)

    # Step 2: Create directory + compose file
    try:
        project_dir.mkdir(parents=True, exist_ok=True)
        compose_content = generate_compose(name, project_type, github_repo, health_endpoint)
        (project_dir / compose_filename).write_text(compose_content)
        steps.append({"step": 2, "name": f"Write {compose_filename}", "status": "complete", "message": f"Written to {project_dir}/{compose_filename}"})
    except Exception as exc:
        steps.append({"step": 2, "name": f"Write {compose_filename}", "status": "error", "message": str(exc)})

    # Step 3: Write .env file
    try:
        env_content = "\n".join(f"{k}={v}" for k, v in (env_vars or {}).items())
        if env_content:
            (project_dir / ".env").write_text(env_content + "\n")
            steps.append({"step": 3, "name": "Write .env file", "status": "complete", "message": f"{len(env_vars or {})} variables written"})
        else:
            steps.append({"step": 3, "name": "Write .env file", "status": "complete", "message": "No env vars provided, skipped"})
    except Exception as exc:
        steps.append({"step": 3, "name": "Write .env file", "status": "error", "message": str(exc)})

    # Step 4: Add Caddy domain route
    caddyfile_block = ""
    if domain:
        try:
            if custom_routes:
                targets = [{"path_prefix": r["path"], "upstream": r["upstream"]} for r in custom_routes]
            else:
                targets = _auto_routes(name, project_type)

            await add_domain(domain, targets, tls_mode=tls_mode)
            caddyfile_block = generate_caddyfile_block(domain, name, project_type, tls_mode, custom_routes)
            steps.append({"step": 4, "name": "Configure Caddy domain", "status": "complete", "message": f"Route added for {domain}"})
        except Exception as exc:
            steps.append({"step": 4, "name": "Configure Caddy domain", "status": "error", "message": str(exc)})
            caddyfile_block = generate_caddyfile_block(domain, name, project_type, tls_mode, custom_routes)
    else:
        steps.append({"step": 4, "name": "Configure Caddy domain", "status": "complete", "message": "No domain specified, skipped"})

    # Step 5: Reload Caddy
    if domain:
        try:
            result = await reload_caddy()
            if result["success"]:
                steps.append({"step": 5, "name": "Reload Caddy", "status": "complete", "message": "Caddy reloaded successfully"})
            else:
                steps.append({"step": 5, "name": "Reload Caddy", "status": "error", "message": result["message"]})
        except Exception as exc:
            steps.append({"step": 5, "name": "Reload Caddy", "status": "error", "message": str(exc)})
    else:
        steps.append({"step": 5, "name": "Reload Caddy", "status": "complete", "message": "Skipped (no domain)"})

    # Step 6: Create database (optional)
    if create_db and database_name:
        try:
            from app.services.db_service import create_database
            db_password = _generate_webhook_secret()
            await create_database(database_name, db_password)
            steps.append({"step": 6, "name": "Create PostgreSQL database", "status": "complete", "message": f"Database '{database_name}' created (user: {database_name})"})
        except Exception as exc:
            steps.append({"step": 6, "name": "Create PostgreSQL database", "status": "error", "message": str(exc)})
    else:
        steps.append({"step": 6, "name": "Create PostgreSQL database", "status": "complete", "message": "Skipped"})

    # Step 7-9: First deploy (pull, start, health check)
    if first_deploy:
        # Step 7: Pull Docker images
        try:
            rc, output = await _run_compose(
                compose_filename, str(project_dir), ["pull"],
            )
            if rc == 0:
                steps.append({"step": 7, "name": "Pull Docker images", "status": "complete", "message": "Images pulled successfully"})
            else:
                steps.append({"step": 7, "name": "Pull Docker images", "status": "error", "message": output.strip()[-200:]})
        except Exception as exc:
            steps.append({"step": 7, "name": "Pull Docker images", "status": "error", "message": str(exc)})

        # Step 8: Start containers
        try:
            rc, output = await _run_compose(
                compose_filename, str(project_dir), ["up", "-d"],
            )
            if rc == 0:
                steps.append({"step": 8, "name": "Start containers", "status": "complete", "message": "Containers started"})
            else:
                steps.append({"step": 8, "name": "Start containers", "status": "error", "message": output.strip()[-200:]})
        except Exception as exc:
            steps.append({"step": 8, "name": "Start containers", "status": "error", "message": str(exc)})

        # Step 9: Health check
        if health_endpoint and domain:
            try:
                healthy = await _health_check(domain, health_endpoint)
                if healthy:
                    steps.append({"step": 9, "name": "Health check", "status": "complete", "message": f"https://{domain}{health_endpoint} is responding"})
                else:
                    steps.append({"step": 9, "name": "Health check", "status": "error", "message": f"Health check failed after 60s - containers may still be starting"})
            except Exception as exc:
                steps.append({"step": 9, "name": "Health check", "status": "error", "message": str(exc)})
        else:
            steps.append({"step": 9, "name": "Health check", "status": "complete", "message": "Skipped (no health endpoint or domain)"})
    else:
        steps.append({"step": 7, "name": "Pull Docker images", "status": "complete", "message": "Skipped (first deploy disabled)"})
        steps.append({"step": 8, "name": "Start containers", "status": "complete", "message": "Skipped"})
        steps.append({"step": 9, "name": "Health check", "status": "complete", "message": "Skipped"})

    compose = generate_compose(name, project_type, github_repo, health_endpoint)
    workflow = generate_workflow(name, display_name, project_type, github_repo)

    return {
        "project_id": project.id,
        "webhook_secret": webhook_secret,
        "compose_preview": compose,
        "caddyfile_preview": caddyfile_block or generate_caddyfile_block(domain, name, project_type, tls_mode, custom_routes),
        "workflow_preview": workflow,
        "steps": steps,
    }


async def _health_check(domain: str, health_endpoint: str, retries: int = 12, interval: int = 5) -> bool:
    """Check if the service is healthy by hitting its health endpoint."""
    import httpx

    url = f"https://{domain}{health_endpoint}"
    for attempt in range(retries):
        try:
            async with httpx.AsyncClient(verify=False, timeout=10) as client:
                resp = await client.get(url)
                if 200 <= resp.status_code < 400:
                    return True
        except Exception:
            pass
        if attempt < retries - 1:
            await asyncio.sleep(interval)
    return False


def _build_response(project_id: str, webhook_secret: str, steps: list) -> dict[str, Any]:
    """Build an error response when wizard fails early."""
    return {
        "project_id": project_id,
        "webhook_secret": webhook_secret,
        "compose_preview": "",
        "caddyfile_preview": "",
        "workflow_preview": "",
        "steps": steps,
    }
