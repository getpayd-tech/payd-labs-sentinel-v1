# Sentinel - Payd Labs Server Management Platform

Sentinel is a self-hosted DevOps portal for Payd Labs. It replaces per-repo SSH deploy scripts with a centralized system: one webhook secret per project, no SSH keys scattered across GitHub repos. It also manages custom domains with automatic TLS provisioning for any service that needs user-facing domain support.

**Live:** [sentinel.paydlabs.com](https://sentinel.paydlabs.com)
**Deploy Guide:** [DEPLOY.md](./DEPLOY.md) | [In-app guide](https://sentinel.paydlabs.com/docs)

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

Sentinel ships a Python CLI and an MCP server for AI agent integration. Both live in `sentinel-cli/`.

### Install

```bash
# Clone the repo (or use an existing checkout)
git clone git@github.com:getpayd-tech/payd-labs-sentinel-v1.git
cd payd-labs-sentinel-v1

# Create a venv and install
python3.12 -m venv sentinel-cli/.venv
source sentinel-cli/.venv/bin/activate
pip install -e sentinel-cli/
```

### CLI usage

```bash
sentinel login                        # OTP auth, caches token at ~/.sentinel/
sentinel projects                     # List all projects
sentinel services                     # List all containers
sentinel status                       # Projects + their last deploy
sentinel deploy bradar                # Trigger deploy by project name
sentinel deploy bradar --tag v1.2.3   # Deploy a specific image tag
sentinel rollback bradar <deploy-id>  # Roll back to a previous deploy
sentinel deployments --project bradar # Deployment history
sentinel logs sentinel-api --tail 50  # Container logs
sentinel logs bradar --since 1h       # Logs from the last hour
```

Auth: run `sentinel login` once (OTP flow, tokens cached with auto-refresh), or set `SENTINEL_TOKEN` env var with a valid JWT.

Override the API URL: `SENTINEL_URL=http://localhost:8000 sentinel projects`

### MCP server for Claude Code

After installing, add to your Claude Code settings:

```json
// .claude/settings.json (project-level) or ~/.claude/settings.json (global)
{
  "mcpServers": {
    "sentinel": {
      "command": "/path/to/payd-labs-sentinel-v1/sentinel-cli/.venv/bin/sentinel-mcp"
    }
  }
}
```

The MCP server exposes 7 tools: `sentinel_list_projects`, `sentinel_list_services`, `sentinel_list_deployments`, `sentinel_deploy`, `sentinel_rollback`, `sentinel_get_logs`, `sentinel_project_status`.

Auth: reads from `~/.sentinel/credentials.json` (run `sentinel login` first) or `SENTINEL_TOKEN` env var.

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
