"""Sentinel MCP server - exposes deployment and monitoring tools for AI agents."""
from __future__ import annotations

import asyncio
import logging

from mcp.server.fastmcp import FastMCP

from sentinel_cli.auth import get_valid_token
from sentinel_cli.client import SentinelClient
from sentinel_cli.config import get_base_url

logger = logging.getLogger(__name__)

mcp = FastMCP(
    "sentinel",
    instructions="Sentinel DevOps portal - manage deployments, services, and projects on the Payd Labs server",
)


async def _get_client() -> SentinelClient | str:
    """Return an authenticated client, or an error message string."""
    base_url = get_base_url()
    token = get_valid_token(base_url)
    if token is None:
        return "Not authenticated. Ask the user to run `sentinel login` in their terminal first."
    return SentinelClient(base_url, token)


def _fmt_projects(items: list[dict]) -> str:
    lines = [f"{'Name':<25} {'Type':<10} {'Domain':<30} {'Status'}"]
    lines.append("-" * 75)
    for p in items:
        lines.append(
            f"{p['name']:<25} {p.get('project_type', ''):<10} "
            f"{(p.get('domain') or '-'):<30} {p.get('status', '')}"
        )
    return "\n".join(lines)


def _fmt_deployments(items: list[dict]) -> str:
    if not items:
        return "No deployments found."
    lines = [f"{'ID':<10} {'Project':<22} {'Status':<10} {'Trigger':<10} {'Tag':<14} {'Started'}"]
    lines.append("-" * 90)
    for d in items:
        lines.append(
            f"{d['id'][:8]:<10} {d.get('project_name', ''):<22} "
            f"{d.get('status', ''):<10} {d.get('trigger', ''):<10} "
            f"{(d.get('image_tag') or '')[:12]:<14} {d.get('started_at', '')}"
        )
    return "\n".join(lines)


def _fmt_services(items: list[dict]) -> str:
    lines = [f"{'Name':<30} {'Status':<15} {'Image'}"]
    lines.append("-" * 80)
    for s in items:
        lines.append(
            f"{s.get('name', ''):<30} {s.get('status', ''):<15} {s.get('image', '')}"
        )
    return "\n".join(lines)


@mcp.tool()
async def sentinel_list_projects() -> str:
    """List all projects registered in Sentinel with their type, domain, and status."""
    client = await _get_client()
    if isinstance(client, str):
        return client
    async with client:
        items = await client.list_projects()
        return _fmt_projects(items)


@mcp.tool()
async def sentinel_list_services() -> str:
    """List all Docker containers on the server with their status and image."""
    client = await _get_client()
    if isinstance(client, str):
        return client
    async with client:
        items = await client.list_services()
        return _fmt_services(items)


@mcp.tool()
async def sentinel_list_deployments(project: str | None = None) -> str:
    """List recent deployments. Optionally filter by project name (slug)."""
    client = await _get_client()
    if isinstance(client, str):
        return client
    async with client:
        pid = None
        if project:
            try:
                pid = await client.get_project_id_by_name(project)
            except ValueError as e:
                return str(e)
        data = await client.list_deployments(project_id=pid)
        return _fmt_deployments(data.get("items", []))


@mcp.tool()
async def sentinel_deploy(project: str, image_tag: str | None = None) -> str:
    """Trigger a deployment for a project by name. Optionally specify an image tag."""
    client = await _get_client()
    if isinstance(client, str):
        return client
    async with client:
        try:
            pid = await client.get_project_id_by_name(project)
        except ValueError as e:
            return str(e)
        try:
            result = await client.deploy(pid, image_tag=image_tag)
            status = result.get("status", "unknown")
            return (
                f"Deploy triggered for {project}\n"
                f"Status: {status}\n"
                f"Trigger: {result.get('trigger', '-')}\n"
                f"Tag: {result.get('image_tag', '-')}\n"
                f"Duration: {result.get('duration_seconds', '-')}s"
            )
        except Exception as e:
            return f"Deploy failed: {e}"


@mcp.tool()
async def sentinel_rollback(project: str, deployment_id: str) -> str:
    """Roll back a project to a previous deployment by project name and deployment ID."""
    client = await _get_client()
    if isinstance(client, str):
        return client
    async with client:
        try:
            pid = await client.get_project_id_by_name(project)
        except ValueError as e:
            return str(e)
        try:
            result = await client.rollback(pid, deployment_id)
            return f"Rollback {result.get('status', 'unknown')} for {project}"
        except Exception as e:
            return f"Rollback failed: {e}"


