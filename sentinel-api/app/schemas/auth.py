"""Payd Auth proxy schemas.

Request/response models for the authentication routes that proxy to
auth.payd.money.
"""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


# -- Requests ----------------------------------------------------------------

class LoginRequest(BaseModel):
    username: str = Field(..., min_length=1, description="Payd username")
    password: str = Field(..., min_length=1, description="Payd password")


class OtpRequest(BaseModel):
    otp: str = Field(..., min_length=4, max_length=10, description="One-time password")


class RefreshRequest(BaseModel):
    refresh_token: str = Field(..., min_length=1, description="Refresh token from verify-otp")


# -- Responses ---------------------------------------------------------------

class LoginResponse(BaseModel):
    session_token: str


class OtpRequestResponse(BaseModel):
    success: bool
    message: str = ""


class VerifyResponse(BaseModel):
    auth_token: str
    refresh_token: str


class RefreshResponse(BaseModel):
    auth_token: str
    refresh_token: str


class UserProfile(BaseModel):
    user_id: str = ""
    username: str = ""
    email: Optional[str] = None
    phone: Optional[str] = None
    full_name: Optional[str] = None
    is_admin: bool = False
    account_status: Optional[str] = None
    created_at: Optional[str] = None

    model_config = {"extra": "allow"}
