<script setup lang="ts">
import Callout from '@/components/docs/Callout.vue'
import CodeBlock from '@/components/docs/CodeBlock.vue'
</script>

<template>
  <div class="prose">
    <h1>Sentinel</h1>
    <p>
      Sentinel is a self-hosted DevOps portal for Payd Labs. It replaces per-repo SSH deploy scripts
      with a centralized system: one webhook secret per project, no SSH keys scattered across GitHub repos.
    </p>

    <h2>How deployments work</h2>
    <CodeBlock language="bash" :code="`Your Repo (GitHub Actions)              Sentinel (on server)
--------------------------              --------------------
1. Build Docker image(s)
2. Push to GHCR
3. POST webhook to Sentinel  ------>   4. Verify HMAC signature
                                       5. docker compose pull
                                       6. docker compose up -d
                                       7. Health check (30s)
                                       8. Auto-rollback if failed
                                       9. Record in deployment log`" />

    <p>
      <strong>One secret per repo:</strong> <code>SENTINEL_WEBHOOK_SECRET</code>.
      No SSH keys needed. Sentinel runs on the server with Docker socket access.
    </p>

    <h2>Features</h2>
    <table>
      <thead><tr><th>Feature</th><th>Description</th></tr></thead>
      <tbody>
        <tr><td><strong>Deploy Wizard</strong></td><td>End-to-end project setup: compose, .env, Caddy, database, first deploy</td></tr>
        <tr><td><strong>Deployments</strong></td><td>Webhook-triggered deploys, manual deploy, rollback, full history</td></tr>
        <tr><td><strong>Custom Domains</strong></td><td>Services register user domains via API with automatic on-demand TLS</td></tr>
        <tr><td><strong>CLI</strong></td><td><code>sentinel</code> command for deploys, logs, status from the terminal</td></tr>
        <tr><td><strong>MCP Server</strong></td><td><code>sentinel-mcp</code> exposes tools for AI agents (Claude Code, etc.)</td></tr>
        <tr><td><strong>Dashboard</strong></td><td>Container health, CPU/RAM/disk metrics, real-time refresh</td></tr>
        <tr><td><strong>Services</strong></td><td>List, restart, stop, start containers; view logs</td></tr>
        <tr><td><strong>Domains</strong></td><td>Manage Caddy routes with TLS (ACME / Cloudflare DNS / on-demand)</td></tr>
        <tr><td><strong>Database</strong></td><td>Browse managed PostgreSQL: databases, tables, schemas, run queries</td></tr>
        <tr><td><strong>Audit</strong></td><td>Full action history with user, action, target, and timestamp</td></tr>
      </tbody>
    </table>

    <h2>Quick start</h2>
    <ol>
      <li><strong>Run the deploy wizard</strong> at <a href="https://sentinel.paydlabs.com/projects/deploy-wizard">sentinel.paydlabs.com/projects/deploy-wizard</a></li>
      <li><strong>Add the workflow</strong> to your repo (wizard generates it)</li>
      <li><strong>Add one secret</strong> to your GitHub repo: <code>SENTINEL_WEBHOOK_SECRET</code></li>
      <li><strong>Push to main</strong> - Sentinel handles the rest</li>
    </ol>

    <Callout type="info" title="Or use the CLI:">
      <code>pip install sentinel-cli</code> then <code>sentinel login</code> and <code>sentinel deploy my-project</code>.
    </Callout>

    <h2>Architecture</h2>
    <CodeBlock language="bash" :code="`Browser -> Caddy (TLS) -> sentinel-api (FastAPI :8000) / sentinel-ui (Vue :80)

sentinel-api has:
  - Docker socket -> manages all containers on the server
  - /apps/ volume -> reads/writes compose files + .env for every project
  - Docker CLI -> runs docker compose pull/up for deployments
  - SQLite -> project records, custom domains, deployments, audit log
  - asyncpg -> DigitalOcean Managed PostgreSQL (database browser)
  - Caddy ask endpoint -> validates custom domains for on-demand TLS`" />
  </div>
</template>
