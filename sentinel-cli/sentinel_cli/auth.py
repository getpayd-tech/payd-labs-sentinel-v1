"""Authentication - OTP login, token caching, and auto-refresh."""
from __future__ import annotations

import base64
import json
import logging
import os
import time

import httpx
from rich.console import Console
from rich.prompt import Prompt

from sentinel_cli.config import CREDENTIALS_DIR, CREDENTIALS_FILE

logger = logging.getLogger(__name__)
console = Console()


def _decode_jwt_payload(token: str) -> dict:
    """Decode the payload segment of a JWT without signature verification."""
    parts = token.split(".")
    if len(parts) != 3:
        raise ValueError("Invalid JWT format")
    payload = parts[1]
    payload += "=" * (4 - len(payload) % 4)
    return json.loads(base64.urlsafe_b64decode(payload))


def save_credentials(auth_token: str, refresh_token: str) -> None:
    """Persist tokens to ~/.sentinel/credentials.json with restricted permissions."""
    claims = _decode_jwt_payload(auth_token)
    expires_at = claims.get("exp", int(time.time()) + 3600)

    CREDENTIALS_DIR.mkdir(parents=True, exist_ok=True)
    CREDENTIALS_DIR.chmod(0o700)

    data = {
        "auth_token": auth_token,
        "refresh_token": refresh_token,
        "expires_at": expires_at,
        "username": claims.get("username", ""),
    }
    CREDENTIALS_FILE.write_text(json.dumps(data, indent=2))
    CREDENTIALS_FILE.chmod(0o600)


def load_credentials() -> dict | None:
    """Load cached credentials from disk. Returns None if missing or corrupt."""
    if not CREDENTIALS_FILE.exists():
        return None
    try:
        return json.loads(CREDENTIALS_FILE.read_text())
    except (json.JSONDecodeError, OSError):
        return None


def get_valid_token(base_url: str) -> str | None:
    """Return a valid auth token, refreshing if needed.

    Checks (in order):
    1. SENTINEL_TOKEN env var
    2. Cached credentials with auto-refresh
    Returns None if no valid token is available.
    """
    env_token = os.environ.get("SENTINEL_TOKEN")
    if env_token:
        return env_token

    creds = load_credentials()
    if not creds:
        return None

    now = time.time()
    if creds["expires_at"] > now + 60:
        return creds["auth_token"]

    # Token expired or near expiry - try refresh
    try:
        new_auth, new_refresh = _refresh_token(base_url, creds["refresh_token"])
        save_credentials(new_auth, new_refresh)
        return new_auth
    except Exception as exc:
        logger.debug("Token refresh failed: %s", exc)
        return None


def _refresh_token(base_url: str, refresh_tok: str) -> tuple[str, str]:
    """Exchange a refresh token for new auth + refresh tokens."""
    with httpx.Client(timeout=30.0) as client:
        resp = client.post(
            f"{base_url}/api/v1/auth/refresh",
            json={"refresh_token": refresh_tok},
        )
        resp.raise_for_status()
        data = resp.json()
        auth_token = data.get("authToken") or data.get("access_token")
        refresh_token = data.get("refreshToken") or data.get("refresh_token")
        if not auth_token or not refresh_token:
            raise ValueError("Missing tokens in refresh response")
        return auth_token, refresh_token


def interactive_login(base_url: str) -> None:
    """Run the full OTP login flow interactively."""
    username = Prompt.ask("[bold]Username[/bold]")
    password = Prompt.ask("[bold]Password[/bold]", password=True)

    with httpx.Client(timeout=30.0) as client:
        # Step 1: Login
        resp = client.post(
            f"{base_url}/api/v1/auth/login",
            json={"username": username, "password": password},
        )
        if resp.status_code >= 400:
            detail = resp.json().get("detail", "Login failed")
            console.print(f"[red]Login failed:[/red] {detail}")
            raise SystemExit(1)

        data = resp.json()
        session_token = data.get("sessionToken", "")

        # Step 2: Request OTP
        resp = client.post(
            f"{base_url}/api/v1/auth/request-otp",
            headers={"x-session-token": session_token},
            content=b"",
        )
        if resp.status_code >= 400:
            detail = resp.json().get("detail", "OTP request failed")
            console.print(f"[red]OTP request failed:[/red] {detail}")
            raise SystemExit(1)

        otp_data = resp.json()
        new_session = otp_data.get("sessionToken")
        if new_session:
            session_token = new_session

        console.print("[dim]OTP sent. Check your phone/email.[/dim]")

        # Step 3: Verify OTP
        otp_code = Prompt.ask("[bold]OTP Code[/bold]")
        resp = client.post(
            f"{base_url}/api/v1/auth/verify-otp",
            json={"otp": otp_code},
            headers={"x-session-token": session_token},
        )
        if resp.status_code >= 400:
            detail = resp.json().get("detail", "OTP verification failed")
            console.print(f"[red]OTP verification failed:[/red] {detail}")
            raise SystemExit(1)

        data = resp.json()
        auth_token = data.get("authToken") or data.get("access_token")
        refresh_token = data.get("refreshToken") or data.get("refresh_token")

        if not auth_token:
            console.print("[red]No auth token in response[/red]")
            raise SystemExit(1)

        # Verify admin status
        claims = _decode_jwt_payload(auth_token)
        if not claims.get("is_admin"):
            console.print("[red]Account is not an admin[/red]")
            raise SystemExit(1)

        save_credentials(auth_token, refresh_token or "")
        console.print(f"[green]Logged in as {claims.get('username', username)}[/green]")
