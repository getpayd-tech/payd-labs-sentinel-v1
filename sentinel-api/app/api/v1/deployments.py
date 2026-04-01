"""Deployment routes — list, trigger, rollback, and webhook receiver."""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import require_admin
from app.config import settings
from app.database import get_db
from app.schemas.deployment import (
    DeploymentList,
    DeploymentResponse,
    DeployTrigger,
    WebhookPayload,
)
from app.services.audit_service import log_action
from app.services.deploy_service import (
    get_deployment,
    list_deployments,
    rollback_deployment,
    trigger_deployment,
    verify_webhook,
)
from app.services.project_service import get_project, get_project_by_name

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/deployments", tags=["Deployments"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _deployment_to_response(dep, project_name: str = "") -> DeploymentResponse:
    return DeploymentResponse(
        id=dep.id,
        project_id=dep.project_id,
        project_name=project_name,
        trigger=dep.trigger,
        image_tag=dep.image_tag,
        previous_image_tag=dep.previous_image_tag,
        status=dep.status,
        started_at=dep.started_at.isoformat() if dep.started_at else None,
        completed_at=dep.completed_at.isoformat() if dep.completed_at else None,
        duration_seconds=dep.duration_seconds,
        logs=dep.logs,
        triggered_by=dep.triggered_by,
    )


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.get("/", response_model=DeploymentList)
async def list_all_deployments(
    project_id: str | None = Query(None, description="Filter by project ID"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    claims: dict = Depends(require_admin),
):
    """List all deployments, optionally filtered by project. Paginated."""
    data = await list_deployments(db, project_id=project_id, page=page, page_size=page_size)

    # Resolve project names
    project_cache: dict[str, str] = {}
    items: list[DeploymentResponse] = []
    for dep in data["items"]:
        pid = dep.project_id
        if pid not in project_cache:
            proj = await get_project(db, pid)
            project_cache[pid] = proj.display_name if proj else ""
        items.append(_deployment_to_response(dep, project_cache[pid]))

    return DeploymentList(
        items=items,
        total=data["total"],
        page=data["page"],
        page_size=data["page_size"],
    )


@router.get("/{deployment_id}", response_model=DeploymentResponse)
async def get_deployment_detail(
    deployment_id: str,
    db: AsyncSession = Depends(get_db),
    claims: dict = Depends(require_admin),
):
    """Get details for a single deployment."""
    dep = await get_deployment(db, deployment_id)
    if not dep:
        raise HTTPException(status_code=404, detail="Deployment not found")

    proj = await get_project(db, dep.project_id)
    project_name = proj.display_name if proj else ""

    return _deployment_to_response(dep, project_name)


@router.post("/{project_id}/deploy", response_model=DeploymentResponse)
async def trigger_manual_deployment(
    project_id: str,
    body: DeployTrigger | None = None,
    request: Request = None,
    db: AsyncSession = Depends(get_db),
    claims: dict = Depends(require_admin),
):
    """Trigger a manual deployment for a project."""
    project = await get_project(db, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    triggered_by = claims.get("username") or claims.get("sub", "admin")
    image_tag = body.image_tag if body else None

    dep = await trigger_deployment(
        db,
        project=project,
        image_tag=image_tag,
        triggered_by=triggered_by,
        trigger_type="manual",
    )

    await log_action(
        db,
        user_id=claims.get("sub"),
        action="deployment.trigger",
        target=project.name,
        details={"deployment_id": dep.id, "image_tag": dep.image_tag, "trigger": "manual"},
        ip_address=request.client.host if request and request.client else None,
    )

    return _deployment_to_response(dep, project.display_name)


@router.post("/{project_id}/rollback/{deployment_id}", response_model=DeploymentResponse)
async def rollback_to_deployment(
    project_id: str,
    deployment_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
    claims: dict = Depends(require_admin),
):
    """Roll back a project to the state of a previous deployment."""
    project = await get_project(db, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    target_dep = await get_deployment(db, deployment_id)
    if not target_dep:
        raise HTTPException(status_code=404, detail="Target deployment not found")

    if target_dep.project_id != project_id:
        raise HTTPException(status_code=400, detail="Deployment does not belong to this project")

    triggered_by = claims.get("username") or claims.get("sub", "admin")

    dep = await rollback_deployment(
        db,
        project=project,
        target_deployment=target_dep,
        triggered_by=triggered_by,
    )

    await log_action(
        db,
        user_id=claims.get("sub"),
        action="deployment.rollback",
        target=project.name,
        details={"deployment_id": dep.id, "rollback_to": deployment_id},
        ip_address=request.client.host if request.client else None,
    )

    return _deployment_to_response(dep, project.display_name)


@router.post("/webhook")
async def receive_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Receive a GitHub / CI webhook and trigger a deployment.

    This endpoint does NOT require admin auth — it uses HMAC-SHA256
    signature verification instead.
    """
    body_bytes = await request.body()
    signature = request.headers.get("X-Hub-Signature-256") or request.headers.get("x-hub-signature-256") or ""

    try:
        payload = WebhookPayload.model_validate_json(body_bytes)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid webhook payload")

    # Look up project
    project = await get_project_by_name(db, payload.project)
    if not project:
        raise HTTPException(status_code=404, detail=f"Project '{payload.project}' not found")

    # Verify HMAC signature
    secret = project.webhook_secret or settings.secret_key
    if not verify_webhook(secret, body_bytes, signature):
        raise HTTPException(status_code=401, detail="Invalid webhook signature")

    # Trigger deployment
    dep = await trigger_deployment(
        db,
        project=project,
        image_tag=payload.image_tag,
        triggered_by=payload.triggered_by or "webhook",
        trigger_type="webhook",
    )

    await log_action(
        db,
        user_id=None,
        action="deployment.webhook",
        target=project.name,
        details={"deployment_id": dep.id, "image_tag": dep.image_tag},
        ip_address=request.client.host if request.client else None,
    )

    return {
        "status": dep.status,
        "deployment_id": dep.id,
        "project": project.name,
    }
