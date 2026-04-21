"""Persistent instance config - setup wizard output.

Complements the env-driven Pydantic Settings in app/config.py. Values stored
in the JSON file take precedence over env settings for the keys that the
setup wizard manages (sentinel_url, caddy_container, etc.). Env vars remain
the source for secrets and bootstrap defaults.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from app.config import settings

logger = logging.getLogger(__name__)


def _path() -> Path:
    return Path(settings.config_file)


def load_instance_config() -> dict[str, Any]:
    """Load the instance config JSON, or return {} if missing/corrupt."""
    p = _path()
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text())
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning("Failed to load instance config at %s: %s", p, exc)
        return {}


def save_instance_config(data: dict[str, Any]) -> None:
    """Write the instance config JSON atomically."""
    p = _path()
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(data, indent=2, sort_keys=True))
    tmp.replace(p)
    logger.info("Wrote instance config to %s", p)


def is_setup_complete() -> bool:
    return bool(load_instance_config().get("setup_complete"))


# Keys the setup wizard manages. Each maps to a Pydantic Settings attr name.
WIZARD_KEYS = (
    "sentinel_url",
    "cors_origins",
    "caddy_container",
    "proxy_network",
    "catchall_upstream",
    "server_ip",
    "allowed_usernames",
    "ghcr_user",
)


def get_effective(key: str) -> str:
    """Return the effective value for a config key: wizard override wins, else env setting."""
    cfg = load_instance_config()
    if key in cfg and cfg[key] not in (None, ""):
        return str(cfg[key])
    # Fall back to the Pydantic setting
    return str(getattr(settings, key, "") or "")


def get_effective_list(key: str) -> list[str]:
    """Parse a comma-separated effective value into a lowercased list.

    Used for allowed_usernames, cors_origins, etc. Returns an empty list
    if neither wizard nor env has a value set.
    """
    raw = get_effective(key)
    return [item.strip().lower() for item in raw.split(",") if item.strip()]
