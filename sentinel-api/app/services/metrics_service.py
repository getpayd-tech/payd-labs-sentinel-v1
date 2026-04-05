"""System metrics collection service.

Uses psutil to gather host-level CPU, memory, disk, network, and uptime
information for the Sentinel dashboard.
"""
from __future__ import annotations

import logging
import time

import psutil

from app.schemas.system import SystemMetrics

logger = logging.getLogger(__name__)


def get_system_metrics() -> SystemMetrics:
    """Collect current system metrics and return a SystemMetrics schema instance."""
    # CPU
    cpu_percent = psutil.cpu_percent(interval=0.5)
    cpu_count = psutil.cpu_count(logical=True) or 1

    # Memory
    mem = psutil.virtual_memory()
    memory_used_mb = round(mem.used / (1024 * 1024), 2)
    memory_total_mb = round(mem.total / (1024 * 1024), 2)
    memory_percent = mem.percent

    # Disk (root partition)
    disk = psutil.disk_usage("/")
    disk_used_gb = round(disk.used / (1024 * 1024 * 1024), 2)
    disk_total_gb = round(disk.total / (1024 * 1024 * 1024), 2)
    disk_percent = disk.percent

    # Network I/O (cumulative since boot)
    net = psutil.net_io_counters()
    network_rx_mb = round(net.bytes_recv / (1024 * 1024), 2)
    network_tx_mb = round(net.bytes_sent / (1024 * 1024), 2)

    # Uptime
    boot_time = psutil.boot_time()
    uptime_seconds = round(time.time() - boot_time, 1)

    # Load average (1, 5, 15 minutes) - returns (0, 0, 0) on Windows
    try:
        load_avg = list(psutil.getloadavg())
    except (AttributeError, OSError):
        load_avg = [0.0, 0.0, 0.0]

    return SystemMetrics(
        cpu_percent=cpu_percent,
        cpu_count=cpu_count,
        memory_used_mb=memory_used_mb,
        memory_total_mb=memory_total_mb,
        memory_percent=memory_percent,
        disk_used_gb=disk_used_gb,
        disk_total_gb=disk_total_gb,
        disk_percent=disk_percent,
        network_rx_mb=network_rx_mb,
        network_tx_mb=network_tx_mb,
        uptime_seconds=uptime_seconds,
        load_average=load_avg,
    )
