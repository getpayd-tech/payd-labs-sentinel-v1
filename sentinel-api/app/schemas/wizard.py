"""Deploy wizard schemas."""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class WizardRequest(BaseModel):
    """Full wizard payload for project provisioning."""
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


class WizardPreviewRequest(BaseModel):
    """Request body for previewing generated artifacts without executing."""
    name: str = Field(..., pattern=r"^[a-z0-9][a-z0-9\-]*$")
    display_name: str = ""
    project_type: str
    github_repo: str
    domain: str = ""
    tls_mode: str = "auto"
    health_endpoint: str = "/health"


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


class WizardResponse(BaseModel):
    """Response from the wizard execution."""
    project_id: str
    webhook_secret: str
    compose_preview: str
    caddyfile_preview: str
    workflow_preview: str
    steps: list[WizardStep]