@mcp.tool()
async def sentinel_get_logs(
    container: str,
    tail: int = 100,
    since_minutes: int | None = None,
) -> str:
    """Get container logs. tail controls line count, since_minutes filters by recency."""
    import time

    client = await _get_client()
    if isinstance(client, str):
        return client
    async with client:
        since_ts = int(time.time()) - since_minutes * 60 if since_minutes else None
        try:
            data = await client.get_service_logs(container, tail=tail, since=since_ts)
        except Exception as e:
            return f"Failed to get logs: {e}"
        entries = data.get("logs", [])
        if not entries:
            return f"No logs found for {container}."
        lines = []
        for entry in entries:
            ts = entry.get("timestamp", "")
            msg = entry.get("message", "")
            stream = entry.get("stream", "stdout")
            prefix = "[stderr] " if stream == "stderr" else ""
            lines.append(f"{ts} {prefix}{msg}")
        return "\n".join(lines)


@mcp.tool()
async def sentinel_project_status(project: str) -> str:
    """Get a project's details and its most recent deployment."""
    client = await _get_client()
    if isinstance(client, str):
        return client
    async with client:
        try:
            pid = await client.get_project_id_by_name(project)
        except ValueError as e:
            return str(e)

        projects = await client.list_projects()
        proj = next((p for p in projects if p["id"] == pid), None)
        if not proj:
            return f"Project {project} not found."

        deps = await client.list_deployments(project_id=pid, page_size=1)
        dep_items = deps.get("items", [])

        lines = [
            f"Project: {proj['name']} ({proj.get('display_name', '')})",
            f"Type: {proj.get('project_type', '-')}",
            f"Domain: {proj.get('domain') or '-'}",
            f"Status: {proj.get('status', '-')}",
            f"GitHub: {proj.get('github_repo') or '-'}",
            f"Health: {proj.get('health_endpoint') or '-'}",
        ]

        if dep_items:
            d = dep_items[0]
            lines.append("")
            lines.append("Latest deployment:")
            lines.append(f"  ID: {d['id'][:8]}")
            lines.append(f"  Status: {d.get('status', '-')}")
            lines.append(f"  Trigger: {d.get('trigger', '-')}")
            lines.append(f"  Tag: {d.get('image_tag', '-')}")
            lines.append(f"  Started: {d.get('started_at', '-')}")
            lines.append(f"  Duration: {d.get('duration_seconds', '-')}s")
            lines.append(f"  By: {d.get('triggered_by', '-')}")
        else:
            lines.append("\nNo deployments yet.")

        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Project management tools
# ---------------------------------------------------------------------------

@mcp.tool()
async def sentinel_create_project(
    name: str,
    project_type: str = "fastapi",
    display_name: str | None = None,
    domain: str | None = None,
    github_repo: str | None = None,
    ghcr_image: str | None = None,
    description: str | None = None,
    compose_path: str | None = None,
    compose_file: str | None = None,
    database_name: str | None = None,
    health_endpoint: str = "/health",
) -> str:
    """Create a new Sentinel project record.

    project_type: fastapi | vue | blended | nuxt | laravel | custom.
    Returns the new project's id and auto-generated webhook_secret.
    """
    client = await _get_client()
    if isinstance(client, str):
        return client
    async with client:
        payload: dict = {
            "name": name,
            "display_name": display_name or name.replace("-", " ").title(),
            "project_type": project_type,
            "health_endpoint": health_endpoint,
        }
        for k, v in (
            ("description", description),
            ("domain", domain),
            ("github_repo", github_repo),
            ("ghcr_image", ghcr_image),
            ("compose_path", compose_path),
            ("compose_file", compose_file),
            ("database_name", database_name),
        ):
            if v:
                payload[k] = v
        try:
            p = await client.create_project(payload)
        except Exception as e:
            return f"Create failed: {e}"
        return (
            f"Created project {p['name']} (id={p['id']})\n"
            f"webhook_secret: {p.get('webhook_secret', '')}\n"
            f"Add SENTINEL_WEBHOOK_SECRET=<webhook_secret> to the GitHub repo secrets."
        )


