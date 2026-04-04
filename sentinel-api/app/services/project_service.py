"""Project management service.

Handles project CRUD, provisioning (directory creation, docker-compose
generation, Caddy route configuration), scanning existing projects, and
encrypted environment variable management.
"""
from __future__ import annotations

import json
import logging
import os
import secrets
import string
from pathlib import Path
from typing import Any, Optional

from cryptography.fernet import Fernet
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.project import Project

logger = logging.getLogger(__name__)

APPS_DIR = Path("/apps")

# ---------------------------------------------------------------------------
# Encryption helpers (Fernet)
# ---------------------------------------------------------------------------

def _get_fernet() -> Fernet | None:
    if not settings.encryption_key:
        return None
    return Fernet(settings.encryption_key.encode())


def _encrypt(plaintext: str) -> str:
    f = _get_fernet()
    if not f:
        return plaintext
    return f.encrypt(plaintext.encode()).decode()


def _decrypt(ciphertext: str) -> str:
    f = _get_fernet()
    if not f:
        return ciphertext
    try:
        return f.decrypt(ciphertext.encode()).decode()
    except Exception:
        return ciphertext


# ---------------------------------------------------------------------------
# Templates
# ---------------------------------------------------------------------------

TEMPLATES: dict[str, dict[str, str]] = {
    "fastapi": {
        "name": "fastapi",
        "description": "FastAPI application with PostgreSQL and Redis",
        "project_type": "fastapi",
    },
    "nextjs": {
        "name": "nextjs",
        "description": "Next.js application with standalone output",
        "project_type": "nextjs",
    },
    "static": {
        "name": "static",
        "description": "Static file hosting via Caddy",
        "project_type": "static",
    },
}


def _generate_compose(project: Project) -> str:
    """Generate a docker-compose.yml string for a project."""
    image = project.ghcr_image or f"ghcr.io/payd-labs/{project.name}:latest"
    port = "8000" if project.project_type == "fastapi" else "3000"

    compose = f"""version: "3.8"

services:
  {project.name}:
    image: {image}
    container_name: {project.name}
    restart: unless-stopped
    env_file:
      - .env
    ports:
      - "{port}"
    networks:
      - payd-network
"""

    if project.health_endpoint:
        compose += f"""    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:{port}{project.health_endpoint}"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 40s
"""

    compose += """
networks:
  payd-network:
    external: true
"""
    return compose


def _generate_webhook_secret() -> str:
    """Generate a random webhook secret."""
    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(32))


# ---------------------------------------------------------------------------
# CRUD
# ---------------------------------------------------------------------------

async def create_project(db: AsyncSession, data: dict[str, Any]) -> Project:
    """Create a new project record."""
    project = Project(**data)
    project.webhook_secret = _generate_webhook_secret()
    db.add(project)
    await db.flush()
    return project


async def get_project(db: AsyncSession, project_id: str) -> Project | None:
    """Fetch a single project by ID."""
    result = await db.execute(select(Project).where(Project.id == project_id))
    return result.scalar_one_or_none()


async def get_project_by_name(db: AsyncSession, name: str) -> Project | None:
    """Fetch a single project by name."""
    result = await db.execute(select(Project).where(Project.name == name))
    return result.scalar_one_or_none()


async def list_projects(db: AsyncSession) -> dict[str, Any]:
    """Return all projects."""
    total_result = await db.execute(select(func.count()).select_from(Project))
    total = total_result.scalar() or 0

    result = await db.execute(select(Project).order_by(Project.created_at.desc()))
    items = list(result.scalars().all())

    return {"items": items, "total": total}


async def update_project(db: AsyncSession, project: Project, data: dict[str, Any]) -> Project:
    """Update fields on an existing project."""
    for key, value in data.items():
        if value is not None and hasattr(project, key):
            setattr(project, key, value)
    await db.flush()
    return project


async def delete_project(db: AsyncSession, project: Project) -> None:
    """Delete a project record."""
    await db.delete(project)
    await db.flush()


# ---------------------------------------------------------------------------
# Provisioning
# ---------------------------------------------------------------------------

