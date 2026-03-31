from __future__ import annotations

from pydantic import BaseModel


class SystemMetrics(BaseModel):
    cpu_percent: float
    cpu_count: int
    memory_used_mb: float
    memory_total_mb: float
    memory_percent: float
    disk_used_gb: float
    disk_total_gb: float
    disk_percent: float
    network_rx_mb: float
    network_tx_mb: float
    uptime_seconds: float
    load_average: list[float]


class MetricsHistoryPoint(BaseModel):
    timestamp: str
    cpu_percent: float
    memory_used_mb: float
    disk_used_gb: float
    container_count: int
