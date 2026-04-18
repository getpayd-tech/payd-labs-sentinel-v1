"""Fail2ban management service.

Wraps `fail2ban-client` subprocess calls (via the host socket mounted into
the sentinel-api container) and parses `/var/log/fail2ban.log` for activity.

The fail2ban daemon itself runs on the host, NOT inside this container.
We only use `fail2ban-client` which talks to the daemon via the mounted
Unix socket at `/var/run/fail2ban/fail2ban.sock`.
"""
from __future__ import annotations

import asyncio
import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

FAIL2BAN_LOG = Path("/var/log/fail2ban.log")

# Log line pattern: 2026-04-18 04:35:26,123 fail2ban.actions  [1234]: NOTICE  [sshd] Ban 1.2.3.4
_LOG_RE = re.compile(
    r"^(?P<ts>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}),\d+\s+"
    r"(?P<logger>\S+)\s+\[\d+\]:\s+"
    r"(?P<level>\w+)\s+"
    r"(?:\[(?P<jail>\S+?)\]\s+)?"
    r"(?P<message>.*)$"
)

# Message patterns within log lines
_ACTION_RE = re.compile(r"^(?P<action>Ban|Unban|Found|Already banned|Restore Ban)\s+(?P<ip>[0-9a-fA-F.:]+)")


# ---------------------------------------------------------------------------
# Subprocess helpers
# ---------------------------------------------------------------------------

async def _run_client(*args: str) -> tuple[int, str]:
    """Run `fail2ban-client <args>` and return (returncode, combined output).

    Uses list-argument form (never shell=True) so arguments are safe even if
    they contain odd characters.
    """
    cmd = ["fail2ban-client", *args]
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
    )
    stdout, _ = await proc.communicate()
    output = stdout.decode("utf-8", errors="replace") if stdout else ""
    return proc.returncode or 0, output


def _require_ok(rc: int, output: str, what: str) -> str:
    if rc != 0:
        raise RuntimeError(f"{what} failed (rc={rc}): {output.strip()}")
    return output


# ---------------------------------------------------------------------------
# Parsers
# ---------------------------------------------------------------------------

def _extract_list_value(output: str, label: str) -> str:
    """Extract a value from `fail2ban-client status` tree output by its label."""
    # Lines look like: "|- Jail list: sshd, recidive"  or "   `- Banned IP list: 1.2.3.4 5.6.7.8"
    for line in output.splitlines():
        if label in line:
            _, _, value = line.partition(":")
            return value.strip()
    return ""


def _parse_jail_list(output: str) -> list[str]:
    raw = _extract_list_value(output, "Jail list")
    if not raw:
        return []
    return [name.strip() for name in raw.split(",") if name.strip()]


def _parse_jail_status(output: str) -> dict[str, Any]:
    def _int(label: str) -> int:
        val = _extract_list_value(output, label)
        try:
            return int(val)
        except (ValueError, TypeError):
            return 0

    banned_raw = _extract_list_value(output, "Banned IP list")
    banned_ips = [ip for ip in banned_raw.split() if ip]

    return {
        "currently_failed": _int("Currently failed"),
        "total_failed": _int("Total failed"),
        "currently_banned": _int("Currently banned"),
        "total_banned": _int("Total banned"),
        "banned_ips": banned_ips,
    }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

async def list_jails() -> list[str]:
    """Return the list of active jail names."""
    rc, output = await _run_client("status")
    _require_ok(rc, output, "fail2ban-client status")
    return _parse_jail_list(output)


async def jail_status(jail: str) -> dict[str, Any]:
    """Return counts + banned IP list for a jail."""
    rc, output = await _run_client("status", jail)
    _require_ok(rc, output, f"fail2ban-client status {jail}")
    status = _parse_jail_status(output)
    status["name"] = jail
    return status


async def ban_ip(jail: str, ip: str) -> None:
    """Ban an IP in a specific jail."""
    rc, output = await _run_client("set", jail, "banip", ip)
    if rc != 0:
        raise RuntimeError(f"Failed to ban {ip} in {jail}: {output.strip()}")
    logger.info("Banned %s in jail %s", ip, jail)


async def unban_ip(jail: str, ip: str) -> None:
    """Unban an IP from a specific jail."""
    rc, output = await _run_client("set", jail, "unbanip", ip)
    if rc != 0:
        raise RuntimeError(f"Failed to unban {ip} from {jail}: {output.strip()}")
    logger.info("Unbanned %s from jail %s", ip, jail)


# ---------------------------------------------------------------------------
# Log parsing
# ---------------------------------------------------------------------------

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


def _parse_log_event(line: str) -> dict[str, Any] | None:
    """Parse one fail2ban log line into structured form, or None if unparseable."""
    line = line.rstrip("\n")
    m = _LOG_RE.match(line)
    if not m:
        return None

    ts_str = m.group("ts")
    try:
        ts = datetime.strptime(ts_str, "%Y-%m-%d %H:%M:%S")
    except ValueError:
        return None

    message = m.group("message")
    jail = m.group("jail")
    level = m.group("level")

    action = None
    ip = None
    action_m = _ACTION_RE.match(message)
    if action_m:
        action = action_m.group("action")
        ip = action_m.group("ip")

    return {
        "timestamp": ts.isoformat(),
        "level": level,
        "jail": jail,
        "action": action,
        "ip": ip,
        "message": message,
    }


async def recent_activity(limit: int = 100, only_actions: bool = True) -> list[dict[str, Any]]:
    """Return recent fail2ban log events, newest first.

    Args:
        limit: max events to return
        only_actions: if True, skip informational lines and only return
                      Ban/Unban/Found events
    """
    # Read enough tail to have `limit` matching events
    raw_lines = await asyncio.to_thread(_iter_log_lines, FAIL2BAN_LOG, limit * 4)
    events: list[dict[str, Any]] = []
    for line in reversed(raw_lines):
        ev = _parse_log_event(line)
        if not ev:
            continue
        if only_actions and not ev["action"]:
            continue
        events.append(ev)
        if len(events) >= limit:
            break
    return events


async def ip_history(ip: str, limit: int = 200) -> list[dict[str, Any]]:
    """Return all fail2ban log events for a specific IP, newest first."""
    raw_lines = await asyncio.to_thread(_iter_log_lines, FAIL2BAN_LOG, None)
    events: list[dict[str, Any]] = []
    for line in reversed(raw_lines):
        if ip not in line:
            continue
        ev = _parse_log_event(line)
        if not ev:
            continue
        if ev["ip"] == ip:
            events.append(ev)
        if len(events) >= limit:
            break
    return events
