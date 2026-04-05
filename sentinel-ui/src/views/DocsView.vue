<script setup lang="ts">
import { ref } from 'vue'
import PageHeader from '@/components/ui/PageHeader.vue'
import { Copy, Check, BookOpen, Rocket, Server, Database, Globe, Key, Terminal, FileCode, ChevronDown, ChevronRight } from 'lucide-vue-next'

const copied = ref('')
const openSections = ref<Set<string>>(new Set(['overview', 'wizard']))

function toggle(id: string) {
  if (openSections.value.has(id)) {
    openSections.value.delete(id)
  } else {
    openSections.value.add(id)
  }
}

function isOpen(id: string) {
  return openSections.value.has(id)
}

async function copy(text: string, label: string) {
  try {
    await navigator.clipboard.writeText(text)
    copied.value = label
    setTimeout(() => { copied.value = '' }, 2000)
  } catch {}
}

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
          file: ./Dockerfile
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

      # Deploy via Sentinel (no SSH needed)
      - name: Deploy via Sentinel
        run: |
          PAYLOAD='{"project":"MY-PROJECT","image_tag":"\${{ github.sha }}","triggered_by":"\${{ github.actor }}"}'
          SIGNATURE=$(echo -n "$PAYLOAD" | openssl dgst -sha256 -hmac "\${{ secrets.SENTINEL_WEBHOOK_SECRET }}" | awk '{print $2}')
          curl -sf -X POST https://sentinel.paydlabs.com/api/v1/deployments/webhook \\
            -H "X-Hub-Signature-256: sha256=$SIGNATURE" \\
            -H "Content-Type: application/json" \\
            -d "$PAYLOAD"`

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

      # Deploy via Sentinel (no SSH needed)
      - name: Deploy via Sentinel
        run: |
          PAYLOAD='{"project":"MY-APP","image_tag":"\${{ github.sha }}","triggered_by":"\${{ github.actor }}"}'
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

const vueCaddyfile = `:80 {
    root * /srv
    try_files {path} /index.html
    file_server
}`

const nuxtDockerfile = `FROM node:20-alpine AS build
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
RUN npm run build