@mcp.tool()
async def sentinel_update_project(
    project: str,
    display_name: str | None = None,
    project_type: str | None = None,
    domain: str | None = None,
    github_repo: str | None = None,
    ghcr_image: str | None = None,
    description: str | None = None,
    compose_path: str | None = None,
    compose_file: str | None = None,
    health_endpoint: str | None = None,
    database_name: str | None = None,
    supports_custom_domains: bool | None = None,
    custom_domain_upstream: str | None = None,
) -> str:
    """Update project fields. Only non-None values are sent."""
    client = await _get_client()
    if isinstance(client, str):
        return client
    async with client:
        try:
            pid = await client.get_project_id_by_name(project)
        except ValueError as e:
            return str(e)
        patch: dict = {}
        for v, field in (
            (display_name, "display_name"),
            (project_type, "project_type"),
            (domain, "domain"),
            (github_repo, "github_repo"),
            (ghcr_image, "ghcr_image"),
            (description, "description"),
            (compose_path, "compose_path"),
            (compose_file, "compose_file"),
            (health_endpoint, "health_endpoint"),
            (database_name, "database_name"),
            (custom_domain_upstream, "custom_domain_upstream"),
        ):
            if v is not None:
                patch[field] = v
        if supports_custom_domains is not None:
            patch["supports_custom_domains"] = supports_custom_domains
        if not patch:
            return "No fields to update. Specify at least one parameter."
        try:
            await client.update_project(pid, patch)
        except Exception as e:
            return f"Update failed: {e}"
        return f"Updated {project} ({len(patch)} fields: {', '.join(patch.keys())})"


@mcp.tool()
async def sentinel_delete_project(project: str) -> str:
    """Delete a project record from Sentinel. Does NOT remove server files or containers."""
    client = await _get_client()
    if isinstance(client, str):
        return client
    async with client:
        try:
            pid = await client.get_project_id_by_name(project)
            await client.delete_project(pid)
            return f"Deleted project {project}"
        except Exception as e:
            return f"Delete failed: {e}"


@mcp.tool()
async def sentinel_scan_projects() -> str:
    """Scan /apps on the server and auto-register any new projects found."""
    client = await _get_client()
    if isinstance(client, str):
        return client
    async with client:
        try:
            result = await client.scan_projects()
        except Exception as e:
            return f"Scan failed: {e}"
        count = result.get("total", 0)
        names = [p.get("name", "") for p in result.get("discovered", [])]
        return f"Scanned /apps. Discovered {count} projects: {', '.join(names) if names else 'none'}"


@mcp.tool()
async def sentinel_provision_project(project: str, create_database: bool = False) -> str:
    """Provision server files (compose, .env, Caddy route) for a project. Optionally create its DB."""
    client = await _get_client()
    if isinstance(client, str):
        return client
    async with client:
        try:
            pid = await client.get_project_id_by_name(project)
            result = await client.provision_project(pid, create_database=create_database)
        except Exception as e:
            return f"Provision failed: {e}"
        lines = [f"Provisioned {project}:"]
        for step in result.get("steps", []):
            lines.append(f"  [{step.get('status', '?')}] step {step.get('step', '')}: {step.get('name', '')}")
        return "\n".join(lines)


@mcp.tool()
async def sentinel_generate_service_key(project: str) -> str:
    """Generate a new service API key for the project (for custom-domains API auth)."""
    client = await _get_client()
    if isinstance(client, str):
        return client
    async with client:
        try:
            pid = await client.get_project_id_by_name(project)
            result = await client.generate_service_key(pid)
        except Exception as e:
            return f"Failed: {e}"
        return f"Service key for {project}: {result.get('service_api_key', '')}"


# ---------------------------------------------------------------------------
# Env var tools
# ---------------------------------------------------------------------------

@mcp.tool()
async def sentinel_list_env(project: str, reveal: bool = False) -> str:
    """List env vars for a project. Values are masked unless reveal=True."""
    client = await _get_client()
    if isinstance(client, str):
        return client
    async with client:
        try:
            pid = await client.get_project_id_by_name(project)
            vars_ = await client.get_env(pid, reveal=reveal)
        except Exception as e:
            return f"Failed: {e}"
        if not vars_:
            return f"No env vars set for {project}."
        lines = [f"Env vars for {project} ({len(vars_)}):"]
        for v in vars_:
            lines.append(f"  {v['key']}={v['value']}")
        return "\n".join(lines)


