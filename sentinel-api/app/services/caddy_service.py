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

from app.services.instance_config import get_effective

logger = logging.getLogger(__name__)

CADDYFILE_PATH = Path("/apps/caddy/Caddyfile")

# Infrastructure block identifiers (not user-managed domains)
_INFRASTRUCTURE_DOMAINS = {"", "https://"}

# The ask URL points to Sentinel, which validates against its custom_domains table.
# Caddy appends ?domain=<name> to the URL automatically - do NOT include {host}.
ON_DEMAND_TLS_DIRECTIVE = """    on_demand_tls {
        ask http://sentinel-api:8000/internal/domain-check
    }"""

def _build_catchall_block() -> str | None:
    """Build the on-demand TLS catch-all block from the configured upstream.

    Returns None if no upstream is configured - in that case no catch-all
    block is emitted and unregistered domains get a clean 404 from Caddy.
    """
    upstream = get_effective("catchall_upstream")
    if not upstream:
        return None
    return (
        "https:// {\n"
        "    tls {\n"
        "        on_demand\n"
        "    }\n"
        f"    reverse_proxy {upstream}\n"
        "}"
    )


# ---------------------------------------------------------------------------
# TLS mode detection
# ---------------------------------------------------------------------------

def _detect_tls_mode(raw_block: str) -> str:
    """Detect the TLS mode from a raw Caddyfile block."""
    lower = raw_block.lower()
    if "dns cloudflare" in lower:
        return "cloudflare_dns"
    if re.search(r"\btls\s+off\b", lower):
        return "off"
    return "auto"


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------

def _parse_caddyfile_raw() -> list[dict[str, Any]]:
    """Parse the Caddyfile into ALL blocks including infrastructure ones."""
    if not CADDYFILE_PATH.exists():
        logger.warning("Caddyfile not found at %s", CADDYFILE_PATH)
        return []

    content = CADDYFILE_PATH.read_text()
    blocks: list[dict[str, Any]] = []

    lines = content.split("\n")
    current_domain: str | None = None
    current_block_lines: list[str] = []
    brace_depth = 0

    for line in lines:
        stripped = line.strip()

        if brace_depth == 0 and stripped and not stripped.startswith("#") and "{" in stripped:
            current_domain = stripped.split("{")[0].strip()
            current_block_lines = [line]
            brace_depth = stripped.count("{") - stripped.count("}")
        elif brace_depth > 0:
            current_block_lines.append(line)
            brace_depth += stripped.count("{") - stripped.count("}")

            if brace_depth <= 0:
                raw = "\n".join(current_block_lines)

                # Extract upstream services as {address, port} objects
                upstreams: list[dict[str, Any]] = []
                for bl in current_block_lines:
                    bl_stripped = bl.strip()
                    if bl_stripped.startswith("reverse_proxy"):
                        parts = bl_stripped.split()
                        for part in parts[1:]:
                            if not part.startswith("{") and not part.startswith("#"):
                                if ":" in part:
                                    addr, port_str = part.rsplit(":", 1)
                                    try:
                                        upstreams.append({"address": addr, "port": int(port_str)})
                                    except ValueError:
                                        upstreams.append({"address": part, "port": 80})
                                else:
                                    upstreams.append({"address": part, "port": 80})

                tls_mode = _detect_tls_mode(raw)
                has_tls = tls_mode != "off"

                blocks.append({
                    "domain": current_domain or "",
                    "upstreams": upstreams,
                    "tls_enabled": has_tls,
                    "tls_auto": tls_mode == "auto",
                    "tls_mode": tls_mode,
                    "raw_config": raw,
                })

                current_domain = None
                current_block_lines = []
                brace_depth = 0

    return blocks


def parse_caddyfile() -> list[dict[str, Any]]:
    """Parse the Caddyfile into user-managed domain blocks only."""
    return [
        b for b in _parse_caddyfile_raw()
        if b["domain"] not in _INFRASTRUCTURE_DOMAINS
    ]


