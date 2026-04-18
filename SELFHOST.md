# Self-Hosting Sentinel

Run your own Sentinel instance on another server. Takes ~15 minutes.

**Audience**: Payd Labs teams running Sentinel for a different server/cluster. Auth is Payd Auth (auth.payd.money), so you need a Payd Auth admin account to log in.

---

## Prerequisites

- A Linux server (Ubuntu 24.04 recommended) with Docker + Docker Compose installed
- A domain pointing to the server (e.g. `sentinel.myteam.com` -> `A record` -> server IP)
- A Payd Auth admin account with `is_admin=true`
- Optional: a GHCR personal-access token (read:packages) if you want Sentinel to pull private images during deploys

## 1. Install Docker

Standard Docker + compose install on Ubuntu:

```bash
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER  # re-login for group membership
```

## 2. Grab the templates

```bash
mkdir -p /apps/sentinel && cd /apps/sentinel

curl -fsSL -o docker-compose.yml \
  https://raw.githubusercontent.com/getpayd-tech/payd-labs-sentinel-v1/main/deploy/docker-compose.selfhost.yml

curl -fsSL -o .env \
  https://raw.githubusercontent.com/getpayd-tech/payd-labs-sentinel-v1/main/deploy/.env.example.selfhost
```

## 3. Configure the .env

Generate secrets:

```bash
# SECRET_KEY
openssl rand -hex 32

# ENCRYPTION_KEY (Fernet)
docker run --rm python:3.12-slim python -c \
  "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())" \
  2>/dev/null || pip install cryptography && \
  python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Edit `.env`:

```ini
SECRET_KEY=<hex from above>
ENCRYPTION_KEY=<fernet key from above>
SENTINEL_URL=https://sentinel.myteam.com
CORS_ORIGINS=https://sentinel.myteam.com
SERVER_IP=1.2.3.4
ALLOWED_USERNAMES=your-payd-auth-username
```

## 4. Create the Docker network and initial Caddyfile

Sentinel and every service it deploys share a single Docker network named `proxy`:

```bash
docker network create proxy

# Minimal starting Caddyfile; Sentinel will edit this file as you add domains.
sudo mkdir -p /apps/caddy
sudo tee /apps/caddy/Caddyfile > /dev/null <<EOF
{
    email admin@myteam.com
}

sentinel.myteam.com {
    reverse_proxy sentinel-api:8000
}
EOF
```

Replace `sentinel.myteam.com` with your actual Sentinel URL.

## 5. Start it

```bash
docker compose up -d
```

Wait a few seconds, then check:

```bash
curl -sSf https://sentinel.myteam.com/health
# {"status":"healthy"}
```

## 6. First-boot setup wizard

Visit `https://sentinel.myteam.com` in your browser. You'll be redirected to the login page. Sign in with your Payd Auth credentials.

After login, Sentinel sees that the setup wizard has not been completed and redirects you to `/setup`. Fill in the form (most fields are pre-populated from your `.env`):

- **Sentinel URL**: public URL you configured above
- **CORS origins**: same as Sentinel URL
- **Caddy container name**: `caddy-proxy` (default)
- **Docker network**: `proxy` (default)
- **Catch-all upstream**: leave blank unless you want unregistered on-demand TLS domains to fall back to a specific service
- **Server IP**: your server's public IP
- **Allowed usernames**: comma-separated Payd Auth usernames who should have access
- **GHCR org**: the GitHub org whose private images Sentinel will pull on your behalf

Hit **Complete Setup**. You land on the dashboard.

## 7. Next steps

- **Scan existing projects**: Projects > Scan Existing. If you have `/apps/<service>/` directories with compose files, Sentinel picks them up.
- **Deploy a new project**: Projects > Deploy Wizard. Generates the compose file, Caddy route, and GitHub Actions workflow for a new service.
- **Add fail2ban monitoring**: Security page works out of the box if `/var/run/fail2ban/fail2ban.sock` is mounted (the self-host compose does this). See the [Security docs](https://sentinel.paydlabs.com/public/docs/security) for details.

## Upgrading

```bash
cd /apps/sentinel
docker compose pull
docker compose up -d
```

## Troubleshooting

### Login works but /setup keeps reloading

Make sure `/data/sentinel_config.json` is writable by the sentinel-api container. Check:

```bash
docker exec sentinel-api ls -la /data/
docker logs sentinel-api | grep -i "instance config"
```

### Caddy doesn't provision TLS certs

- DNS must point to the server BEFORE Caddy requests a cert.
- Port 80 and 443 must be open on your firewall (`sudo ufw allow 80,443/tcp`).
- Check Caddy logs: `docker logs caddy-proxy --tail 50`.

### "proxy network not found"

You forgot step 4. Run `docker network create proxy`, then `docker compose up -d`.

### Database browser shows empty list

Set `PG_ADMIN_HOST` / `PG_ADMIN_USER` / `PG_ADMIN_PASSWORD` in `.env` to point at your managed PostgreSQL, then `docker compose up -d` to recreate.

### fail2ban endpoints return 500

The fail2ban socket mount assumes fail2ban is installed on the host. If not, edit `docker-compose.yml` and comment out the three fail2ban-related mounts, then recreate.

---

## What this self-host instance CAN'T do

- Log you in without Payd Auth (no local auth in v1)
- Manage servers other than the one it runs on (sentinel-api uses the local Docker socket)
- Pull private images from a GHCR org without a GHCR_TOKEN
