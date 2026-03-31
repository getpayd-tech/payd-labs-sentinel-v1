from __future__ import annotations

from pydantic import BaseModel


class SystemStats(BaseModel):
    cpu_percent: float
    memory_used_mb: float
    memory_total_mb: float
    memory_percent: float
    disk_used_gb: float
    disk_total_gb: float
    disk_percent: float
    uptime_seconds: float


class ContainerInfo(BaseModel):
    name: str
    status: str
    health: str | None = None
    image: str
    created: str
    started_at: str | None = None
    ports: dict | None = None
    cpu_percent: float = 0.0
    memory_usage_mb: float = 0.0
    memory_limit_mb: float = 0.0
    network_rx_mb: float = 0.0
    network_tx_mb: float = 0.0


class DashboardStats(BaseModel):
    total_containers: int
    running_containers: int
    healthy_containers: int
    unhealthy_containers: int
    system: SystemStats
    containers: list[ContainerInfo]


class HealthOverview(BaseModel):
    service_name: str
    status: str  # healthy, unhealthy, unknown
    uptime: str | None = None
    last_check: str | None = None
