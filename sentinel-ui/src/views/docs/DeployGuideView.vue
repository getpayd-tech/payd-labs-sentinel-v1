<script setup lang="ts">
import Callout from '@/components/docs/Callout.vue'
import CodeBlock from '@/components/docs/CodeBlock.vue'

const singleWorkflow = `name: Deploy My App

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
          username: \${{ github.actor }}
          password: \${{ secrets.GITHUB_TOKEN }}

      - uses: docker/setup-buildx-action@v3

      - uses: docker/build-push-action@v6
        with:
          context: .
          push: true
          tags: |
            ghcr.io/getpayd-tech/MY-APP:latest
            ghcr.io/getpayd-tech/MY-APP:\${{ github.sha }}
          cache-from: type=gha
          cache-to: type=gha,mode=max

      - name: Deploy via Sentinel
        run: |
          PAYLOAD='{"project":"MY-APP","image_tag":"\${{ github.sha }}","triggered_by":"\${{ github.actor }}"}'
          SIGNATURE=$(echo -n "$PAYLOAD" | openssl dgst -sha256 -hmac "\${{ secrets.SENTINEL_WEBHOOK_SECRET }}" | awk '{print $2}')
          curl -sf -X POST https://sentinel.paydlabs.com/api/v1/deployments/webhook \\
            -H "X-Hub-Signature-256: sha256=$SIGNATURE" \\
            -H "Content-Type: application/json" \\
            -d "$PAYLOAD"`

const blendedWorkflow = `name: Deploy My Project

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
          username: \${{ github.actor }}
          password: \${{ secrets.GITHUB_TOKEN }}
      - uses: docker/setup-buildx-action@v3

      # Build API image
      - uses: docker/build-push-action@v6
        with:
          context: .
          push: true
          tags: |
            ghcr.io/getpayd-tech/MY-PROJECT-api:latest
            ghcr.io/getpayd-tech/MY-PROJECT-api:\${{ github.sha }}
          cache-from: type=gha,scope=api
          cache-to: type=gha,mode=max,scope=api

      # Build UI image
      - uses: docker/build-push-action@v6
        with:
          context: ./admin
          push: true
          tags: |
            ghcr.io/getpayd-tech/MY-PROJECT-ui:latest
            ghcr.io/getpayd-tech/MY-PROJECT-ui:\${{ github.sha }}
          cache-from: type=gha,scope=ui
          cache-to: type=gha,mode=max,scope=ui

      - name: Deploy via Sentinel
        run: |
          PAYLOAD='{"project":"MY-PROJECT","image_tag":"\${{ github.sha }}","triggered_by":"\${{ github.actor }}"}'
          SIGNATURE=$(echo -n "$PAYLOAD" | openssl dgst -sha256 -hmac "\${{ secrets.SENTINEL_WEBHOOK_SECRET }}" | awk '{print $2}')
          curl -sf -X POST https://sentinel.paydlabs.com/api/v1/deployments/webhook \\
            -H "X-Hub-Signature-256: sha256=$SIGNATURE" \\
            -H "Content-Type: application/json" \\
            -d "$PAYLOAD"`

const fastapiDockerfile = `FROM python:3.12-slim AS builder
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
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]`

const vueDockerfile = `FROM node:20-alpine AS build
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
RUN npm run build

FROM caddy:2-alpine
COPY --from=build /app/dist /srv
COPY Caddyfile /etc/caddy/Caddyfile
EXPOSE 80`
</script>

