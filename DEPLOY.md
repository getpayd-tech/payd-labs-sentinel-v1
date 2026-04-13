# Deploying with Sentinel

This guide covers how to deploy any project to the Payd Labs server using Sentinel. No SSH keys needed - just one webhook secret per project.

Also available in-app at [sentinel.paydlabs.com/docs](https://sentinel.paydlabs.com/docs).

---

## Overview

Sentinel handles deployment server-side. Your repo's CI/CD only needs to:

1. Build a Docker image
2. Push it to GHCR
3. Send a webhook to Sentinel

Sentinel then pulls the image, starts the containers, runs health checks, and auto-rolls back on failure.

```
GitHub Actions                             Sentinel
─────────────                              ────────
Build image → Push to GHCR
POST /deployments/webhook  ──────────→     Verify HMAC signature
                                           docker compose pull
                                           docker compose up -d
                                           Health check (60s retry)
                                           If unhealthy → rollback
                                           Record deployment in DB
```

---

## Step 1: Provision the Project with the Deploy Wizard

Go to **[sentinel.paydlabs.com/projects/deploy-wizard](https://sentinel.paydlabs.com/projects/deploy-wizard)**.

The wizard walks you through 6 steps:

| Step | What you enter | What Sentinel does |
|------|---------------|-------------------|
| **1. Project Type** | FastAPI, Vue, Blended (API+UI), Nuxt, or Laravel | Sets defaults (port, health endpoint, suggested env vars) |
| **2. Repository** | GitHub repo (e.g. `getpayd-tech/my-app`) | Auto-derives project name, GHCR image path |
| **3. Domain & TLS** | Domain + TLS mode + optional custom Caddy routes | Adds route to Caddyfile, reloads Caddy |
| **4. Database** | Whether to create a PostgreSQL database | Creates DB + user on managed cluster |
| **5. Environment** | Key-value pairs or bulk-paste a `.env` file | Writes `.env` to `/apps/{project}/` |
| **6. Review & Deploy** | Compose filename, first deploy toggle | Creates project dir, writes compose file, optionally pulls + starts containers |

After provisioning, the wizard shows:
- **Webhook secret** - copy this for Step 2
- **Generated workflow** - copy this for Step 2
- **Step-by-step results** - which steps succeeded/failed

> **Note:** "Pull & start containers" (steps 7-9) will fail for brand new projects because the GHCR images don't exist yet. This is normal - the images get created when CI/CD runs for the first time in Step 3.

---

## Step 2: Add the CI/CD Workflow to Your Repo

Create `.github/workflows/deploy.yml` in your project repo. The wizard generates this for you - just copy it.

### Single-container project (FastAPI, Vue, Nuxt, or Laravel)

```yaml
name: Deploy

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

      - uses: docker/build-push-action@v6
        with:
          context: .
          push: true
          tags: |
            ghcr.io/getpayd-tech/MY-APP:latest
            ghcr.io/getpayd-tech/MY-APP:${{ github.sha }}
          cache-from: type=gha
          cache-to: type=gha,mode=max

      - name: Deploy via Sentinel
        run: |
          PAYLOAD='{"project":"MY-APP","image_tag":"${{ github.sha }}","triggered_by":"${{ github.actor }}"}'
          SIGNATURE=$(echo -n "$PAYLOAD" | openssl dgst -sha256 -hmac "${{ secrets.SENTINEL_WEBHOOK_SECRET }}" | awk '{print $2}')
          curl -sf -X POST https://sentinel.paydlabs.com/api/v1/deployments/webhook \
            -H "X-Hub-Signature-256: sha256=$SIGNATURE" \
            -H "Content-Type: application/json" \
            -d "$PAYLOAD"
```

**Replace** `MY-APP` with your project name (must match what you entered in the wizard).

### Blended project (API + UI - two images)

```yaml
name: Deploy

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

      # API image
      - uses: docker/build-push-action@v6
        with:
          context: .
          file: ./Dockerfile
          push: true
          tags: |
            ghcr.io/getpayd-tech/MY-PROJECT-api:latest
            ghcr.io/getpayd-tech/MY-PROJECT-api:${{ github.sha }}
          cache-from: type=gha,scope=api
          cache-to: type=gha,mode=max,scope=api

      # UI image
      - uses: docker/build-push-action@v6
        with:
          context: ./admin
          push: true
          tags: |
            ghcr.io/getpayd-tech/MY-PROJECT-ui:latest
            ghcr.io/getpayd-tech/MY-PROJECT-ui:${{ github.sha }}
          cache-from: type=gha,scope=ui
          cache-to: type=gha,mode=max,scope=ui

      - name: Deploy via Sentinel
        run: |
          PAYLOAD='{"project":"MY-PROJECT","image_tag":"${{ github.sha }}","triggered_by":"${{ github.actor }}"}'
          SIGNATURE=$(echo -n "$PAYLOAD" | openssl dgst -sha256 -hmac "${{ secrets.SENTINEL_WEBHOOK_SECRET }}" | awk '{print $2}')
          curl -sf -X POST https://sentinel.paydlabs.com/api/v1/deployments/webhook \
            -H "X-Hub-Signature-256: sha256=$SIGNATURE" \
            -H "Content-Type: application/json" \
            -d "$PAYLOAD"
```

**Replace** `MY-PROJECT` with your project name. Adjust `context` and `file` paths to match your repo layout (e.g. API at root `./Dockerfile`, UI at `./admin/Dockerfile`).

---

## Step 3: Add the Webhook Secret to GitHub

Go to your repo → **Settings → Secrets and variables → Actions** → **New repository secret**.

| Secret name | Value |
|-------------|-------|
| `SENTINEL_WEBHOOK_SECRET` | The webhook secret shown after the wizard completes (also visible on the project detail page in Sentinel) |

**That's it.** No SSH keys, no server IP, no deploy user. `GITHUB_TOKEN` is provided automatically by GitHub Actions.

---

## Step 4: DNS (if needed)

Point your domain to the server:

```
my-app.paydlabs.com  →  A record  →  46.101.240.141
```

If `*.paydlabs.com` already has a wildcard A record pointing to the server, no DNS change is needed.

---

## Step 5: Push to Deploy

Push a commit to `main`. GitHub Actions will:

1. Build your Docker image(s)
2. Push to GHCR (`ghcr.io/getpayd-tech/...`)
3. Send the webhook to Sentinel
4. Sentinel pulls the new image, recreates containers, and health-checks

Track it in Sentinel at **Deployments** - you'll see the status, duration, logs, and who triggered it.

---

## What Sentinel Does on Webhook

When Sentinel receives the webhook POST:

1. **Verifies HMAC-SHA256 signature** - rejects if the secret doesn't match
2. **Looks up the project** by name - rejects if not registered
3. **Creates a deployment record** (status: `in_progress`)
4. **Runs `docker compose pull`** in the project's `/apps/{name}/` directory
5. **Runs `docker compose up -d`** to recreate containers with new images
6. **Health check** - hits `https://{domain}{health_endpoint}` every 5 seconds for up to 60 seconds
7. **If healthy** → deployment status set to `success`
8. **If unhealthy** → automatic rollback (`docker compose up -d` with previous config), status set to `failed`
9. **Records everything** - start time, end time, duration, full logs, who triggered it

---

## Dockerfile Requirements

Your project needs a `Dockerfile` for CI/CD to build the image.

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

With a `Caddyfile` in the same directory for SPA routing:

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

### Laravel (PHP)

```dockerfile
FROM php:8.3-fpm AS builder
RUN apt-get update && apt-get install -y git unzip libpq-dev \
    && docker-php-ext-install pdo pdo_pgsql
COPY --from=composer:latest /usr/bin/composer /usr/bin/composer
WORKDIR /app
COPY . .
RUN composer install --no-dev --optimize-autoloader

FROM php:8.3-fpm
RUN apt-get update && apt-get install -y libpq-dev nginx \
    && docker-php-ext-install pdo pdo_pgsql
COPY --from=builder /app /var/www/html
EXPOSE 8000
CMD ["php", "artisan", "serve", "--host=0.0.0.0", "--port=8000"]
```

---

## Migrating from SSH-based CI/CD to Sentinel

> **Status (April 2026):** All 10 services have been migrated to webhook-based deploys. Legacy `DROPLET_*` secrets have been removed from all repos except sentinel itself (which keeps SSH as the primary deploy path due to a self-deploy race condition). The steps below are preserved for reference if new SSH-based repos are created in the future.

Most existing Payd repos deploy via SSH (`appleboy/ssh-action`), which requires `DROPLET_IP`, `DROPLET_USER`, and `DROPLET_SSH_KEY` secrets. Here's how to migrate to the Sentinel webhook flow.

### What changes

| Before (SSH) | After (Sentinel webhook) |
|---|---|
| 3 secrets: `DROPLET_IP`, `DROPLET_USER`, `DROPLET_SSH_KEY` | 1 secret: `SENTINEL_WEBHOOK_SECRET` |
| Workflow SSHs into server, runs `docker compose pull/up` | Workflow sends HTTP POST, Sentinel runs pull/up server-side |
| No centralized deploy history | All deploys tracked in Sentinel with logs, timing, rollback |
| Each repo manages its own health check script | Sentinel runs health checks automatically |

### Step-by-step migration

**1. Register the project in Sentinel**

Go to Sentinel → Projects → Scan Existing. This auto-discovers projects in `/apps/` that have a `docker-compose.yml`. Click into the project and fill in any missing details (GitHub repo, domain, health endpoint).

**2. Get the webhook secret**

On the project detail page, copy the **webhook secret**. Every project gets one auto-generated when it's registered.

**3. Add the webhook secret to GitHub**

Go to your repo → Settings → Secrets → Actions → New repository secret:

| Name | Value |
|------|-------|
| `SENTINEL_WEBHOOK_SECRET` | *(paste the webhook secret from step 2)* |

**4. Replace the SSH deploy step in your workflow**

Find the deploy step in `.github/workflows/deploy.yml`. It currently looks like this:

```yaml
# OLD - remove this
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
      echo "$GHCR_TOKEN" | docker login ghcr.io -u getpayd-tech --password-stdin
      cd /apps/my-project
      docker compose pull
      docker compose up -d
      # ... health check ...
      docker image prune -f
```

Replace it with:

```yaml
# NEW - add this
- name: Deploy via Sentinel
  run: |
    PAYLOAD='{"project":"my-project","image_tag":"${{ github.sha }}","triggered_by":"${{ github.actor }}"}'
    SIGNATURE=$(echo -n "$PAYLOAD" | openssl dgst -sha256 -hmac "${{ secrets.SENTINEL_WEBHOOK_SECRET }}" | awk '{print $2}')
    curl -sf -X POST https://sentinel.paydlabs.com/api/v1/deployments/webhook \
      -H "X-Hub-Signature-256: sha256=$SIGNATURE" \
      -H "Content-Type: application/json" \
      -d "$PAYLOAD"
```

Make sure the `"project"` value matches the project name in Sentinel exactly.

**5. Remove old secrets**

After verifying the webhook deploy works (push a commit, check Sentinel → Deployments), remove the old secrets from the repo:
- `DROPLET_IP`
- `DROPLET_USER`
- `DROPLET_SSH_KEY`

**6. Verify**

- Push a commit to `main`
- Watch GitHub Actions - the build step should succeed, then the webhook step
- Check Sentinel → Deployments - a new entry should appear with status `success`
- Visit the project's domain to confirm it's running

---

## Troubleshooting

### Webhook returns 401 "Invalid webhook signature"
- Check that `SENTINEL_WEBHOOK_SECRET` in GitHub matches the value shown on the project's detail page in Sentinel
- Make sure the project name in the payload matches exactly (case-sensitive)

### Webhook returns 404 "Project not found"
- The project name in the webhook payload must match the `name` field in Sentinel (not the display name)
- Run "Scan Existing" or create the project via the wizard first

### `docker compose pull` fails
- The GHCR images must be pushed before the webhook fires (build step must come before deploy step in the workflow)
- Check that the image names in `docker-compose.yml` match what CI/CD pushes to GHCR

### Health check fails
- The health endpoint must respond with HTTP 2xx within 60 seconds of containers starting
- Check the container logs in Sentinel → Services → click the container → Logs
- If the app needs more startup time, the health check retries 12 times with 5-second intervals

### Containers not showing in Sentinel
- Make sure containers are on the `proxy` Docker network (required for Caddy routing)
- Check that `docker-compose.yml` has `networks: proxy: external: true`

---

## Custom Domains (On-Demand TLS)

Sentinel supports dynamic custom domains for any project. This lets services like OneLink or Payd Shops allow their users to bring custom domains with automatic TLS certificate provisioning.

### How it works

1. Sentinel stores custom domain records in its `custom_domains` table
2. Each registered domain gets an explicit Caddy block with `tls { on_demand }`
3. Caddy calls Sentinel's `/internal/domain-check?domain={host}` before issuing any cert
4. Sentinel returns 200 if the domain is active, 404 otherwise
5. Traffic routes directly to the project's configured upstream container

### Setup for a project

**1. Enable custom domains on the project**

In Sentinel UI -> Projects -> click the project -> Edit:
- Toggle **Enable custom domains** on
- Set **Custom Domain Upstream** to the container:port (e.g. `payd-labs-one-link:8000`)
- Save

**2. Generate a service API key**

On the project detail page, or via API:

```bash
curl -X POST https://sentinel.paydlabs.com/api/v1/projects/{project_id}/generate-service-key \
  -H "x-auth-token: YOUR_ADMIN_TOKEN"
```

Store the returned `service_api_key` in the service's environment.

**3. Register domains from your service backend**

```bash
curl -X POST https://sentinel.paydlabs.com/api/v1/custom-domains \
  -H "X-Service-Key: sak_..." \
  -H "Content-Type: application/json" \
  -d '{"domain": "mybrand.com"}'
```

Returns the domain record with `status: "active"` if the Caddy block was written and reloaded successfully.

**4. Tell the user to point DNS**

The user creates an A record pointing their domain to `46.101.240.141`. Caddy provisions a Let's Encrypt cert automatically on first request.

### Custom domains API reference

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/api/v1/custom-domains` | X-Service-Key | Register a domain for the project |
| GET | `/api/v1/custom-domains` | X-Service-Key | List domains for the project |
| DELETE | `/api/v1/custom-domains/{domain}` | X-Service-Key | Remove a domain |
| GET | `/api/v1/custom-domains/all` | Admin JWT | List all domains (admin) |
| DELETE | `/api/v1/custom-domains/admin/{domain}` | Admin JWT | Force-remove any domain (admin) |
| GET | `/internal/domain-check?domain={host}` | None (internal) | Caddy ask endpoint |

---

## Using the CLI

Sentinel includes a terminal CLI for managing deployments without the web UI.

### Install

```bash
cd payd-labs-sentinel
python3.12 -m venv sentinel-cli/.venv
source sentinel-cli/.venv/bin/activate
pip install -e sentinel-cli/
```

### First-time login

```bash
sentinel login
```

Enter your Payd Auth username, password, and OTP code. The CLI caches tokens at `~/.sentinel/credentials.json` and auto-refreshes them. You can also skip the login flow by setting `SENTINEL_TOKEN` env var with a valid admin JWT.

### Deploy from the terminal

```bash
sentinel deploy my-project          # Deploy latest
sentinel deploy my-project --tag v2 # Deploy specific tag
sentinel deployments -p my-project  # Check history
sentinel logs my-container --tail 50 --since 1h
sentinel status                     # All projects + last deploy
```

### MCP server for AI agents

After installing the CLI package, configure Claude Code to use the MCP server:

```json
{
  "mcpServers": {
    "sentinel": {
      "command": "/path/to/sentinel-cli/.venv/bin/sentinel-mcp"
    }
  }
}
```

Agents can then call tools like `sentinel_deploy`, `sentinel_get_logs`, `sentinel_list_projects`, etc.

---

## Reference

### Webhook endpoint

```
POST https://sentinel.paydlabs.com/api/v1/deployments/webhook

Headers:
  X-Hub-Signature-256: sha256={HMAC-SHA256 of body using webhook secret}
  Content-Type: application/json

Body:
  {
    "project": "my-project-name",
    "image_tag": "abc123",
    "triggered_by": "github-username"
  }
```

### Server directory structure

```
/apps/
├── caddy/
│   └── Caddyfile           # Reverse proxy config (managed by Sentinel)
├── sentinel/               # Sentinel itself
├── my-project/
│   ├── docker-compose.yml  # Generated by wizard
│   └── .env                # Written by wizard
└── another-project/
    ├── docker-compose.yml
    └── .env
```

### Supported project types

| Type | Containers | Default port | Health endpoint | Use case |
|------|-----------|-------------|-----------------|----------|
| FastAPI | 1 | 8000 | `/health` | Python API |
| Vue | 1 | 80 | N/A | SPA served by Caddy |
| Blended | 2 (api + ui) | 8000 + 80 | `/health` | FastAPI + Vue |
| Nuxt | 1 | 3000 | `/api/health` | SSR Node.js |
| Laravel | 1 | 8000 | `/health` | PHP API |
