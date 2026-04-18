"""Security / fail2ban schemas."""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field, IPvAnyAddress


class BannedIp(BaseModel):
    ip: str
    banned_at: Optional[str] = None


class JailStatus(BaseModel):
    name: str
    currently_failed: int = 0
    total_failed: int = 0
    currently_banned: int = 0
    total_banned: int = 0
    banned_ips: list[str] = Field(default_factory=list)


class JailList(BaseModel):
    jails: list[str]


class Fail2banEvent(BaseModel):
    timestamp: str
    level: Optional[str] = None
    jail: Optional[str] = None
    action: Optional[str] = None
    ip: Optional[str] = None
    message: str = ""


class AuthEvent(BaseModel):
    timestamp: str
    event: str  # success | failure | info
    detail: str  # publickey | password | wrong_password | invalid_user | root_refused | disconnect | ...
    user: Optional[str] = None
    ip: Optional[str] = None
    raw: str = ""


class TopAttacker(BaseModel):
    ip: str
    failures: int


class AuthStats(BaseModel):
    window_hours: int
    successes: int
    failures: int
    info: int
    unique_ips: int
    top_attackers: list[TopAttacker]


class BanRequest(BaseModel):
    ip: IPvAnyAddress


class IpHistory(BaseModel):
    ip: str
    fail2ban_events: list[Fail2banEvent]
    auth_events: list[AuthEvent]
