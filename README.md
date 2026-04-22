# Sentinel - Payd Labs Server Management Platform

Sentinel is a self-hosted DevOps portal for Payd Labs. It replaces per-repo SSH deploy scripts with a centralized system: one webhook secret per project, no SSH keys scattered across GitHub repos. It also manages custom domains with automatic TLS provisioning for any service that needs user-facing domain support.

**Live:** [sentinel.paydlabs.com](https://sentinel.paydlabs.com)
**Deploy Guide:** [DEPLOY.md](./DEPLOY.md) | [In-app guide](https://sentinel.paydlabs.com/docs)
**Self-hosting:** [SELFHOST.md](./SELFHOST.md)

---

## How Deployment Works

```
Your Repo (GitHub Actions)                 Sentinel (on server)
--------------------------                 --------------------
1. Build Docker image(s)
2. Push to GHCR
3. POST webhook to Sentinel   ------>      4. Verify HMAC signature
                                           5. docker compose pull
                                           6. docker compose up -d
                                           7. Health check (60s)
                                           8. Auto-rollback if failed
                                           9. Record in deployment log
```

**One secret per repo:** `SENTINEL_WEBHOOK_SECRET`
**No SSH keys needed.** Sentinel runs on the server with Docker socket access.

---

## Quick Start: Deploy a New Project

1. **Run the wizard** at [sentinel.paydlabs.com/projects/deploy-wizard](https://sentinel.paydlabs.com/projects/deploy-wizard)
2. **Add the workflow** to your repo (wizard generates it, just copy to `.github/workflows/deploy.yml`)
3. **Add one secret** to your GitHub repo: `SENTINEL_WEBHOOK_SECRET` (shown after wizard completes)
4. **Push to main** - Sentinel handles the rest

For the full step-by-step guide with examples, Dockerfile templates, and troubleshooting, see **[DEPLOY.md](./DEPLOY.md)**.

---

## Managed Services

All 10 services on the Payd Labs server (`46.101.240.141`) deploy through Sentinel:

| Service | Domain | Type |
|---------|--------|------|
| payd-connect | connect.payd.money | blended (API + docs) |
| payd-shops-api | shops-api.paydlabs.com | fastapi |
| payd-shops-ui | shops.payd.money, \*.onpayd.shop | vue |
| noni-api | noni.payd.money | fastapi + redis |
| noni-ui | noni.payd.money | vue |
| bradar | bradar.paydlabs.com | custom (Node/Express) |
| payd-stables | stables.paydlabs.com | fastapi |
| payd-labs-offline | offline.paydlabs.com | blended |
| payd-labs-one-link | link.paydlabs.com, payd.one | fastapi |
| payd-pos | pos.paydlabs.com, pos-api.paydlabs.com | blended |
| sentinel | sentinel.paydlabs.com | blended (self-managed) |

---

## Features

| Feature | Description |
|---------|-------------|
| **Deploy Wizard** | End-to-end project setup: compose, .env, Caddy, database, first deploy |
| **Dashboard** | Container health, CPU/RAM/disk metrics, real-time refresh |
| **Services** | List, restart, stop, start containers; view logs |
| **Deployments** | Webhook-triggered deploys, manual deploy, rollback, history |
| **Projects** | Register, scan, edit projects; manage env vars |
| **Custom Domains** | Services register user domains via API; Sentinel writes Caddy blocks with on-demand TLS |
| **Database** | Browse managed PostgreSQL: databases, tables, schemas, run queries |
| **Domains** | Manage Caddy routes with TLS (ACME / Cloudflare DNS / on-demand) |
| **Logs** | Aggregated log viewer across all containers |
| **System** | CPU, memory, disk, network metrics |
| **Audit** | Full action history |
| **CLI** | `sentinel` command for deploys, logs, status from the terminal |
| **MCP Server** | `sentinel-mcp` exposes tools for AI agents (Claude Code, etc.) |

---

## Custom Domains

Services like OneLink and Payd Shops can let their users bring custom domains. Sentinel is the central domain authority:

1. **Admin enables custom domains** on a project and sets the upstream container (e.g. `payd-labs-one-link:8000`)
2. **Admin generates a service API key** for the project
3. **The service backend** calls Sentinel to register a domain:
   ```bash
   curl -X POST https://sentinel.paydlabs.com/api/v1/custom-domains \
     -H "X-Service-Key: sak_..." \
     -H "Content-Type: application/json" \
     -d '{"domain": "mybrand.com"}'
   ```
4. **Sentinel writes a Caddy block** with `tls { on_demand }` and reloads
5. **User points DNS** to `46.101.240.141`
6. **Caddy auto-provisions a TLS cert** (validated via Sentinel's `/internal/domain-check` endpoint)

The Caddy `on_demand_tls { ask }` endpoint points to `sentinel-api:8000/internal/domain-check`, which checks the `custom_domains` table. A catch-all `https://` block still routes unregistered domains to OneLink for backward compatibility.

See the admin UI at **Custom Domains** in the sidebar, or the project detail page for service key management.

---

## CLI + MCP Server

Sentinel ships a Python CLI and an MCP server for AI-agent integration. Both live in `sentinel-cli/` and are published to PyPI as `sentinel-cli`.

### Install

```bash
pip install sentinel-cli    # requires Python 3.12+
sentinel login              # one-time OTP via Payd Auth
```

### End-to-end deploy of a new service

One command does everything (project + env + database + Caddy route + server provision + GitHub workflow commit + GitHub secret + first deploy):

```bash
cd my-app-repo    # a git repo with a Dockerfile
sentinel bootstrap \
  --name my-app --type fastapi --domain my-app.paydlabs.com \
  --repo https://github.com/getpayd-tech/my-app \
  --create-db \
  --env APP_ENV=production \
  --env SECRET_KEY="$(openssl rand -hex 32)" \
  --deploy
```

Prerequisites: `git` + `gh` (authed). Without them, the CLI prints the webhook_secret for manual setup.

### Daily ops

```bash
sentinel status                              # Dashboard: projects + last deploy
sentinel deploy <project> [--tag sha]        # Trigger deploy
sentinel rollback <project> <deploy-id>
sentinel deployments [--project X]
sentinel logs <container> [--tail N] [--since 1h]
sentinel restart|stop|start <container>
sentinel audit [--action X] [--limit N]
```

### Provisioning subcommands

```bash
sentinel project create|show|update|delete|scan|provision|service-key
sentinel env list|set|unset <project> [KEY=VAL ...]
sentinel db list|create|tables|query
sentinel domain list|add|remove|reload|tls
sentinel custom-domain list|remove
sentinel security banned|ban|unban|activity|auth|ip
sentinel repo setup <project>    # for existing projects without a workflow
sentinel init                    # interactive wizard
```

Full command reference: [sentinel-cli/README.md](./sentinel-cli/README.md).

Auth: `sentinel login` (cached at `~/.sentinel/`, auto-refreshed) or `SENTINEL_TOKEN` env var.

Override API URL: `SENTINEL_URL=http://localhost:8000 sentinel ...`.

### MCP server for Claude Code

30 tools covering the full CLI surface. Add to `.claude/settings.json`:

```json
{
  "mcpServers": {
    "sentinel": { "command": "sentinel-mcp" }
  }
}
```

Tools span project CRUD, deploys, env vars, databases, domains, services, audit, security. See [sentinel-cli/README.md](./sentinel-cli/README.md) for the full list.

---

## Architecture

```
Browser -> Caddy (TLS) -> sentinel-api (FastAPI :8000) / sentinel-ui (Vue :80)

sentinel-api has:
  - Docker socket -> manages all containers on the server
  - /apps/ volume -> reads/writes compose files + .env for every project
  - Docker CLI -> runs docker compose pull/up for deployments
  - SQLite -> project records, custom domains, deployments, audit log
  - asyncpg -> DigitalOcean Managed PostgreSQL (database browser)
  - Caddy ask endpoint -> validates custom domains for on-demand TLS
```

**Server:** DigitalOcean, Ubuntu 24.04, 4 CPU / 8GB RAM, IP `46.101.240.141`

---

## Local Development

```bash
# Backend
cd sentinel-api
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000

# Frontend
cd sentinel-ui
npm install
npm run dev  # http://localhost:5173, proxies /api to :8000
```

---

## Project Structure

```
payd-labs-sentinel/
 sentinel-api/
    app/
       main.py, config.py, auth.py, database.py
       api/v1/          # Route handlers (projects, deployments, custom_domains, domains, ...)
       services/        # Business logic (deploy, caddy, project, ...)
       models/          # SQLAlchemy models (Project, Deployment, CustomDomain, AuditLog, ...)
       schemas/         # Pydantic schemas
       templates/       # Compose + workflow templates
 sentinel-ui/
    src/
       views/           # Page components
       components/      # Reusable UI
       services/        # API clients
       stores/          # Pinia (auth, theme)
 sentinel-cli/
    sentinel_cli/
       cli.py           # Typer CLI (sentinel command)
       mcp_server.py    # FastMCP server (sentinel-mcp command)
       client.py        # Shared async httpx API client
       auth.py          # OTP login, token cache, auto-refresh
       config.py        # URL + credential paths
 DEPLOY.md              # Deployment guide
 .github/workflows/     # Sentinel's own CI/CD
```

---

## Auth

Uses Payd Auth (`auth.payd.money`), same as Stables. Login with username + password -> OTP -> JWT. Access restricted by `is_admin` claim + `ALLOWED_USERNAMES` whitelist.

For service-to-service auth (custom domains API), each project has a separate `service_api_key` sent via `X-Service-Key` header.

---

## Sentinel's Own Environment (`/apps/sentinel/.env`)

| Variable | Example |
|----------|---------|
| `APP_ENV` | `production` |
| `DATABASE_URL` | `sqlite+aiosqlite:////data/sentinel.db` |
| `CORS_ORIGINS` | `https://sentinel.paydlabs.com` |
| `PG_ADMIN_HOST` | `dbaas-db-xxx.db.ondigitalocean.com` |
| `PG_ADMIN_PORT` | `25060` |
| `PG_ADMIN_USER` | `doadmin` |
| `PG_ADMIN_PASSWORD` | `...` |
| `ALLOWED_USERNAMES` | `benaiah,vincentee,snow` |
| `GHCR_TOKEN` | `ghp_...` (long-lived PAT for pulling private GHCR images) |
| `GHCR_USER` | `getpayd-tech` |
| `ENCRYPTION_KEY` | Fernet key for encrypting env vars at rest |
