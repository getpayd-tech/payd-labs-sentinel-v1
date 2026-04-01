"""Aggregated log routes — fetch and filter logs across containers."""
from __future__ import annotations

import asyncio
import logging
from typing import Optional

from fastapi import APIRouter, Depends, Query

from app.auth import require_admin
from app.schemas.logs import AggregatedLogs, LogEntry
from app.services.log_service import get_aggregated_logs

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/logs", tags=["Logs"])


@router.get("/", response_model=AggregatedLogs)
async def get_logs(
    containers: Optional[str] = Query(
        None,
        description="Comma-separated container names. If omitted, all running containers are included.",
    ),
    search: Optional[str] = Query(None, description="Filter by text (case-insensitive)"),
    level: Optional[str] = Query(None, description="Filter by log level (DEBUG, INFO, WARN, ERROR, CRITICAL)"),
    tail: int = Query(200, ge=1, le=5000, description="Number of trailing lines per container"),
    since: Optional[int] = Query(None, description="Unix timestamp — only return logs after this time"),
    claims: dict = Depends(require_admin),
):
    """Fetch aggregated logs from one or more containers.

    Logs are merged and sorted by timestamp. Supports filtering by
    container names, search text, log level, and time.
    """
    container_list: list[str] | None = None
    if containers:
        container_list = [c.strip() for c in containers.split(",") if c.strip()]

    data = await asyncio.to_thread(
        get_aggregated_logs,
        containers=container_list,
        search=search,
        level=level,
        tail=tail,
        since=since,
    )

    return AggregatedLogs(
        entries=[LogEntry(**e) for e in data["entries"]],
        total=data["total"],
    )
