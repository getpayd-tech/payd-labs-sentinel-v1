"""System metrics routes — current and historical metrics."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import require_admin
from app.database import get_db
from app.models.metrics_snapshot import MetricsSnapshot
from app.schemas.system import MetricsHistoryPoint, SystemMetrics
from app.services.metrics_service import get_system_metrics

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/system", tags=["System"])


@router.get("/metrics", response_model=SystemMetrics)
async def current_metrics(claims: dict = Depends(require_admin)):
    """Return current system metrics (CPU, memory, disk, network, uptime)."""
    return get_system_metrics()


@router.get("/metrics/history", response_model=list[MetricsHistoryPoint])
async def metrics_history(
    hours: int = Query(default=24, ge=1, le=168, description="Number of hours of history to return"),
    db: AsyncSession = Depends(get_db),
    claims: dict = Depends(require_admin),
):
    """Return historical metrics snapshots from the database.

    Defaults to the last 24 hours, configurable up to 7 days (168 hours).
    """
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)

    q = (
        select(MetricsSnapshot)
        .where(MetricsSnapshot.created_at >= cutoff)
        .order_by(MetricsSnapshot.created_at.asc())
    )
    result = await db.execute(q)
    snapshots = result.scalars().all()

    return [
        MetricsHistoryPoint(
            timestamp=s.created_at.isoformat() if s.created_at else "",
            cpu_percent=s.cpu_percent,
            memory_used_mb=s.memory_used_mb,
            disk_used_gb=s.disk_used_gb,
            container_count=s.container_count,
        )
        for s in snapshots
    ]