# ---------------------------------------------------------------------------
# On-demand TLS helpers
# ---------------------------------------------------------------------------

def has_on_demand_tls() -> bool:
    """Check whether on-demand TLS is currently configured."""
    domains = {b["domain"] for b in _parse_caddyfile_raw()}
    return "" in domains and "https://" in domains


async def enable_on_demand_tls() -> None:
    """Enable on-demand TLS by merging the directive into the global block.

    If a global block (bare ``{ ... }``) already exists (e.g. from an email
    directive), the on_demand_tls directive is appended inside it. Otherwise
    a new global block is created. A catch-all ``https://`` block is added
    at the end of the file.
    """
    if has_on_demand_tls():
        raise ValueError("On-demand TLS is already enabled")

    existing = ""
    if CADDYFILE_PATH.exists():
        existing = CADDYFILE_PATH.read_text().strip()

    CADDYFILE_PATH.parent.mkdir(parents=True, exist_ok=True)

    # Check for an existing global block (starts with { on its own line)
    global_match = re.match(r"^(\{[^}]*\})", existing, re.DOTALL)
    if global_match:
        # Merge the on_demand_tls directive into the existing global block
        old_global = global_match.group(1)
        # Insert the directive before the closing brace
        closing_idx = old_global.rfind("}")
        new_global = old_global[:closing_idx].rstrip() + "\n" + ON_DEMAND_TLS_DIRECTIVE + "\n}"
        content = existing.replace(old_global, new_global, 1)
    else:
        # No global block yet - create one
        new_global = "{\n" + ON_DEMAND_TLS_DIRECTIVE + "\n}"
        content = new_global + "\n\n" + existing

    content = content.strip()
    catchall = _build_catchall_block()
    if catchall:
        content += "\n\n" + catchall
    CADDYFILE_PATH.write_text(content + "\n")
    logger.info(
        "Enabled on-demand TLS (ask -> sentinel-api, catchall=%s)",
        "yes" if catchall else "none",
    )


async def disable_on_demand_tls() -> None:
    """Remove on-demand TLS directive from global block and the catch-all."""
    if not has_on_demand_tls():
        raise ValueError("On-demand TLS is not currently enabled")

    content = CADDYFILE_PATH.read_text()

    # Remove the on_demand_tls directive from the global block
    content = re.sub(
        r"\n?\s*on_demand_tls\s*\{[^}]*\}\n?",
        "\n",
        content,
    )

    # Remove the catch-all https:// block
    raw_blocks = _parse_caddyfile_raw()
    for block in raw_blocks:
        if block["domain"] == "https://":
            content = content.replace(block["raw_config"], "")

    # If the global block is now empty (only whitespace/newlines between braces), remove it
    content = re.sub(r"^\{\s*\}\n*", "", content.strip(), count=1)

    content = re.sub(r"\n{3,}", "\n\n", content).strip() + "\n"
    CADDYFILE_PATH.write_text(content)
    logger.info("Disabled on-demand TLS")


# ---------------------------------------------------------------------------
# Block generation
# ---------------------------------------------------------------------------

