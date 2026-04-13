<script setup lang="ts">
import EndpointBadge from '@/components/docs/EndpointBadge.vue'
import Callout from '@/components/docs/Callout.vue'
</script>

<template>
  <div class="prose">
    <h1>API Reference</h1>
    <p>
      Base URL: <code>https://sentinel.paydlabs.com/api/v1</code>
    </p>

    <h2>Authentication</h2>
    <table>
      <thead><tr><th>Method</th><th>Header</th><th>Used by</th></tr></thead>
      <tbody>
        <tr><td>Admin JWT</td><td><code>x-auth-token</code></td><td>Web UI, CLI, most endpoints</td></tr>
        <tr><td>Service Key</td><td><code>X-Service-Key</code></td><td>Custom domains API (per-project)</td></tr>
        <tr><td>HMAC-SHA256</td><td><code>X-Hub-Signature-256</code></td><td>Webhook deploy endpoint</td></tr>
      </tbody>
    </table>

    <h2>Auth</h2>
    <EndpointBadge method="POST" path="/auth/login" />
    <p>Forward username + password to Payd Auth. Returns <code>sessionToken</code>.</p>

    <EndpointBadge method="POST" path="/auth/request-otp" />
    <p>Request OTP delivery. Requires <code>x-session-token</code> header.</p>

    <EndpointBadge method="POST" path="/auth/verify-otp" />
    <p>Verify OTP code. Returns <code>authToken</code> + <code>refreshToken</code>.</p>

    <EndpointBadge method="POST" path="/auth/refresh" />
    <p>Refresh auth token using <code>refresh_token</code> in body.</p>

    <EndpointBadge method="GET" path="/auth/me" />
    <p>Get current user profile (admin only).</p>

    <h2>Projects</h2>
    <EndpointBadge method="GET" path="/projects" />
    <p>List all registered projects.</p>

    <EndpointBadge method="POST" path="/projects" />
    <p>Create a new project. Auto-generates webhook secret.</p>

    <EndpointBadge method="GET" path="/projects/{id}" />
    <p>Get details for a single project.</p>

    <EndpointBadge method="PUT" path="/projects/{id}" />
    <p>Update project metadata (display name, domain, github repo, container names, etc.).</p>

    <EndpointBadge method="DELETE" path="/projects/{id}" />
    <p>Delete project record (does not remove server files).</p>

    <EndpointBadge method="GET" path="/projects/{id}/env" />
    <p>Get environment variables (masked unless <code>?reveal=true</code>).</p>

    <EndpointBadge method="PUT" path="/projects/{id}/env" />
    <p>Update environment variables. Body: <code>{{ '{ "variables": { "KEY": "value" } }' }}</code></p>

    <EndpointBadge method="POST" path="/projects/scan" />
    <p>Scan <code>/apps/</code> directory to auto-discover and register existing projects.</p>

    <EndpointBadge method="POST" path="/projects/wizard" />
    <p>Execute full deploy wizard (provision directory, compose, Caddy, database, first deploy).</p>

    <h2>Deployments</h2>
    <EndpointBadge method="GET" path="/deployments" />
    <p>List deployments (paginated). Optional query params: <code>project_id</code>, <code>page</code>, <code>page_size</code>.</p>

    <EndpointBadge method="GET" path="/deployments/{id}" />
    <p>Get details for a single deployment (including full logs).</p>

    <EndpointBadge method="POST" path="/deployments/{project_id}/deploy" />
    <p>Trigger manual deployment. Optional body: <code>{{ '{ "image_tag": "v1.2.3" }' }}</code></p>

    <EndpointBadge method="POST" path="/deployments/{project_id}/rollback/{deployment_id}" />
    <p>Roll back to a previous deployment.</p>

    <EndpointBadge method="POST" path="/deployments/webhook" />
    <p>
      Webhook endpoint for CI/CD. Authenticated via <code>X-Hub-Signature-256: sha256=...</code> (HMAC-SHA256).
      Body: <code>{{ '{ "project": "name", "image_tag": "sha", "triggered_by": "user" }' }}</code>
    </p>

    <h2>Services</h2>
    <EndpointBadge method="GET" path="/services" />
    <p>List all Docker containers with basic info.</p>

    <EndpointBadge method="GET" path="/services/{name}" />
    <p>Get detailed info for a container.</p>

    <EndpointBadge method="POST" path="/services/{name}/restart" />
    <p>Restart a container.</p>

    <EndpointBadge method="POST" path="/services/{name}/stop" />
    <p>Stop a running container.</p>

    <EndpointBadge method="POST" path="/services/{name}/start" />
    <p>Start a stopped container.</p>

    <EndpointBadge method="GET" path="/services/{name}/logs" />
    <p>Get container logs. Query params: <code>tail</code> (int), <code>since</code> (unix timestamp).</p>

    <h2>Domains</h2>
    <EndpointBadge method="GET" path="/domains" />
    <p>List all Caddy domain routes.</p>

    <EndpointBadge method="POST" path="/domains" />
    <p>Add a new domain route to the Caddyfile.</p>

    <EndpointBadge method="PUT" path="/domains/{domain}" />
    <p>Update an existing domain route.</p>

    <EndpointBadge method="DELETE" path="/domains/{domain}" />
    <p>Remove a domain route.</p>

    <EndpointBadge method="POST" path="/domains/reload" />
    <p>Reload Caddy configuration.</p>

    <EndpointBadge method="GET" path="/domains/on-demand-tls" />
    <p>Check if on-demand TLS is enabled.</p>

    <EndpointBadge method="POST" path="/domains/on-demand-tls/enable" />
    <p>Enable on-demand TLS.</p>

    <EndpointBadge method="POST" path="/domains/on-demand-tls/disable" />
    <p>Disable on-demand TLS.</p>

    <h2>Custom Domains</h2>
    <Callout type="info">
      Service endpoints use <code>X-Service-Key</code> header. Admin endpoints use <code>x-auth-token</code>.
    </Callout>

    <EndpointBadge method="POST" path="/custom-domains" />
    <p>Register a custom domain (service key auth). Body: <code>{{ '{ "domain": "mybrand.com" }' }}</code></p>

    <EndpointBadge method="GET" path="/custom-domains" />
    <p>List custom domains for the authenticated project (service key).</p>

    <EndpointBadge method="DELETE" path="/custom-domains/{domain}" />
    <p>Remove a custom domain (service key, must own the domain).</p>

    <EndpointBadge method="GET" path="/custom-domains/all" />
    <p>List all custom domains across all projects (admin).</p>

    <EndpointBadge method="DELETE" path="/custom-domains/admin/{domain}" />
    <p>Force-remove any custom domain (admin).</p>

    <h2>Database</h2>
    <EndpointBadge method="GET" path="/database/databases" />
    <p>List all databases on the managed PostgreSQL instance.</p>

    <EndpointBadge method="POST" path="/database/databases" />
    <p>Create a new database and dedicated user.</p>

    <EndpointBadge method="GET" path="/database/databases/{name}/tables" />
    <p>List tables in a database with row counts.</p>

    <EndpointBadge method="GET" path="/database/databases/{name}/tables/{table}" />
    <p>Get column schema for a table.</p>

    <EndpointBadge method="POST" path="/database/databases/{name}/query" />
    <p>Execute a read-only SQL query. Body: <code>{{ '{ "sql": "SELECT ..." }' }}</code></p>

    <h2>System</h2>
    <EndpointBadge method="GET" path="/system/metrics" />
    <p>Current system metrics (CPU, memory, disk, uptime).</p>

    <EndpointBadge method="GET" path="/system/metrics/history" />
    <p>Historical metric snapshots.</p>

    <h2>Audit</h2>
    <EndpointBadge method="GET" path="/audit" />
    <p>Paginated audit log. Optional filters: <code>action</code>, <code>target</code>, <code>user_id</code>, <code>date_from</code>, <code>date_to</code>.</p>

    <h2>Other</h2>
    <EndpointBadge method="GET" path="/health" />
    <p>Health check (no auth). Returns 200 if healthy, 503 if degraded.</p>

    <EndpointBadge method="GET" path="/dashboard/stats" />
    <p>Aggregated dashboard stats (container count, system metrics).</p>

    <EndpointBadge method="GET" path="/logs" />
    <p>Aggregated logs across multiple containers. Filterable by container names, text search, stream.</p>
  </div>
</template>
