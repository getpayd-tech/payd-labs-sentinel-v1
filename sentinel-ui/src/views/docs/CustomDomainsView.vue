<script setup lang="ts">
import Callout from '@/components/docs/Callout.vue'
import CodeBlock from '@/components/docs/CodeBlock.vue'
import EndpointBadge from '@/components/docs/EndpointBadge.vue'
import ParamTable from '@/components/docs/ParamTable.vue'
import ResponseBlock from '@/components/docs/ResponseBlock.vue'

const generateKeyCmd = `curl -X POST https://sentinel.paydlabs.com/api/v1/projects/{id}/generate-service-key \\
  -H 'x-auth-token: YOUR_ADMIN_TOKEN'`

const generateKeyResp = `{ "service_api_key": "sak_KER2AnNp8qyJ7yizZtH8..." }`

const registerCmd = `curl -X POST https://sentinel.paydlabs.com/api/v1/custom-domains \\
  -H 'X-Service-Key: sak_...' \\
  -H 'Content-Type: application/json' \\
  -d '{"domain": "mybrand.com"}'`

const registerResp = `{
  "id": "8d974...",
  "project_id": "60738...",
  "project_name": "Payd Labs One Link",
  "domain": "mybrand.com",
  "status": "active",
  "created_at": "2026-04-12T06:15:51"
}`
</script>

<template>
  <div class="prose">
    <h1>Custom Domains</h1>
    <p>
      Sentinel manages dynamic custom domains with automatic TLS provisioning via Caddy's on-demand TLS.
      Any service (OneLink, Payd Shops, etc.) can let its users bring their own domains.
    </p>

    <h2>How it works</h2>
    <ol>
      <li><strong>Service registers a domain</strong> via Sentinel's API with its project-scoped service key</li>
      <li><strong>Sentinel writes a Caddy block</strong> for that domain with on-demand TLS and the project's upstream</li>
      <li><strong>Sentinel reloads Caddy</strong></li>
      <li><strong>User points DNS</strong> to <code>46.101.240.141</code></li>
      <li><strong>Caddy auto-provisions</strong> a Let's Encrypt cert on first request (validated via Sentinel's ask endpoint)</li>
    </ol>

    <h2>Setup</h2>

    <h3>1. Enable custom domains on the project</h3>
    <p>In Sentinel UI, go to Projects, click the project, then Edit:</p>
    <ul>
      <li>Toggle <strong>Enable custom domains</strong> on</li>
      <li>Set <strong>Custom Domain Upstream</strong> to the container:port (e.g. <code>payd-labs-one-link:8000</code>)</li>
    </ul>

    <h3>2. Generate a service API key</h3>
    <EndpointBadge method="POST" path="/api/v1/projects/{project_id}/generate-service-key" />
    <p>Requires admin JWT. Returns a <code>sak_</code>-prefixed key. Store it in your service's environment.</p>
    <CodeBlock language="bash" :code="generateKeyCmd" />
    <ResponseBlock title="Success" :status="200" :code="generateKeyResp" />

    <h3>3. Register domains from your service</h3>
    <EndpointBadge method="POST" path="/api/v1/custom-domains" />
    <ParamTable :params="[
      { name: 'domain', type: 'string', required: true, description: 'Fully qualified domain name (e.g. mybrand.com)' },
    ]" />
    <CodeBlock language="bash" :code="registerCmd" />
    <ResponseBlock title="Success" :status="201" :code="registerResp" />

    <h3>4. Tell the user to point DNS</h3>
    <p>The user creates an A record:</p>
    <CodeBlock language="bash" code="mybrand.com  ->  A record  ->  46.101.240.141" />
    <p>Caddy provisions a Let's Encrypt cert automatically on first request.</p>

    <h2>Service API reference</h2>
    <p>All endpoints use <code>X-Service-Key</code> header for auth (project-scoped).</p>

    <table>
      <thead><tr><th>Method</th><th>Path</th><th>Description</th></tr></thead>
      <tbody>
        <tr><td><code>POST</code></td><td>/api/v1/custom-domains</td><td>Register a domain</td></tr>
        <tr><td><code>GET</code></td><td>/api/v1/custom-domains</td><td>List domains for this project</td></tr>
        <tr><td><code>DELETE</code></td><td>/api/v1/custom-domains/{domain}</td><td>Remove a domain</td></tr>
      </tbody>
    </table>

    <h2>Admin endpoints</h2>
    <p>Use admin JWT (<code>x-auth-token</code> header).</p>
    <table>
      <thead><tr><th>Method</th><th>Path</th><th>Description</th></tr></thead>
      <tbody>
        <tr><td><code>GET</code></td><td>/api/v1/custom-domains/all</td><td>List all custom domains across projects</td></tr>
        <tr><td><code>DELETE</code></td><td>/api/v1/custom-domains/admin/{domain}</td><td>Force-remove any domain</td></tr>
      </tbody>
    </table>

    <Callout type="info" title="Caddy ask endpoint">
      <code>GET /internal/domain-check?domain=&#123;host&#125;</code> is called by Caddy (Docker-internal)
      before issuing any on-demand cert. Returns 200 if the domain is active in Sentinel, 404 otherwise.
    </Callout>
  </div>
</template>