<template>
  <div class="prose">
    <h1>Deploy Guide</h1>
    <p>Step-by-step guide to deploying a new project to the Payd Labs server using Sentinel.</p>

    <h2>Step 1: Run the Deploy Wizard</h2>
    <p>
      Go to <a href="https://sentinel.paydlabs.com/projects/deploy-wizard">Projects &rarr; Deploy Wizard</a> and fill in:
    </p>
    <ol>
      <li><strong>Project Type</strong> - FastAPI, Vue, Blended (API + UI), Nuxt, or Laravel</li>
      <li><strong>Repository</strong> - GitHub repo URL. Name and GHCR image are auto-derived.</li>
      <li><strong>Domain &amp; TLS</strong> - Domain name, TLS mode (ACME / Cloudflare DNS), optional custom Caddy routes.</li>
      <li><strong>Database</strong> - Optionally create a PostgreSQL database on the managed cluster. If selected, <code>DATABASE_URL</code> is auto-populated in your .env file.</li>
      <li><strong>Environment</strong> - Add variables one by one or bulk-paste an entire .env file.</li>
      <li><strong>Review &amp; Deploy</strong> - Preview generated files, provision, optionally pull and start containers.</li>
    </ol>

    <Callout type="info" title="Database URL auto-populated">
      When you select "Create database" in the wizard, Sentinel generates a dedicated user and password,
      creates the database, and automatically writes the <code>DATABASE_URL</code> to your project's .env file.
      No need to construct it manually.
    </Callout>

    <h2>Step 2: Add the CI/CD Workflow</h2>
    <p>Create <code>.github/workflows/deploy.yml</code> in your project repo. The wizard generates this for you.</p>

    <h3>Single container (FastAPI / Vue / Nuxt / Laravel)</h3>
    <CodeBlock :code="singleWorkflow" language="yaml" title="deploy.yml" />
    <p>Replace <code>MY-APP</code> with your project name (must match the wizard).</p>

    <h3>Blended (API + UI - two images)</h3>
    <CodeBlock :code="blendedWorkflow" language="yaml" title="deploy.yml" />
    <p>Replace <code>MY-PROJECT</code> with your project name. Adjust <code>context</code> paths to match your repo.</p>

    <h2>Step 3: Add GitHub Secrets</h2>
    <p>Go to your repo's <strong>Settings &rarr; Secrets and variables &rarr; Actions</strong> and add:</p>
    <table>
      <thead><tr><th>Secret</th><th>Value</th></tr></thead>
      <tbody>
        <tr>
          <td><code>SENTINEL_WEBHOOK_SECRET</code></td>
          <td>From the project detail page in Sentinel (auto-generated)</td>
        </tr>
      </tbody>
    </table>

    <Callout type="success" title="That's it.">
      No SSH keys, no server IP, no deploy user. Sentinel handles deployments server-side via its Docker socket.
      <code>GITHUB_TOKEN</code> is provided automatically by GitHub Actions.
    </Callout>

    <h2>Step 4: DNS</h2>
    <p>Point your domain to the server:</p>
    <CodeBlock language="bash" code="your-app.paydlabs.com  ->  A record  ->  46.101.240.141" />
    <p>If <code>*.paydlabs.com</code> already has a wildcard A record, no DNS change is needed.</p>

    <h2>Step 5: Push to Deploy</h2>
    <p>Push a commit to <code>main</code>. GitHub Actions will:</p>
    <ol>
      <li>Build Docker image(s) and push to GHCR</li>
      <li>Send webhook to Sentinel</li>
      <li>Sentinel pulls new images, recreates containers</li>
      <li>Health check (30s retry)</li>
      <li>Auto-rollback if health check fails</li>
    </ol>

    <h2>Dockerfile Examples</h2>

    <h3>FastAPI (Python)</h3>
    <CodeBlock :code="fastapiDockerfile" language="bash" title="Dockerfile" />

    <h3>Vue / Vite (served by Caddy)</h3>
    <CodeBlock :code="vueDockerfile" language="bash" title="Dockerfile" />

    <h2>Troubleshooting</h2>
    <table>
      <thead><tr><th>Problem</th><th>Solution</th></tr></thead>
      <tbody>
        <tr><td>Webhook returns 401</td><td>Check <code>SENTINEL_WEBHOOK_SECRET</code> matches the project detail page</td></tr>
        <tr><td>Webhook returns 404</td><td>Project name in payload must match the <code>name</code> field in Sentinel (not display name)</td></tr>
        <tr><td><code>docker compose pull</code> fails</td><td>Build step must push to GHCR before the webhook fires</td></tr>
        <tr><td>Health check fails</td><td>Endpoint must respond 2xx within 30s. Check container logs in Sentinel.</td></tr>
        <tr><td>Containers missing in dashboard</td><td>Must be on the <code>proxy</code> Docker network</td></tr>
      </tbody>
    </table>
  </div>
</template>
