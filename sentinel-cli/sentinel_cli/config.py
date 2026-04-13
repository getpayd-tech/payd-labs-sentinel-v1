"""Configuration constants for Sentinel CLI."""
from __future__ import annotations

import os
from pathlib import Path

DEFAULT_BASE_URL = "https://sentinel.paydlabs.com"
CREDENTIALS_DIR = Path.home() / ".sentinel"
CREDENTIALS_FILE = CREDENTIALS_DIR / "credentials.json"


def get_base_url(override: str | None = None) -> str:
    """Return Sentinel API base URL from override, env var, or default."""
    if override:
        return override.rstrip("/")
    return os.environ.get("SENTINEL_URL", DEFAULT_BASE_URL).rstrip("/")
