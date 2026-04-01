"""Aggregated log schemas."""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel


class LogEntry(BaseModel):
    """Single log entry with container context."""
    timestamp: str
    message: str
    stream: str  # stdout, stderr
    container_name: str = ""
    container: str = ""
    level: Optional[str] = None


class AggregatedLogs(BaseModel):
    """Aggregated logs from one or more containers."""
    entries: list[LogEntry]
    total: int
    containers: list[str] = []
