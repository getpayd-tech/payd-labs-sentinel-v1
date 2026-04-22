<script setup lang="ts">
import Callout from '@/components/docs/Callout.vue'
import CodeBlock from '@/components/docs/CodeBlock.vue'
</script>

<template>
  <div class="prose">
    <h1>MCP Server</h1>
    <p>
      Sentinel ships an MCP (Model Context Protocol) server that exposes 30 tools for AI agents like Claude Code.
      Agents can do full end-to-end provisioning - create projects, set env vars, add domains, create databases,
      trigger deploys, roll back, manage bans - through natural-language conversation.
    </p>

    <h2>Install</h2>
    <CodeBlock language="bash" code="pip install sentinel-cli" />
    <p>This installs both the <code>sentinel</code> CLI and the <code>sentinel-mcp</code> MCP server.</p>

    <h2>Setup for Claude Code</h2>
    <p>Add to your <code>.claude/settings.json</code> (project-level or global):</p>
    <CodeBlock language="json" :code='`{
  "mcpServers": {
    "sentinel": {
      "command": "sentinel-mcp"
    }
  }
}`' title=".claude/settings.json" />

    <Callout type="warning" title="Auth required">
      The MCP server reads tokens from <code>~/.sentinel/credentials.json</code>.
      Run <code>sentinel login</code> in your terminal before using the MCP tools.
      Alternatively, set <code>SENTINEL_TOKEN</code> in the MCP server's env config.
    </Callout>

    <h2>Tool catalog</h2>

    <h3>Projects</h3>
    <table>
      <thead><tr><th>Tool</th><th>Description</th></tr></thead>
      <tbody>
        <tr><td><code>sentinel_list_projects</code></td><td>List all projects with type, domain, status</td></tr>
        <tr><td><code>sentinel_create_project</code></td><td>Create a new project record (name, type, domain, repo, ...)</td></tr>
        <tr><td><code>sentinel_update_project</code></td><td>Update project fields (display_name, domain, custom_domains toggle, ...)</td></tr>
        <tr><td><code>sentinel_delete_project</code></td><td>Delete project record (server files left in place)</td></tr>
        <tr><td><code>sentinel_scan_projects</code></td><td>Auto-discover and register projects from /apps/ on the server</td></tr>
        <tr><td><code>sentinel_provision_project</code></td><td>Write compose + .env + Caddy route for an existing project</td></tr>
        <tr><td><code>sentinel_project_status</code></td><td>Project details combined with latest deployment</td></tr>
        <tr><td><code>sentinel_generate_service_key</code></td><td>Generate API key for custom-domains service-to-service calls</td></tr>
        <tr><td><code>sentinel_get_workflow</code></td><td>Returns the generated GitHub Actions workflow YAML + webhook secret</td></tr>
      </tbody>
    </table>

    <h3>Deployments</h3>
    <table>
      <thead><tr><th>Tool</th><th>Description</th></tr></thead>
      <tbody>
        <tr><td><code>sentinel_list_deployments</code></td><td>Recent deployments, optionally filtered by project</td></tr>
        <tr><td><code>sentinel_deploy</code></td><td>Trigger a deployment by project name</td></tr>
        <tr><td><code>sentinel_rollback</code></td><td>Roll back to a previous deployment</td></tr>
      </tbody>
    </table>

    <h3>Services (containers)</h3>
    <table>
      <thead><tr><th>Tool</th><th>Description</th></tr></thead>
      <tbody>
        <tr><td><code>sentinel_list_services</code></td><td>All Docker containers with status and image</td></tr>
        <tr><td><code>sentinel_restart_service</code></td><td>Restart a container</td></tr>
        <tr><td><code>sentinel_stop_service</code></td><td>Stop a running container</td></tr>
        <tr><td><code>sentinel_start_service</code></td><td>Start a stopped container</td></tr>
        <tr><td><code>sentinel_get_logs</code></td><td>Container logs with tail + since-minutes filter</td></tr>
      </tbody>
    </table>

    <h3>Environment variables</h3>
    <table>
      <thead><tr><th>Tool</th><th>Description</th></tr></thead>
      <tbody>
        <tr><td><code>sentinel_list_env</code></td><td>List env vars for a project (values masked by default)</td></tr>
        <tr><td><code>sentinel_set_env</code></td><td>Set/update env vars (merges with existing)</td></tr>
        <tr><td><code>sentinel_unset_env</code></td><td>Remove one or more env vars</td></tr>
      </tbody>
    </table>

    <h3>Database</h3>
    <table>
      <thead><tr><th>Tool</th><th>Description</th></tr></thead>
      <tbody>
        <tr><td><code>sentinel_list_databases</code></td><td>List managed PostgreSQL databases</td></tr>
        <tr><td><code>sentinel_create_database</code></td><td>Create a new database with a dedicated user</td></tr>
        <tr><td><code>sentinel_list_tables</code></td><td>List tables in a database</td></tr>
        <tr><td><code>sentinel_db_query</code></td><td>Run a read-only SELECT query</td></tr>
      </tbody>
    </table>

    <h3>Domains</h3>
    <table>
      <thead><tr><th>Tool</th><th>Description</th></tr></thead>
      <tbody>
        <tr><td><code>sentinel_list_domains</code></td><td>List Caddy domain blocks</td></tr>
        <tr><td><code>sentinel_add_domain</code></td><td>Add a domain to Caddy (host, upstream, TLS mode)</td></tr>
        <tr><td><code>sentinel_remove_domain</code></td><td>Remove a domain from Caddy</td></tr>
        <tr><td><code>sentinel_reload_caddy</code></td><td>Reload Caddy configuration</td></tr>
        <tr><td><code>sentinel_list_custom_domains</code></td><td>List user-registered custom domains across all projects</td></tr>
      </tbody>
    </table>

    <h3>Audit</h3>
    <table>
      <thead><tr><th>Tool</th><th>Description</th></tr></thead>
      <tbody>
        <tr><td><code>sentinel_audit_log</code></td><td>Recent audit entries, optionally filtered by action name</td></tr>
      </tbody>
    </table>

    <h2>Example conversations</h2>
    <p>With the MCP server connected, you can give Claude Code high-level instructions:</p>
    <ul>
      <li>"Deploy my-app and show me the logs if it fails"</li>
      <li>"Create a new FastAPI project called payments-api with a database"</li>
      <li>"Set DATABASE_URL on payments-api to ..."</li>
      <li>"Add a custom domain userbrand.com pointing to my-app:8000"</li>
      <li>"Show me the last 50 failed SSH attempts"</li>
      <li>"Roll back bradar to its previous deployment"</li>
      <li>"What projects haven't been deployed in the last week?"</li>
    </ul>
    <p>The agent picks the appropriate tools and orchestrates them.</p>

    <h2>Testing with MCP Inspector</h2>
    <CodeBlock language="bash" code="npx @modelcontextprotocol/inspector sentinel-mcp" />
    <p>Opens a browser UI where you can invoke each tool manually and see the raw responses.</p>
  </div>
</template>
