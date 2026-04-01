"""Dashboard routes — aggregated stats and health overview."""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends

from app.auth import require_admin
from app.schemas.dashboard import ContainerInfo, DashboardStats, HealthOverview, SystemStats
from app.services.docker_service import list_containers
from app.services.metrics_service import get_system_metrics

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


@router.get("/stats", response_model=DashboardStats)
async def dashboard_stats(claims: dict = Depends(require_admin)):
    """Return aggregated dashboard statistics: system metrics and container info."""
    # System metrics
    metrics = get_system_metrics()
    system = SystemStats(
        cpu_percent=metrics.cpu_percent,
        memory_used_mb=metrics.memory_used_mb,
        memory_total_mb=metrics.memory_total_mb,
        memory_percent=metrics.memory_percent,
        disk_used_gb=metrics.disk_used_gb,
        disk_total_gb=metrics.disk_total_gb,
        disk_percent=metrics.disk_percent,
        uptime_seconds=metrics.uptime_seconds,
    )

    # Container info
    raw_containers = list_containers()
    containers = [ContainerInfo(**c) for c in raw_containers]

    total = len(containers)
    running = sum(1 for c in containers if c.status == "running")
    healthy = sum(1 for c in containers if c.health == "healthy")
    unhealthy = sum(1 for c in containers if c.health == "unhealthy")

    return DashboardStats(
        total_containers=total,
        running_containers=running,
        healthy_containers=healthy,
        unhealthy_containers=unhealthy,
        system=system,
        containers=containers,
    )


@router.get("/health", response_model=list[HealthOverview])
async def health_overview(claims: dict = Depends(require_admin)):
    """Return a health summary for every container."""
    raw_containers = list_containers()
    overview: list[HealthOverview] = []

    for c in raw_containers:
        health_status = c.get("health")
        if health_status is None:
            if c.get("status") == "running":
                health_status = "unknown"
            else:
                health_status = c.get("status", "unknown")

        overview.append(
            HealthOverview(
                service_name=c["name"],
                status=health_status,
                uptime=c.get("started_at"),
                last_check=None,
            )
        )

    return overview
