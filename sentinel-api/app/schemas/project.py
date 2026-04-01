"""Project schemas."""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class ProjectCreate(BaseModel):
    """Request body for creating a new project."""
    name: str = Field(..., min_length=1, max_length=100, pattern=r"^[a-z0-9][a-z0-9\-]*$")
    display_name: str = Field(..., min_length=1, max_length=200)
    project_type: str = Field("fastapi", description="fastapi, nextjs, static, custom")
    github_repo: Optional[str] = None
    ghcr_image: Optional[str] = None
    domain: Optional[str] = None
    health_endpoint: Optional[str] = "/health"
    database_name: Optional[str] = None
    container_names: Optional[dict] = None


class ProjectUpdate(BaseModel):
    """Request body for updating an existing project."""
    display_name: Optional[str] = None
    project_type: Optional[str] = None
    github_repo: Optional[str] = None
    ghcr_image: Optional[str] = None
    domain: Optional[str] = None
    health_endpoint: Optional[str] = None
    database_name: Optional[str] = None
    container_names: Optional[dict] = None
    status: Optional[str] = None


class ProjectResponse(BaseModel):
    """Full project record."""
    id: str
    name: str
    display_name: str
    project_type: str
    github_repo: Optional[str] = None
    ghcr_image: Optional[str] = None
    domain: Optional[str] = None
    compose_path: Optional[str] = None
    container_names: Optional[dict] = None
    health_endpoint: Optional[str] = None
    webhook_secret: Optional[str] = None
    database_name: Optional[str] = None
    status: str = "active"
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

    model_config = {"from_attributes": True}


class ProjectList(BaseModel):
    """List of projects."""
    items: list[ProjectResponse]
    total: int


class EnvVar(BaseModel):
    """Single environment variable with masked value."""
    key: str
    value: str  # masked (e.g. "****1234")
    is_secret: bool = True


class EnvVarUpdate(BaseModel):
    """Request body for updating environment variables."""
    variables: dict[str, str] = Field(
        ...,
        description="Key-value pairs of environment variables",
    )


class ProvisionRequest(BaseModel):
    """Request body for provisioning server resources."""
    create_database: bool = Field(
        False,
        description="Whether to create a PostgreSQL database for the project",
    )


class TemplateInfo(BaseModel):
    """Available project template."""
    name: str
    description: str
    project_type: str
