"""Sentinel CLI - manage deployments, services, and projects from the terminal."""
from __future__ import annotations

import asyncio
import re
import time
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from sentinel_cli.auth import get_valid_token, interactive_login
from sentinel_cli.client import SentinelClient
from sentinel_cli.config import get_base_url

app = typer.Typer(
    name="sentinel",
    help="Sentinel DevOps CLI - deploy, monitor, and manage services.",
    no_args_is_help=True,
)
console = Console()


def _run(coro):
    """Run an async coroutine from a sync Typer command."""
    return asyncio.run(coro)


def _get_client(url: str | None) -> SentinelClient:
    """Build an authenticated SentinelClient or exit with an error."""
    base_url = get_base_url(url)
    token = get_valid_token(base_url)
    if token is None:
        console.print("[red]Not logged in or session expired. Run:[/red] sentinel login")
        raise typer.Exit(1)
    return SentinelClient(base_url, token)


def _parse_since(value: str) -> int:
    """Parse a human duration ('30s', '5m', '1h', '2d') to a Unix timestamp."""
    m = re.fullmatch(r"(\d+)\s*([smhd])", value.strip().lower())
    if not m:
        console.print(f"[red]Invalid duration:[/red] '{value}'. Use e.g. 30s, 5m, 1h, 2d")
        raise typer.Exit(1)
    amount, unit = int(m.group(1)), m.group(2)
    multipliers = {"s": 1, "m": 60, "h": 3600, "d": 86400}
    return int(time.time()) - amount * multipliers[unit]


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

@app.command()
def login(url: Optional[str] = typer.Option(None, "--url", help="Sentinel base URL")) -> None:
    """Log in to Sentinel via OTP."""
    interactive_login(get_base_url(url))


@app.command()
def projects(url: Optional[str] = typer.Option(None, "--url", hidden=True)) -> None:
    """List all registered projects."""
    async def _run_it():
        async with _get_client(url) as c:
            items = await c.list_projects()
            table = Table(title="Projects")
            table.add_column("Name", style="bold")
            table.add_column("Type")
            table.add_column("Domain")
            table.add_column("Status")
            for p in items:
                table.add_row(
                    p["name"],
                    p.get("project_type", ""),
                    p.get("domain") or "-",
                    p.get("status", ""),
                )
            console.print(table)
    _run(_run_it())


@app.command()
def services(url: Optional[str] = typer.Option(None, "--url", hidden=True)) -> None:
    """List all Docker containers."""
    async def _run_it():
        async with _get_client(url) as c:
            items = await c.list_services()
            table = Table(title="Services")
            table.add_column("Name", style="bold")
            table.add_column("Status")
            table.add_column("Image")
            for s in items:
                table.add_row(
                    s.get("name", ""),
                    s.get("status", ""),
                    s.get("image", ""),
                )
            console.print(table)
    _run(_run_it())


@app.command()
def deployments(
    project: Optional[str] = typer.Option(None, "--project", "-p", help="Filter by project name"),
    url: Optional[str] = typer.Option(None, "--url", hidden=True),
) -> None:
    """List recent deployments."""
    async def _run_it():
        async with _get_client(url) as c:
            pid = None
            if project:
                pid = await c.get_project_id_by_name(project)
            data = await c.list_deployments(project_id=pid)
            items = data.get("items", [])
            table = Table(title="Deployments")
            table.add_column("ID", max_width=8)
            table.add_column("Project")
            table.add_column("Status")
            table.add_column("Trigger")
            table.add_column("Tag", max_width=12)
            table.add_column("Started")
            table.add_column("Duration")
            for d in items:
                tag = (d.get("image_tag") or "")[:12]
                dur = f"{d['duration_seconds']}s" if d.get("duration_seconds") else "-"
                table.add_row(
                    d["id"][:8],
                    d.get("project_name", ""),
                    d.get("status", ""),
                    d.get("trigger", ""),
                    tag,
                    d.get("started_at", ""),
                    dur,
                )
            console.print(table)
    _run(_run_it())


