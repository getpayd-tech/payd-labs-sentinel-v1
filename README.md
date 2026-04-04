# Sentinel - Payd Labs Server Management Platform

Sentinel is a self-hosted DevOps portal for Payd Labs' infrastructure. It consolidates container management, deployments, database administration, domain routing, and system monitoring into a single dashboard — replacing per-repo SSH-based GitHub Actions with a centralized deployment system.

**Live:** [sentinel.paydlabs.com](https://sentinel.paydlabs.com)

---

## Architecture

```
Browser → Caddy (TLS termination, reverse proxy)
              ├── /api/* → sentinel-api (FastAPI, port 8000)
              └── /*     → sentinel-ui  (Vue SPA, port 80)

sentinel-api
  ├── Docker socket (/var/run/docker.sock — container management + deploys)
  ├── /apps/ volume (compose files, .env files for all projects)
  ├── SQLite database (/data/sentinel.db)
  ├── Docker CLI (docker compose pull/up for deployments)
  └── asyncpg → DigitalOcean Managed PostgreSQL (port 25060, SSL)
```

**Server:** DigitalOcean droplet, Ubuntu 24.04, 4 CPU / 8GB RAM / 154GB disk, IP `46.101.240.141`

**Three Sentinel containers** on the shared `proxy` network:
- **sentinel-api** — FastAPI backend (Python 3.12)
- **sentinel-ui** — Vue 3 SPA served by Caddy Alpine
- **sentinel-redis** — Redis 7 Alpine

---

## Features

| Feature | Description |
|---------|-------------|
| **Dashboard** | Container health, CPU/RAM/disk metrics, real-time refresh |
| **Services** | List, restart, stop, start Docker containers; view logs |
| **Deploy Wizard** | End-to-end guided project setup: compose, .env, Caddy, database, pull, start, health check |
| **Deployments** | Webhook-triggered deploys, manual deploy, rollback, history |
| **Projects** | Register projects, scan existing /apps/, provision new ones |
| **Database** | Browse managed PostgreSQL: databases, tables, schemas, run SELECT queries |
| **Domains** | Parse/edit Caddyfile routes with TLS management (ACME/Cloudflare DNS), reload Caddy |
| **Logs** | Aggregated log viewer across all containers with search/filter |
| **System** | CPU, memory, disk, network metrics (psutil) |
| **Audit** | Full action history: who did what, when, from where |

---

## Deploying a New Project (End-to-End Guide)

This guide uses `payd-labs-offline` as a real example — a blended FastAPI + Vue project.

### Step 1: Run the Deploy Wizard

Go to **[sentinel.paydlabs.com/projects/deploy-wizard](https://sentinel.paydlabs.com/projects/deploy-wizard)** and fill in:

1. **Project Type** — Select the stack (FastAPI, Vue, Blended, Nuxt, or Laravel)
2. **Repository** — Enter the GitHub repo (e.g. `getpayd-tech/payd-labs-offline`)
   - Project name, display name, and GHCR image paths are auto-derived
   - Set health endpoint (default: `/health`)
3. **Domain & TLS** — Enter the domain (e.g. `offline.paydlabs.com`)
   - TLS mode: Auto ACME (default), Cloudflare DNS (for wildcards), or Off
   - Optionally add custom Caddy routes (e.g. `/ingest/*`, `/callbacks/*` → API container)
4. **Database** — Toggle "Create PostgreSQL database" if needed, enter name
5. **Environment Variables** — Add key/value pairs or use "Bulk Paste" to paste an entire `.env` file
6. **Review & Deploy** — Preview the generated `docker-compose.yml`, Caddyfile block, and GitHub Actions workflow
   - Select compose filename (`docker-compose.yml` or `docker-compose.prod.yml`)
   - Toggle "Pull & start containers" (only works if GHCR images already exist)
   - Click **Provision & Deploy**

The wizard executes 9 steps:
1. Create/update project record in Sentinel DB
2. Write `docker-compose.yml` to `/apps/{project-name}/`
3. Write `.env` file
4. Add Caddy domain route to Caddyfile
5. Reload Caddy
6. Create PostgreSQL database (if requested)
7. Pull Docker images from GHCR
8. Start containers (`docker compose up -d`)
9. Health check verification

**Note:** Steps 7-9 will fail if the GHCR images don't exist yet. This is expected for brand new projects — the images get built and pushed when you set up CI/CD (Step 2 below).

### Step 2: Set Up CI/CD in the Project Repo

The wizard generates a GitHub Actions workflow. Copy it to your project repo.

#### For a Blended Project (API + UI)

Create `.github/workflows/deploy.yml` in the project repo:

```yaml
name: Deploy Offline

on:
  push:
    branches: [main]

jobs:
  build-and-deploy:
    runs-on: ubuntu-latest
    permissions:
      contents: read
      packages: write

    steps:
      - uses: actions/checkout@v4

      - uses: docker/login-action@v3
        with:
          registry: ghcr.io
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}

      - uses: docker/setup-buildx-action@v3

      # ── Build API image ──
      - name: Build and push API
        uses: docker/build-push-action@v6
        with:
          context: .
          file: ./Dockerfile           # or ./api/Dockerfile if monorepo
          push: true
          tags: |
            ghcr.io/getpayd-tech/payd-labs-offline-api:latest
            ghcr.io/getpayd-tech/payd-labs-offline-api:${{ github.sha }}
          cache-from: type=gha,scope=api
          cache-to: type=gha,mode=max,scope=api

      # ── Build UI image ──
      - name: Build and push UI
        uses: docker/build-push-action@v6
        with:
          context: ./admin              # or ./ui, ./frontend — wherever the Vue app is
          push: true
          tags: |
            ghcr.io/getpayd-tech/payd-labs-offline-ui:latest
            ghcr.io/getpayd-tech/payd-labs-offline-ui:${{ github.sha }}
          cache-from: type=gha,scope=ui
          cache-to: type=gha,mode=max,scope=ui

      # ── Deploy via SSH ──
      - name: Deploy to server
        uses: appleboy/ssh-action@v1
        env:
          GHCR_TOKEN: ${{ secrets.GITHUB_TOKEN }}
        with:
          host: ${{ secrets.DROPLET_IP }}
          username: ${{ secrets.DROPLET_USER }}
          key: ${{ secrets.DROPLET_SSH_KEY }}
          envs: GHCR_TOKEN
          script: |
            set -e
            echo "$GHCR_TOKEN" | docker login ghcr.io -u getpayd-tech --password-stdin
            cd /apps/payd-labs-offline
            docker compose pull
            docker compose up -d

            echo "Waiting for health check..."
            for i in $(seq 1 12); do
              if curl -sf http://localhost:8000/health > /dev/null 2>&1; then
                echo "API is healthy!"
                break
              fi
              if [ "$i" -eq 12 ]; then
                echo "Health check failed after 60s"
                docker logs payd-labs-offline-api --tail 50
                exit 1
              fi
              echo "Attempt $i/12 — waiting 5s..."
              sleep 5
            done

            docker image prune -f
            echo "Deployed successfully"
```

#### For a Single-Container Project (FastAPI only, Vue only, Nuxt, Laravel)

```yaml
name: Deploy My App

on:
  push:
    branches: [main]

jobs:
  build-and-deploy:
    runs-on: ubuntu-latest
    permissions:
      contents: read
      packages: write

    steps:
      - uses: actions/checkout@v4

      - uses: docker/login-action@v3
        with:
          registry: ghcr.io
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}

      - uses: docker/setup-buildx-action@v3

      - name: Build and push
        uses: docker/build-push-action@v6
        with:
          context: .
          push: true
          tags: |
            ghcr.io/getpayd-tech/my-app:latest
            ghcr.io/getpayd-tech/my-app:${{ github.sha }}
          cache-from: type=gha
          cache-to: type=gha,mode=max

      - name: Deploy to server
        uses: appleboy/ssh-action@v1
        env:
          GHCR_TOKEN: ${{ secrets.GITHUB_TOKEN }}
        with:
          host: ${{ secrets.DROPLET_IP }}
          username: ${{ secrets.DROPLET_USER }}
          key: ${{ secrets.DROPLET_SSH_KEY }}
          envs: GHCR_TOKEN
          script: |
            set -e
            echo "$GHCR_TOKEN" | docker login ghcr.io -u getpayd-tech --password-stdin
            cd /apps/my-app
            docker compose pull
            docker compose up -d

            echo "Waiting for health check..."
            for i in $(seq 1 12); do
              if curl -sf http://localhost:8000/health > /dev/null 2>&1; then
                echo "Healthy!"
                break
              fi
              [ "$i" -eq 12 ] && echo "Health check failed" && exit 1
              sleep 5
            done

            docker image prune -f
```

### Step 3: Add GitHub Secrets

Go to your repo's **Settings → Secrets and variables → Actions** and add:

| Secret | Value |
|--------|-------|
| `DROPLET_IP` | `46.101.240.141` |
| `DROPLET_USER` | `deploy` |
| `DROPLET_SSH_KEY` | The SSH private key for the `deploy` user (same key used across all Payd projects) |

`GITHUB_TOKEN` is automatically available — no need to add it.

The Sentinel wizard shows all these values with copy buttons after provisioning.

### Step 4: DNS

Point the domain to the server IP:

```
offline.paydlabs.com → A record → 46.101.240.141
```

If `*.paydlabs.com` is already a wildcard A record pointing to the server, no DNS change is needed.

### Step 5: First Deploy

Push to `main` on your project repo. GitHub Actions will:

1. Build Docker image(s) and push to GHCR
2. SSH into the server
3. `docker compose pull` → pulls the new images
4. `docker compose up -d` → starts/recreates containers
5. Health check → verifies the service is responding
6. Image cleanup → removes old unused images

After the first successful deploy:
- Visit `https://offline.paydlabs.com/health` to verify
- Visit `https://offline.paydlabs.com` to see the UI
- Check Sentinel dashboard to see the new containers

### Step 6: Verify in Sentinel

1. **Dashboard** — New containers should appear with health status
2. **Services** — Click the container name to see logs, restart, etc.
3. **Deployments** — Future deploys will be tracked here (if using webhook mode)

---

## Dockerfile Requirements

For the CI/CD workflow to build images, each project needs a `Dockerfile`:

### FastAPI (Python)

```dockerfile
FROM python:3.12-slim AS builder
RUN apt-get update && apt-get install -y gcc libpq-dev && rm -rf /var/lib/apt/lists/*
WORKDIR /build
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

FROM python:3.12-slim
RUN apt-get update && apt-get install -y curl libpq5 && rm -rf /var/lib/apt/lists/*
COPY --from=builder /install /usr/local
WORKDIR /app
COPY . .
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### Vue / Vite (served by Caddy)

```dockerfile
FROM node:20-alpine AS build
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
RUN npm run build

FROM caddy:2-alpine
COPY --from=build /app/dist /srv
COPY Caddyfile /etc/caddy/Caddyfile
EXPOSE 80
```

With a `Caddyfile` for SPA routing:
```
:80 {
    root * /srv
    try_files {path} /index.html
    file_server
}
```

### Nuxt 3 (SSR)

```dockerfile
FROM node:20-alpine AS build
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
RUN npm run build

FROM node:20-alpine
WORKDIR /app
COPY --from=build /app/.output .output
EXPOSE 3000
CMD ["node", ".output/server/index.mjs"]
```

---

## Authentication

Sentinel uses Payd Auth (`auth.payd.money`) — the same auth system as Stables admin.

**Login flow:**
1. Username + password → Payd Auth → session token
2. Auto-request OTP → sent to user's email
3. OTP verification → auth token + refresh token (JWT)
4. JWT `is_admin` claim checked + username whitelist (`ALLOWED_USERNAMES` env var)

**Token management:**
- On 401/403: API interceptor attempts token refresh before logging out
- Router guard checks JWT expiry + is_admin claim on every navigation

---

## Environment Variables (Sentinel Server)

### Backend (`/apps/sentinel/.env`)

| Variable | Description | Example |
|----------|-------------|---------|
| `APP_ENV` | Environment | `production` |
| `SECRET_KEY` | Application secret key | `your-secret-key` |
| `DATABASE_URL` | SQLite connection | `sqlite+aiosqlite:////data/sentinel.db` |
| `PAYD_AUTH_URL` | Payd Auth base URL | `https://auth.payd.money` |
| `CORS_ORIGINS` | Allowed CORS origins | `https://sentinel.paydlabs.com` |
| `PG_ADMIN_HOST` | Managed PostgreSQL host | `dbaas-db-xxx.db.ondigitalocean.com` |
| `PG_ADMIN_PORT` | Managed PostgreSQL port | `25060` |
| `PG_ADMIN_USER` | PostgreSQL admin user | `doadmin` |
| `PG_ADMIN_PASSWORD` | PostgreSQL admin password | `...` |
| `PG_ADMIN_DATABASE` | Default database | `defaultdb` |
| `PG_ADMIN_SSLMODE` | SSL mode | `require` |
| `ALLOWED_USERNAMES` | Login whitelist | `benaiah,vincentee,snow` |

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

## API Endpoints

All endpoints require `x-auth-token` header with a valid admin JWT (except `/auth/*` and `/health`).

| Group | Prefix | Key Endpoints |
|-------|--------|---------------|
| Auth | `/api/v1/auth` | POST `/login`, `/request-otp`, `/verify-otp`, `/refresh`; GET `/me` |
| Dashboard | `/api/v1/dashboard` | GET `/stats`, `/health` |
| Services | `/api/v1/services` | GET list, `/{name}`; POST `/{name}/restart`, `/stop`, `/start`; GET `/{name}/logs` |
| Deployments | `/api/v1/deployments` | GET list; POST `/{project_id}/deploy`, `/rollback`, `/webhook` |
| Projects | `/api/v1/projects` | CRUD; POST `/scan`, `/wizard`, `/wizard/preview`; GET `/wizard/defaults/{type}` |
| Database | `/api/v1/database` | GET `/databases`, `/databases/{name}/tables`; POST `/databases/{name}/query`, `/databases` |
| Domains | `/api/v1/domains` | CRUD; POST `/reload` |
| Logs | `/api/v1/logs` | GET aggregated logs with filters |
| System | `/api/v1/system` | GET `/metrics` |
| Audit | `/api/v1/audit` | GET paginated audit log |

---

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
│       ├── services/            # Business logic (docker, caddy, wizard, etc.)
│       ├── templates/           # Compose + workflow templates
│       │   ├── compose/         # fastapi.yml, vue.yml, blended.yml, nuxt.yml, laravel.yml
│       │   └── workflow/        # deploy.yml template
│       └── tasks/               # APScheduler background jobs
├── sentinel-ui/
│   └── src/
│       ├── views/               # Page components (incl. DeployWizardView)
│       ├── components/          # Reusable UI components
│       ├── services/            # API client functions
│       ├── stores/              # Pinia stores (auth, theme)
│       ├── styles/globals.css   # Design system CSS variables
│       └── router/              # Vue Router with auth guards
├── docker-compose.prod.yml      # Production compose (Sentinel itself)
└── .github/workflows/deploy.yml # Sentinel CI/CD
```

---

## Design System

Follows the Payd design system (matching Stables admin):
- **Colors:** Navy `#10263E`, Accent Green `#18D26E`
- **Fonts:** Space Grotesk (headings), Nunito (body)
- **Dark mode:** CSS variables auto-adapt (`bg-surface`, `text-text`, `border-border`)
- **Components:** Card, Badge, Button, Input, Modal, PageHeader

---

## Migration Plan: Moving Existing Services to Sentinel

### Current State
9 projects deployed across 14+ Docker containers, each with its own GitHub Actions workflow that SSHs directly to the server.

### Target State
All projects registered in Sentinel. Each project's CI/CD builds images, pushes to GHCR, and deploys via SSH to the server. Sentinel provides the dashboard for monitoring, logs, and management.

### Migration Steps Per Project

| Step | Action | Risk |
|------|--------|------|
| 1 | **Scan** existing projects in Sentinel (Projects → Scan Existing) | None — read-only |
| 2 | **Verify** project metadata is correct (compose path, container names) | None |
| 3 | **Generate** webhook secret for the project (auto-created on scan) | None |
| 4 | **Add** GitHub secrets (`DROPLET_IP`, `DROPLET_USER`, `DROPLET_SSH_KEY`) to the repo | None |
| 5 | **Add/update** the repo's deploy workflow (see templates above) | Low — test on a non-critical project first |
| 6 | **Test** by pushing a commit and verifying the deploy completes | Low |

### Recommended Migration Order

1. **sentinel** — already using CI/CD
2. **payd-labs-offline** — newest project, built for Sentinel from the start
3. **bradar** — low traffic, good test candidate
4. **noni** (noni-api, noni-ui) — monitoring tool, low risk
5. **payd-connect** (api + docs) — core service, migrate after confidence built
6. **payd-shops** (api + ui) — production service
7. **payd-stables** — production service, migrate last

### Post-Migration Cleanup

After all projects are migrated:
1. Standardize compose filenames (all use `docker-compose.yml`)
2. Standardize health check endpoints (all use `/health`)
3. Archive old workflow files in each repo
4. Document each project in Sentinel (domain, repo, containers)