@mcp.tool()
async def sentinel_set_env(project: str, variables: dict[str, str]) -> str:
    """Set one or more env vars. Merges with existing vars (does not clobber)."""
    client = await _get_client()
    if isinstance(client, str):
        return client
    async with client:
        try:
            pid = await client.get_project_id_by_name(project)
            existing = await client.get_env(pid, reveal=True)
            merged = {v["key"]: v["value"] for v in existing}
            merged.update(variables)
            result = await client.set_env(pid, merged)
        except Exception as e:
            return f"Failed: {e}"
        return f"{result.get('detail', f'Set {len(variables)} env vars')}"


@mcp.tool()
async def sentinel_unset_env(project: str, keys: list[str]) -> str:
    """Remove one or more env vars."""
    client = await _get_client()
    if isinstance(client, str):
        return client
    async with client:
        try:
            pid = await client.get_project_id_by_name(project)
            existing = await client.get_env(pid, reveal=True)
            merged = {v["key"]: v["value"] for v in existing if v["key"] not in keys}
            await client.set_env(pid, merged)
        except Exception as e:
            return f"Failed: {e}"
        return f"Removed {len(keys)} env var(s) from {project}: {', '.join(keys)}"


# ---------------------------------------------------------------------------
# Database tools
# ---------------------------------------------------------------------------

@mcp.tool()
async def sentinel_list_databases() -> str:
    """List databases on the managed PostgreSQL."""
    client = await _get_client()
    if isinstance(client, str):
        return client
    async with client:
        try:
            dbs = await client.list_databases()
        except Exception as e:
            return f"Failed: {e}"
        if not dbs:
            return "No databases found (or PostgreSQL admin not configured)."
        lines = [f"{'Name':<25} {'Owner':<20} {'Size (MB)':>10} {'Tables':>8}"]
        for d in dbs:
            lines.append(
                f"{d.get('name', ''):<25} {d.get('owner', ''):<20} "
                f"{d.get('size_mb', 0):>10} {d.get('tables_count', 0):>8}"
            )
        return "\n".join(lines)


@mcp.tool()
async def sentinel_create_database(name: str, password: str | None = None) -> str:
    """Create a new PostgreSQL database with a dedicated user."""
    client = await _get_client()
    if isinstance(client, str):
        return client
    async with client:
        try:
            result = await client.create_database(name, password=password)
        except Exception as e:
            return f"Failed: {e}"
        parts = [f"Created database {name} (owner={result.get('user', name)})"]
        if result.get("password"):
            parts.append(f"password: {result['password']}")
        return ". ".join(parts)


@mcp.tool()
async def sentinel_list_tables(database: str) -> str:
    """List tables in a database."""
    client = await _get_client()
    if isinstance(client, str):
        return client
    async with client:
        try:
            tables = await client.list_tables(database)
        except Exception as e:
            return f"Failed: {e}"
        if not tables:
            return f"No tables in {database}."
        lines = [f"Tables in {database}:"]
        for t in tables:
            lines.append(
                f"  {t.get('schema', '-')}.{t.get('name', '')} - "
                f"{t.get('row_count', 0)} rows, {t.get('size_kb', 0)} KB"
            )
        return "\n".join(lines)


@mcp.tool()
async def sentinel_db_query(database: str, sql: str) -> str:
    """Run a read-only SELECT query against a database."""
    client = await _get_client()
    if isinstance(client, str):
        return client
    async with client:
        try:
            result = await client.query(database, sql)
        except Exception as e:
            return f"Query failed: {e}"
        rows = result.get("rows", [])
        cols = result.get("columns", [])
        if not rows:
            return "0 rows"
        # Compact text representation
        lines = [" | ".join(cols)]
        lines.append("-+-".join("-" * len(c) for c in cols))
        for r in rows[:50]:
            lines.append(" | ".join(str(r.get(c, "")) for c in cols))
        lines.append(f"\n{result.get('row_count', len(rows))} rows in {result.get('execution_time_ms', 0)}ms")
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Domain + custom domain tools
# ---------------------------------------------------------------------------

