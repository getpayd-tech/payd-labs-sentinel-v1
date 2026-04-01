"""Deployment schemas."""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class DeployTrigger(BaseModel):
    """Request body for manual deployment trigger."""
    image_tag: Optional[str] = Field(
        None,
        description="Docker image tag to deploy. If omitted, pulls latest.",
    )


class WebhookPayload(BaseModel):
    """Expected payload from a GitHub webhook or CI trigger."""
    project: str = Field(..., description="Project name matching the project record")
    image_tag: Optional[str] = None
    triggered_by: Optional[str] = None


class DeploymentResponse(BaseModel):
    """Full deployment record."""
    id: str
    project_id: str
    project_name: str = ""
    trigger: str  # webhook, manual, rollback
    image_tag: Optional[str] = None
    previous_image_tag: Optional[str] = None
    status: str  # pending, in_progress, success, failed, rolled_back
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    duration_seconds: Optional[int] = None
    logs: Optional[str] = None
    triggered_by: Optional[str] = None

    model_config = {"from_attributes": True}


class DeploymentList(BaseModel):
    """Paginated list of deployments."""
    items: list[DeploymentResponse]
    total: int
    page: int
    page_size: int
