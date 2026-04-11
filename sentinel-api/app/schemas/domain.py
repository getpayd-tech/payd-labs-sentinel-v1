"""Domain / Caddy routing schemas."""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class UpstreamTarget(BaseModel):
    """A single upstream target (address:port)."""
    address: str
    port: int = 80


class ProxyTarget(BaseModel):
    """A single reverse-proxy rule inside a domain block."""
    path_prefix: str = Field("/", description="URL path prefix to match (e.g. '/api')")
    upstream: str = Field(..., description="Upstream address (e.g. 'my-app:8000')")


class DomainInfo(BaseModel):
    """Parsed Caddy domain block."""
    domain: str
    upstreams: list[UpstreamTarget] = []
    tls_enabled: bool = True
    tls_auto: bool = True
    tls_mode: str = "auto"  # auto | cloudflare_dns | off
    created_at: Optional[str] = None


class DomainCreate(BaseModel):
    """Request body for adding a new domain route."""
    domain: str = Field(..., min_length=1, description="Domain name (e.g. 'app.example.com')")
    upstreams: list[UpstreamTarget] = Field(
        ...,
        min_length=1,
        description="Upstream targets for this domain",
    )
    tls_mode: str = Field("auto", description="TLS mode: auto (ACME), cloudflare_dns, off")


class DomainUpdate(BaseModel):
    """Request body for updating an existing domain route."""
    upstreams: list[UpstreamTarget] = Field(
        ...,
        min_length=1,
        description="Replacement upstream targets",
    )
    tls_mode: str = Field("auto", description="TLS mode: auto (ACME), cloudflare_dns, off")


class CaddyReloadResponse(BaseModel):
    """Result of a Caddy reload operation."""
    success: bool
    message: str = ""


class OnDemandTlsStatus(BaseModel):
    """Status of on-demand TLS configuration."""
    enabled: bool
    message: str = ""
