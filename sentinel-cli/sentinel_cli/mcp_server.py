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


def main():
    """Entry point for the sentinel-mcp command."""
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
