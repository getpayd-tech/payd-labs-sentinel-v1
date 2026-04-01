"""Deploy wizard orchestration service.

Handles the full project provisioning flow: create project record,
generate docker-compose + Caddyfile + workflow artifacts, write files
to disk, configure Caddy, and optionally create a PostgreSQL database.
"""
from __future__ import annotations

import logging
import secrets
import string
from pathlib import Path
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.project import Project
from app.services.caddy_service import add_domain, reload_caddy, _build_block
from app.services.db_service import create_database

logger = logging.getLogger(__name__)

APPS_DIR = Path("/apps")
TEMPLATES_DIR = Path(__file__).parent.parent / "templates"


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
    },
    "vue": {
        "port": 80,
        "health_endpoint": "",
        "suggested_env": [],
        "description": "Vue/Vite SPA served by Caddy",
        "container_count": 1,
    },
    "blended": {
        "port": 8000,
        "health_endpoint": "/health",
        "suggested_env": ["DATABASE_URL", "SECRET_KEY", "REDIS_URL", "APP_ENV", "CORS_ORIGINS"],
        "description": "FastAPI backend + Vue frontend (two containers)",
        "container_count": 2,
    },
    "nuxt": {
        "port": 3000,
        "health_endpoint": "/api/health",
        "suggested_env": ["NUXT_PUBLIC_API_BASE", "DATABASE_URL", "SECRET_KEY"],
        "description": "Nuxt 3 SSR application",
        "container_count": 1,
    },
    "laravel": {
        "port": 8000,
        "health_endpoint": "/health",
        "suggested_env": ["APP_KEY", "APP_ENV", "DB_CONNECTION", "DB_HOST", "DB_PORT", "DB_DATABASE", "DB_USERNAME", "DB_PASSWORD", "REDIS_HOST"],
        "description": "Laravel PHP application",
        "container_count": 1,
    },
}


def get_type_defaults(project_type: str) -> dict[str, Any]:
    """Return default config values for a project type."""
    return TYPE_DEFAULTS.get(project_type, TYPE_DEFAULTS["fastapi"])


# ---------------------------------------------------------------------------
# Artifact generation
# ---------------------------------------------------------------------------

def _generate_webhook_secret() -> str:
    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(32))


def _ghcr_image(github_repo: str, suffix: str = "") -> str:
    """Derive GHCR image path from GitHub repo."""
    parts = github_repo.split("/")
    org = parts[0] if len(parts) > 1 else "getpayd-tech"
    repo = parts[-1]
    name = f"ghcr.io/{org}/{repo}"
    if suffix:
        name += f"-{suffix}"
    return name


def generate_compose(
    name: str,
    project_type: str,
    github_repo: str,
    health_endpoint: str = "/health",
) -> str:
    """Generate docker-compose.yml content from a template."""
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
) -> str:
    """Generate a Caddyfile block for the project."""
    defaults = get_type_defaults(project_type)

    if project_type == "blended":
        targets = [
            {"path_prefix": "/api", "upstream": f"{name}-api:8000"},
            {"path_prefix": "/", "upstream": f"{name}-ui:80"},
        ]
    elif project_type == "vue":
        targets = [{"path_prefix": "/", "upstream": f"{name}:80"}]
    elif project_type == "nuxt":
        targets = [{"path_prefix": "/", "upstream": f"{name}:3000"}]
    elif project_type == "laravel":
        targets = [{"path_prefix": "/", "upstream": f"{name}:8000"}]
    else:
        # fastapi or custom
        targets = [{"path_prefix": "/", "upstream": f"{name}:{defaults['port']}"}]

    return _build_block(domain, targets, tls_mode=tls_mode)


