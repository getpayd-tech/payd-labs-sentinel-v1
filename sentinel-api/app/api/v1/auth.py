"""Authentication routes — Payd Auth proxy.

Transparent proxy to https://auth.payd.money, matching the exact pattern
used by Payd Stables admin. Returns raw upstream responses with tokens
extracted from response headers and injected into the response body.
"""
from __future__ import annotations

import base64
import json
import logging

import httpx
from fastapi import APIRouter, HTTPException, Header, Request

from app.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["Auth"])

PAYD_AUTH_URL = settings.payd_auth_url
TIMEOUT = 30.0


@router.post("/login")
async def login(request: Request):
    """Forward username + password to Payd Auth, return response with sessionToken."""
    body = await request.json()
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        resp = await client.post(
            f"{PAYD_AUTH_URL}/api/v2/login",
            json=body,
            headers={"Content-Type": "application/json"},
        )
    data = resp.json() if resp.status_code < 500 else {}
    # Session token comes in response header
    session_token = resp.headers.get("x-session-token")
    if session_token:
        data["sessionToken"] = session_token
    if resp.status_code >= 400:
        raise HTTPException(status_code=resp.status_code, detail=data.get("message") or data.get("error") or "Login failed")
    return data


@router.post("/request-otp")
async def request_otp(request: Request, x_session_token: str = Header("")):
    """Forward session token to Payd Auth to trigger OTP delivery."""
    body = await request.json() if await request.body() else {}
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        resp = await client.post(
            f"{PAYD_AUTH_URL}/api/v2/request_otp",
            json=body,
            headers={
                "Content-Type": "application/json",
                "x-session-token": x_session_token,
            },
        )
    data = resp.json() if resp.status_code < 500 else {}
    # Updated session token may come in response header
    new_token = resp.headers.get("x-session-token")
    if new_token:
        data["sessionToken"] = new_token
    if resp.status_code >= 400:
        raise HTTPException(status_code=resp.status_code, detail=data.get("message") or data.get("error") or "OTP request failed")
    return data


@router.post("/verify-otp")
async def verify_otp(request: Request, x_session_token: str = Header("")):
    """Forward OTP + session token to Payd Auth, return auth + refresh tokens."""
    body = await request.json()
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        resp = await client.post(
            f"{PAYD_AUTH_URL}/api/v2/verify_otp",
            json=body,
            headers={
                "Content-Type": "application/json",
                "x-session-token": x_session_token,
            },
        )
    data = resp.json() if resp.status_code < 500 else {}
    # Tokens may come in response headers or body
    auth_token = (
        resp.headers.get("x-auth-token")
        or data.get("access_token")
        or data.get("authToken")
    )
    refresh_token = (
        resp.headers.get("x-auth-refresh")
        or data.get("refresh_token")
        or data.get("refreshToken")
    )
    if auth_token:
        data["authToken"] = auth_token
    if refresh_token:
        data["refreshToken"] = refresh_token
    if resp.status_code >= 400:
        raise HTTPException(status_code=resp.status_code, detail=data.get("message") or data.get("error") or "OTP verification failed")
    return data


@router.post("/refresh")
async def refresh(request: Request):
    """Forward refresh token to Payd Auth to renew the session."""
    body = await request.json()
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        resp = await client.post(
            f"{PAYD_AUTH_URL}/api/v2/renew_session",
            json=body,
            headers={"Content-Type": "application/json"},
        )
    data = resp.json() if resp.status_code < 500 else {}
    auth_token = (
        resp.headers.get("x-auth-token")
        or data.get("access_token")
        or data.get("authToken")
    )
    refresh_token = (
        resp.headers.get("x-auth-refresh")
        or data.get("refresh_token")
        or data.get("refreshToken")
    )
    if auth_token:
        data["authToken"] = auth_token
    if refresh_token:
        data["refreshToken"] = refresh_token
    if resp.status_code >= 400:
        raise HTTPException(status_code=resp.status_code, detail=data.get("message") or data.get("error") or "Token refresh failed")
    return data


@router.get("/me")
async def me(x_auth_token: str = Header("")):
    """Fetch user profile from Payd Auth, verify admin status, return profile."""
    if not x_auth_token:
        raise HTTPException(status_code=401, detail="No token")

    try:
        # Decode JWT claims (no verification — Payd Auth handles that)
        parts = x_auth_token.split(".")
        payload = parts[1] + "=" * (4 - len(parts[1]) % 4)
        claims = json.loads(base64.b64decode(payload))

        user_id = claims.get("user_id", "")
        is_admin = claims.get("is_admin", False)

        if not is_admin:
            raise HTTPException(status_code=403, detail="Admin access required")

        # Username whitelist check
        username = claims.get("username", "").lower()
        allowed = settings.allowed_username_list if hasattr(settings, 'allowed_username_list') else []
        if allowed and username not in [u.lower() for u in allowed]:
            raise HTTPException(status_code=403, detail="Access denied. Your account is not whitelisted.")

        # Fetch profile from Payd Auth (v3 endpoint with user_id)
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            resp = await client.get(
                f"{PAYD_AUTH_URL}/api/v3/user_profile/{user_id}",
                headers={"x-auth-token": x_auth_token},
            )

        if resp.status_code != 200:
            raise HTTPException(status_code=401, detail="Invalid token")

        profile_data = resp.json()
        user = (
            profile_data.get("user_profile", {}).get("user")
            or profile_data.get("data", {}).get("user")
            or profile_data
        )

        return {
            "user_id": user_id,
            "username": user.get("username", claims.get("username", "")),
            "email": user.get("email", claims.get("email", "")),
            "is_admin": is_admin,
            "first_name": user.get("first_name", ""),
            "last_name": user.get("last_name", ""),
        }
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=401, detail="Token validation failed")