async def provision_project(db: AsyncSession, project: Project, create_database: bool = False) -> dict[str, Any]:
    """Provision server resources for a project.

    Steps:
    1. Create /apps/{name}/ directory
    2. Generate docker-compose.yml from template
    3. Write .env file
    4. Append Caddy route (if domain configured)
    5. Reload Caddy
    6. Optionally create a PostgreSQL database

    Returns a summary dict of actions taken.
    """
    actions: list[str] = []
    project_dir = APPS_DIR / project.name

    # 1. Directory
    try:
        project_dir.mkdir(parents=True, exist_ok=True)
        actions.append(f"Created directory: {project_dir}")
    except OSError as exc:
        actions.append(f"Failed to create directory: {exc}")
        return {"success": False, "actions": actions}

    # 2. docker-compose.yml
    compose_content = _generate_compose(project)
    compose_path = project_dir / "docker-compose.yml"
    try:
        compose_path.write_text(compose_content)
        actions.append(f"Generated docker-compose.yml at {compose_path}")

        project.compose_path = str(project_dir)
        await db.flush()
    except OSError as exc:
        actions.append(f"Failed to write docker-compose.yml: {exc}")

    # 3. .env file
    env_path = project_dir / ".env"
    if not env_path.exists():
        try:
            env_path.write_text(f"# Environment for {project.name}\n")
            actions.append(f"Created .env at {env_path}")
        except OSError as exc:
            actions.append(f"Failed to write .env: {exc}")

    # 4. Caddy route
    if project.domain:
        try:
            from app.services.caddy_service import add_domain
            await add_domain(
                project.domain,
                [{"path_prefix": "/", "upstream": f"{project.name}:8000"}],
            )
            actions.append(f"Added Caddy route for {project.domain}")
        except Exception as exc:
            actions.append(f"Failed to add Caddy route: {exc}")

    # 5. Database
    if create_database and project.database_name:
        try:
            from app.services.db_service import create_database as create_db
            db_password = _generate_webhook_secret()
            await create_db(project.database_name, db_password)
            actions.append(f"Created database: {project.database_name}")

            # Append DB URL to .env
            db_url = (
                f"DATABASE_URL=postgresql://{project.database_name}:{db_password}"
                f"@{settings.pg_admin_host}:{settings.pg_admin_port}/{project.database_name}"
                f"?sslmode={settings.pg_admin_sslmode}"
            )
            with open(env_path, "a") as f:
                f.write(f"\n{db_url}\n")
            actions.append("Wrote DATABASE_URL to .env")
        except Exception as exc:
            actions.append(f"Failed to create database: {exc}")

    return {"success": True, "actions": actions}


# ---------------------------------------------------------------------------
# Environment variables
# ---------------------------------------------------------------------------

def get_env_vars(project: Project, reveal: bool = False) -> list[dict[str, Any]]:
    """Read .env file for a project. Masks values unless reveal=True."""
    compose_dir = project.compose_path or str(APPS_DIR / project.name)
    env_path = Path(compose_dir) / ".env"

    if not env_path.exists():
        return []

    result: list[dict[str, Any]] = []
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()

        if reveal:
            result.append({"key": key, "value": value})
        else:
            masked = ("****" + value[-4:]) if len(value) > 4 else "****"
            result.append({"key": key, "value": masked})

    return result


def update_env_vars(project: Project, variables: dict[str, str]) -> None:
    """Write environment variables to the project's .env file.

    Merges with existing variables: updates existing keys, adds new ones.
    """
    compose_dir = project.compose_path or str(APPS_DIR / project.name)
    env_path = Path(compose_dir) / ".env"

    # Read existing
    existing: dict[str, str] = {}
    comments: list[str] = []
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                comments.append(line)
                continue
            if "=" in stripped:
                k, v = stripped.split("=", 1)
                existing[k.strip()] = v.strip()

    # Merge
    existing.update(variables)

    # Write
    lines = comments[:]
    for k, v in existing.items():
        lines.append(f"{k}={v}")

    env_path.parent.mkdir(parents=True, exist_ok=True)
    env_path.write_text("\n".join(lines) + "\n")


# ---------------------------------------------------------------------------
# Scan existing projects
# ---------------------------------------------------------------------------

async def scan_existing_projects(db: AsyncSession) -> list[dict[str, Any]]:
    """Scan /apps directory to auto-discover and register existing projects.

    Looks for directories containing a docker-compose.yml file.
    Returns a list of dicts describing what was found/registered.
    """
    discovered: list[dict[str, Any]] = []

    if not APPS_DIR.exists():
        return discovered

    for entry in sorted(APPS_DIR.iterdir()):
        if not entry.is_dir():
            continue

        compose_file = entry / "docker-compose.yml"
        if not compose_file.exists():
            compose_file = entry / "docker-compose.yaml"
            if not compose_file.exists():
                continue

        name = entry.name

        # Check if already registered
        existing = await get_project_by_name(db, name)
        if existing:
            discovered.append({"name": name, "status": "already_registered", "project_id": existing.id})
            continue

        # Auto-register
        project = Project(
            name=name,
            display_name=name.replace("-", " ").title(),
            project_type="custom",
            compose_path=str(entry),
            webhook_secret=_generate_webhook_secret(),
        )
        db.add(project)
        await db.flush()

        discovered.append({"name": name, "status": "registered", "project_id": project.id})

    return discovered


def get_templates() -> list[dict[str, str]]:
    """Return available project templates."""
    return list(TEMPLATES.values())
