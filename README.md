# Sentinel - Payd Labs Server Management Platform

Sentinel is a self-hosted DevOps portal for Payd Labs' infrastructure. It consolidates container management, deployments, database administration, domain routing, and system monitoring into a single dashboard — replacing per-repo SSH-based GitHub Actions with a centralized webhook-based deployment system.

**Live:** [sentinel.paydlabs.com](https://sentinel.paydlabs.com)

## Architecture

```
Browser → Caddy (sentinel.paydlabs.com)
              ├── /api/* → sentinel-api (FastAPI, port 8000)
              └── /*     → sentinel-ui  (Vue SPA, port 80)

sentinel-api
  ├── Docker socket (container management)
  ├── /apps/ volume (compose files, .env metadata)
  ├── SQLite database (/data/sentinel.db)
  └── asyncpg → DigitalOcean Managed PostgreSQL (port 25060, SSL)
```

Three containers on the shared `proxy` network:
- **sentinel-api** — FastAPI backend (Python 3.12, ~50MB RAM)
- **sentinel-ui** — Vue 3 SPA served by Caddy Alpine (~15MB RAM)
- **sentinel-redis** — Redis 7 Alpine (~10MB RAM)

## Features

| Feature | Description |
|---------|-------------|
| **Dashboard** | Container health, CPU/RAM/disk metrics, real-time refresh |
| **Services** | List, restart, stop, start Docker containers; view logs |
| **Deployments** | Webhook-triggered deploys, manual deploy, rollback, history |
| **Projects** | Register projects, scan existing /apps/, provision new ones |
| **Database** | Browse managed PostgreSQL: databases, tables, schemas, run SELECT queries |
| **Domains** | Parse/edit Caddyfile routes, reload Caddy |
| **Logs** | Aggregated log viewer across all containers with search/filter |
| **System** | CPU, memory, disk, network metrics (psutil) |
| **Audit** | Full action history: who did what, when, from where |

## Authentication

Sentinel uses Payd Auth (`auth.payd.money`) — the same auth system as Stables admin.

**Login flow:**
1. Username + password → Payd Auth → session token
2. Auto-request OTP → sent to user's email
3. OTP verification → auth token + refresh token (JWT)
4. JWT `is_admin` claim checked + username whitelist (`ALLOWED_USERNAMES` env var)

**Token management:**
- Auth token stored in localStorage (`sentinel_admin_token`)
- Refresh token stored alongside (`sentinel_admin_refresh`)
- On 401/403: API interceptor attempts token refresh before logging out
- Router guard checks JWT expiry + is_admin claim on every navigation

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

## Environment Variables

### Backend (`sentinel-api/.env`)

| Variable | Description | Example |
|----------|-------------|---------|
| `APP_ENV` | Environment (development/production) | `production` |
| `SECRET_KEY` | Application secret key | `your-secret-key` |
| `DATABASE_URL` | SQLite connection string | `sqlite+aiosqlite:////data/sentinel.db` |
| `PAYD_AUTH_URL` | Payd Auth base URL | `https://auth.payd.money` |
| `CORS_ORIGINS` | Allowed CORS origins (comma-separated) | `https://sentinel.paydlabs.com` |
| `PG_ADMIN_HOST` | Managed PostgreSQL host | `dbaas-db-xxx.db.ondigitalocean.com` |
| `PG_ADMIN_PORT` | Managed PostgreSQL port | `25060` |
| `PG_ADMIN_USER` | Managed PostgreSQL admin user | `doadmin` |
| `PG_ADMIN_PASSWORD` | Managed PostgreSQL password | `...` |
| `PG_ADMIN_DATABASE` | Default database to connect to | `defaultdb` |
| `PG_ADMIN_SSLMODE` | SSL mode for PostgreSQL | `require` |
| `ALLOWED_USERNAMES` | Comma-separated login whitelist | `benaiah,vincentee,snow` |
| `ENCRYPTION_KEY` | Fernet key for env var encryption | `...` |

## Deployment

### CI/CD (GitHub Actions)

Push to `main` triggers the deploy workflow (`.github/workflows/deploy.yml`):

1. Build two Docker images (API + UI)
2. Push to GHCR (`ghcr.io/getpayd-tech/sentinel-api`, `ghcr.io/getpayd-tech/sentinel-ui`)
3. SSH to server, pull new images, recreate containers
4. Health check to verify API is responding

### Manual Server Deploy

```bash
ssh deploy@46.101.240.141
cd /apps/sentinel
docker compose -f docker-compose.prod.yml pull
docker compose -f docker-compose.prod.yml up -d
docker ps  # verify containers are healthy
```

### Adding a New Service to Sentinel

1. Register the project via Sentinel UI (Projects → New Project) or scan existing `/apps/` dirs
2. Sentinel generates a webhook secret for the project
3. In the project's GitHub repo, replace the SSH deploy step with:

```yaml
- name: Trigger Sentinel Deploy
  run: |
    curl -X POST https://sentinel.paydlabs.com/api/v1/deployments/webhook \
      -H "X-Hub-Signature-256: sha256=$(echo -n '${{ toJSON(github.event) }}' | openssl dgst -sha256 -hmac '${{ secrets.SENTINEL_WEBHOOK_SECRET }}' | awk '{print $2}')" \
      -H "Content-Type: application/json" \
      -d '{"project": "my-project", "image_tag": "${{ github.sha }}", "triggered_by": "${{ github.actor }}"}'
```

4. Add `SENTINEL_WEBHOOK_SECRET` to the repo's GitHub Secrets
5. Remove old SSH deploy secrets (`DROPLET_IP`, `DROPLET_USER`, `DROPLET_SSH_KEY`)

## Project Structure

```
payd-labs-sentinel/
├── sentinel-api/
│   └── app/
│       ├── main.py              # FastAPI app with lifespan
│       ├── config.py            # pydantic-settings config
│       ├── database.py          # SQLAlchemy async (aiosqlite)
│       ├── auth.py              # require_admin dependency
│       ├── models/              # SQLAlchemy models
│       ├── schemas/             # Pydantic request/response
│       ├── api/v1/              # Route handlers
│       ├── services/            # Business logic
│       └── tasks/               # APScheduler background jobs
├── sentinel-ui/
│   └── src/
│       ├── views/               # Page components
│       ├── components/          # Reusable UI components
│       ├── services/            # API client functions
│       ├── stores/              # Pinia stores (auth, theme)
│       ├── styles/globals.css   # Design system CSS variables
│       └── router/              # Vue Router with auth guards
├── docker-compose.prod.yml      # Production compose
└── .github/workflows/deploy.yml # CI/CD
```

## API Endpoints

All endpoints require `x-auth-token` header with a valid admin JWT (except `/auth/*` and `/health`).

| Group | Prefix | Key Endpoints |
|-------|--------|---------------|
| Auth | `/api/v1/auth` | POST `/login`, `/request-otp`, `/verify-otp`, `/refresh`; GET `/me` |
| Dashboard | `/api/v1/dashboard` | GET `/stats`, `/health` |
| Services | `/api/v1/services` | GET list, `/{name}`; POST `/{name}/restart`, `/stop`, `/start`; GET `/{name}/logs` |
| Deployments | `/api/v1/deployments` | GET list; POST `/{project_id}/deploy`, `/rollback`, `/webhook` |
| Projects | `/api/v1/projects` | CRUD; POST `/scan`, `/{id}/provision` |
| Database | `/api/v1/database` | GET `/databases`, `/databases/{name}/tables`, `/databases/{name}/tables/{table}`; POST `/databases/{name}/query`, `/databases` |
| Domains | `/api/v1/domains` | CRUD; POST `/reload` |
| Logs | `/api/v1/logs` | GET aggregated logs with filters |
| System | `/api/v1/system` | GET `/metrics` |
| Audit | `/api/v1/audit` | GET paginated audit log |

## Design System

Follows the Payd design system (matching Stables admin):
- **Colors:** Navy `#10263E`, Accent Green `#18D26E`
- **Fonts:** Space Grotesk (headings), Nunito (body)
- **Dark mode:** CSS variables that auto-adapt (bg-surface, text-text, border-border)
- **Components:** Card, Badge, Button, Input, Modal, PageHeader

---

## Migration Plan: Moving Existing Services to Sentinel

### Current State
8 projects deployed across 11 Docker containers, each with its own GitHub Actions workflow that SSHs directly to the server. SSH keys are scattered across GitHub repos.

### Target State
All projects registered in Sentinel. Deployments triggered via webhook from GitHub Actions — no SSH keys needed, just one `SENTINEL_WEBHOOK_SECRET` per project.

### Migration Steps Per Project

| Step | Action | Risk |
|------|--------|------|
| 1 | **Scan** existing projects in Sentinel (Projects → Scan Existing) | None — read-only |
| 2 | **Verify** project metadata is correct (compose path, container names) | None |
| 3 | **Generate** webhook secret for the project (auto-created on scan) | None |
| 4 | **Add** `SENTINEL_WEBHOOK_SECRET` to the project's GitHub repo secrets | None |
| 5 | **Update** the repo's deploy workflow to use the Sentinel webhook curl instead of SSH | Low — test on a non-critical project first |
| 6 | **Remove** old SSH secrets (`DROPLET_IP`, `DROPLET_USER`, `DROPLET_SSH_KEY`) from GitHub | None after step 5 is verified |
| 7 | **Test** by pushing a commit and verifying Sentinel handles the deployment | Low |

### Recommended Migration Order

1. **sentinel** (this project) — already using Sentinel CI/CD
2. **bradar** — low traffic, good test candidate
3. **noni** (noni-api, noni-ui) — monitoring tool, low risk
4. **payd-connect** (api + docs) — core service, migrate after confidence built
5. **payd-shops** (api + ui) — production service
6. **payd-stables** — production service, migrate last

### Post-Migration Cleanup

After all projects are migrated:
1. Remove the `deploy` user's SSH authorized keys for old GitHub Actions IP ranges
2. Rotate the `deploy` user's SSH key (the one used by Sentinel's own CI/CD remains)
3. Update UFW rules if any were SSH-specific
4. Archive old workflow files in each repo
