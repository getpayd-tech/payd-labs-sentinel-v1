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


# ---------------------------------------------------------------------------
# Security sub-app (fail2ban + auth log)
# ---------------------------------------------------------------------------

security_app = typer.Typer(help="Manage fail2ban bans and inspect SSH auth activity.")
app.add_typer(security_app, name="security")


@security_app.command("banned")
def security_banned(
    jail: str = typer.Option("sshd", "--jail", help="Jail name"),
    url: Optional[str] = typer.Option(None, "--url", hidden=True),
) -> None:
    """List currently banned IPs in a jail."""
    async def _run_it():
        async with _get_client(url) as c:
            status = await c.jail_status(jail)
            ips = status.get("banned_ips", [])
            table = Table(title=f"Banned IPs - {jail}")
            table.add_column("IP", style="bold")
            for ip in ips:
                table.add_row(ip)
            console.print(table)
            console.print(
                f"[dim]{status.get('currently_banned', 0)} banned, "
                f"{status.get('currently_failed', 0)} currently failing, "
                f"{status.get('total_banned', 0)} total bans lifetime[/dim]"
            )
    _run(_run_it())


@security_app.command("ban")
def security_ban(
    ip: str = typer.Argument(help="IP address to ban"),
    jail: str = typer.Option("sshd", "--jail", help="Jail name"),
    url: Optional[str] = typer.Option(None, "--url", hidden=True),
) -> None:
    """Ban an IP address."""
    async def _run_it():
        async with _get_client(url) as c:
            try:
                await c.ban_ip(jail, ip)
                console.print(f"[green]Banned {ip} in {jail}[/green]")
            except Exception as e:
                console.print(f"[red]Failed to ban {ip}:[/red] {e}")
                raise typer.Exit(1)
    _run(_run_it())


@security_app.command("unban")
def security_unban(
    ip: str = typer.Argument(help="IP address to unban"),
    jail: str = typer.Option("sshd", "--jail", help="Jail name"),
    url: Optional[str] = typer.Option(None, "--url", hidden=True),
) -> None:
    """Unban an IP address."""
    async def _run_it():
        async with _get_client(url) as c:
            try:
                await c.unban_ip(jail, ip)
                console.print(f"[green]Unbanned {ip} from {jail}[/green]")
            except Exception as e:
                console.print(f"[red]Failed to unban {ip}:[/red] {e}")
                raise typer.Exit(1)
    _run(_run_it())


@security_app.command("activity")
def security_activity(
    tail: int = typer.Option(50, "--tail", "-n"),
    url: Optional[str] = typer.Option(None, "--url", hidden=True),
) -> None:
    """Recent fail2ban log activity."""
    async def _run_it():
        async with _get_client(url) as c:
            events = await c.security_activity(limit=tail)
            if not events:
                console.print("[dim]No recent fail2ban activity.[/dim]")
                return
            for ev in events:
                ts = ev.get("timestamp", "")
                action = ev.get("action", "")
                ip = ev.get("ip", "")
                jail = ev.get("jail", "")
                color = "red" if action == "Ban" else "green" if action == "Unban" else "yellow"
                console.print(
                    f"[dim]{ts}[/dim] [{color}]{action or '-':<7}[/{color}] "
                    f"[cyan]{ip or '-':<18}[/cyan] [magenta]{jail or '-'}[/magenta]"
                )
    _run(_run_it())


@security_app.command("ip")
def security_ip(
    ip: str = typer.Argument(help="IP address to look up"),
    url: Optional[str] = typer.Option(None, "--url", hidden=True),
) -> None:
    """Show full history for an IP (fail2ban + SSH auth)."""
    async def _run_it():
        async with _get_client(url) as c:
            hist = await c.ip_history(ip)
            console.print(f"[bold]History for {ip}[/bold]")
            console.print()
            console.print(f"[cyan]fail2ban events ({len(hist.get('fail2ban_events', []))}):[/cyan]")
            for ev in hist.get("fail2ban_events", [])[:30]:
                action = ev.get("action") or "-"
                console.print(f"  [dim]{ev.get('timestamp', '')}[/dim] {action:<7} jail={ev.get('jail') or '-'}")
            console.print()
            console.print(f"[cyan]SSH auth events ({len(hist.get('auth_events', []))}):[/cyan]")
            for ev in hist.get("auth_events", [])[:30]:
                color = "green" if ev.get("event") == "success" else "red" if ev.get("event") == "failure" else "yellow"
                console.print(
                    f"  [dim]{ev.get('timestamp', '')}[/dim] "
                    f"[{color}]{ev.get('detail', '-'):<18}[/{color}] "
                    f"user={ev.get('user') or '-'}"
                )
    _run(_run_it())


@security_app.command("auth")
def security_auth(
    tail: int = typer.Option(50, "--tail", "-n"),
    event_type: Optional[str] = typer.Option(None, "--type", help="success|failure|info"),
    url: Optional[str] = typer.Option(None, "--url", hidden=True),
) -> None:
    """Recent SSH auth events."""
    async def _run_it():
        async with _get_client(url) as c:
            events = await c.auth_log(limit=tail, event_type=event_type)
            if not events:
                console.print("[dim]No recent SSH auth events.[/dim]")
                return
            for ev in events:
                color = "green" if ev.get("event") == "success" else "red" if ev.get("event") == "failure" else "yellow"
                console.print(
                    f"[dim]{ev.get('timestamp', '')}[/dim] "
                    f"[{color}]{ev.get('detail', '-'):<18}[/{color}] "
                    f"[cyan]{ev.get('ip') or '-':<18}[/cyan] "
                    f"user={ev.get('user') or '-'}"
                )
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


