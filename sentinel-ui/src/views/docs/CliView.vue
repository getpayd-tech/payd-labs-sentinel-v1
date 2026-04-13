<script setup lang="ts">
import Callout from '@/components/docs/Callout.vue'
import CodeBlock from '@/components/docs/CodeBlock.vue'
</script>

<template>
  <div class="prose">
    <h1>CLI</h1>
    <p>Manage deployments, view logs, and monitor services from the terminal.</p>

    <h2>Install</h2>
    <CodeBlock language="bash" code="pip install sentinel-cli" />
    <p>Requires Python 3.12+. Published on <a href="https://pypi.org/project/sentinel-cli/">PyPI</a>.</p>

    <h2>Authentication</h2>
    <p>Run <code>sentinel login</code> once. The CLI walks you through the same OTP flow as the web UI:</p>
    <CodeBlock language="bash" :code="`$ sentinel login
Username: benaiah
Password: ********
OTP sent. Check your phone/email.
OTP Code: 123456
Logged in as benaiah`" />
    <p>
      Tokens are cached at <code>~/.sentinel/credentials.json</code> and auto-refreshed before expiry.
      Or skip login by setting <code>SENTINEL_TOKEN</code> env var with a valid admin JWT.
    </p>

    <h2>Commands</h2>

    <h3>sentinel projects</h3>
    <p>List all registered projects.</p>
    <CodeBlock language="bash" code="sentinel projects" />

    <h3>sentinel services</h3>
    <p>List all Docker containers with status.</p>
    <CodeBlock language="bash" code="sentinel services" />

    <h3>sentinel status</h3>
    <p>Combined view of each project with its last deployment.</p>
    <CodeBlock language="bash" code="sentinel status" />

    <h3>sentinel deploy</h3>
    <p>Trigger a deployment by project name (slug).</p>
    <CodeBlock language="bash" :code="`sentinel deploy bradar              # Deploy latest
sentinel deploy bradar --tag v1.2.3  # Deploy specific tag`" />

    <h3>sentinel rollback</h3>
    <p>Roll back to a previous deployment.</p>
    <CodeBlock language="bash" code="sentinel rollback bradar a0062aaa" />

    <h3>sentinel deployments</h3>
    <p>List recent deployment history.</p>
    <CodeBlock language="bash" :code="`sentinel deployments                    # All projects
sentinel deployments --project bradar    # Filter by project`" />

    <h3>sentinel logs</h3>
    <p>View container logs with tail and time filters.</p>
    <CodeBlock language="bash" :code="`sentinel logs sentinel-api --tail 50
sentinel logs bradar --since 1h
sentinel logs noni-api --tail 200 --since 2d`" />
    <p>Supports duration suffixes: <code>s</code> (seconds), <code>m</code> (minutes), <code>h</code> (hours), <code>d</code> (days).</p>

    <h2>Configuration</h2>
    <table>
      <thead><tr><th>Env var</th><th>Default</th><th>Description</th></tr></thead>
      <tbody>
        <tr><td><code>SENTINEL_URL</code></td><td><code>https://sentinel.paydlabs.com</code></td><td>Sentinel API base URL</td></tr>
        <tr><td><code>SENTINEL_TOKEN</code></td><td>(none)</td><td>Admin JWT - skips login if set</td></tr>
      </tbody>
    </table>

    <Callout type="info" title="Local development">
      Point at a local Sentinel instance: <code>SENTINEL_URL=http://localhost:8000 sentinel projects</code>
    </Callout>
  </div>
</template>
