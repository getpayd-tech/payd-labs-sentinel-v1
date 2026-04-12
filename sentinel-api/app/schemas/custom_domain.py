"""Custom domain schemas."""
from __future__ import annotations

import re
from typing import Optional

from pydantic import BaseModel, Field, field_validator


_DOMAIN_RE = re.compile(
    r"^(?!-)[a-zA-Z0-9-]{1,63}(?<!-)(\.[a-zA-Z0-9-]{1,63})*\.[a-zA-Z]{2,}$"
)


class CustomDomainCreate(BaseModel):
    """Request body for registering a custom domain."""
    domain: str = Field(..., min_length=4, max_length=200, description="Fully qualified domain name")

    @field_validator("domain")
    @classmethod
    def validate_domain(cls, v: str) -> str:
        v = v.strip().lower()
        if v.startswith("*."):
            raise ValueError("Wildcard domains are not supported")
        if not _DOMAIN_RE.match(v):
            raise ValueError("Invalid domain format")
        return v


class CustomDomainResponse(BaseModel):
    """Custom domain record."""
    id: str
    project_id: str
    project_name: str = ""
    domain: str
    status: str
    error_message: Optional[str] = None
    verified_at: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

    model_config = {"from_attributes": True}


class CustomDomainList(BaseModel):
    """List of custom domains."""
    items: list[CustomDomainResponse]
    total: int
