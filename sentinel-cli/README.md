# sentinel-cli

CLI and MCP server for the [Sentinel](https://sentinel.paydlabs.com) DevOps portal. Manage deployments end-to-end from the terminal or via AI agents.

## Install

```bash
pip install sentinel-cli
```

Requires Python 3.12+.

## Quick start

```bash
sentinel login    # one-time OTP via Payd Auth, caches token at ~/.sentinel/

# End-to-end bootstrap of a new service (one command):
sentinel bootstrap \
  --name my-app --type fastapi --domain my-app.paydlabs.com \
  --repo https://github.com/getpayd-tech/my-app \
  --create-db \
  --env SECRET_KEY="$(openssl rand -hex 32)" \
  --env APP_ENV=production \
  --deploy
```

Runs 7 steps: project create, env set, database create, Caddy route, server provision, write workflow to local git repo + set GitHub secret via `gh`, first deploy.

## Command reference

### Everyday ops

```bash
sentinel status              # All projects + their latest deploy
sentinel projects            # List projects
sentinel services            # List containers
sentinel deploy <project>    # Trigger deploy
sentinel deploy <project> --tag v1.2.3
sentinel rollback <project> <deploy-id>
sentinel deployments [--project X]
sentinel logs <container> [--tail 100] [--since 1h]
sentinel restart|stop|start <container>
sentinel audit [--action X] [--limit 30]
```

### Projects

```bash
sentinel project create <name> --type fastapi --domain X --repo URL
sentinel project show <name>
sentinel project update <name> --domain new --custom-domains
sentinel project delete <name>
sentinel project scan                     # Auto-discover /apps/
sentinel project provision <name>         # Write compose + .env + Caddy
sentinel project service-key <name>       # Generate API key for custom-domains API
```

### Environment variables

```bash
sentinel env list <project> [--reveal]
sentinel env set <project> KEY=VAL KEY2=VAL2 ...
sentinel env unset <project> KEY1 KEY2
```

### Database (managed PostgreSQL)

```bash
sentinel db list
sentinel db create <name> [--password PW]
sentinel db tables <db>
sentinel db query <db> "SELECT * FROM ..."
```

### Domains + TLS

```bash
sentinel domain list
sentinel domain add <domain> --upstream container:port [--tls auto|cloudflare_dns|on_demand|off]
sentinel domain remove <domain>
sentinel domain reload
sentinel domain tls status|enable|disable
sentinel custom-domain list [--project X]
sentinel custom-domain remove <domain>
```

### Security (fail2ban + SSH auth log)

```bash
sentinel security banned [--jail sshd]
sentinel security ban <ip> [--jail sshd]
sentinel security unban <ip> [--jail sshd]
sentinel security activity [--tail 50]
sentinel security auth [--tail 50] [--type success|failure|info]
sentinel security ip <ip>           # Full history (fail2ban + SSH)
```

### Repo setup (close the loop on new services)

```bash
# End-to-end (recommended for new services):
sentinel bootstrap --name X --type T --domain D --repo URL [...]

# For existing Sentinel projects that need the workflow added to their repo:
cd my-existing-repo
sentinel repo setup <project>
#  -> fetches generated workflow YAML from Sentinel
#  -> writes .github/workflows/deploy.yml
#  -> runs `gh secret set SENTINEL_WEBHOOK_SECRET ...`
#  -> commits + pushes
# Flags: --no-secret, --no-commit, --message "msg"
```

### Interactive wizard

```bash
sentinel init    # prompts for each field, runs the 9-step wizard
```

## Auth

Run `sentinel login` once. Tokens are cached at `~/.sentinel/credentials.json` with auto-refresh.

Or set `SENTINEL_TOKEN` env var with a valid admin JWT to skip the login flow.

Override the API URL: `SENTINEL_URL=http://localhost:8000 sentinel projects`

## MCP Server (for Claude Code / AI agents)

The package includes an MCP server that exposes 30 tools for AI agents.

Add to your Claude Code settings:

```json
{
  "mcpServers": {
    "sentinel": {
      "command": "sentinel-mcp"
    }
  }
}
```

### Available tools

**Projects**: `sentinel_list_projects`, `sentinel_create_project`, `sentinel_update_project`, `sentinel_delete_project`, `sentinel_scan_projects`, `sentinel_provision_project`, `sentinel_project_status`, `sentinel_generate_service_key`, `sentinel_get_workflow`

**Deployments**: `sentinel_list_deployments`, `sentinel_deploy`, `sentinel_rollback`

**Services**: `sentinel_list_services`, `sentinel_restart_service`, `sentinel_stop_service`, `sentinel_start_service`, `sentinel_get_logs`

**Env**: `sentinel_list_env`, `sentinel_set_env`, `sentinel_unset_env`

**Database**: `sentinel_list_databases`, `sentinel_create_database`, `sentinel_list_tables`, `sentinel_db_query`

**Domains**: `sentinel_list_domains`, `sentinel_add_domain`, `sentinel_remove_domain`, `sentinel_reload_caddy`, `sentinel_list_custom_domains`

**Audit**: `sentinel_audit_log`

The MCP server reads auth from `~/.sentinel/credentials.json` (run `sentinel login` first) or `SENTINEL_TOKEN` env var.

## What is Sentinel?

Sentinel is a self-hosted DevOps portal for managing Docker container deployments behind Caddy reverse proxy. It provides webhook-based deploys, automatic health checks with rollback, custom domain management with on-demand TLS, fail2ban monitoring, and a web UI.

[sentinel.paydlabs.com](https://sentinel.paydlabs.com) | [GitHub](https://github.com/getpayd-tech/payd-labs-sentinel-v1) | [Self-hosting guide](https://github.com/getpayd-tech/payd-labs-sentinel-v1/blob/main/SELFHOST.md)