# ---------------------------------------------------------------------------
# Project sub-app (create, show, update, delete, scan, provision)
# ---------------------------------------------------------------------------

project_app = typer.Typer(help="Create, inspect, and manage Sentinel projects.")
app.add_typer(project_app, name="project")


@project_app.command("create")
def project_create(
    name: str = typer.Argument(help="Project slug (lowercase, hyphens)"),
    display_name: Optional[str] = typer.Option(None, "--display", help="Human-readable name"),
    type: str = typer.Option("fastapi", "--type", "-t", help="fastapi|vue|blended|nuxt|laravel|custom"),
    domain: Optional[str] = typer.Option(None, "--domain", "-d"),
    github_repo: Optional[str] = typer.Option(None, "--repo", "-r", help="GitHub repo URL"),
    ghcr_image: Optional[str] = typer.Option(None, "--image", help="GHCR image path"),
    description: Optional[str] = typer.Option(None, "--description"),
    compose_path: Optional[str] = typer.Option(None, "--compose-path", help="Override /apps/<name>"),
    compose_file: Optional[str] = typer.Option(None, "--compose-file", help="e.g. docker-compose.prod.yml"),
    health_endpoint: str = typer.Option("/health", "--health"),
    database_name: Optional[str] = typer.Option(None, "--db"),
    url: Optional[str] = typer.Option(None, "--url", hidden=True),
) -> None:
    """Create a project record in Sentinel."""
    async def _run_it():
        async with _get_client(url) as c:
            payload: dict = {
                "name": name,
                "display_name": display_name or name.replace("-", " ").title(),
                "project_type": type,
                "health_endpoint": health_endpoint,
            }
            for k, v in {
                "description": description,
                "github_repo": github_repo,
                "ghcr_image": ghcr_image,
                "domain": domain,
                "compose_path": compose_path,
                "compose_file": compose_file,
                "database_name": database_name,
            }.items():
                if v:
                    payload[k] = v
            try:
                p = await c.create_project(payload)
                console.print(f"[green]Created project[/green] [bold]{p['name']}[/bold] (id={p['id'][:8]})")
                if p.get("webhook_secret"):
                    console.print(f"  webhook_secret: [yellow]{p['webhook_secret']}[/yellow]")
            except Exception as e:
                console.print(f"[red]Failed:[/red] {e}")
                raise typer.Exit(1)
    _run(_run_it())


@project_app.command("show")
def project_show(
    name: str = typer.Argument(),
    url: Optional[str] = typer.Option(None, "--url", hidden=True),
) -> None:
    """Show project detail."""
    async def _run_it():
        async with _get_client(url) as c:
            pid = await c.get_project_id_by_name(name)
            p = await c.get_project(pid)
            for k in (
                "name", "display_name", "description", "project_type", "status",
                "domain", "github_repo", "ghcr_image", "compose_path", "compose_file",
                "health_endpoint", "database_name", "webhook_secret",
                "supports_custom_domains", "custom_domain_upstream", "service_api_key",
            ):
                val = p.get(k)
                if val is not None and val != "":
                    console.print(f"  [dim]{k:26}[/dim] {val}")
            containers = p.get("container_names") or {}
            if containers:
                console.print(f"  [dim]{'containers':26}[/dim] {', '.join(containers.keys())}")
    _run(_run_it())


