"""Custom domain management routes.

Provides:
- Internal ``/domain-check`` endpoint for Caddy on-demand TLS validation.
- Service-to-service CRUD via X-Service-Key for registering custom domains.
- Admin endpoints for listing/removing any custom domain.
"""
from __future__ import annotations

import logging
import secrets

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import require_admin, require_service_key
from app.database import get_db
from app.models.custom_domain import CustomDomain
from app.models.project import Project
from app.schemas.custom_domain import (
    CustomDomainCreate,
    CustomDomainList,
    CustomDomainResponse,
)
from app.services.audit_service import log_action
from app.services.caddy_service import add_domain, reload_caddy, remove_domain

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Custom Domains"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _domain_to_response(d: CustomDomain, project_name: str = "") -> CustomDomainResponse:
    return CustomDomainResponse(
        id=d.id,
        project_id=d.project_id,
        project_name=project_name,
        domain=d.domain,
        status=d.status,
        error_message=d.error_message,
        verified_at=d.verified_at.isoformat() if d.verified_at else None,
        created_at=d.created_at.isoformat() if d.created_at else None,
        updated_at=d.updated_at.isoformat() if d.updated_at else None,
    )


# ---------------------------------------------------------------------------
# Internal - Caddy ask endpoint (no auth, Docker-network only)
# ---------------------------------------------------------------------------

@router.get("/internal/domain-check")
async def domain_check(
    domain: str = Query(..., description="Domain to validate"),
    db: AsyncSession = Depends(get_db),
):
    """Caddy on-demand TLS ask endpoint.

    Returns 200 if the domain is registered and active, 404 otherwise.
    Caddy calls this before issuing a certificate for any on-demand domain.
    """
    result = await db.execute(
        select(CustomDomain).where(
            CustomDomain.domain == domain.lower(),
            CustomDomain.status == "active",
        )
    )
    if result.scalar_one_or_none():
        return {"allowed": True}
    raise HTTPException(status_code=404, detail="Domain not registered")


# ---------------------------------------------------------------------------
# Service-to-service (X-Service-Key auth)
# ---------------------------------------------------------------------------

@router.post("/api/v1/custom-domains", response_model=CustomDomainResponse, status_code=201)
async def register_custom_domain(
    body: CustomDomainCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    project: Project = Depends(require_service_key),
):
    """Register a custom domain for the authenticated project.

    Writes a Caddy block with on-demand TLS routing to the project's
    configured upstream and reloads Caddy.
    """
    if not project.custom_domain_upstream:
        raise HTTPException(
            status_code=400,
            detail="Project has no custom_domain_upstream configured",
        )

    # Check uniqueness
    existing = await db.execute(
        select(CustomDomain).where(CustomDomain.domain == body.domain)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail=f"Domain '{body.domain}' is already registered")

    # Create record
    cd = CustomDomain(
        project_id=project.id,
        domain=body.domain,
        status="pending",
    )
    db.add(cd)
    await db.flush()

    # Write Caddy block
    upstream = project.custom_domain_upstream
    targets = [{"path_prefix": "/", "upstream": upstream}]
    try:
        await add_domain(body.domain, targets, tls_mode="on_demand")
        result = await reload_caddy()
        if not result["success"]:
            raise RuntimeError(result["message"])
        cd.status = "active"
    except Exception as exc:
        logger.error("Failed to add Caddy block for %s: %s", body.domain, exc)
        cd.status = "failed"
        cd.error_message = str(exc)[:500]
        # Attempt to clean up the Caddy block
        try:
            await remove_domain(body.domain)
        except Exception:
            pass

    await db.flush()
    response = _domain_to_response(cd, project.display_name)

    await log_action(
        db,
        user_id=None,
        action="custom_domain.register",
        target=body.domain,
        details={"project_id": project.id, "project_name": project.name, "status": cd.status},
        ip_address=request.client.host if request and request.client else None,
    )

    if cd.status == "failed":
        raise HTTPException(status_code=500, detail=f"Domain registered but Caddy config failed: {cd.error_message}")

    return response


@router.get("/api/v1/custom-domains", response_model=CustomDomainList)
async def list_project_domains(
    db: AsyncSession = Depends(get_db),
    project: Project = Depends(require_service_key),
):
    """List custom domains belonging to the authenticated project."""
    count_result = await db.execute(
        select(func.count()).select_from(CustomDomain).where(CustomDomain.project_id == project.id)
    )
    total = count_result.scalar() or 0

    result = await db.execute(
        select(CustomDomain)
        .where(CustomDomain.project_id == project.id)
        .order_by(CustomDomain.created_at.desc())
    )
    items = [_domain_to_response(d, project.display_name) for d in result.scalars().all()]
    return CustomDomainList(items=items, total=total)


