"""Domain / Caddy route management routes."""
from __future__ import annotations

import asyncio
import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import require_admin
from app.database import get_db
from app.schemas.domain import (
    CaddyReloadResponse,
    DomainCreate,
    DomainInfo,
    DomainUpdate,
    OnDemandTlsStatus,
)
from app.services.audit_service import log_action
from app.services.caddy_service import (
    add_domain,
    disable_on_demand_tls,
    enable_on_demand_tls,
    has_on_demand_tls,
    parse_caddyfile,
    reload_caddy,
    remove_domain,
    update_domain,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/domains", tags=["Domains"])


@router.get("", response_model=list[DomainInfo])
async def list_domains(claims: dict = Depends(require_admin)):
    """List all domain routes parsed from the Caddyfile."""
    blocks = await asyncio.to_thread(parse_caddyfile)
    return [DomainInfo(**b) for b in blocks]


@router.post("", response_model=DomainInfo, status_code=201)
async def create_domain(
    body: DomainCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    claims: dict = Depends(require_admin),
):
    """Add a new domain route to the Caddyfile."""
    try:
        targets = [{"path_prefix": "/", "upstream": f"{u.address}:{u.port}"} for u in body.upstreams]
        await add_domain(body.domain, targets, tls_mode=body.tls_mode)
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
        details={"upstreams": [u.model_dump() for u in body.upstreams]},
        ip_address=request.client.host if request and request.client else None,
    )

    # Return the newly added block
    blocks = await asyncio.to_thread(parse_caddyfile)
    for block in blocks:
        if block["domain"].lower() == body.domain.lower():
            return DomainInfo(**block)

    return DomainInfo(domain=body.domain, upstreams=[], tls_enabled=True, tls_auto=body.tls_auto)


# ---------------------------------------------------------------------------
# On-demand TLS (must be registered before /{domain} to avoid path collision)
# ---------------------------------------------------------------------------

@router.get("/on-demand-tls", response_model=OnDemandTlsStatus)
async def get_on_demand_tls_status(claims: dict = Depends(require_admin)):
    """Check whether on-demand TLS is currently configured."""
    enabled = await asyncio.to_thread(has_on_demand_tls)
    return OnDemandTlsStatus(enabled=enabled)


@router.post("/on-demand-tls/enable", response_model=OnDemandTlsStatus)
async def enable_on_demand_tls_route(
    request: Request,
    db: AsyncSession = Depends(get_db),
    claims: dict = Depends(require_admin),
):
    """Enable on-demand TLS for OneLink custom domains."""
    try:
        await enable_on_demand_tls()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    result = await reload_caddy()

    await log_action(
        db,
        user_id=claims.get("sub"),
        action="caddy.on_demand_tls.enable",
        target="caddy-proxy",
        details=result,
        ip_address=request.client.host if request and request.client else None,
    )

    if not result["success"]:
        raise HTTPException(status_code=500, detail=result["message"])

    return OnDemandTlsStatus(enabled=True, message="On-demand TLS enabled and Caddy reloaded")


@router.post("/on-demand-tls/disable", response_model=OnDemandTlsStatus)
async def disable_on_demand_tls_route(
    request: Request,
    db: AsyncSession = Depends(get_db),
    claims: dict = Depends(require_admin),
):
    """Disable on-demand TLS for OneLink custom domains."""
    try:
        await disable_on_demand_tls()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    result = await reload_caddy()

    await log_action(
        db,
        user_id=claims.get("sub"),
        action="caddy.on_demand_tls.disable",
        target="caddy-proxy",
        details=result,
        ip_address=request.client.host if request and request.client else None,
    )

    if not result["success"]:
        raise HTTPException(status_code=500, detail=result["message"])

    return OnDemandTlsStatus(enabled=False, message="On-demand TLS disabled and Caddy reloaded")


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
        targets = [{"path_prefix": "/", "upstream": f"{u.address}:{u.port}"} for u in body.upstreams]
        await update_domain(domain, targets, tls_mode=body.tls_mode)
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
        details={"upstreams": [u.model_dump() for u in body.upstreams]},
        ip_address=request.client.host if request and request.client else None,
    )

    blocks = await asyncio.to_thread(parse_caddyfile)
    for block in blocks:
        if block["domain"].lower() == domain.lower():
            return DomainInfo(**block)

    return DomainInfo(domain=domain, upstreams=[], tls_enabled=True, tls_auto=True)


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