@project_app.command("update")
def project_update(
    name: str = typer.Argument(),
    display_name: Optional[str] = typer.Option(None, "--display"),
    type: Optional[str] = typer.Option(None, "--type", "-t"),
    domain: Optional[str] = typer.Option(None, "--domain", "-d"),
    github_repo: Optional[str] = typer.Option(None, "--repo", "-r"),
    ghcr_image: Optional[str] = typer.Option(None, "--image"),
    description: Optional[str] = typer.Option(None, "--description"),
    compose_path: Optional[str] = typer.Option(None, "--compose-path"),
    compose_file: Optional[str] = typer.Option(None, "--compose-file"),
    health_endpoint: Optional[str] = typer.Option(None, "--health"),
    database_name: Optional[str] = typer.Option(None, "--db"),
    custom_domains: Optional[bool] = typer.Option(None, "--custom-domains/--no-custom-domains"),
    custom_domain_upstream: Optional[str] = typer.Option(None, "--custom-upstream"),
    url: Optional[str] = typer.Option(None, "--url", hidden=True),
) -> None:
    """Update project fields. Only provided flags are sent."""
    async def _run_it():
        async with _get_client(url) as c:
            pid = await c.get_project_id_by_name(name)
            patch: dict = {}
            for cli_name, field in (
                (display_name, "display_name"),
                (type, "project_type"),
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
                if cli_name is not None:
                    patch[field] = cli_name
            if custom_domains is not None:
                patch["supports_custom_domains"] = custom_domains
            if not patch:
                console.print("[yellow]No fields provided - use flags like --domain, --display, ...[/yellow]")
                return
            updated = await c.update_project(pid, patch)
            console.print(f"[green]Updated[/green] {updated['name']} ({len(patch)} fields)")
    _run(_run_it())


@project_app.command("delete")
def project_delete(
    name: str = typer.Argument(),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation"),
    url: Optional[str] = typer.Option(None, "--url", hidden=True),
) -> None:
    """Delete a project record from Sentinel. Does NOT remove server files or containers."""
    if not yes:
        if not typer.confirm(f"Delete project '{name}' from Sentinel?"):
            raise typer.Abort()

    async def _run_it():
        async with _get_client(url) as c:
            pid = await c.get_project_id_by_name(name)
            await c.delete_project(pid)
            console.print(f"[green]Deleted[/green] {name}")
    _run(_run_it())


@project_app.command("scan")
def project_scan(url: Optional[str] = typer.Option(None, "--url", hidden=True)) -> None:
    """Scan /apps/ for existing projects and register any new ones."""
    async def _run_it():
        async with _get_client(url) as c:
            result = await c.scan_projects()
            count = result.get("total", 0)
            console.print(f"[green]Scanned /apps - discovered {count} project(s)[/green]")
            for p in result.get("discovered", []):
                console.print(f"  {p.get('name')}")
    _run(_run_it())


@project_app.command("provision")
def project_provision(
    name: str = typer.Argument(),
    create_database: bool = typer.Option(False, "--create-db", help="Also create PostgreSQL DB"),
    url: Optional[str] = typer.Option(None, "--url", hidden=True),
) -> None:
    """Provision server files (compose, .env, Caddy route) for an existing project record."""
    async def _run_it():
        async with _get_client(url) as c:
            pid = await c.get_project_id_by_name(name)
            result = await c.provision_project(pid, create_database=create_database)
            console.print(f"[green]Provisioned[/green] {name}")
            for step in result.get("steps", []):
                status = step.get("status", "unknown")
                color = {"complete": "green", "error": "red", "skipped": "yellow"}.get(status, "dim")
                console.print(f"  [{color}]{status:10}[/{color}] {step.get('name', '')}")
    _run(_run_it())


@project_app.command("service-key")
def project_service_key(
    name: str = typer.Argument(),
    url: Optional[str] = typer.Option(None, "--url", hidden=True),
) -> None:
    """Generate a new service API key (for custom-domains API calls)."""
    async def _run_it():
        async with _get_client(url) as c:
            pid = await c.get_project_id_by_name(name)
            result = await c.generate_service_key(pid)
            key = result.get("service_api_key", "")
            console.print(f"[green]Generated service key for {name}:[/green]")
            console.print(f"  [yellow]{key}[/yellow]")
            console.print("[dim]Add to X-Service-Key header for /api/v1/custom-domains calls.[/dim]")
    _run(_run_it())


# ---------------------------------------------------------------------------
# Env sub-app
# ---------------------------------------------------------------------------

env_app = typer.Typer(help="Manage project environment variables.")
app.add_typer(env_app, name="env")


@env_app.command("list")
def env_list(
    project: str = typer.Argument(),
    reveal: bool = typer.Option(False, "--reveal", help="Show unmasked values"),
    url: Optional[str] = typer.Option(None, "--url", hidden=True),
) -> None:
    """List env vars for a project (values masked unless --reveal)."""
    async def _run_it():
        async with _get_client(url) as c:
            pid = await c.get_project_id_by_name(project)
            vars_ = await c.get_env(pid, reveal=reveal)
            if not vars_:
                console.print("[dim]No env vars set.[/dim]")
                return
            for v in vars_:
                console.print(f"  [cyan]{v['key']}[/cyan]={v['value']}")
    _run(_run_it())


@env_app.command("set")
def env_set(
    project: str = typer.Argument(),
    pairs: list[str] = typer.Argument(help="KEY=VALUE ... (can pass multiple)"),
    url: Optional[str] = typer.Option(None, "--url", hidden=True),
) -> None:
    """Set one or more env vars. Merges with existing vars."""
    async def _run_it():
        async with _get_client(url) as c:
            pid = await c.get_project_id_by_name(project)
            # Merge with existing so we don't clobber
            existing = await c.get_env(pid, reveal=True)
            merged = {v["key"]: v["value"] for v in existing}
            for pair in pairs:
                if "=" not in pair:
                    console.print(f"[red]Invalid KEY=VALUE: {pair}[/red]")
                    raise typer.Exit(1)
                k, _, v = pair.partition("=")
                merged[k.strip()] = v
            result = await c.set_env(pid, merged)
            console.print(f"[green]{result.get('detail', 'Env vars updated')}[/green]")
    _run(_run_it())


@env_app.command("unset")
def env_unset(
    project: str = typer.Argument(),
    keys: list[str] = typer.Argument(help="One or more env var names to remove"),
    url: Optional[str] = typer.Option(None, "--url", hidden=True),
) -> None:
    """Remove one or more env vars."""
    async def _run_it():
        async with _get_client(url) as c:
            pid = await c.get_project_id_by_name(project)
            existing = await c.get_env(pid, reveal=True)
            merged = {v["key"]: v["value"] for v in existing if v["key"] not in keys}
            result = await c.set_env(pid, merged)
            console.print(f"[green]Removed {len(keys)} env var(s): {', '.join(keys)}[/green]")
    _run(_run_it())


# ---------------------------------------------------------------------------
# Database sub-app
# ---------------------------------------------------------------------------

db_app = typer.Typer(help="Manage the external PostgreSQL instance (if configured).")
app.add_typer(db_app, name="db")


@db_app.command("list")
def db_list(url: Optional[str] = typer.Option(None, "--url", hidden=True)) -> None:
    """List databases on the managed PostgreSQL instance."""
    async def _run_it():
        async with _get_client(url) as c:
            dbs = await c.list_databases()
            table = Table(title="Databases")
            table.add_column("Name", style="bold")
            table.add_column("Owner")
            table.add_column("Size (MB)", justify="right")
            table.add_column("Tables", justify="right")
            for d in dbs:
                table.add_row(
                    d.get("name", ""),
                    d.get("owner", ""),
                    str(d.get("size_mb", 0)),
                    str(d.get("tables_count", 0)),
                )
            console.print(table)
    _run(_run_it())


@db_app.command("create")
def db_create(
    name: str = typer.Argument(help="Database name (also used for the dedicated user)"),
    password: Optional[str] = typer.Option(None, "--password", "-p", help="If omitted a random one is generated"),
    url: Optional[str] = typer.Option(None, "--url", hidden=True),
) -> None:
    """Create a new database + dedicated user."""
    async def _run_it():
        async with _get_client(url) as c:
            try:
                result = await c.create_database(name, password=password)
                console.print(f"[green]Created database {name} with owner {result.get('user', name)}[/green]")
                if result.get("password"):
                    console.print(f"  password: [yellow]{result['password']}[/yellow]  (save this)")
            except Exception as e:
                console.print(f"[red]Failed:[/red] {e}")
                raise typer.Exit(1)
    _run(_run_it())


@db_app.command("tables")
def db_tables(
    db: str = typer.Argument(),
    url: Optional[str] = typer.Option(None, "--url", hidden=True),
) -> None:
    """List tables in a database."""
    async def _run_it():
        async with _get_client(url) as c:
            tables = await c.list_tables(db)
            table = Table(title=f"Tables in {db}")
            table.add_column("Schema")
            table.add_column("Name", style="bold")
            table.add_column("Rows", justify="right")
            table.add_column("Size (KB)", justify="right")
            for t in tables:
                table.add_row(
                    t.get("schema", "-"),
                    t.get("name", ""),
                    str(t.get("row_count", 0)),
                    str(t.get("size_kb", 0)),
                )
            console.print(table)
    _run(_run_it())


@db_app.command("query")
def db_query(
    db: str = typer.Argument(),
    sql: str = typer.Argument(help="SELECT statement only"),
    url: Optional[str] = typer.Option(None, "--url", hidden=True),
) -> None:
    """Run a read-only SELECT query."""
    async def _run_it():
        async with _get_client(url) as c:
            try:
                result = await c.query(db, sql)
            except Exception as e:
                console.print(f"[red]Query failed:[/red] {e}")
                raise typer.Exit(1)
            rows = result.get("rows", [])
            cols = result.get("columns", [])
            if not rows:
                console.print("[dim]0 rows.[/dim]")
                return
            table = Table()
            for col in cols:
                table.add_column(col, overflow="fold")
            for row in rows[:100]:  # cap at 100 in the terminal
                table.add_row(*[str(row.get(c, "")) for c in cols])
            console.print(table)
            console.print(f"[dim]{result.get('row_count', len(rows))} rows in {result.get('execution_time_ms', 0)}ms[/dim]")
    _run(_run_it())


# ---------------------------------------------------------------------------
# Domain sub-app
# ---------------------------------------------------------------------------

domain_app = typer.Typer(help="Manage Caddy reverse-proxy domains.")
app.add_typer(domain_app, name="domain")


@domain_app.command("list")
def domain_list(url: Optional[str] = typer.Option(None, "--url", hidden=True)) -> None:
    """List Caddy domain blocks."""
    async def _run_it():
        async with _get_client(url) as c:
            domains = await c.list_domains()
            table = Table(title="Domains")
            table.add_column("Domain", style="bold")
            table.add_column("Upstreams")
            table.add_column("TLS Mode")
            for d in domains:
                upstreams = ", ".join(f"{u['address']}:{u['port']}" for u in d.get("upstreams", []))
                table.add_row(d.get("domain", ""), upstreams, d.get("tls_mode", "auto"))
            console.print(table)
    _run(_run_it())


@domain_app.command("add")
def domain_add(
    domain: str = typer.Argument(help="e.g. app.example.com"),
    upstream: str = typer.Option(..., "--upstream", "-u", help="container:port"),
    tls_mode: str = typer.Option("auto", "--tls", help="auto|cloudflare_dns|on_demand|off"),
    url: Optional[str] = typer.Option(None, "--url", hidden=True),
) -> None:
    """Add a domain to the Caddyfile."""
    async def _run_it():
        async with _get_client(url) as c:
            try:
                result = await c.add_domain(domain, upstream, tls_mode=tls_mode)
                console.print(f"[green]Added {domain} -> {upstream} ({tls_mode})[/green]")
            except Exception as e:
                console.print(f"[red]Failed:[/red] {e}")
                raise typer.Exit(1)
    _run(_run_it())


@domain_app.command("remove")
def domain_remove(
    domain: str = typer.Argument(),
    yes: bool = typer.Option(False, "--yes", "-y"),
    url: Optional[str] = typer.Option(None, "--url", hidden=True),
) -> None:
    """Remove a domain from the Caddyfile."""
    if not yes and not typer.confirm(f"Remove domain '{domain}'?"):
        raise typer.Abort()

    async def _run_it():
        async with _get_client(url) as c:
            await c.remove_domain(domain)
            console.print(f"[green]Removed {domain}[/green]")
    _run(_run_it())


@domain_app.command("reload")
def domain_reload(url: Optional[str] = typer.Option(None, "--url", hidden=True)) -> None:
    """Reload Caddy configuration."""
    async def _run_it():
        async with _get_client(url) as c:
            result = await c.reload_caddy()
            ok = result.get("success", False)
            color = "green" if ok else "red"
            console.print(f"[{color}]Caddy reload: {result.get('message', 'unknown')}[/{color}]")
    _run(_run_it())


@domain_app.command("tls")
def domain_tls(
    action: str = typer.Argument(help="status | enable | disable"),
    url: Optional[str] = typer.Option(None, "--url", hidden=True),
) -> None:
    """Manage on-demand TLS."""
    if action not in ("status", "enable", "disable"):
        console.print(f"[red]Unknown action '{action}'. Use status|enable|disable.[/red]")
        raise typer.Exit(1)

    async def _run_it():
        async with _get_client(url) as c:
            if action == "status":
                result = await c.on_demand_tls_status()
            elif action == "enable":
                result = await c.enable_on_demand_tls()
            else:
                result = await c.disable_on_demand_tls()
            enabled = result.get("enabled", False)
            color = "green" if enabled else "dim"
            console.print(f"[{color}]on-demand TLS: {'enabled' if enabled else 'disabled'}[/{color}]")
            if result.get("message"):
                console.print(f"  {result['message']}")
    _run(_run_it())


# ---------------------------------------------------------------------------
# Custom domain sub-app
# ---------------------------------------------------------------------------

cd_app = typer.Typer(help="Inspect and manage custom domains across all projects (admin).")
app.add_typer(cd_app, name="custom-domain")


@cd_app.command("list")
def cd_list(
    project: Optional[str] = typer.Option(None, "--project", "-p"),
    url: Optional[str] = typer.Option(None, "--url", hidden=True),
) -> None:
    """List custom domains across all projects."""
    async def _run_it():
        async with _get_client(url) as c:
            pid = None
            if project:
                pid = await c.get_project_id_by_name(project)
            data = await c.list_custom_domains(project_id=pid)
            items = data.get("items", [])
            table = Table(title="Custom Domains")
            table.add_column("Domain", style="bold")
            table.add_column("Project")
            table.add_column("Status")
            for d in items:
                table.add_row(
                    d.get("domain", ""),
                    d.get("project_name", ""),
                    d.get("status", ""),
                )
            console.print(table)
    _run(_run_it())


@cd_app.command("remove")
def cd_remove(
    domain: str = typer.Argument(),
    yes: bool = typer.Option(False, "--yes", "-y"),
    url: Optional[str] = typer.Option(None, "--url", hidden=True),
) -> None:
    """Force-remove a custom domain (admin)."""
    if not yes and not typer.confirm(f"Remove custom domain '{domain}'?"):
        raise typer.Abort()

    async def _run_it():
        async with _get_client(url) as c:
            await c.admin_remove_custom_domain(domain)
            console.print(f"[green]Removed {domain}[/green]")
    _run(_run_it())


# ---------------------------------------------------------------------------
# Service control top-level commands
# ---------------------------------------------------------------------------

@app.command()
def restart(
    name: str = typer.Argument(help="Container name"),
    url: Optional[str] = typer.Option(None, "--url", hidden=True),
) -> None:
    """Restart a container."""
    async def _run_it():
        async with _get_client(url) as c:
            await c.restart_service(name)
            console.print(f"[green]Restarted {name}[/green]")
    _run(_run_it())


@app.command()
def stop(
    name: str = typer.Argument(help="Container name"),
    url: Optional[str] = typer.Option(None, "--url", hidden=True),
) -> None:
    """Stop a running container."""
    async def _run_it():
        async with _get_client(url) as c:
            await c.stop_service(name)
            console.print(f"[yellow]Stopped {name}[/yellow]")
    _run(_run_it())


@app.command()
def start(
    name: str = typer.Argument(help="Container name"),
    url: Optional[str] = typer.Option(None, "--url", hidden=True),
) -> None:
    """Start a stopped container."""
    async def _run_it():
        async with _get_client(url) as c:
            await c.start_service(name)
            console.print(f"[green]Started {name}[/green]")
    _run(_run_it())


# ---------------------------------------------------------------------------
# Audit
# ---------------------------------------------------------------------------

@app.command()
def audit(
    action_filter: Optional[str] = typer.Option(None, "--action", help="Filter by action e.g. project.create"),
    limit: int = typer.Option(30, "--limit", "-n"),
    url: Optional[str] = typer.Option(None, "--url", hidden=True),
) -> None:
    """View recent audit log entries."""
    async def _run_it():
        async with _get_client(url) as c:
            result = await c.audit_log(page=1, per_page=limit, action=action_filter)
            items = result.get("items", [])
            if not items:
                console.print("[dim]No audit entries.[/dim]")
                return
            table = Table(title="Audit Log")
            table.add_column("Time")
            table.add_column("User")
            table.add_column("Action")
            table.add_column("Target")
            for i in items:
                table.add_row(
                    i.get("timestamp", "")[:19],
                    i.get("user") or "-",
                    i.get("action", ""),
                    i.get("target") or "-",
                )
            console.print(table)
    _run(_run_it())


# ---------------------------------------------------------------------------
# Init - interactive wizard alias (minimal prompts, calls /projects/wizard)
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Repo setup - write workflow + set GitHub secret (closes the repo-side gap)
# ---------------------------------------------------------------------------

repo_app = typer.Typer(help="Configure a git repo to deploy via Sentinel.")
app.add_typer(repo_app, name="repo")


def _run_local(cmd: list[str], cwd: str | None = None) -> tuple[int, str]:
    """Run a local shell command and return (returncode, combined output)."""
    import subprocess
    try:
        result = subprocess.run(
            cmd,
            cwd=cwd,
            capture_output=True,
            text=True,
            check=False,
            timeout=60,
        )
        return result.returncode, (result.stdout or "") + (result.stderr or "")
    except FileNotFoundError:
        return 127, f"Command not found: {cmd[0]}"
    except Exception as e:
        return 1, str(e)


def _detect_github_repo(repo_dir: str) -> str | None:
    """Infer the owner/repo slug from git remote origin."""
    import re
    rc, out = _run_local(["git", "-C", repo_dir, "remote", "get-url", "origin"])
    if rc != 0:
        return None
    url = out.strip()
    # Match git@github.com:owner/repo.git or https://github.com/owner/repo(.git)
    m = re.search(r"github\.com[:/]([^/]+/[^/]+?)(\.git)?$", url)
    return m.group(1) if m else None


@repo_app.command("setup")
def repo_setup(
    project: str = typer.Argument(help="Sentinel project name"),
    repo_dir: str = typer.Option(".", "--dir", help="Path to the git repo (defaults to cwd)"),
    github_repo: Optional[str] = typer.Option(None, "--repo", help="owner/name (inferred from git remote if omitted)"),
    skip_secret: bool = typer.Option(False, "--no-secret", help="Skip setting GitHub secret"),
    skip_commit: bool = typer.Option(False, "--no-commit", help="Write the file but do not commit + push"),
    commit_message: str = typer.Option("ci: Sentinel webhook deploys", "--message", "-m"),
    url: Optional[str] = typer.Option(None, "--url", hidden=True),
) -> None:
    """Write .github/workflows/deploy.yml + set SENTINEL_WEBHOOK_SECRET in the git repo.

    Requires `git` and (unless --no-secret) `gh` CLI authed against GitHub.
    """
    import os
    from pathlib import Path

    async def _run_it():
        async with _get_client(url) as c:
            try:
                pid = await c.get_project_id_by_name(project)
                info = await c.get_project_workflow(pid)
            except Exception as e:
                console.print(f"[red]Failed to fetch workflow:[/red] {e}")
                raise typer.Exit(1)
            yaml = info.get("workflow_yaml", "")
            secret = info.get("webhook_secret", "")
            return yaml, secret

        return "", ""

    yaml, secret = _run(_run_it())

    # Write workflow file
    target_dir = os.path.abspath(repo_dir)
    if not (Path(target_dir) / ".git").exists():
        console.print(f"[red]{target_dir} is not a git repo[/red]")
        raise typer.Exit(1)

    wf_dir = Path(target_dir) / ".github" / "workflows"
    wf_dir.mkdir(parents=True, exist_ok=True)
    wf_path = wf_dir / "deploy.yml"
    wf_path.write_text(yaml)
    console.print(f"[green]Wrote[/green] {wf_path.relative_to(target_dir)} ({len(yaml)} bytes)")

    # Set GitHub secret
    if not skip_secret:
        if not github_repo:
            github_repo = _detect_github_repo(target_dir)
        if not github_repo:
            console.print("[yellow]Could not detect github repo - pass --repo owner/name or use --no-secret[/yellow]")
        else:
            rc, out = _run_local(
                ["gh", "secret", "set", "SENTINEL_WEBHOOK_SECRET", "-R", github_repo, "--body", secret],
            )
            if rc == 0:
                console.print(f"[green]Set SENTINEL_WEBHOOK_SECRET[/green] on {github_repo}")
            else:
                console.print(f"[red]gh secret set failed:[/red] {out.strip()}")
                console.print("[dim]Tip: run `gh auth login` first, or use --no-secret and set it manually.[/dim]")

    # Commit + push
    if not skip_commit:
        rc1, _ = _run_local(["git", "-C", target_dir, "add", str(wf_path.relative_to(target_dir))])
        rc2, out2 = _run_local(["git", "-C", target_dir, "commit", "-m", commit_message])
        if rc2 == 0:
            console.print("[green]Committed[/green]")
            rc3, out3 = _run_local(["git", "-C", target_dir, "push"])
            if rc3 == 0:
                console.print("[green]Pushed to remote[/green] - GitHub Actions will build + deploy")
            else:
                console.print(f"[yellow]Commit OK but push failed:[/yellow] {out3.strip()}")
        elif "nothing to commit" in out2:
            console.print("[dim]Nothing to commit - workflow already up to date.[/dim]")
        else:
            console.print(f"[yellow]Commit failed:[/yellow] {out2.strip()}")


# ---------------------------------------------------------------------------
# bootstrap - one-command end-to-end: project + env + db + domain + provision
# + repo setup + deploy
# ---------------------------------------------------------------------------

@app.command()
def bootstrap(
    name: str = typer.Option(..., "--name", "-n", prompt=True, help="Project slug"),
    type: str = typer.Option("fastapi", "--type", "-t", prompt=True),
    domain: str = typer.Option(..., "--domain", "-d", prompt=True),
    github_repo: str = typer.Option(..., "--repo", "-r", prompt=True, help="Full GitHub repo URL"),
    ghcr_image: Optional[str] = typer.Option(None, "--image", help="Defaults to ghcr.io/<owner>/<name>"),
    upstream: Optional[str] = typer.Option(None, "--upstream", help="Defaults to <name>:8000 for fastapi, <name>:80 for vue"),
    create_db: bool = typer.Option(False, "--create-db"),
    env: list[str] = typer.Option([], "--env", "-e", help="KEY=VALUE (repeatable)"),
    repo_dir: str = typer.Option(".", "--dir", help="Local git repo path"),
    deploy_now: bool = typer.Option(False, "--deploy", help="Trigger first deploy (images must already be on GHCR)"),
    url: Optional[str] = typer.Option(None, "--url", hidden=True),
) -> None:
    """End-to-end project setup: Sentinel scaffolding + repo workflow + secret + optional deploy.

    Example:

        sentinel bootstrap --name my-app --type fastapi --domain my-app.paydlabs.com \\
          --repo https://github.com/getpayd-tech/my-app --create-db \\
          --env APP_ENV=production --env SECRET_KEY=xyz --deploy
    """
    import re

    # Defaults
    if not ghcr_image:
        # Derive from github repo: https://github.com/owner/repo -> ghcr.io/owner/repo
        m = re.search(r"github\.com[:/]([^/]+)/([^/.]+)", github_repo)
        if m:
            ghcr_image = f"ghcr.io/{m.group(1)}/{name}"
    if not upstream:
        port = 80 if type == "vue" else 8000
        upstream = f"{name}:{port}"

    env_dict: dict[str, str] = {}
    for pair in env:
        if "=" in pair:
            k, _, v = pair.partition("=")
            env_dict[k.strip()] = v

    async def _run_it():
        async with _get_client(url) as c:
            # 1. Project
            console.print("[bold cyan]1/7[/bold cyan] Creating project record...")
            try:
                p = await c.create_project({
                    "name": name,
                    "display_name": name.replace("-", " ").title(),
                    "project_type": type,
                    "github_repo": github_repo,
                    "ghcr_image": ghcr_image,
                    "domain": domain,
                    "health_endpoint": "/health",
                    **({"database_name": name.replace("-", "_")} if create_db else {}),
                })
                pid = p["id"]
                console.print(f"    [green]project id={pid[:8]}[/green]")
            except Exception as e:
                console.print(f"    [red]failed: {e}[/red]")
                raise typer.Exit(1)

            # 2. Env vars
            if env_dict:
                console.print(f"[bold cyan]2/7[/bold cyan] Setting {len(env_dict)} env vars...")
                await c.set_env(pid, env_dict)
                console.print("    [green]ok[/green]")
            else:
                console.print("[bold cyan]2/7[/bold cyan] Skipping env vars (none provided)")

            # 3. Database
            if create_db:
                console.print("[bold cyan]3/7[/bold cyan] Creating database...")
                try:
                    db_result = await c.create_database(name.replace("-", "_"))
                    console.print(f"    [green]ok ({db_result.get('user', '')})[/green]")
                except Exception as e:
                    console.print(f"    [yellow]skipped: {e}[/yellow]")
            else:
                console.print("[bold cyan]3/7[/bold cyan] Skipping database (no --create-db)")

            # 4. Domain
            console.print(f"[bold cyan]4/7[/bold cyan] Adding Caddy domain {domain} -> {upstream}...")
            try:
                await c.add_domain(domain, upstream)
                console.print("    [green]ok[/green]")
            except Exception as e:
                console.print(f"    [yellow]skipped: {e}[/yellow]")

            # 5. Provision (compose + .env + caddy)
            console.print("[bold cyan]5/7[/bold cyan] Provisioning server files...")
            try:
                result = await c.provision_project(pid, create_database=False)
                for step in result.get("steps", []):
                    if step.get("status") == "error":
                        console.print(f"    [red]{step.get('name')}: error[/red]")
            except Exception as e:
                console.print(f"    [yellow]warning: {e}[/yellow]")
            console.print("    [green]ok[/green]")

            # 6. Fetch generated workflow + secret
            console.print("[bold cyan]6/7[/bold cyan] Fetching generated workflow...")
            info = await c.get_project_workflow(pid)
            yaml = info.get("workflow_yaml", "")
            secret = info.get("webhook_secret", "")
            console.print("    [green]ok[/green]")

            return pid, yaml, secret

    pid, yaml, secret = _run(_run_it())

    # 7. Repo setup (local git ops)
    console.print("[bold cyan]7/7[/bold cyan] Writing workflow + setting GitHub secret in local repo...")
    import os
    from pathlib import Path

    target_dir = os.path.abspath(repo_dir)
    if not (Path(target_dir) / ".git").exists():
        console.print(f"    [yellow]{target_dir} is not a git repo - skipping repo step[/yellow]")
        console.print(f"    [dim]webhook_secret: {secret}[/dim]")
    else:
        wf_dir = Path(target_dir) / ".github" / "workflows"
        wf_dir.mkdir(parents=True, exist_ok=True)
        wf_path = wf_dir / "deploy.yml"
        wf_path.write_text(yaml)
        console.print(f"    [green]wrote {wf_path.relative_to(target_dir)}[/green]")

        gh_repo = _detect_github_repo(target_dir)
        if gh_repo:
            rc, out = _run_local(["gh", "secret", "set", "SENTINEL_WEBHOOK_SECRET", "-R", gh_repo, "--body", secret])
            if rc == 0:
                console.print(f"    [green]set SENTINEL_WEBHOOK_SECRET on {gh_repo}[/green]")
            else:
                console.print(f"    [yellow]gh secret set failed: {out.strip()}[/yellow]")
                console.print(f"    [dim]webhook_secret (set it manually): {secret}[/dim]")
        else:
            console.print(f"    [dim]webhook_secret (set it manually): {secret}[/dim]")

    # Optional first deploy
    if deploy_now:
        console.print("[bold cyan]Deploying...[/bold cyan]")
        async def _do_deploy():
            async with _get_client(url) as c:
                try:
                    result = await c.deploy(pid)
                    status = result.get("status", "unknown")
                    color = "green" if status == "success" else "red"
                    console.print(f"    [{color}]deploy: {status}[/{color}]")
                except Exception as e:
                    console.print(f"    [red]deploy failed: {e}[/red]")
        _run(_do_deploy())

    console.print()
    console.print(f"[bold green]Bootstrap complete![/bold green] Project {name} is ready.")
    console.print("[dim]Next: commit + push in your app repo to trigger first deploy (if --deploy not used).[/dim]")


@app.command()
def init(url: Optional[str] = typer.Option(None, "--url", hidden=True)) -> None:
    """Interactive deploy wizard (creates project + compose + Caddy + optional DB + optional first deploy)."""
    from rich.prompt import Prompt, Confirm

    async def _run_it():
        console.print("[bold]Sentinel Deploy Wizard[/bold]")
        name = Prompt.ask("Project slug (lowercase, hyphens)")
        display_name = Prompt.ask("Display name", default=name.replace("-", " ").title())
        project_type = Prompt.ask(
            "Project type",
            choices=["fastapi", "vue", "blended", "nuxt", "laravel", "custom"],
            default="fastapi",
        )
        github_repo = Prompt.ask("GitHub repo URL (org/name or full URL)")
        domain = Prompt.ask("Domain", default="")
        tls_mode = Prompt.ask("TLS mode", choices=["auto", "cloudflare_dns", "off"], default="auto")
        create_database = Confirm.ask("Create a PostgreSQL database?", default=False)
        first_deploy = Confirm.ask("Run first deploy now? (images must be pushed to GHCR already)", default=False)
        compose_filename = Prompt.ask("Compose filename", default="docker-compose.yml")

        payload = {
            "name": name,
            "display_name": display_name,
            "project_type": project_type,
            "github_repo": github_repo,
            "domain": domain or None,
            "tls_mode": tls_mode,
            "create_database": create_database,
            "first_deploy": first_deploy,
            "compose_filename": compose_filename,
        }
        console.print("[dim]Running wizard (this may take a minute)...[/dim]")
        async with _get_client(url) as c:
            try:
                result = await c.run_wizard(payload)
            except Exception as e:
                console.print(f"[red]Wizard failed:[/red] {e}")
                raise typer.Exit(1)
            console.print(f"[green]Project created:[/green] id={result.get('project_id', '')[:8]}")
            if result.get("webhook_secret"):
                console.print(f"  webhook_secret: [yellow]{result['webhook_secret']}[/yellow]")
            for step in result.get("steps", []):
                status = step.get("status", "")
                color = {"complete": "green", "error": "red", "skipped": "yellow"}.get(status, "dim")
                console.print(f"  [{color}]{status:10}[/{color}] step {step.get('step', '?')}: {step.get('name', '')}")
    _run(_run_it())
