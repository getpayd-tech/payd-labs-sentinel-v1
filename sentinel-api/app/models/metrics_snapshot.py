from __future__ import annotations

from datetime import datetime

from sqlalchemy import Integer, Float, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class MetricsSnapshot(Base):
    __tablename__ = "metrics_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    cpu_percent: Mapped[float] = mapped_column(Float, nullable=False)
    memory_used_mb: Mapped[float] = mapped_column(Float, nullable=False)
    memory_total_mb: Mapped[float] = mapped_column(Float, nullable=False)
    disk_used_gb: Mapped[float] = mapped_column(Float, nullable=False)
    disk_total_gb: Mapped[float] = mapped_column(Float, nullable=False)
    network_rx_mb: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    network_tx_mb: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    container_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), index=True)
