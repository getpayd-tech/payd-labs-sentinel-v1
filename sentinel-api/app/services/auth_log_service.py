"""SSH auth log parser.

Parses `/var/log/auth.log` for sshd events. The log file is mounted
read-only into the sentinel-api container.

Understood event patterns:
- "Accepted publickey for <user> from <ip> port ..."      -> success
- "Failed password for <user> from <ip> port ..."         -> failure
- "Failed password for invalid user <user> from <ip> ..." -> failure (unknown)
- "Invalid user <user> from <ip> ..."                     -> failure (no user)
- "ROOT LOGIN REFUSED FROM <ip> ..."                      -> failure (root)
- "Disconnected from <ip> ..."                            -> informational
- "Connection closed by <ip> ..."                         -> informational
"""
from __future__ import annotations

import asyncio
import logging
import re
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

AUTH_LOG = Path("/var/log/auth.log")

# Syslog timestamp + process line (two formats - ISO and traditional "Apr 18 04:35:26")
_ISO_LINE_RE = re.compile(
    r"^(?P<ts>\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:[+-]\d{2}:?\d{2}|Z)?)\s+"
    r"\S+\s+"
    r"(?P<process>\S+?)(?:\[\d+\])?:\s+"
    r"(?P<message>.*)$"
)
_SYSLOG_LINE_RE = re.compile(
    r"^(?P<ts>[A-Z][a-z]{2}\s+\d{1,2}\s+\d{2}:\d{2}:\d{2})\s+"
    r"\S+\s+"
    r"(?P<process>\S+?)(?:\[\d+\])?:\s+"
    r"(?P<message>.*)$"
)

# Message patterns
_PATTERNS = [
    (re.compile(r"^Accepted publickey for (?P<user>\S+) from (?P<ip>\S+) port \d+"), "success", "publickey"),
    (re.compile(r"^Accepted password for (?P<user>\S+) from (?P<ip>\S+) port \d+"), "success", "password"),
    (re.compile(r"^Failed password for invalid user (?P<user>\S+) from (?P<ip>\S+) port \d+"), "failure", "invalid_user"),
    (re.compile(r"^Failed password for (?P<user>\S+) from (?P<ip>\S+) port \d+"), "failure", "wrong_password"),
    (re.compile(r"^Invalid user (?P<user>\S+) from (?P<ip>\S+) port \d+"), "failure", "invalid_user"),
    (re.compile(r"^ROOT LOGIN REFUSED FROM (?P<ip>\S+)"), "failure", "root_refused"),
    (re.compile(r"^Disconnected from (?:authenticating user \S+ )?(?P<ip>\S+) port \d+"), "info", "disconnect"),
    (re.compile(r"^Connection closed by (?:authenticating user \S+ )?(?P<ip>\S+) port \d+"), "info", "connection_closed"),
    (re.compile(r"^Connection reset by (?P<ip>\S+) port \d+"), "info", "connection_reset"),
]


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------

def _parse_ts(ts: str) -> datetime | None:
    """Parse either ISO or traditional syslog timestamp."""
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except ValueError:
        pass
    # Traditional syslog - infer current year
    try:
        year = datetime.now().year
        return datetime.strptime(f"{year} {ts}", "%Y %b %d %H:%M:%S")
    except ValueError:
        return None


def _parse_line(line: str) -> dict[str, Any] | None:
    line = line.rstrip("\n")
    m = _ISO_LINE_RE.match(line) or _SYSLOG_LINE_RE.match(line)
    if not m:
        return None

    process = m.group("process")
    # Only interested in sshd entries
    if not process.startswith("sshd"):
        return None

    ts = _parse_ts(m.group("ts"))
    if ts is None:
        return None

    message = m.group("message")
    for pattern, event_type, detail in _PATTERNS:
        mm = pattern.search(message)
        if mm:
            data = mm.groupdict()
            return {
                "timestamp": ts.isoformat(),
                "event": event_type,
                "detail": detail,
                "user": data.get("user"),
                "ip": data.get("ip"),
                "raw": message,
            }
    return None


def _iter_log_lines(path: Path, limit: int | None = None) -> list[str]:
    """Read last `limit` lines from a file (or all if limit is None)."""
    if not path.exists():
        return []
    try:
        with path.open("r", errors="replace") as f:
            lines = f.readlines()
        if limit is not None:
            lines = lines[-limit:]
        return lines
    except OSError as exc:
        logger.warning("Cannot read %s: %s", path, exc)
        return []


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

async def recent_auth(limit: int = 100, event_type: str | None = None) -> list[dict[str, Any]]:
    """Return recent SSH auth events, newest first.

    Args:
        limit: max events to return
        event_type: filter by event type ("success", "failure", "info") or None for all
    """
    # Read enough tail to find `limit` matching events. Many lines in auth.log
    # are non-sshd (sudo, cron, etc) so pull generously.
    raw = await asyncio.to_thread(_iter_log_lines, AUTH_LOG, limit * 10)
    events: list[dict[str, Any]] = []
    for line in reversed(raw):
        ev = _parse_line(line)
        if not ev:
            continue
        if event_type and ev["event"] != event_type:
            continue
        events.append(ev)
        if len(events) >= limit:
            break
    return events


async def auth_events_for_ip(ip: str, limit: int = 200) -> list[dict[str, Any]]:
    """Return SSH auth events for a specific IP, newest first."""
    raw = await asyncio.to_thread(_iter_log_lines, AUTH_LOG, None)
    events: list[dict[str, Any]] = []
    for line in reversed(raw):
        if ip not in line:
            continue
        ev = _parse_line(line)
        if ev and ev.get("ip") == ip:
            events.append(ev)
        if len(events) >= limit:
            break
    return events


async def auth_stats(hours: int = 24) -> dict[str, Any]:
    """Aggregate SSH stats over the last N hours.

    Returns counts + top attacker IPs.
    """
    cutoff = datetime.now() - timedelta(hours=hours)
    # Read a large tail (auth.log typically has tens of thousands of lines/day)
    raw = await asyncio.to_thread(_iter_log_lines, AUTH_LOG, 50000)

    successes = 0
    failures = 0
    info = 0
    ips: set[str] = set()
    failure_counter: Counter[str] = Counter()

    for line in raw:
        ev = _parse_line(line)
        if not ev:
            continue
        ts = datetime.fromisoformat(ev["timestamp"])
        if ts < cutoff:
            continue
        if ev["ip"]:
            ips.add(ev["ip"])
        if ev["event"] == "success":
            successes += 1
        elif ev["event"] == "failure":
            failures += 1
            if ev["ip"]:
                failure_counter[ev["ip"]] += 1
        else:
            info += 1

    top_attackers = [
        {"ip": ip, "failures": cnt}
        for ip, cnt in failure_counter.most_common(10)
    ]

    return {
        "window_hours": hours,
        "successes": successes,
        "failures": failures,
        "info": info,
        "unique_ips": len(ips),
        "top_attackers": top_attackers,
    }
