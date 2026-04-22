<script setup lang="ts">
import Callout from '@/components/docs/Callout.vue'
import CodeBlock from '@/components/docs/CodeBlock.vue'
</script>

<template>
  <div class="prose">
    <h1>CLI</h1>
    <p>
      Manage the full deployment lifecycle from the terminal - from creating a new project to deploying,
      monitoring, and rolling back. 30+ commands covering every step of the UI.
    </p>

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

    <h2>End-to-end bootstrap (one command)</h2>
    <p>
      From an app repo with a <code>Dockerfile</code>, provision everything Sentinel-side AND update
      the GitHub repo in a single command:
    </p>
    <CodeBlock language="bash" :code='`cd my-app-repo
sentinel bootstrap \
  --name my-app --type fastapi --domain my-app.paydlabs.com \
  --repo https://github.com/getpayd-tech/my-app \
  --create-db \
  --env APP_ENV=production \
  --env SECRET_KEY="$(openssl rand -hex 32)" \
  --deploy`' />
    <p>
      What it does: (1) creates the project record, (2) sets env vars, (3) creates the PostgreSQL
      database + user, (4) adds the Caddy domain route, (5) provisions <code>/apps/my-app/</code>
      on the server, (6) writes <code>.github/workflows/deploy.yml</code> in the current repo,
      (7) sets <code>SENTINEL_WEBHOOK_SECRET</code> on the GitHub repo via <code>gh</code>,
      (8) triggers the first deploy.
    </p>
    <Callout type="info" title="Prerequisites for --deploy">
      Local machine needs <code>git</code> and <code>gh</code> (GitHub CLI, authed). If <code>gh</code>
      isn't available, pass <code>--no-secret</code> and set the webhook secret manually - the CLI
      prints it.
    </Callout>

    <h2>Daily operations</h2>

    <h3>Status + deploy</h3>
    <CodeBlock language="bash" :code="`sentinel status                          # Projects + last deploy
sentinel projects                        # List projects
sentinel services                        # List containers
sentinel deploy bradar                   # Deploy latest image tag
sentinel deploy bradar --tag v1.2.3      # Deploy specific tag
sentinel rollback bradar a0062aaa        # Roll back to a deployment
sentinel deployments --project bradar    # Deploy history
sentinel audit --action fail2ban.ban     # Recent audit events`" />

    <h3>Logs + service control</h3>
    <CodeBlock language="bash" :code="`sentinel logs bradar --tail 50 --since 1h
sentinel restart bradar
sentinel stop bradar
sentinel start bradar`" />

    <h2>Provisioning subcommands</h2>
    <p>If you prefer step-by-step over <code>bootstrap</code>, each stage is its own subcommand.</p>

    <h3>Projects</h3>
    <CodeBlock language="bash" :code="`sentinel project create my-app --type fastapi --domain my-app.paydlabs.com \\
  --repo https://github.com/getpayd-tech/my-app --image ghcr.io/getpayd-tech/my-app
sentinel project show my-app
sentinel project update my-app --custom-domains --custom-upstream my-app:8000
sentinel project scan                    # Auto-discover /apps/ directories
sentinel project provision my-app        # Write compose + .env + Caddy route
sentinel project service-key my-app      # Generate API key (for custom-domains API)
sentinel project delete my-app`" />

    <h3>Env vars</h3>
    <CodeBlock language="bash" :code="`sentinel env list my-app                 # Masked values
sentinel env list my-app --reveal        # Unmasked values
sentinel env set my-app KEY1=val1 KEY2=val2
sentinel env unset my-app OLD_KEY`" />

    <h3>Database (managed PostgreSQL)</h3>
    <CodeBlock language="bash" :code='`sentinel db list
sentinel db create my_app                # Creates DB + dedicated user
sentinel db tables my_app
sentinel db query my_app "SELECT count(*) FROM users"`' />

    <h3>Domains + TLS</h3>
    <CodeBlock language="bash" :code="`sentinel domain list
sentinel domain add my-app.paydlabs.com --upstream my-app:8000 --tls auto
sentinel domain remove my-app.paydlabs.com
sentinel domain reload                   # Reload Caddy
sentinel domain tls status|enable|disable

sentinel custom-domain list              # Domains registered via services
sentinel custom-domain remove userbrand.com`" />

    <h3>Security (fail2ban + SSH auth log)</h3>
    <CodeBlock language="bash" :code="`sentinel security banned                 # Currently banned IPs
sentinel security ban 1.2.3.4
sentinel security unban 1.2.3.4
sentinel security activity --tail 50     # Recent fail2ban events
sentinel security auth --tail 50 --type failure
sentinel security ip 1.2.3.4             # Full history (fail2ban + SSH)`" />

    <h3>Repo setup (existing projects)</h3>
    <p>
      For a project that's already in Sentinel but doesn't have the GitHub Actions workflow yet:
    </p>
    <CodeBlock language="bash" :code='`cd my-existing-repo
sentinel repo setup my-app

# Fetches the generated workflow YAML + webhook secret from Sentinel.
# Writes .github/workflows/deploy.yml.
# Runs "gh secret set SENTINEL_WEBHOOK_SECRET ...".
# Commits + pushes.
# Flags: --no-secret, --no-commit, --message "msg"`' />

    <h3>Interactive wizard</h3>
    <CodeBlock language="bash" :code="`sentinel init    # Prompts through the 9-step deploy wizard`" />

    <h2>Configuration</h2>
    <table>
      <thead><tr><th>Env var</th><th>Default</th><th>Description</th></tr></thead>
      <tbody>
        <tr><td><code>SENTINEL_URL</code></td><td><code>https://sentinel.paydlabs.com</code></td><td>Sentinel API base URL</td></tr>
        <tr><td><code>SENTINEL_TOKEN</code></td><td>(none)</td><td>Admin JWT - skips login if set</td></tr>
      </tbody>
    </table>

    <Callout type="info" title="Point at a different Sentinel instance">
      <code>SENTINEL_URL=https://sentinel.myteam.com sentinel status</code>
    </Callout>

    <Callout type="info" title="Full command reference">
      Each subcommand supports <code>--help</code>. See the <a href="https://pypi.org/project/sentinel-cli/">PyPI page</a> or the <a href="https://github.com/getpayd-tech/payd-labs-sentinel-v1/blob/main/sentinel-cli/README.md">package README</a> for the complete list.
    </Callout>
  </div>
</template>
