"""Aggregated log service.

Fetches logs from multiple Docker containers, merges them by timestamp,
and supports search / level filtering.
"""
from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from typing import Any, Optional

from app.services.docker_service import get_container_logs, list_containers

logger = logging.getLogger(__name__)

# Common log level patterns
_LEVEL_RE = re.compile(
    r"\b(DEBUG|INFO|WARN(?:ING)?|ERROR|CRITICAL|FATAL)\b",
    re.IGNORECASE,
)


def _detect_level(message: str) -> str | None:
    """Try to detect a log level from the message text."""
    match = _LEVEL_RE.search(message)
    if match:
        level = match.group(1).upper()
        if level == "WARNING":
            level = "WARN"
        return level
    return None


def get_aggregated_logs(
    containers: Optional[list[str]] = None,
    search: Optional[str] = None,
    level: Optional[str] = None,
    tail: int = 200,
    since: Optional[int] = None,
) -> dict[str, Any]:
    """Fetch and merge logs from one or more Docker containers.

    Args:
        containers: List of container names. If None, fetches from all running containers.
        search: Text to filter log messages (case-insensitive substring match).
        level: Filter by log level (DEBUG, INFO, WARN, ERROR, CRITICAL).
        tail: Number of trailing lines per container.
        since: Unix timestamp — only include logs after this time.

    Returns:
        Dict with ``entries`` (list of log entry dicts) and ``total``.
    """
    # Determine which containers to fetch
    if not containers:
        all_containers = list_containers()
        containers = [c["name"] for c in all_containers if c["status"] == "running"]

    all_entries: list[dict[str, Any]] = []

    for container_name in containers:
        try:
            raw = get_container_logs(container_name, tail=tail, since=since)
            for entry in raw.get("logs", []):
                detected_level = _detect_level(entry.get("message", ""))
                all_entries.append({
                    "timestamp": entry["timestamp"],
                    "message": entry["message"],
                    "stream": entry["stream"],
                    "container_name": container_name,
                    "level": detected_level,
                })
        except Exception as exc:
            logger.debug("Failed to get logs for %s: %s", container_name, exc)

    # Filter by level
    if level:
        level_upper = level.upper()
        if level_upper == "WARNING":
            level_upper = "WARN"
        all_entries = [e for e in all_entries if e.get("level") == level_upper]

    # Filter by search
    if search:
        search_lower = search.lower()
        all_entries = [e for e in all_entries if search_lower in e["message"].lower()]

    # Sort by timestamp
    all_entries.sort(key=lambda e: e["timestamp"])

    return {
        "entries": all_entries,
        "total": len(all_entries),
    }
