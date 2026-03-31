from __future__ import annotations

from pydantic import BaseModel


class ContainerDetail(BaseModel):
    name: str
    id: str
    status: str
    health: str | None = None
    image: str
    image_id: str
    created: str
    started_at: str | None = None
    restart_count: int = 0
    platform: str | None = None
    ports: dict | None = None
    networks: list[str] = []
    volumes: list[str] = []
    env_keys: list[str] = []  # Keys only, no values
    labels: dict[str, str] = {}
    cpu_percent: float = 0.0
    memory_usage_mb: float = 0.0
    memory_limit_mb: float = 0.0


class ContainerAction(BaseModel):
    success: bool
    message: str


class LogEntry(BaseModel):
    timestamp: str
    message: str
    stream: str  # stdout, stderr


class ContainerLogs(BaseModel):
    container_name: str
    logs: list[LogEntry]
    total: int