def generate_workflow(
    name: str,
    display_name: str,
    project_type: str,
    github_repo: str,
) -> str:
    """Generate GitHub Actions workflow content."""
    template_file = TEMPLATES_DIR / "workflow" / "deploy.yml"
    template = template_file.read_text()

    ghcr = _ghcr_image(github_repo)
    build_context = "."
    if project_type == "blended":
        # For blended, the workflow needs 2 build steps — provide a note
        build_context = "."  # User will need to customize

    replacements = {
        "{PROJECT_NAME}": name,
        "{DISPLAY_NAME}": display_name,
        "{GHCR_IMAGE}": ghcr,
        "{BUILD_CONTEXT}": build_context,
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
) -> dict[str, str]:
    """Generate all artifacts as strings without writing to disk."""
    return {
        "compose": generate_compose(name, project_type, github_repo, health_endpoint),
        "caddyfile": generate_caddyfile_block(domain, name, project_type, tls_mode) if domain else "",
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
) -> dict[str, Any]:
    """Execute the full wizard: create project, provision files, configure Caddy, optionally create DB."""
    steps: list[dict[str, Any]] = []
    webhook_secret = _generate_webhook_secret()
    defaults = get_type_defaults(project_type)

    # Step 1: Create project record
    try:
        ghcr = _ghcr_image(github_repo)
        container_names = (
            {f"{name}-api": f"{name}-api", f"{name}-ui": f"{name}-ui"}
            if project_type == "blended"
            else {name: name}
        )

        project = Project(
            name=name,
            display_name=display_name,
            project_type=project_type,
            github_repo=github_repo,
            ghcr_image=ghcr,
            domain=domain,
            compose_path=str(APPS_DIR / name),
            container_names=container_names,
            health_endpoint=health_endpoint or defaults["health_endpoint"],
            webhook_secret=webhook_secret,
            database_name=database_name if create_db else None,
            status="active",
        )
        db.add(project)
        await db.flush()
        steps.append({"step": 1, "name": "Create project record", "status": "complete", "message": f"Project '{display_name}' registered"})
    except Exception as exc:
        steps.append({"step": 1, "name": "Create project record", "status": "error", "message": str(exc)})
        return {"project_id": "", "webhook_secret": "", "compose_preview": "", "caddyfile_preview": "", "workflow_preview": "", "steps": steps}

    # Step 2: Create directory + docker-compose.yml
    try:
        project_dir = APPS_DIR / name
        project_dir.mkdir(parents=True, exist_ok=True)

        compose_content = generate_compose(name, project_type, github_repo, health_endpoint)
        (project_dir / "docker-compose.yml").write_text(compose_content)
        steps.append({"step": 2, "name": "Generate docker-compose.yml", "status": "complete", "message": f"Written to {project_dir}/docker-compose.yml"})
    except Exception as exc:
        steps.append({"step": 2, "name": "Generate docker-compose.yml", "status": "error", "message": str(exc)})

    # Step 3: Write .env file
    try:
        env_content = "\n".join(f"{k}={v}" for k, v in (env_vars or {}).items())
        if env_content:
            (project_dir / ".env").write_text(env_content + "\n")
            steps.append({"step": 3, "name": "Write environment file", "status": "complete", "message": f"{len(env_vars or {})} variables written"})
        else:
            steps.append({"step": 3, "name": "Write environment file", "status": "complete", "message": "No env vars provided, skipped"})
    except Exception as exc:
        steps.append({"step": 3, "name": "Write environment file", "status": "error", "message": str(exc)})

    # Step 4: Add Caddy domain route
    caddyfile_block = ""
    if domain:
        try:
            if project_type == "blended":
                targets = [
                    {"path_prefix": "/api", "upstream": f"{name}-api:8000"},
                    {"path_prefix": "/", "upstream": f"{name}-ui:80"},
                ]
            elif project_type == "vue":
                targets = [{"path_prefix": "/", "upstream": f"{name}:80"}]
            elif project_type == "nuxt":
                targets = [{"path_prefix": "/", "upstream": f"{name}:3000"}]
            else:
                targets = [{"path_prefix": "/", "upstream": f"{name}:{defaults['port']}"}]

            await add_domain(domain, targets, tls_mode=tls_mode)
            caddyfile_block = generate_caddyfile_block(domain, name, project_type, tls_mode)
            steps.append({"step": 4, "name": "Configure Caddy domain", "status": "complete", "message": f"Route added for {domain}"})

            # Reload Caddy
            result = await reload_caddy()
            if result["success"]:
                steps.append({"step": 5, "name": "Reload Caddy", "status": "complete", "message": "Caddy reloaded successfully"})
            else:
                steps.append({"step": 5, "name": "Reload Caddy", "status": "error", "message": result["message"]})
        except Exception as exc:
            steps.append({"step": 4, "name": "Configure Caddy domain", "status": "error", "message": str(exc)})
            caddyfile_block = generate_caddyfile_block(domain, name, project_type, tls_mode)
    else:
        steps.append({"step": 4, "name": "Configure Caddy domain", "status": "complete", "message": "No domain specified, skipped"})

    # Step 6: Create database (optional)
    if create_db and database_name:
        try:
            db_password = _generate_webhook_secret()  # reuse secret generator for DB password
            await create_database(database_name, db_password)
            steps.append({"step": 6, "name": "Create PostgreSQL database", "status": "complete", "message": f"Database '{database_name}' created"})
        except Exception as exc:
            steps.append({"step": 6, "name": "Create PostgreSQL database", "status": "error", "message": str(exc)})
    else:
        steps.append({"step": 6, "name": "Create PostgreSQL database", "status": "complete", "message": "Skipped (not requested)"})

    # Generate workflow preview
    workflow = generate_workflow(name, display_name, project_type, github_repo)
    compose = generate_compose(name, project_type, github_repo, health_endpoint)

    return {
        "project_id": project.id,
        "webhook_secret": webhook_secret,
        "compose_preview": compose,
        "caddyfile_preview": caddyfile_block or generate_caddyfile_block(domain, name, project_type, tls_mode),
        "workflow_preview": workflow,
        "steps": steps,
    }
