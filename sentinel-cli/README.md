# sentinel-cli

CLI and MCP server for the [Sentinel](https://sentinel.paydlabs.com) DevOps portal. Deploy, monitor, and manage services from the terminal or via AI agents.

## Install

```bash
pip install sentinel-cli
```

Requires Python 3.12+.

## CLI

```bash
sentinel login                        # OTP auth (Payd Auth)
sentinel projects                     # List all projects
sentinel services                     # List all containers
sentinel status                       # Projects + last deploy overview
sentinel deploy bradar                # Deploy by project name
sentinel deploy bradar --tag v1.2.3   # Deploy specific image tag
sentinel rollback bradar <deploy-id>  # Roll back to previous deploy
sentinel deployments --project bradar # Deployment history
sentinel logs sentinel-api --tail 50  # Container logs
sentinel logs bradar --since 1h       # Logs from last hour
```

### Auth

Run `sentinel login` once. Tokens are cached at `~/.sentinel/credentials.json` with auto-refresh.

Or set `SENTINEL_TOKEN` env var with a valid admin JWT to skip the login flow.

### Override API URL

```bash
SENTINEL_URL=http://localhost:8000 sentinel projects
```

## MCP Server (for Claude Code / AI agents)

The package includes an MCP server that exposes Sentinel tools for AI agents.

Add to your Claude Code settings (`.claude/settings.json`):

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

| Tool | Description |
|------|-------------|
| `sentinel_list_projects` | List all projects with type, domain, status |
| `sentinel_list_services` | List all Docker containers with status |
| `sentinel_list_deployments` | Recent deployments, filterable by project |
| `sentinel_deploy` | Trigger a deployment by project name |
| `sentinel_rollback` | Roll back to a previous deployment |
| `sentinel_get_logs` | Container logs with tail and time filter |
| `sentinel_project_status` | Project details + latest deployment |

The MCP server reads auth from `~/.sentinel/credentials.json` (run `sentinel login` first) or `SENTINEL_TOKEN` env var.

## What is Sentinel?

Sentinel is a self-hosted DevOps portal for managing Docker container deployments behind Caddy reverse proxy. It provides webhook-based deploys, automatic health checks with rollback, custom domain management with on-demand TLS, and a web UI for monitoring.

[sentinel.paydlabs.com](https://sentinel.paydlabs.com) | [GitHub](https://github.com/getpayd-tech/payd-labs-sentinel-v1)
