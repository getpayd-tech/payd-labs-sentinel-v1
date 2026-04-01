"""Authentication routes — Payd Auth proxy.

All authentication is delegated to https://auth.payd.money.  These routes
forward credentials / tokens and return the upstream responses.
"""
from __future__ import annotations

import base64
import json
import logging

import httpx
from fastapi import APIRouter, HTTPException, Request

from app.config import settings
from app.schemas.auth import (
    LoginRequest,
    LoginResponse,
    OtpRequest,
    OtpRequestResponse,
    RefreshRequest,
    RefreshResponse,
    UserProfile,
    VerifyResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["Auth"])

AUTH_BASE = settings.payd_auth_url
TIMEOUT = 30.0


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _forward(
    method: str,
    url: str,
    *,
    json_body: dict | None = None,
    headers: dict | None = None,
) -> httpx.Response:
    """Forward a request to Payd Auth and return the raw response."""
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        response = await client.request(
            method,
            url,
            json=json_body,
            headers=headers or {},
        )
    return response


def _raise_upstream(response: httpx.Response) -> None:
    """Raise an HTTPException that mirrors the upstream error."""
    try:
        body = response.json()
        detail = body.get("message") or body.get("detail") or body.get("error") or str(body)
    except Exception:
        detail = response.text or "Upstream auth error"
    raise HTTPException(status_code=response.status_code, detail=detail)


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.post("/login", response_model=LoginResponse)
async def login(body: LoginRequest):
    """Forward username + password to Payd Auth, return session token.

    The session token is used in subsequent OTP requests.
    """
    response = await _forward(
        "POST",
        f"{AUTH_BASE}/api/v2/login",
        json_body={"username": body.username, "password": body.password},
    )

    if response.status_code != 200:
        _raise_upstream(response)

    data = response.json()
    session_token = data.get("sessionToken") or data.get("session_token") or ""
    if not session_token:
        raise HTTPException(status_code=502, detail="No session token in upstream response")

    return LoginResponse(session_token=session_token)


@router.post("/request-otp", response_model=OtpRequestResponse)
async def request_otp(request: Request):
    """Forward session token to Payd Auth to trigger OTP delivery."""
    session_token = request.headers.get("x-session-token") or ""
    if not session_token:
        raise HTTPException(status_code=400, detail="Missing x-session-token header")

    response = await _forward(
        "POST",
        f"{AUTH_BASE}/api/v2/request_otp",
        headers={"x-session-token": session_token},
    )

    if response.status_code != 200:
        _raise_upstream(response)

    data = response.json()
    return OtpRequestResponse(
        success=True,
        message=data.get("message", "OTP sent"),
    )


@router.post("/verify-otp", response_model=VerifyResponse)
async def verify_otp(body: OtpRequest, request: Request):
    """Forward OTP + session token to Payd Auth, return auth + refresh tokens."""
    session_token = request.headers.get("x-session-token") or ""
    if not session_token:
        raise HTTPException(status_code=400, detail="Missing x-session-token header")

    response = await _forward(
        "POST",
        f"{AUTH_BASE}/api/v2/verify_otp",
        json_body={"otp": body.otp},
        headers={"x-session-token": session_token},
    )

    if response.status_code != 200:
        _raise_upstream(response)

    data = response.json()
    auth_token = data.get("authToken") or data.get("auth_token") or ""
    refresh_token = data.get("refreshToken") or data.get("refresh_token") or ""

    if not auth_token:
        raise HTTPException(status_code=502, detail="No auth token in upstream response")

    return VerifyResponse(auth_token=auth_token, refresh_token=refresh_token)


@router.post("/refresh", response_model=RefreshResponse)
async def refresh(body: RefreshRequest):
    """Forward refresh token to Payd Auth to renew the session."""
    response = await _forward(
        "POST",
        f"{AUTH_BASE}/api/v2/renew_session",
        json_body={"refresh_token": body.refresh_token},
    )

    if response.status_code != 200:
        _raise_upstream(response)

    data = response.json()
    auth_token = data.get("authToken") or data.get("auth_token") or ""
    refresh_token = data.get("refreshToken") or data.get("refresh_token") or ""

    if not auth_token:
        raise HTTPException(status_code=502, detail="No auth token in upstream response")

    return RefreshResponse(auth_token=auth_token, refresh_token=refresh_token)


@router.get("/me", response_model=UserProfile)
async def me(request: Request):
    """Fetch user profile from Payd Auth, verify admin status, return profile.

    Requires ``x-auth-token`` header with a valid Payd Auth JWT.
    """
    auth_token = request.headers.get("x-auth-token") or ""
    if not auth_token:
        raise HTTPException(status_code=401, detail="Missing x-auth-token header")

    # Decode JWT claims locally to check admin flag
    try:
        parts = auth_token.split(".")
        if len(parts) != 3:
            raise HTTPException(status_code=401, detail="Invalid token format")
        payload = parts[1]
        payload += "=" * (4 - len(payload) % 4)
        claims = json.loads(base64.urlsafe_b64decode(payload))
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid token format")

    if not claims.get("is_admin", False):
        raise HTTPException(status_code=403, detail="Admin access required")

    # Fetch full profile from upstream
    response = await _forward(
        "GET",
        f"{AUTH_BASE}/api/v1/user_profile",
        headers={"x-auth-token": auth_token},
    )

    if response.status_code != 200:
        _raise_upstream(response)

    data = response.json()

    return UserProfile(
        user_id=str(data.get("user_id") or data.get("id") or claims.get("sub", "")),
        username=data.get("username") or claims.get("username", ""),
        email=data.get("email"),
        phone=data.get("phone"),
        full_name=data.get("full_name") or data.get("fullName"),
        is_admin=claims.get("is_admin", False),
        account_status=data.get("account_status") or data.get("status"),
        created_at=data.get("created_at"),
    )
