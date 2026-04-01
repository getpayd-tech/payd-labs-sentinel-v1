"""Payd Auth integration — admin verification dependency.

Decodes JWT claims from x-auth-token header and verifies admin status.
Payd Auth (auth.payd.money) handles actual token validation; we only
decode the payload to extract claims for authorization decisions.
"""
from __future__ import annotations

import base64
import json
import logging

from fastapi import HTTPException, Request

logger = logging.getLogger(__name__)


async def require_admin(request: Request) -> dict:
    """Extract and verify admin JWT from x-auth-token header.

    Decodes the JWT payload (base64, no cryptographic verification — Payd Auth
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

    # Username whitelist — if configured, only listed usernames may log in
    from app.config import settings
    allowed = settings.allowed_username_list
    if allowed:
        username = (claims.get("username") or "").lower()
        if username not in allowed:
            raise HTTPException(status_code=403, detail="Access denied. Your account is not whitelisted.")

    return claims