@mcp.tool()
async def sentinel_list_domains() -> str:
    """List Caddy domain blocks."""
    client = await _get_client()
    if isinstance(client, str):
        return client
    async with client:
        try:
            domains = await client.list_domains()
        except Exception as e:
            return f"Failed: {e}"
        if not domains:
            return "No domains registered in Caddy."
        lines = []
        for d in domains:
            upstreams = ", ".join(f"{u['address']}:{u['port']}" for u in d.get("upstreams", []))
            lines.append(f"{d.get('domain', ''):<30} -> {upstreams}  (tls={d.get('tls_mode', 'auto')})")
        return "\n".join(lines)


@mcp.tool()
async def sentinel_add_domain(
    domain: str,
    upstream: str,
    tls_mode: str = "auto",
) -> str:
    """Add a domain to Caddy. upstream is container:port, tls_mode is auto|cloudflare_dns|on_demand|off."""
    client = await _get_client()
    if isinstance(client, str):
        return client
    async with client:
        try:
            await client.add_domain(domain, upstream, tls_mode=tls_mode)
        except Exception as e:
            return f"Failed: {e}"
        return f"Added {domain} -> {upstream} (tls={tls_mode}). Caddy reloads automatically."


@mcp.tool()
async def sentinel_remove_domain(domain: str) -> str:
    """Remove a domain from Caddy."""
    client = await _get_client()
    if isinstance(client, str):
        return client
    async with client:
        try:
            await client.remove_domain(domain)
        except Exception as e:
            return f"Failed: {e}"
        return f"Removed {domain}"


@mcp.tool()
async def sentinel_reload_caddy() -> str:
    """Reload Caddy configuration."""
    client = await _get_client()
    if isinstance(client, str):
        return client
    async with client:
        try:
            result = await client.reload_caddy()
        except Exception as e:
            return f"Failed: {e}"
        return f"Caddy reload: {result.get('message', 'unknown')}"


@mcp.tool()
async def sentinel_list_custom_domains(project: str | None = None) -> str:
    """List custom domains across all projects. Optionally filter by project name."""
    client = await _get_client()
    if isinstance(client, str):
        return client
    async with client:
        pid = None
        if project:
            try:
                pid = await client.get_project_id_by_name(project)
            except ValueError as e:
                return str(e)
        try:
            data = await client.list_custom_domains(project_id=pid)
        except Exception as e:
            return f"Failed: {e}"
        items = data.get("items", [])
        if not items:
            return "No custom domains."
        lines = []
        for d in items:
            lines.append(
                f"{d.get('domain', ''):<30} project={d.get('project_name', ''):<25} status={d.get('status', '')}"
            )
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Service control tools
# ---------------------------------------------------------------------------

@mcp.tool()
async def sentinel_restart_service(name: str) -> str:
    """Restart a container."""
    client = await _get_client()
    if isinstance(client, str):
        return client
    async with client:
        try:
            await client.restart_service(name)
            return f"Restarted {name}"
        except Exception as e:
            return f"Failed: {e}"


@mcp.tool()
async def sentinel_stop_service(name: str) -> str:
    """Stop a running container."""
    client = await _get_client()
    if isinstance(client, str):
        return client
    async with client:
        try:
            await client.stop_service(name)
            return f"Stopped {name}"
        except Exception as e:
            return f"Failed: {e}"


@mcp.tool()
async def sentinel_start_service(name: str) -> str:
    """Start a stopped container."""
    client = await _get_client()
    if isinstance(client, str):
        return client
    async with client:
        try:
            await client.start_service(name)
            return f"Started {name}"
        except Exception as e:
            return f"Failed: {e}"


# ---------------------------------------------------------------------------
# Audit
# ---------------------------------------------------------------------------

@mcp.tool()
async def sentinel_audit_log(limit: int = 30, action: str | None = None) -> str:
    """View recent audit log entries. Optionally filter by action (e.g. 'project.create')."""
    client = await _get_client()
    if isinstance(client, str):
        return client
    async with client:
        try:
            result = await client.audit_log(page=1, per_page=limit, action=action)
        except Exception as e:
            return f"Failed: {e}"
        items = result.get("items", [])
        if not items:
            return "No audit entries match."
        lines = []
        for i in items:
            lines.append(
                f"{i.get('timestamp', '')[:19]}  "
                f"user={i.get('user') or '-':<15} "
                f"{i.get('action', ''):<30} "
                f"target={i.get('target') or '-'}"
            )
        return "\n".join(lines)


def main():
    """Entry point for the sentinel-mcp command."""
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
