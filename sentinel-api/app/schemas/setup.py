"""Setup wizard schemas."""
from __future__ import annotations

from pydantic import BaseModel, Field


class SetupStatus(BaseModel):
    """Whether the setup wizard has been completed."""
    setup_complete: bool
    # Current effective config (may come from env if wizard not completed yet)
    sentinel_url: str = ""
    caddy_container: str = ""
    proxy_network: str = ""
    catchall_upstream: str = ""
    server_ip: str = ""
    allowed_usernames: str = ""
    ghcr_user: str = ""


class SetupRequest(BaseModel):
    """Setup wizard form submission."""
    sentinel_url: str = Field(..., min_length=1, description="Public URL of this Sentinel instance")
    cors_origins: str = Field("", description="Comma-separated CORS origins")
    caddy_container: str = Field("caddy-proxy", description="Docker container name for Caddy")
    proxy_network: str = Field("proxy", description="External Docker network name")
    catchall_upstream: str = Field("", description="Optional on-demand TLS catch-all upstream (host:port)")
    server_ip: str = Field("", description="Server IP shown in DNS instructions")
    allowed_usernames: str = Field("", description="Comma-separated whitelist of Payd Auth usernames")
    ghcr_user: str = Field("", description="GHCR org or user for pulling deploy images")


class SetupResponse(BaseModel):
    """Response after completing setup."""
    setup_complete: bool = True
    message: str
