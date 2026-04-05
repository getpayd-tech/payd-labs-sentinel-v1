# Sentinel - Payd Labs Server Management Platform

Sentinel is a self-hosted DevOps portal for Payd Labs. It replaces per-repo SSH deploy scripts with a centralized system: one webhook secret per project, no SSH keys scattered across GitHub repos.

**Live:** [sentinel.paydlabs.com](https://sentinel.paydlabs.com)
**Deploy Guide:** [DEPLOY.md](./DEPLOY.md) | [In-app guide](https://sentinel.paydlabs.com/docs)

---

## How Deployment Works

```
Your Repo (GitHub Actions)                 Sentinel (on server)
──────────────────────────                 ────────────────────
1. Build Docker image(s)
2. Push to GHCR
3. POST webhook to Sentinel   ─────→      4. Verify HMAC signature
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

## Features

| Feature | Description |
|---------|-------------|
| **Deploy Wizard** | End-to-end project setup: compose, .env, Caddy, database, first deploy |
| **Dashboard** | Container health, CPU/RAM/disk metrics, real-time refresh |
| **Services** | List, restart, stop, start containers; view logs |
| **Deployments** | Webhook-triggered deploys, manual deploy, rollback, history |
| **Projects** | Register, scan, edit projects; manage env vars |
| **Database** | Browse managed PostgreSQL: databases, tables, schemas, run queries |
| **Domains** | Manage Caddy routes with TLS (ACME / Cloudflare DNS) |
| **Logs** | Aggregated log viewer across all containers |
| **System** | CPU, memory, disk, network metrics |
| **Audit** | Full action history |

---

## Architecture

```
Browser → Caddy (TLS) → sentinel-api (FastAPI :8000) / sentinel-ui (Vue :80)

sentinel-api has:
  - Docker socket → manages all containers on the server
  - /apps/ volume → reads/writes compose files + .env for every project
  - Docker CLI → runs docker compose pull/up for deployments
  - SQLite → project records, deployments, audit log
  - asyncpg → DigitalOcean Managed PostgreSQL (database browser)
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
├── sentinel-api/
│   └── app/
│       ├── main.py, config.py, auth.py, database.py
│       ├── api/v1/          # Route handlers
│       ├── services/        # Business logic
│       ├── models/          # SQLAlchemy models
│       ├── schemas/         # Pydantic schemas
│       └── templates/       # Compose + workflow templates
├── sentinel-ui/
│   └── src/
│       ├── views/           # Page components
│       ├── components/      # Reusable UI
│       ├── services/        # API clients
│       └── stores/          # Pinia (auth, theme)
├── DEPLOY.md                # Deployment guide
└── .github/workflows/       # Sentinel's own CI/CD
```

---

## Auth

Uses Payd Auth (`auth.payd.money`), same as Stables. Login with username + password → OTP → JWT. Access restricted by `is_admin` claim + `ALLOWED_USERNAMES` whitelist.

---

## Sentinel's Own Environment (`/apps/sentinel/.env`)

| Variable | Example |
|----------|---------|
| `APP_ENV` | `production` |
| `DATABASE_URL` | `sqlite+aiosqlite:////data/sentinel.db` |
| `PAYD_AUTH_URL` | `https://auth.payd.money` |
| `PG_ADMIN_HOST` | `dbaas-db-xxx.db.ondigitalocean.com` |
| `PG_ADMIN_PORT` | `25060` |
| `PG_ADMIN_USER` | `doadmin` |
| `PG_ADMIN_PASSWORD` | `...` |
| `ALLOWED_USERNAMES` | `benaiah,vincentee,snow` |