def _build_block(
    domain: str,
    proxy_targets: list[dict[str, str]],
    tls_mode: str = "auto",
) -> str:
    """Build a Caddyfile block string from a domain and proxy targets."""
    lines = [f"{domain} {{"]

    # TLS configuration
    if tls_mode == "on_demand":
        lines.append("    tls {")
        lines.append("        on_demand")
        lines.append("    }")
    elif tls_mode == "cloudflare_dns":
        lines.append("    tls {")
        lines.append("        dns cloudflare {$CLOUDFLARE_API_TOKEN}")
        lines.append("    }")
    elif tls_mode == "off":
        lines.append("    tls off")

    # Security headers
    lines.append("    header {")
    lines.append('        X-XSS-Protection "1; mode=block"')
    lines.append('        Permissions-Policy "camera=(), microphone=(), geolocation=()"')
    lines.append("        -Server")
    lines.append("    }")

    # Proxy targets
    for target in proxy_targets:
        path_prefix = target.get("path_prefix", "/")
        upstream = target["upstream"]

        if path_prefix and path_prefix != "/":
            lines.append(f"    handle {path_prefix}* {{")
            lines.append(f"        reverse_proxy {upstream}")
            lines.append("    }")
        else:
            lines.append(f"    handle {{")
            lines.append(f"        reverse_proxy {upstream}")
            lines.append("    }")

    lines.append("}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Modification
# ---------------------------------------------------------------------------

async def add_domain(
    domain: str,
    proxy_targets: list[dict[str, str]],
    tls_mode: str = "auto",
) -> None:
    """Append a new domain block to the Caddyfile."""
    existing = parse_caddyfile()
    for block in existing:
        if block["domain"].lower() == domain.lower():
            raise ValueError(f"Domain '{domain}' already exists in Caddyfile")

    block_text = _build_block(domain, proxy_targets, tls_mode=tls_mode)

    CADDYFILE_PATH.parent.mkdir(parents=True, exist_ok=True)

    if has_on_demand_tls():
        # Insert before the catch-all block so explicit domains take priority
        content = CADDYFILE_PATH.read_text()
        raw_blocks = _parse_caddyfile_raw()
        catchall_raw = next(
            b["raw_config"] for b in raw_blocks if b["domain"] == "https://"
        )
        content = content.replace(catchall_raw, f"{block_text}\n\n{catchall_raw}")
        CADDYFILE_PATH.write_text(content)
    else:
        with open(CADDYFILE_PATH, "a") as f:
            f.write(f"\n\n{block_text}\n")

    logger.info("Added Caddy domain block for %s (tls=%s)", domain, tls_mode)


async def update_domain(
    domain: str,
    proxy_targets: list[dict[str, str]],
    tls_mode: str = "auto",
) -> None:
    """Replace an existing domain block in the Caddyfile."""
    if not CADDYFILE_PATH.exists():
        raise ValueError("Caddyfile not found")

    content = CADDYFILE_PATH.read_text()

    blocks = parse_caddyfile()
    found = False
    for block in blocks:
        if block["domain"].lower() == domain.lower():
            old_block = block["raw_config"]
            new_block = _build_block(domain, proxy_targets, tls_mode=tls_mode)
            content = content.replace(old_block, new_block)
            found = True
            break

    if not found:
        raise ValueError(f"Domain '{domain}' not found in Caddyfile")

    CADDYFILE_PATH.write_text(content)
    logger.info("Updated Caddy domain block for %s (tls=%s)", domain, tls_mode)


async def remove_domain(domain: str) -> None:
    """Remove a domain block from the Caddyfile."""
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

    content = re.sub(r"\n{3,}", "\n\n", content).strip() + "\n"
    CADDYFILE_PATH.write_text(content)
    logger.info("Removed Caddy domain block for %s", domain)


async def reload_caddy() -> dict[str, Any]:
    """Reload the Caddy configuration inside the caddy-proxy container.

    Uses the Docker SDK (via socket) since the docker CLI binary may not
    be installed inside the sentinel-api container.
    """
    try:
        import docker
        client = docker.DockerClient.from_env()
        try:
            container_name = get_effective("caddy_container") or "caddy-proxy"
            container = client.containers.get(container_name)
            result = container.exec_run(
                ["caddy", "reload", "--config", "/etc/caddy/Caddyfile", "--adapter", "caddyfile"],
            )
            output = result.output.decode("utf-8", errors="replace") if result.output else ""

            if result.exit_code == 0:
                logger.info("Caddy reloaded successfully")
                return {"success": True, "message": "Caddy reloaded successfully"}
            else:
                logger.error("Caddy reload failed (rc=%d): %s", result.exit_code, output)
                return {"success": False, "message": f"Caddy reload failed: {output}"}
        finally:
            client.close()
    except Exception as exc:
        logger.error("Failed to reload Caddy: %s", exc)
        return {"success": False, "message": str(exc)}
