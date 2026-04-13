<script setup lang="ts">
import Callout from '@/components/docs/Callout.vue'
import CodeBlock from '@/components/docs/CodeBlock.vue'
</script>

<template>
  <div class="prose">
    <h1>MCP Server</h1>
    <p>
      Sentinel ships an MCP (Model Context Protocol) server that exposes deployment and monitoring tools
      for AI agents like Claude Code.
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

    <h2>Available tools</h2>
    <table>
      <thead><tr><th>Tool</th><th>Parameters</th><th>Description</th></tr></thead>
      <tbody>
        <tr>
          <td><code>sentinel_list_projects</code></td>
          <td>(none)</td>
          <td>List all projects with type, domain, and status</td>
        </tr>
        <tr>
          <td><code>sentinel_list_services</code></td>
          <td>(none)</td>
          <td>List all Docker containers with status and image</td>
        </tr>
        <tr>
          <td><code>sentinel_list_deployments</code></td>
          <td><code>project?</code> (string)</td>
          <td>Recent deployments, optionally filtered by project name</td>
        </tr>
        <tr>
          <td><code>sentinel_deploy</code></td>
          <td><code>project</code> (string), <code>image_tag?</code> (string)</td>
          <td>Trigger a deployment by project name</td>
        </tr>
        <tr>
          <td><code>sentinel_rollback</code></td>
          <td><code>project</code> (string), <code>deployment_id</code> (string)</td>
          <td>Roll back to a previous deployment</td>
        </tr>
        <tr>
          <td><code>sentinel_get_logs</code></td>
          <td><code>container</code> (string), <code>tail?</code> (int), <code>since_minutes?</code> (int)</td>
          <td>Container logs with tail count and recency filter</td>
        </tr>
        <tr>
          <td><code>sentinel_project_status</code></td>
          <td><code>project</code> (string)</td>
          <td>Project details combined with latest deployment info</td>
        </tr>
      </tbody>
    </table>

    <h2>Example usage</h2>
    <p>Once configured, you can ask Claude Code things like:</p>
    <ul>
      <li>"List my Sentinel projects"</li>
      <li>"Deploy bradar"</li>
      <li>"Show me the last 5 deployments for payd-pos"</li>
      <li>"Get the last 50 lines of logs from sentinel-api"</li>
      <li>"What's the status of payd-labs-one-link?"</li>
    </ul>

    <p>The agent calls the appropriate MCP tool and returns the result in context.</p>

    <h2>Testing with MCP Inspector</h2>
    <CodeBlock language="bash" code="npx @modelcontextprotocol/inspector sentinel-mcp" />
    <p>This opens a browser UI where you can invoke each tool manually and see the raw responses.</p>
  </div>
</template>
