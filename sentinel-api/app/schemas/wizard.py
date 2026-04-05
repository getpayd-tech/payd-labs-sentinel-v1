"""Deploy wizard schemas."""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class CaddyRoute(BaseModel):
    """A single Caddy reverse proxy route path."""
    path: str = Field(..., description="Path pattern, e.g. '/api/*'")
    upstream: str = Field(..., description="Upstream target, e.g. 'offline-api:8000'")


class WizardRequest(BaseModel):
    """Full wizard payload for project provisioning + first deploy."""
    name: str = Field(..., pattern=r"^[a-z0-9][a-z0-9\-]*$", min_length=2, max_length=64)
    display_name: str = Field(..., min_length=1)
    project_type: str = Field(..., description="fastapi | vue | blended | nuxt | laravel")
    github_repo: str = Field(..., description="e.g. getpayd-tech/my-app")
    domain: str = Field(..., min_length=1)
    tls_mode: str = Field("auto", description="auto | cloudflare_dns | off")
    create_database: bool = False
    database_name: Optional[str] = None
    env_vars: dict[str, str] = {}
    health_endpoint: str = "/health"
    compose_filename: str = Field("docker-compose.yml", description="Compose file name")
    caddy_routes: list[CaddyRoute] = Field([], description="Custom Caddy routes. Empty = auto-generate from type")
    first_deploy: bool = Field(True, description="Pull and start containers after provisioning")


class WizardPreviewRequest(BaseModel):
    """Request body for previewing generated artifacts without executing."""
    name: str = Field(..., pattern=r"^[a-z0-9][a-z0-9\-]*$")
    display_name: str = ""
    project_type: str
    github_repo: str
    domain: str = ""
    tls_mode: str = "auto"
    health_endpoint: str = "/health"
    caddy_routes: list[CaddyRoute] = []


class WizardStep(BaseModel):
    """A single step in the wizard execution."""
    step: int
    name: str
    status: str  # pending | complete | error
    message: str = ""


class TypeDefaults(BaseModel):
    """Default values for a project type."""
    port: int
    health_endpoint: str
    suggested_env: list[str] = []
    description: str = ""
    container_count: int = 1
    default_routes: list[CaddyRoute] = []


class WizardDraft(BaseModel):
    """Saved wizard draft - all form state for resuming later."""
    id: Optional[str] = None
    name: str = ""
    display_name: str = ""
    project_type: str = ""
    github_repo: str = ""
    domain: str = ""
    tls_mode: str = "auto"
    create_database: bool = False
    database_name: Optional[str] = None
    env_vars: dict[str, str] = {}
    health_endpoint: str = "/health"
    compose_filename: str = "docker-compose.yml"
    caddy_routes: list[CaddyRoute] = []
    first_deploy: bool = True
    current_step: int = 1
    use_custom_routes: bool = False


class WizardResponse(BaseModel):
    """Response from the wizard execution."""
    project_id: str
    webhook_secret: str
    compose_preview: str
    caddyfile_preview: str
    workflow_preview: str
    steps: list[WizardStep]
