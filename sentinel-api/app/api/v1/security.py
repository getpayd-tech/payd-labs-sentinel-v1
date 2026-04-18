"""Security routes - fail2ban management + SSH auth log viewing."""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import require_admin
from app.database import get_db
from app.schemas.security import (
    AuthEvent,
    AuthStats,
    BanRequest,
    Fail2banEvent,
    IpHistory,
    JailList,
    JailStatus,
)
from app.services import auth_log_service, fail2ban_service
from app.services.audit_service import log_action

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/security", tags=["Security"])


# ---------------------------------------------------------------------------
# Jails
# ---------------------------------------------------------------------------

@router.get("/jails", response_model=JailList)
async def list_jails(claims: dict = Depends(require_admin)):
    """List active fail2ban jails."""
    try:
        jails = await fail2ban_service.list_jails()
    except Exception as exc:
        logger.error("Failed to list jails: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))
    return JailList(jails=jails)


@router.get("/jails/{jail}", response_model=JailStatus)
async def get_jail(jail: str, claims: dict = Depends(require_admin)):
    """Get full status for a jail: counts + banned IPs."""
    try:
        status = await fail2ban_service.jail_status(jail)
    except Exception as exc:
        logger.error("Failed to get status for jail %s: %s", jail, exc)
        raise HTTPException(status_code=500, detail=str(exc))
    return JailStatus(**status)


@router.post("/jails/{jail}/ban", status_code=201)
async def ban_ip(
    jail: str,
    body: BanRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    claims: dict = Depends(require_admin),
):
    """Ban an IP in a jail."""
    ip = str(body.ip)
    try:
        await fail2ban_service.ban_ip(jail, ip)
    except Exception as exc:
        logger.error("Failed to ban %s in %s: %s", ip, jail, exc)
        raise HTTPException(status_code=500, detail=str(exc))

    await log_action(
        db,
        user_id=claims.get("sub"),
        action="fail2ban.ban",
        target=ip,
        details={"jail": jail},
        ip_address=request.client.host if request and request.client else None,
    )
    return {"detail": f"Banned {ip} in {jail}"}


@router.delete("/jails/{jail}/banned/{ip}")
async def unban_ip(
    jail: str,
    ip: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
    claims: dict = Depends(require_admin),
):
    """Unban an IP from a jail."""
    try:
        await fail2ban_service.unban_ip(jail, ip)
    except Exception as exc:
        logger.error("Failed to unban %s from %s: %s", ip, jail, exc)
        raise HTTPException(status_code=500, detail=str(exc))

    await log_action(
        db,
        user_id=claims.get("sub"),
        action="fail2ban.unban",
        target=ip,
        details={"jail": jail},
        ip_address=request.client.host if request and request.client else None,
    )
    return {"detail": f"Unbanned {ip} from {jail}"}


# ---------------------------------------------------------------------------
# Activity
# ---------------------------------------------------------------------------

@router.get("/activity", response_model=list[Fail2banEvent])
async def activity(
    limit: int = Query(100, ge=1, le=500),
    only_actions: bool = Query(True),
    claims: dict = Depends(require_admin),
):
    """Recent fail2ban log events (Ban/Unban/Found by default)."""
    events = await fail2ban_service.recent_activity(limit=limit, only_actions=only_actions)
    return [Fail2banEvent(**e) for e in events]


@router.get("/ips/{ip}/history", response_model=IpHistory)
async def ip_history(
    ip: str,
    claims: dict = Depends(require_admin),
):
    """Combined fail2ban + auth log history for an IP."""
    f2b = await fail2ban_service.ip_history(ip, limit=200)
    auth = await auth_log_service.auth_events_for_ip(ip, limit=200)
    return IpHistory(
        ip=ip,
        fail2ban_events=[Fail2banEvent(**e) for e in f2b],
        auth_events=[AuthEvent(**e) for e in auth],
    )


# ---------------------------------------------------------------------------
# Auth log
# ---------------------------------------------------------------------------

@router.get("/auth-log", response_model=list[AuthEvent])
async def auth_log(
    limit: int = Query(100, ge=1, le=500),
    event_type: str | None = Query(None, pattern=r"^(success|failure|info)$"),
    claims: dict = Depends(require_admin),
):
    """Recent SSH auth events, newest first."""
    events = await auth_log_service.recent_auth(limit=limit, event_type=event_type)
    return [AuthEvent(**e) for e in events]


@router.get("/auth-stats", response_model=AuthStats)
async def auth_stats(
    hours: int = Query(24, ge=1, le=168),
    claims: dict = Depends(require_admin),
):
    """Aggregate SSH stats over the last N hours."""
    stats = await auth_log_service.auth_stats(hours=hours)
    return AuthStats(**stats)
