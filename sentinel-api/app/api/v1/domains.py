"""Domain / Caddy route management routes."""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import require_admin
from app.database import get_db
from app.schemas.domain import (
    CaddyReloadResponse,
    DomainCreate,
    DomainInfo,
    DomainList,
    DomainUpdate,
)
from app.services.audit_service import log_action
from app.services.caddy_service import (
    add_domain,
    parse_caddyfile,
    reload_caddy,
    remove_domain,
    update_domain,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/domains", tags=["Domains"])


@router.get("/", response_model=DomainList)
async def list_domains(claims: dict = Depends(require_admin)):
    """List all domain routes parsed from the Caddyfile."""
    blocks = parse_caddyfile()
    items = [DomainInfo(**b) for b in blocks]
    return DomainList(items=items, total=len(items))


@router.post("/", response_model=DomainInfo, status_code=201)
async def create_domain(
    body: DomainCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    claims: dict = Depends(require_admin),
):
    """Add a new domain route to the Caddyfile."""
    try:
        targets = [t.model_dump() for t in body.proxy_targets]
        await add_domain(body.domain, targets)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        logger.error("Failed to add domain %s: %s", body.domain, exc)
        raise HTTPException(status_code=500, detail=f"Failed to add domain: {exc}")

    await log_action(
        db,
        user_id=claims.get("sub"),
        action="domain.create",
        target=body.domain,
        details={"proxy_targets": targets},
        ip_address=request.client.host if request and request.client else None,
    )

    # Return the newly added block
    blocks = parse_caddyfile()
    for block in blocks:
        if block["domain"].lower() == body.domain.lower():
            return DomainInfo(**block)

    # Fallback
    return DomainInfo(domain=body.domain, upstream_services=[], has_tls=True, raw_config="")


@router.put("/{domain}", response_model=DomainInfo)
async def update_domain_route(
    domain: str,
    body: DomainUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    claims: dict = Depends(require_admin),
):
    """Update an existing domain route in the Caddyfile."""
    try:
        targets = [t.model_dump() for t in body.proxy_targets]
        await update_domain(domain, targets)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        logger.error("Failed to update domain %s: %s", domain, exc)
        raise HTTPException(status_code=500, detail=f"Failed to update domain: {exc}")

    await log_action(
        db,
        user_id=claims.get("sub"),
        action="domain.update",
        target=domain,
        details={"proxy_targets": targets},
        ip_address=request.client.host if request and request.client else None,
    )

    blocks = parse_caddyfile()
    for block in blocks:
        if block["domain"].lower() == domain.lower():
            return DomainInfo(**block)

    return DomainInfo(domain=domain, upstream_services=[], has_tls=True, raw_config="")


@router.delete("/{domain}")
async def delete_domain_route(
    domain: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
    claims: dict = Depends(require_admin),
):
    """Remove a domain route from the Caddyfile."""
    try:
        await remove_domain(domain)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        logger.error("Failed to remove domain %s: %s", domain, exc)
        raise HTTPException(status_code=500, detail=f"Failed to remove domain: {exc}")

    await log_action(
        db,
        user_id=claims.get("sub"),
        action="domain.delete",
        target=domain,
        ip_address=request.client.host if request and request.client else None,
    )

    return {"detail": f"Domain '{domain}' removed"}


@router.post("/reload", response_model=CaddyReloadResponse)
async def reload_caddy_config(
    request: Request,
    db: AsyncSession = Depends(get_db),
    claims: dict = Depends(require_admin),
):
    """Reload the Caddy configuration."""
    result = await reload_caddy()

    await log_action(
        db,
        user_id=claims.get("sub"),
        action="caddy.reload",
        target="caddy-proxy",
        details=result,
        ip_address=request.client.host if request and request.client else None,
    )

    return CaddyReloadResponse(**result)
