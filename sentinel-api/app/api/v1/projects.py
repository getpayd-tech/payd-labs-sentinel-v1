"""Project management routes — CRUD, provisioning, env vars, templates, scanning, wizard."""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import require_admin
from app.database import get_db
from app.schemas.project import (
    EnvVar,
    EnvVarUpdate,
    ProjectCreate,
    ProjectList,
    ProjectResponse,
    ProjectUpdate,
    ProvisionRequest,
    TemplateInfo,
)
from app.schemas.wizard import (
    TypeDefaults,
    WizardPreviewRequest,
    WizardRequest,
    WizardResponse,
    WizardStep,
)
from app.services.audit_service import log_action
from app.services.project_service import (
    create_project,
    delete_project,
    get_env_vars,
    get_project,
    get_templates,
    list_projects,
    provision_project,
    scan_existing_projects,
    update_env_vars,
    update_project,
)
from app.services.wizard_service import (
    execute_wizard,
    get_type_defaults,
    preview_artifacts,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/projects", tags=["Projects"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _project_to_response(p) -> ProjectResponse:
    return ProjectResponse(
        id=p.id,
        name=p.name,
        display_name=p.display_name,
        project_type=p.project_type,
        github_repo=p.github_repo,
        ghcr_image=p.ghcr_image,
        domain=p.domain,
        compose_path=p.compose_path,
        container_names=p.container_names,
        health_endpoint=p.health_endpoint,
        webhook_secret=p.webhook_secret,
        database_name=p.database_name,
        status=p.status,
        created_at=p.created_at.isoformat() if p.created_at else None,
        updated_at=p.updated_at.isoformat() if p.updated_at else None,
    )


# ---------------------------------------------------------------------------
# Wizard routes (placed before /{id} to avoid route conflicts)
# ---------------------------------------------------------------------------

@router.get("/wizard/defaults/{project_type}", response_model=TypeDefaults)
async def get_wizard_defaults(project_type: str, claims: dict = Depends(require_admin)):
    """Return default configuration values for a project type."""
    defaults = get_type_defaults(project_type)
    return TypeDefaults(**defaults)


@router.post("/wizard/preview")
async def wizard_preview(
    body: WizardPreviewRequest,
    claims: dict = Depends(require_admin),
):
    """Preview generated artifacts (compose, Caddyfile, workflow) without executing."""
    custom_routes = [{"path": r.path, "upstream": r.upstream} for r in body.caddy_routes] if body.caddy_routes else None
    artifacts = preview_artifacts(
        name=body.name,
        display_name=body.display_name or body.name.replace("-", " ").title(),
        project_type=body.project_type,
        github_repo=body.github_repo,
        domain=body.domain,
        tls_mode=body.tls_mode,
        health_endpoint=body.health_endpoint,
        custom_routes=custom_routes,
    )
    return artifacts


@router.post("/wizard", response_model=WizardResponse)
async def wizard_execute(
    body: WizardRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    claims: dict = Depends(require_admin),
):
    """Execute the full deploy wizard — provision project, files, Caddy, and optionally database."""
    custom_routes = [{"path": r.path, "upstream": r.upstream} for r in body.caddy_routes] if body.caddy_routes else None
    result = await execute_wizard(
        db=db,
        name=body.name,
        display_name=body.display_name,
        project_type=body.project_type,
        github_repo=body.github_repo,
        domain=body.domain,
        tls_mode=body.tls_mode,
        create_db=body.create_database,
        database_name=body.database_name,
        env_vars=body.env_vars,
        health_endpoint=body.health_endpoint,
        compose_filename=body.compose_filename,
        custom_routes=custom_routes,
        first_deploy=body.first_deploy,
    )

    try:
        await log_action(
            db,
            user_id=claims.get("sub"),
            action="wizard.execute",
            target=body.name,
            details={"project_type": body.project_type, "domain": body.domain, "steps": len(result["steps"])},
            ip_address=request.client.host if request and request.client else None,
        )
    except Exception as exc:
        logger.warning("Audit log failed for wizard (non-fatal): %s", exc)

    return WizardResponse(
        project_id=result["project_id"],
        webhook_secret=result["webhook_secret"],
        compose_preview=result["compose_preview"],
        caddyfile_preview=result["caddyfile_preview"],
        workflow_preview=result["workflow_preview"],
        steps=[WizardStep(**s) for s in result["steps"]],
    )


# ---------------------------------------------------------------------------
# Templates & scanning (placed before /{id} to avoid route conflicts)
# ---------------------------------------------------------------------------

@router.get("/templates", response_model=list[TemplateInfo])
async def list_templates(claims: dict = Depends(require_admin)):
    """List available project templates."""
    return [TemplateInfo(**t) for t in get_templates()]


@router.post("/scan")
async def scan_projects(
    request: Request,
    db: AsyncSession = Depends(get_db),
    claims: dict = Depends(require_admin),
):
    """Scan /apps directory to auto-discover and register existing projects."""
    results = await scan_existing_projects(db)

    await log_action(
        db,
        user_id=claims.get("sub"),
        action="project.scan",
        target="/apps",
        details={"discovered": len(results)},
        ip_address=request.client.host if request and request.client else None,
    )

    return {"discovered": results, "total": len(results)}


# ---------------------------------------------------------------------------
# CRUD
# ---------------------------------------------------------------------------

@router.get("", response_model=ProjectList)
async def list_all_projects(
    db: AsyncSession = Depends(get_db),
    claims: dict = Depends(require_admin),
):
    """List all registered projects."""
    data = await list_projects(db)
    return ProjectList(
        items=[_project_to_response(p) for p in data["items"]],
        total=data["total"],
    )


@router.post("", response_model=ProjectResponse, status_code=201)
async def create_new_project(
    body: ProjectCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    claims: dict = Depends(require_admin),
):
    """Create a new project."""
    project = await create_project(db, body.model_dump())

    await log_action(
        db,
        user_id=claims.get("sub"),
        action="project.create",
        target=project.name,
        details={"project_id": project.id},
        ip_address=request.client.host if request and request.client else None,
    )

    return _project_to_response(project)


@router.get("/{project_id}", response_model=ProjectResponse)
async def get_project_detail(
    project_id: str,
    db: AsyncSession = Depends(get_db),
    claims: dict = Depends(require_admin),
):
    """Get details for a single project."""
    project = await get_project(db, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return _project_to_response(project)


@router.put("/{project_id}", response_model=ProjectResponse)
async def update_existing_project(
    project_id: str,
    body: ProjectUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    claims: dict = Depends(require_admin),
):
    """Update an existing project."""
    project = await get_project(db, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    updated = await update_project(db, project, body.model_dump(exclude_unset=True))

    await log_action(
        db,
        user_id=claims.get("sub"),
        action="project.update",
        target=project.name,
        details={"project_id": project.id, "changes": body.model_dump(exclude_unset=True)},
        ip_address=request.client.host if request and request.client else None,
    )

    return _project_to_response(updated)


@router.delete("/{project_id}")
async def delete_existing_project(
    project_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
    claims: dict = Depends(require_admin),
):
    """Delete a project record (does not remove server files)."""
    project = await get_project(db, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    project_name = project.name
    await delete_project(db, project)

    await log_action(
        db,
        user_id=claims.get("sub"),
        action="project.delete",
        target=project_name,
        details={"project_id": project_id},
        ip_address=request.client.host if request and request.client else None,
    )

    return {"detail": f"Project '{project_name}' deleted"}


# ---------------------------------------------------------------------------
# Provisioning
# ---------------------------------------------------------------------------

@router.post("/{project_id}/provision")
async def provision_project_resources(
    project_id: str,
    body: ProvisionRequest | None = None,
    request: Request = None,
    db: AsyncSession = Depends(get_db),
    claims: dict = Depends(require_admin),
):
    """Provision server resources for a project (dir, compose, Caddy, DB)."""
    project = await get_project(db, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    create_database = body.create_database if body else False
    result = await provision_project(db, project, create_database=create_database)

    await log_action(
        db,
        user_id=claims.get("sub"),
        action="project.provision",
        target=project.name,
        details=result,
        ip_address=request.client.host if request and request.client else None,
    )

    return result


# ---------------------------------------------------------------------------
# Environment variables
# ---------------------------------------------------------------------------

@router.get("/{project_id}/env", response_model=list[EnvVar])
async def get_project_env(
    project_id: str,
    db: AsyncSession = Depends(get_db),
    claims: dict = Depends(require_admin),
):
    """Get environment variable keys for a project (values are masked)."""
    project = await get_project(db, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return [EnvVar(**v) for v in get_env_vars(project)]


@router.put("/{project_id}/env")
async def update_project_env(
    project_id: str,
    body: EnvVarUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    claims: dict = Depends(require_admin),
):
    """Update environment variables for a project."""
    project = await get_project(db, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    update_env_vars(project, body.variables)

    await log_action(
        db,
        user_id=claims.get("sub"),
        action="project.env.update",
        target=project.name,
        details={"keys_updated": list(body.variables.keys())},
        ip_address=request.client.host if request and request.client else None,
    )

    return {"detail": f"Updated {len(body.variables)} environment variables"}
