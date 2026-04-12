"""Authentication dependencies.

- require_admin: Decodes JWT claims from x-auth-token header and verifies
  admin status. Payd Auth (auth.payd.money) handles actual token validation;
  we only decode the payload for authorization decisions.
- require_service_key: Validates X-Service-Key header against project
  service_api_key for service-to-service auth (custom domains API).
"""
from __future__ import annotations

import base64
import json
import logging

from fastapi import Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db

logger = logging.getLogger(__name__)


async def require_admin(request: Request) -> dict:
    """Extract and verify admin JWT from x-auth-token header.

    Decodes the JWT payload (base64, no cryptographic verification - Payd Auth
    handles that upstream). Checks the ``is_admin`` claim and returns the full
    claims dict so downstream handlers can access user_id, username, etc.

    Raises:
        HTTPException 401: Missing or malformed token.
        HTTPException 403: Token is valid but user is not an admin.
    """
    token = request.headers.get("x-auth-token")
    if not token:
        raise HTTPException(status_code=401, detail="Missing auth token")

    try:
        parts = token.split(".")
        if len(parts) != 3:
            raise HTTPException(status_code=401, detail="Invalid token format")

        payload = parts[1]
        # Pad base64 to a multiple of 4
        payload += "=" * (4 - len(payload) % 4)
        claims = json.loads(base64.urlsafe_b64decode(payload))
    except (json.JSONDecodeError, UnicodeDecodeError, Exception) as exc:
        logger.warning("Failed to decode auth token: %s", exc)
        raise HTTPException(status_code=401, detail="Invalid token format")

    if not claims.get("is_admin", False):
        raise HTTPException(status_code=403, detail="Admin access required")

    # Username whitelist - if configured, only listed usernames may log in
    from app.config import settings
    allowed = settings.allowed_username_list
    if allowed:
        username = (claims.get("username") or "").lower()
        if username not in allowed:
            raise HTTPException(status_code=403, detail="Access denied. Your account is not whitelisted.")

    return claims


async def require_service_key(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Authenticate a service-to-service call via X-Service-Key header.

    Looks up the project whose ``service_api_key`` matches the header
    value. The project must also have ``supports_custom_domains`` enabled.

    Returns the Project ORM instance so the caller knows which project
    is making the request.
    """
    from app.models.project import Project

    key = request.headers.get("x-service-key")
    if not key:
        raise HTTPException(status_code=401, detail="Missing X-Service-Key header")

    result = await db.execute(
        select(Project).where(Project.service_api_key == key)
    )
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=401, detail="Invalid service key")
    if not project.supports_custom_domains:
        raise HTTPException(status_code=403, detail="Custom domains not enabled for this project")
    return project
