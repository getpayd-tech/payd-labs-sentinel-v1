"""Service management routes — container CRUD, lifecycle actions, and logs."""
from __future__ import annotations

import asyncio
import logging

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import require_admin
from app.database import get_db
from app.schemas.dashboard import ContainerInfo
from app.schemas.service import ContainerAction, ContainerDetail, ContainerLogs, LogEntry
from app.services.audit_service import log_action
from app.services.docker_service import (
    get_container,
    get_container_logs,
    list_containers,
    restart_container,
    start_container,
    stop_container,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/services", tags=["Services"])


@router.get("/", response_model=list[ContainerInfo])
async def list_services(claims: dict = Depends(require_admin)):
    """List all Docker containers with basic info and cached stats."""
    raw = await asyncio.to_thread(list_containers)
    return [ContainerInfo(**c) for c in raw]


@router.get("/{name}", response_model=ContainerDetail)
async def get_service(name: str, claims: dict = Depends(require_admin)):
    """Get detailed information for a specific container."""
    data = await asyncio.to_thread(get_container, name)
    return ContainerDetail(**data)


@router.post("/{name}/restart", response_model=ContainerAction)
async def restart_service(
    name: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
    claims: dict = Depends(require_admin),
):
    """Restart a container. Requires admin access."""
    result = await asyncio.to_thread(restart_container, name)

    await log_action(
        db,
        user_id=claims.get("sub"),
        action="container.restart",
        target=name,
        details=result,
        ip_address=request.client.host if request.client else None,
    )

    return ContainerAction(**result)


@router.post("/{name}/stop", response_model=ContainerAction)
async def stop_service(
    name: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
    claims: dict = Depends(require_admin),
):
    """Stop a running container. Requires admin access."""
    result = await asyncio.to_thread(stop_container, name)

    await log_action(
        db,
        user_id=claims.get("sub"),
        action="container.stop",
        target=name,
        details=result,
        ip_address=request.client.host if request.client else None,
    )

    return ContainerAction(**result)


@router.post("/{name}/start", response_model=ContainerAction)
async def start_service(
    name: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
    claims: dict = Depends(require_admin),
):
    """Start a stopped container. Requires admin access."""
    result = await asyncio.to_thread(start_container, name)

    await log_action(
        db,
        user_id=claims.get("sub"),
        action="container.start",
        target=name,
        details=result,
        ip_address=request.client.host if request.client else None,
    )

    return ContainerAction(**result)


@router.get("/{name}/logs", response_model=ContainerLogs)
async def get_service_logs(
    name: str,
    tail: int = Query(default=100, ge=1, le=5000, description="Number of trailing log lines"),
    since: int | None = Query(default=None, description="Unix timestamp — only return logs after this time"),
    claims: dict = Depends(require_admin),
):
    """Retrieve container logs with optional tail count and time filter."""
    raw = await asyncio.to_thread(get_container_logs, name, tail, since)
    return ContainerLogs(
        container_name=raw["container_name"],
        logs=[LogEntry(**entry) for entry in raw["logs"]],
        total=raw["total"],
    )
