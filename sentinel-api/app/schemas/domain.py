"""Domain / Caddy routing schemas."""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class ProxyTarget(BaseModel):
    """A single reverse-proxy rule inside a domain block."""
    path_prefix: str = Field("/", description="URL path prefix to match (e.g. '/api')")
    upstream: str = Field(..., description="Upstream address (e.g. 'my-app:8000')")


class DomainInfo(BaseModel):
    """Parsed Caddy domain block."""
    domain: str
    upstream_services: list[str] = []
    has_tls: bool = True
    raw_config: str = ""


class DomainCreate(BaseModel):
    """Request body for adding a new domain route."""
    domain: str = Field(..., min_length=1, description="Domain name (e.g. 'app.example.com')")
    proxy_targets: list[ProxyTarget] = Field(
        ...,
        min_length=1,
        description="Reverse-proxy rules for this domain",
    )


class DomainUpdate(BaseModel):
    """Request body for updating an existing domain route."""
    proxy_targets: list[ProxyTarget] = Field(
        ...,
        min_length=1,
        description="Replacement reverse-proxy rules",
    )


class DomainList(BaseModel):
    """List of all domain routes."""
    items: list[DomainInfo]
    total: int


class CaddyReloadResponse(BaseModel):
    """Result of a Caddy reload operation."""
    success: bool
    message: str = ""
