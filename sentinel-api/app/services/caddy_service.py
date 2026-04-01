"""Caddy reverse-proxy management service.

Provides helpers for parsing, modifying, and reloading the Caddyfile
used by the caddy-proxy container.
"""
from __future__ import annotations

import asyncio
import logging
import re
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

CADDYFILE_PATH = Path("/apps/caddy/Caddyfile")


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------

def parse_caddyfile() -> list[dict[str, Any]]:
    """Parse the Caddyfile into a list of domain block dicts.

    Each dict contains:
    - domain: str
    - upstream_services: list[str]
    - has_tls: bool
    - raw_config: str (the raw block text)
    """
    if not CADDYFILE_PATH.exists():
        logger.warning("Caddyfile not found at %s", CADDYFILE_PATH)
        return []

    content = CADDYFILE_PATH.read_text()
    blocks: list[dict[str, Any]] = []

    # Simple brace-level parser
    lines = content.split("\n")
    current_domain: str | None = None
    current_block_lines: list[str] = []
    brace_depth = 0

    for line in lines:
        stripped = line.strip()

        if brace_depth == 0 and stripped and not stripped.startswith("#") and "{" in stripped:
            # Start of a new domain block
            current_domain = stripped.split("{")[0].strip()
            current_block_lines = [line]
            brace_depth = stripped.count("{") - stripped.count("}")
        elif brace_depth > 0:
            current_block_lines.append(line)
            brace_depth += stripped.count("{") - stripped.count("}")

            if brace_depth <= 0:
                # Block closed
                raw = "\n".join(current_block_lines)

                # Extract upstream services
                upstreams: list[str] = []
                for bl in current_block_lines:
                    bl_stripped = bl.strip()
                    if bl_stripped.startswith("reverse_proxy"):
                        # e.g. "reverse_proxy my-app:8000"
                        parts = bl_stripped.split()
                        for part in parts[1:]:
                            if not part.startswith("{") and not part.startswith("#"):
                                upstreams.append(part)

                blocks.append({
                    "domain": current_domain or "",
                    "upstream_services": upstreams,
                    "has_tls": "tls" in raw.lower() or not current_domain or "" == current_domain or ":" not in (current_domain or ""),
                    "raw_config": raw,
                })

                current_domain = None
                current_block_lines = []
                brace_depth = 0

    return blocks


# ---------------------------------------------------------------------------
# Modification
# ---------------------------------------------------------------------------

def _build_block(domain: str, proxy_targets: list[dict[str, str]]) -> str:
    """Build a Caddyfile block string from a domain and proxy targets."""
    lines = [f"{domain} {{"]

    for target in proxy_targets:
        path_prefix = target.get("path_prefix", "/")
        upstream = target["upstream"]

        if path_prefix and path_prefix != "/":
            lines.append(f"    handle_path {path_prefix}* {{")
            lines.append(f"        reverse_proxy {upstream}")
            lines.append("    }")
        else:
            lines.append(f"    reverse_proxy {upstream}")

    lines.append("}")
    return "\n".join(lines)


async def add_domain(domain: str, proxy_targets: list[dict[str, str]]) -> None:
    """Append a new domain block to the Caddyfile.

    Args:
        domain: The domain name (e.g. "app.example.com").
        proxy_targets: List of dicts with ``path_prefix`` and ``upstream``.

    Raises:
        ValueError: If the domain already exists in the Caddyfile.
    """
    existing = parse_caddyfile()
    for block in existing:
        if block["domain"].lower() == domain.lower():
            raise ValueError(f"Domain '{domain}' already exists in Caddyfile")

    block_text = _build_block(domain, proxy_targets)

    CADDYFILE_PATH.parent.mkdir(parents=True, exist_ok=True)

    with open(CADDYFILE_PATH, "a") as f:
        f.write(f"\n\n{block_text}\n")

    logger.info("Added Caddy domain block for %s", domain)


async def update_domain(domain: str, proxy_targets: list[dict[str, str]]) -> None:
    """Replace an existing domain block in the Caddyfile.

    Raises:
        ValueError: If the domain is not found.
    """
    if not CADDYFILE_PATH.exists():
        raise ValueError("Caddyfile not found")

    content = CADDYFILE_PATH.read_text()

    # Find and replace the block
    blocks = parse_caddyfile()
    found = False
    for block in blocks:
        if block["domain"].lower() == domain.lower():
            old_block = block["raw_config"]
            new_block = _build_block(domain, proxy_targets)
            content = content.replace(old_block, new_block)
            found = True
            break

    if not found:
        raise ValueError(f"Domain '{domain}' not found in Caddyfile")

    CADDYFILE_PATH.write_text(content)
    logger.info("Updated Caddy domain block for %s", domain)


async def remove_domain(domain: str) -> None:
    """Remove a domain block from the Caddyfile.

    Raises:
        ValueError: If the domain is not found.
    """
    if not CADDYFILE_PATH.exists():
        raise ValueError("Caddyfile not found")

    content = CADDYFILE_PATH.read_text()

    blocks = parse_caddyfile()
    found = False
    for block in blocks:
        if block["domain"].lower() == domain.lower():
            content = content.replace(block["raw_config"], "")
            found = True
            break

    if not found:
        raise ValueError(f"Domain '{domain}' not found in Caddyfile")

    # Clean up multiple blank lines
    content = re.sub(r"\n{3,}", "\n\n", content).strip() + "\n"
    CADDYFILE_PATH.write_text(content)
    logger.info("Removed Caddy domain block for %s", domain)


async def reload_caddy() -> dict[str, Any]:
    """Reload the Caddy configuration inside the caddy-proxy container.

    Returns a dict with success status and any output.
    """
    try:
        proc = await asyncio.create_subprocess_exec(
            "docker", "exec", "caddy-proxy",
            "caddy", "reload",
            "--config", "/etc/caddy/Caddyfile",
            "--adapter", "caddyfile",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
        stdout, _ = await proc.communicate()
        output = stdout.decode("utf-8", errors="replace") if stdout else ""

        if proc.returncode == 0:
            logger.info("Caddy reloaded successfully")
            return {"success": True, "message": "Caddy reloaded successfully"}
        else:
            logger.error("Caddy reload failed (rc=%d): %s", proc.returncode, output)
            return {"success": False, "message": f"Caddy reload failed: {output}"}
    except Exception as exc:
        logger.error("Failed to reload Caddy: %s", exc)
        return {"success": False, "message": str(exc)}