@router.delete("/api/v1/custom-domains/{domain}")
async def remove_custom_domain(
    domain: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
    project: Project = Depends(require_service_key),
):
    """Remove a custom domain owned by the authenticated project."""
    result = await db.execute(
        select(CustomDomain).where(
            CustomDomain.domain == domain.lower(),
            CustomDomain.project_id == project.id,
        )
    )
    cd = result.scalar_one_or_none()
    if not cd:
        raise HTTPException(status_code=404, detail="Domain not found or not owned by this project")

    # Remove Caddy block
    try:
        await remove_domain(domain)
        await reload_caddy()
    except ValueError:
        logger.warning("Caddy block for %s not found during removal (may have been manually deleted)", domain)
    except Exception as exc:
        logger.error("Failed to remove Caddy block for %s: %s", domain, exc)

    await db.delete(cd)
    await db.flush()

    await log_action(
        db,
        user_id=None,
        action="custom_domain.remove",
        target=domain,
        details={"project_id": project.id, "project_name": project.name},
        ip_address=request.client.host if request and request.client else None,
    )

    return {"detail": f"Domain '{domain}' removed"}


# ---------------------------------------------------------------------------
# Admin endpoints (x-auth-token JWT)
# ---------------------------------------------------------------------------

@router.get("/api/v1/custom-domains/all", response_model=CustomDomainList)
async def list_all_custom_domains(
    db: AsyncSession = Depends(get_db),
    claims: dict = Depends(require_admin),
    project_id: str | None = Query(None, description="Filter by project ID"),
):
    """List all custom domains across all projects (admin only)."""
    base = select(CustomDomain)
    count_base = select(func.count()).select_from(CustomDomain)
    if project_id:
        base = base.where(CustomDomain.project_id == project_id)
        count_base = count_base.where(CustomDomain.project_id == project_id)

    count_result = await db.execute(count_base)
    total = count_result.scalar() or 0

    result = await db.execute(base.order_by(CustomDomain.created_at.desc()))
    domains = result.scalars().all()

    # Batch-fetch project names
    project_ids = {d.project_id for d in domains}
    names: dict[str, str] = {}
    if project_ids:
        proj_result = await db.execute(
            select(Project.id, Project.display_name).where(Project.id.in_(project_ids))
        )
        names = {row[0]: row[1] for row in proj_result.all()}

    items = [_domain_to_response(d, names.get(d.project_id, "")) for d in domains]
    return CustomDomainList(items=items, total=total)


@router.delete("/api/v1/custom-domains/admin/{domain}")
async def admin_remove_custom_domain(
    domain: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
    claims: dict = Depends(require_admin),
):
    """Force-remove any custom domain (admin only)."""
    result = await db.execute(
        select(CustomDomain).where(CustomDomain.domain == domain.lower())
    )
    cd = result.scalar_one_or_none()
    if not cd:
        raise HTTPException(status_code=404, detail="Domain not found")

    try:
        await remove_domain(domain)
        await reload_caddy()
    except ValueError:
        pass
    except Exception as exc:
        logger.error("Failed to remove Caddy block for %s: %s", domain, exc)

    await db.delete(cd)
    await db.flush()

    await log_action(
        db,
        user_id=claims.get("sub"),
        action="custom_domain.admin_remove",
        target=domain,
        details={"project_id": cd.project_id},
        ip_address=request.client.host if request and request.client else None,
    )

    return {"detail": f"Domain '{domain}' removed by admin"}


# ---------------------------------------------------------------------------
# Generate service API key (admin only)
# ---------------------------------------------------------------------------

@router.post("/api/v1/projects/{project_id}/generate-service-key")
async def generate_service_key(
    project_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
    claims: dict = Depends(require_admin),
):
    """Generate a new service API key for a project. Overwrites any existing key."""
    from app.services.project_service import get_project

    project = await get_project(db, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    key = "sak_" + secrets.token_urlsafe(32)
    project.service_api_key = key
    await db.flush()
    await db.refresh(project, ["updated_at"])

    await log_action(
        db,
        user_id=claims.get("sub"),
        action="project.generate_service_key",
        target=project.name,
        details={"project_id": project.id},
        ip_address=request.client.host if request and request.client else None,
    )

    return {"service_api_key": key}
