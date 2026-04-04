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

def parse_caddyfile() -> list[dict[str, Any]]:
    """Parse the Caddyfile into a list of domain block dicts."""
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
    if tls_mode == "cloudflare_dns":
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
            container = client.containers.get("caddy-proxy")
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