@app.command()
def deploy(
    project: str = typer.Argument(help="Project name (slug)"),
    tag: Optional[str] = typer.Option(None, "--tag", "-t", help="Image tag to deploy"),
    url: Optional[str] = typer.Option(None, "--url", hidden=True),
) -> None:
    """Trigger a deployment for a project."""
    async def _run_it():
        async with _get_client(url) as c:
            pid = await c.get_project_id_by_name(project)
            console.print(f"[dim]Deploying {project}...[/dim]")
            result = await c.deploy(pid, image_tag=tag)
            status = result.get("status", "unknown")
            color = "green" if status == "success" else "yellow" if status == "in_progress" else "red"
            panel = Panel(
                f"Status: [{color}]{status}[/{color}]\n"
                f"Trigger: {result.get('trigger', '-')}\n"
                f"Tag: {result.get('image_tag', '-')}\n"
                f"Duration: {result.get('duration_seconds', '-')}s",
                title=f"Deploy - {project}",
            )
            console.print(panel)
    _run(_run_it())


@app.command()
def rollback(
    project: str = typer.Argument(help="Project name (slug)"),
    deployment_id: str = typer.Argument(help="Deployment ID to roll back to"),
    url: Optional[str] = typer.Option(None, "--url", hidden=True),
) -> None:
    """Roll back a project to a previous deployment."""
    async def _run_it():
        async with _get_client(url) as c:
            pid = await c.get_project_id_by_name(project)
            console.print(f"[dim]Rolling back {project} to {deployment_id[:8]}...[/dim]")
            result = await c.rollback(pid, deployment_id)
            status = result.get("status", "unknown")
            color = "green" if status == "success" else "red"
            console.print(f"[{color}]Rollback {status}[/{color}]")
    _run(_run_it())


@app.command()
def logs(
    container: str = typer.Argument(help="Container name"),
    tail: int = typer.Option(100, "--tail", "-n", help="Number of lines"),
    since: Optional[str] = typer.Option(None, "--since", "-s", help="Duration (e.g. 30s, 5m, 1h, 2d)"),
    url: Optional[str] = typer.Option(None, "--url", hidden=True),
) -> None:
    """View container logs."""
    async def _run_it():
        since_ts = _parse_since(since) if since else None
        async with _get_client(url) as c:
            data = await c.get_service_logs(container, tail=tail, since=since_ts)
            entries = data.get("logs", [])
            if not entries:
                console.print("[dim]No logs found.[/dim]")
                return
            for entry in entries:
                ts = entry.get("timestamp", "")
                msg = entry.get("message", "")
                stream = entry.get("stream", "stdout")
                if stream == "stderr":
                    console.print(f"[dim]{ts}[/dim] [red]{msg}[/red]")
                else:
                    console.print(f"[dim]{ts}[/dim] {msg}")
    _run(_run_it())


@app.command()
def status(url: Optional[str] = typer.Option(None, "--url", hidden=True)) -> None:
    """Show each project with its latest deployment."""
    async def _run_it():
        async with _get_client(url) as c:
            items = await c.list_projects()
            table = Table(title="Project Status")
            table.add_column("Project", style="bold")
            table.add_column("Domain")
            table.add_column("Last Deploy")
            table.add_column("Status")
            table.add_column("Tag", max_width=12)
            table.add_column("By")
            for p in items:
                deps = await c.list_deployments(project_id=p["id"], page_size=1)
                dep_items = deps.get("items", [])
                if dep_items:
                    d = dep_items[0]
                    table.add_row(
                        p["name"],
                        p.get("domain") or "-",
                        d.get("started_at", "-"),
                        d.get("status", "-"),
                        (d.get("image_tag") or "")[:12],
                        d.get("triggered_by") or "-",
                    )
                else:
                    table.add_row(p["name"], p.get("domain") or "-", "-", "-", "-", "-")
            console.print(table)
    _run(_run_it())
