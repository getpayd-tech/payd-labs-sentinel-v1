"""Setup wizard routes.

Public GET for setup status so the UI can decide whether to redirect to /setup
on first boot. Admin-gated POST to submit the wizard form.
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import require_admin
from app.database import get_db
from app.schemas.setup import SetupRequest, SetupResponse, SetupStatus
from app.services.audit_service import log_action
from app.services.instance_config import (
    get_effective,
    is_setup_complete,
    load_instance_config,
    save_instance_config,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/setup", tags=["Setup"])


@router.get("/status", response_model=SetupStatus)
async def status():
    """Return current setup state + effective config values.

    Unauthenticated so the UI can check at load time to decide whether to
    redirect to /setup.
    """
    return SetupStatus(
        setup_complete=is_setup_complete(),
        sentinel_url=get_effective("sentinel_url"),
        caddy_container=get_effective("caddy_container"),
        proxy_network=get_effective("proxy_network"),
        catchall_upstream=get_effective("catchall_upstream"),
        server_ip=get_effective("server_ip"),
        allowed_usernames=get_effective("allowed_usernames"),
        ghcr_user=get_effective("ghcr_user"),
    )


@router.post("", response_model=SetupResponse)
async def submit(
    body: SetupRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    claims: dict = Depends(require_admin),
):
    """Save setup wizard answers to the instance config file."""
    data = load_instance_config()
    data.update({
        "setup_complete": True,
        "sentinel_url": body.sentinel_url.rstrip("/"),
        "cors_origins": body.cors_origins,
        "caddy_container": body.caddy_container or "caddy-proxy",
        "proxy_network": body.proxy_network or "proxy",
        "catchall_upstream": body.catchall_upstream,
        "server_ip": body.server_ip,
        "allowed_usernames": body.allowed_usernames,
        "ghcr_user": body.ghcr_user,
    })
    save_instance_config(data)

    await log_action(
        db,
        user_id=claims.get("sub"),
        action="setup.complete",
        target=body.sentinel_url,
        details={"caddy_container": body.caddy_container, "proxy_network": body.proxy_network},
        ip_address=request.client.host if request and request.client else None,
    )

    return SetupResponse(message="Setup complete. Welcome to Sentinel.")
