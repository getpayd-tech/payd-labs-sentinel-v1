from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, String, Text, DateTime, JSON, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    display_name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    project_type: Mapped[str] = mapped_column(String(20), nullable=False, default="fastapi")
    github_repo: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    ghcr_image: Mapped[Optional[str]] = mapped_column(String(300), nullable=True)
    domain: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    compose_path: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    compose_file: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    container_names: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    health_endpoint: Mapped[Optional[str]] = mapped_column(String(200), nullable=True, default="/health")
    webhook_secret: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    database_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    env_vars_encrypted: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    supports_custom_domains: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    custom_domain_upstream: Mapped[Optional[str]] = mapped_column(String(300), nullable=True)
    service_api_key: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())