FROM node:20-alpine
WORKDIR /app
COPY --from=build /app/.output .output
EXPOSE 3000
CMD ["node", ".output/server/index.mjs"]`
</script>

<template>
  <div class="animate-fade-in">
    <PageHeader title="Deploy Guide" description="How to deploy a new project from scratch using Sentinel" />

    <div class="max-w-3xl space-y-3">

      <!-- Overview -->
      <div class="card overflow-hidden">
        <button class="w-full flex items-center gap-3 px-5 py-4 text-left" @click="toggle('overview')">
          <BookOpen class="w-5 h-5 text-accent shrink-0" />
          <h2 class="text-sm font-heading font-semibold text-text flex-1">Overview</h2>
          <component :is="isOpen('overview') ? ChevronDown : ChevronRight" class="w-4 h-4 text-text-tertiary" />
        </button>
        <div v-if="isOpen('overview')" class="px-5 pb-5 text-sm text-text-secondary space-y-3 border-t border-border pt-4">
          <p>Deploying a new project has two parts:</p>
          <ol class="list-decimal ml-5 space-y-1">
            <li><strong class="text-text">Sentinel Deploy Wizard</strong> - provisions the server: creates the project directory, docker-compose file, .env file, Caddy domain route, and optionally a PostgreSQL database.</li>
            <li><strong class="text-text">GitHub Actions CI/CD</strong> - builds Docker images, pushes them to GHCR, and deploys to the server via SSH on every push to <code class="bg-surface-tertiary px-1 rounded text-xs">main</code>.</li>
          </ol>
          <p>The wizard handles Step 1. You set up CI/CD once in Step 2, then every future push auto-deploys.</p>
        </div>
      </div>

      <!-- Step 1: Wizard -->
      <div class="card overflow-hidden">
        <button class="w-full flex items-center gap-3 px-5 py-4 text-left" @click="toggle('wizard')">
          <Rocket class="w-5 h-5 text-accent shrink-0" />
          <h2 class="text-sm font-heading font-semibold text-text flex-1">Step 1: Run the Deploy Wizard</h2>
          <component :is="isOpen('wizard') ? ChevronDown : ChevronRight" class="w-4 h-4 text-text-tertiary" />
        </button>
        <div v-if="isOpen('wizard')" class="px-5 pb-5 text-sm text-text-secondary space-y-3 border-t border-border pt-4">
          <p>Go to <router-link to="/projects/deploy-wizard" class="text-accent hover:underline">Projects &rarr; Deploy Wizard</router-link> and fill in:</p>
          <div class="space-y-2">
            <div class="flex gap-2"><span class="font-mono text-xs bg-surface-tertiary px-1.5 py-0.5 rounded text-accent shrink-0">1</span><span><strong class="text-text">Project Type</strong> - FastAPI, Vue, Blended (API + UI), Nuxt, or Laravel</span></div>
            <div class="flex gap-2"><span class="font-mono text-xs bg-surface-tertiary px-1.5 py-0.5 rounded text-accent shrink-0">2</span><span><strong class="text-text">Repository</strong> - GitHub repo URL or org/name. Name and GHCR image auto-derived.</span></div>
            <div class="flex gap-2"><span class="font-mono text-xs bg-surface-tertiary px-1.5 py-0.5 rounded text-accent shrink-0">3</span><span><strong class="text-text">Domain & TLS</strong> - Domain name, TLS mode, optional custom Caddy routes.</span></div>
            <div class="flex gap-2"><span class="font-mono text-xs bg-surface-tertiary px-1.5 py-0.5 rounded text-accent shrink-0">4</span><span><strong class="text-text">Database</strong> - Optionally create a PostgreSQL database on the managed cluster.</span></div>
            <div class="flex gap-2"><span class="font-mono text-xs bg-surface-tertiary px-1.5 py-0.5 rounded text-accent shrink-0">5</span><span><strong class="text-text">Environment</strong> - Add variables one by one or bulk-paste an entire .env file.</span></div>
            <div class="flex gap-2"><span class="font-mono text-xs bg-surface-tertiary px-1.5 py-0.5 rounded text-accent shrink-0">6</span><span><strong class="text-text">Review & Deploy</strong> - Preview generated files, select compose filename, provision.</span></div>
          </div>
          <div class="p-3 rounded-lg bg-surface-tertiary text-xs">
            <strong class="text-text">Note:</strong> The "Pull & start containers" step will fail if GHCR images don't exist yet. This is normal for new projects - images are created in Step 2 when CI/CD runs for the first time.
          </div>
        </div>
      </div>

      <!-- Step 2: CI/CD -->
      <div class="card overflow-hidden">
        <button class="w-full flex items-center gap-3 px-5 py-4 text-left" @click="toggle('cicd')">
          <FileCode class="w-5 h-5 text-accent shrink-0" />
          <h2 class="text-sm font-heading font-semibold text-text flex-1">Step 2: Set Up CI/CD in Your Repo</h2>
          <component :is="isOpen('cicd') ? ChevronDown : ChevronRight" class="w-4 h-4 text-text-tertiary" />
        </button>
        <div v-if="isOpen('cicd')" class="px-5 pb-5 text-sm text-text-secondary space-y-4 border-t border-border pt-4">
          <p>Create <code class="bg-surface-tertiary px-1 rounded text-xs">.github/workflows/deploy.yml</code> in your project repo.</p>

          <div>
            <div class="flex items-center justify-between mb-2">
              <h3 class="text-xs font-semibold text-text uppercase tracking-wide">Blended (API + UI) - Two Images</h3>
              <button class="p-1 rounded text-text-tertiary hover:text-accent transition-colors" @click="copy(blendedWorkflow, 'blended')">
                <component :is="copied === 'blended' ? Check : Copy" class="w-3.5 h-3.5" />
              </button>
            </div>
            <pre class="p-3 text-xs font-mono bg-surface-tertiary rounded-lg overflow-x-auto max-h-48 text-text-secondary">{{ blendedWorkflow }}</pre>
          </div>

          <div>
            <div class="flex items-center justify-between mb-2">
              <h3 class="text-xs font-semibold text-text uppercase tracking-wide">Single Container (FastAPI / Vue / Nuxt / Laravel)</h3>
              <button class="p-1 rounded text-text-tertiary hover:text-accent transition-colors" @click="copy(singleWorkflow, 'single')">
                <component :is="copied === 'single' ? Check : Copy" class="w-3.5 h-3.5" />
              </button>
            </div>
            <pre class="p-3 text-xs font-mono bg-surface-tertiary rounded-lg overflow-x-auto max-h-48 text-text-secondary">{{ singleWorkflow }}</pre>
          </div>

          <p class="text-xs"><strong class="text-text">Replace</strong> <code class="bg-surface-tertiary px-1 rounded">MY-PROJECT</code> / <code class="bg-surface-tertiary px-1 rounded">MY-APP</code> with your actual project name, and adjust <code class="bg-surface-tertiary px-1 rounded">context</code> / <code class="bg-surface-tertiary px-1 rounded">file</code> paths to match your repo structure.</p>
        </div>
      </div>

      <!-- Step 3: Secrets -->
      <div class="card overflow-hidden">
        <button class="w-full flex items-center gap-3 px-5 py-4 text-left" @click="toggle('secrets')">
          <Key class="w-5 h-5 text-accent shrink-0" />
          <h2 class="text-sm font-heading font-semibold text-text flex-1">Step 3: Add GitHub Secrets</h2>
          <component :is="isOpen('secrets') ? ChevronDown : ChevronRight" class="w-4 h-4 text-text-tertiary" />
        </button>
        <div v-if="isOpen('secrets')" class="px-5 pb-5 text-sm text-text-secondary space-y-3 border-t border-border pt-4">
          <p>Go to your repo's <strong class="text-text">Settings &rarr; Secrets and variables &rarr; Actions</strong> and add:</p>
          <div class="space-y-2">
            <div class="flex items-center gap-2">
              <code class="w-56 shrink-0 text-accent font-mono bg-surface-tertiary px-2 py-1 rounded text-xs">SENTINEL_WEBHOOK_SECRET</code>
              <span class="flex-1 text-xs">From the project's detail page in Sentinel (auto-generated)</span>
            </div>
          </div>
          <div class="p-3 mt-2 rounded-lg bg-surface-tertiary text-xs">
            <strong class="text-text">That's it.</strong> No SSH keys, no server IP, no deploy user. Sentinel handles the deployment server-side via its Docker socket. <code class="bg-surface px-1 rounded">GITHUB_TOKEN</code> is automatic.
          </div>
        </div>
      </div>

      <!-- Step 4: DNS -->
      <div class="card overflow-hidden">
        <button class="w-full flex items-center gap-3 px-5 py-4 text-left" @click="toggle('dns')">
          <Globe class="w-5 h-5 text-accent shrink-0" />
          <h2 class="text-sm font-heading font-semibold text-text flex-1">Step 4: DNS</h2>
          <component :is="isOpen('dns') ? ChevronDown : ChevronRight" class="w-4 h-4 text-text-tertiary" />
        </button>
        <div v-if="isOpen('dns')" class="px-5 pb-5 text-sm text-text-secondary space-y-2 border-t border-border pt-4">
          <p>Point your domain to the server:</p>
          <div class="p-3 rounded-lg bg-surface-tertiary font-mono text-xs">
            your-app.paydlabs.com &rarr; A record &rarr; 46.101.240.141
          </div>
          <p class="text-xs">If <code class="bg-surface-tertiary px-1 rounded">*.paydlabs.com</code> is already a wildcard A record, no DNS change is needed.</p>
        </div>
      </div>

      <!-- Step 5: Deploy -->
      <div class="card overflow-hidden">
        <button class="w-full flex items-center gap-3 px-5 py-4 text-left" @click="toggle('deploy')">
          <Terminal class="w-5 h-5 text-accent shrink-0" />
          <h2 class="text-sm font-heading font-semibold text-text flex-1">Step 5: First Deploy</h2>
          <component :is="isOpen('deploy') ? ChevronDown : ChevronRight" class="w-4 h-4 text-text-tertiary" />
        </button>
        <div v-if="isOpen('deploy')" class="px-5 pb-5 text-sm text-text-secondary space-y-3 border-t border-border pt-4">
          <p>Push to <code class="bg-surface-tertiary px-1 rounded text-xs">main</code> on your project repo. GitHub Actions will:</p>
          <ol class="list-decimal ml-5 space-y-1 text-xs">
            <li>Build Docker image(s) and push to GHCR</li>
            <li>SSH into the server</li>
            <li><code class="bg-surface-tertiary px-1 rounded">docker compose pull</code> - pull new images</li>
            <li><code class="bg-surface-tertiary px-1 rounded">docker compose up -d</code> - start/recreate containers</li>
            <li>Health check - verify the service responds</li>
            <li>Image cleanup - remove old unused images</li>
          </ol>
          <p class="text-xs">After the first deploy, visit your domain to verify. New containers will appear on the Sentinel Dashboard.</p>
        </div>
      </div>

      <!-- Dockerfiles -->
      <div class="card overflow-hidden">
        <button class="w-full flex items-center gap-3 px-5 py-4 text-left" @click="toggle('dockerfiles')">
          <Server class="w-5 h-5 text-accent shrink-0" />
          <h2 class="text-sm font-heading font-semibold text-text flex-1">Dockerfile Examples</h2>
          <component :is="isOpen('dockerfiles') ? ChevronDown : ChevronRight" class="w-4 h-4 text-text-tertiary" />
        </button>
        <div v-if="isOpen('dockerfiles')" class="px-5 pb-5 text-sm text-text-secondary space-y-4 border-t border-border pt-4">
          <div>
            <div class="flex items-center justify-between mb-2">
              <h3 class="text-xs font-semibold text-text uppercase tracking-wide">FastAPI (Python)</h3>
              <button class="p-1 rounded text-text-tertiary hover:text-accent transition-colors" @click="copy(fastapiDockerfile, 'fastapi-df')">
                <component :is="copied === 'fastapi-df' ? Check : Copy" class="w-3.5 h-3.5" />
              </button>
            </div>
            <pre class="p-3 text-xs font-mono bg-surface-tertiary rounded-lg overflow-x-auto max-h-40 text-text-secondary">{{ fastapiDockerfile }}</pre>
          </div>
          <div>
            <div class="flex items-center justify-between mb-2">
              <h3 class="text-xs font-semibold text-text uppercase tracking-wide">Vue / Vite (Caddy)</h3>
              <button class="p-1 rounded text-text-tertiary hover:text-accent transition-colors" @click="copy(vueDockerfile + '\n\n# Caddyfile:\n' + vueCaddyfile, 'vue-df')">
                <component :is="copied === 'vue-df' ? Check : Copy" class="w-3.5 h-3.5" />
              </button>
            </div>
            <pre class="p-3 text-xs font-mono bg-surface-tertiary rounded-lg overflow-x-auto max-h-40 text-text-secondary">{{ vueDockerfile }}</pre>
            <p class="text-xs mt-2">With a <code class="bg-surface-tertiary px-1 rounded">Caddyfile</code> for SPA routing:</p>
            <pre class="p-3 text-xs font-mono bg-surface-tertiary rounded-lg overflow-x-auto text-text-secondary mt-1">{{ vueCaddyfile }}</pre>
          </div>
          <div>
            <div class="flex items-center justify-between mb-2">
              <h3 class="text-xs font-semibold text-text uppercase tracking-wide">Nuxt 3 (SSR)</h3>
              <button class="p-1 rounded text-text-tertiary hover:text-accent transition-colors" @click="copy(nuxtDockerfile, 'nuxt-df')">
                <component :is="copied === 'nuxt-df' ? Check : Copy" class="w-3.5 h-3.5" />
              </button>
            </div>
            <pre class="p-3 text-xs font-mono bg-surface-tertiary rounded-lg overflow-x-auto max-h-40 text-text-secondary">{{ nuxtDockerfile }}</pre>
          </div>
        </div>
      </div>

    </div>
  </div>
</template>
