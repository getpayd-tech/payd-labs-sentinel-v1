"""Async HTTP client for the Sentinel API."""
from __future__ import annotations

import httpx


class SentinelClient:
    """Wraps Sentinel API endpoints used by the CLI and MCP server."""

    def __init__(self, base_url: str, token: str):
        self._http = httpx.AsyncClient(
            base_url=f"{base_url.rstrip('/')}/api/v1",
            headers={"x-auth-token": token, "Content-Type": "application/json"},
            timeout=60.0,
        )

    async def aclose(self) -> None:
        await self._http.aclose()

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        await self.aclose()

    # -- Projects --

    async def list_projects(self) -> list[dict]:
        resp = await self._http.get("/projects")
        resp.raise_for_status()
        data = resp.json()
        return data.get("items", data) if isinstance(data, dict) else data

    async def get_project_id_by_name(self, name: str) -> str:
        """Resolve a project slug to its UUID. Raises ValueError if not found."""
        projects = await self.list_projects()
        for p in projects:
            if p["name"] == name:
                return p["id"]
        available = ", ".join(p["name"] for p in projects)
        raise ValueError(f"Project '{name}' not found. Available: {available}")

    async def get_project(self, project_id: str) -> dict:
        resp = await self._http.get(f"/projects/{project_id}")
        resp.raise_for_status()
        return resp.json()

    async def create_project(self, payload: dict) -> dict:
        resp = await self._http.post("/projects", json=payload)
        resp.raise_for_status()
        return resp.json()

    async def update_project(self, project_id: str, payload: dict) -> dict:
        resp = await self._http.put(f"/projects/{project_id}", json=payload)
        resp.raise_for_status()
        return resp.json()

    async def delete_project(self, project_id: str) -> None:
        resp = await self._http.delete(f"/projects/{project_id}")
        resp.raise_for_status()

    async def scan_projects(self) -> dict:
        resp = await self._http.post("/projects/scan")
        resp.raise_for_status()
        return resp.json()

    async def provision_project(self, project_id: str, create_database: bool = False) -> dict:
        resp = await self._http.post(
            f"/projects/{project_id}/provision",
            json={"create_database": create_database},
        )
        resp.raise_for_status()
        return resp.json()

    async def run_wizard(self, payload: dict) -> dict:
        """Run the full 9-step deploy wizard. Long-running (up to 5 min)."""
        resp = await self._http.post(
            "/projects/wizard",
            json=payload,
            timeout=httpx.Timeout(300.0),
        )
        resp.raise_for_status()
        return resp.json()

    async def wizard_preview(self, payload: dict) -> dict:
        resp = await self._http.post("/projects/wizard/preview", json=payload)
        resp.raise_for_status()
        return resp.json()

    async def generate_service_key(self, project_id: str) -> dict:
        resp = await self._http.post(f"/projects/{project_id}/generate-service-key")
        resp.raise_for_status()
        return resp.json()

    # -- Env vars --

    async def get_env(self, project_id: str, reveal: bool = False) -> list[dict]:
        resp = await self._http.get(
            f"/projects/{project_id}/env",
            params={"reveal": str(reveal).lower()},
        )
        resp.raise_for_status()
        return resp.json()

    async def set_env(self, project_id: str, variables: dict[str, str]) -> dict:
        resp = await self._http.put(
            f"/projects/{project_id}/env",
            json={"variables": variables},
        )
        resp.raise_for_status()
        return resp.json()

    # -- Databases --

    async def list_databases(self) -> list[dict]:
        resp = await self._http.get("/database/databases")
        resp.raise_for_status()
        return resp.json()

    async def create_database(self, name: str, password: str | None = None) -> dict:
        body: dict = {"name": name}
        if password:
            body["password"] = password
        resp = await self._http.post("/database/databases", json=body)
        resp.raise_for_status()
        return resp.json()

    async def list_tables(self, db: str) -> list[dict]:
        resp = await self._http.get(f"/database/databases/{db}/tables")
        resp.raise_for_status()
        return resp.json()

    async def query(self, db: str, sql: str) -> dict:
        resp = await self._http.post(
            f"/database/databases/{db}/query",
            json={"sql": sql},
        )
        resp.raise_for_status()
        return resp.json()

    # -- Domains --

    async def list_domains(self) -> list[dict]:
        resp = await self._http.get("/domains")
        resp.raise_for_status()
        return resp.json()

    async def add_domain(
        self,
        domain: str,
        upstream: str,
        tls_mode: str = "auto",
    ) -> dict:
        host, _, port = upstream.partition(":")
        port_num = int(port) if port else 80
        resp = await self._http.post(
            "/domains",
            json={
                "domain": domain,
                "upstreams": [{"address": host, "port": port_num}],
                "tls_mode": tls_mode,
            },
        )
        resp.raise_for_status()
        return resp.json()

    async def remove_domain(self, domain: str) -> None:
        resp = await self._http.delete(f"/domains/{domain}")
        resp.raise_for_status()

    async def reload_caddy(self) -> dict:
        resp = await self._http.post("/domains/reload")
        resp.raise_for_status()
        return resp.json()

    async def on_demand_tls_status(self) -> dict:
        resp = await self._http.get("/domains/on-demand-tls")
        resp.raise_for_status()
        return resp.json()

    async def enable_on_demand_tls(self) -> dict:
        resp = await self._http.post("/domains/on-demand-tls/enable")
        resp.raise_for_status()
        return resp.json()

    async def disable_on_demand_tls(self) -> dict:
        resp = await self._http.post("/domains/on-demand-tls/disable")
        resp.raise_for_status()
        return resp.json()

    # -- Custom domains (admin) --

    async def list_custom_domains(self, project_id: str | None = None) -> dict:
        params = {"project_id": project_id} if project_id else {}
        resp = await self._http.get("/custom-domains/all", params=params)
        resp.raise_for_status()
        return resp.json()

    async def admin_remove_custom_domain(self, domain: str) -> None:
        resp = await self._http.delete(f"/custom-domains/admin/{domain}")
        resp.raise_for_status()

    # -- Service control --

    async def restart_service(self, name: str) -> dict:
        resp = await self._http.post(f"/services/{name}/restart")
        resp.raise_for_status()
        return resp.json()

    async def stop_service(self, name: str) -> dict:
        resp = await self._http.post(f"/services/{name}/stop")
        resp.raise_for_status()
        return resp.json()

    async def start_service(self, name: str) -> dict:
        resp = await self._http.post(f"/services/{name}/start")
        resp.raise_for_status()
        return resp.json()

    # -- Audit --

    async def audit_log(self, page: int = 1, per_page: int = 50, action: str | None = None) -> dict:
        params: dict = {"page": page, "per_page": per_page}
        if action:
            params["action"] = action
        resp = await self._http.get("/audit", params=params)
        resp.raise_for_status()
        return resp.json()

    # -- Deployments --

    async def list_deployments(
        self,
        project_id: str | None = None,
        page_size: int = 20,
    ) -> dict:
        params: dict = {"page_size": page_size}
        if project_id:
            params["project_id"] = project_id
        resp = await self._http.get("/deployments", params=params)
        resp.raise_for_status()
        return resp.json()

    async def deploy(self, project_id: str, image_tag: str | None = None) -> dict:
        body = {"image_tag": image_tag} if image_tag else {}
        resp = await self._http.post(f"/deployments/{project_id}/deploy", json=body)
        resp.raise_for_status()
        return resp.json()

    async def rollback(self, project_id: str, deployment_id: str) -> dict:
        resp = await self._http.post(f"/deployments/{project_id}/rollback/{deployment_id}")
        resp.raise_for_status()
        return resp.json()

    # -- Services --

    async def list_services(self) -> list[dict]:
        resp = await self._http.get("/services")
        resp.raise_for_status()
        return resp.json()

    async def get_service_logs(
        self,
        name: str,
        tail: int = 100,
        since: int | None = None,
    ) -> dict:
        params: dict = {"tail": tail}
        if since is not None:
            params["since"] = since
        resp = await self._http.get(f"/services/{name}/logs", params=params)
        resp.raise_for_status()
        return resp.json()

    # -- Security / fail2ban --

    async def list_jails(self) -> list[str]:
        resp = await self._http.get("/security/jails")
        resp.raise_for_status()
        return resp.json().get("jails", [])

    async def jail_status(self, jail: str) -> dict:
        resp = await self._http.get(f"/security/jails/{jail}")
        resp.raise_for_status()
        return resp.json()

    async def ban_ip(self, jail: str, ip: str) -> None:
        resp = await self._http.post(f"/security/jails/{jail}/ban", json={"ip": ip})
        resp.raise_for_status()

    async def unban_ip(self, jail: str, ip: str) -> None:
        resp = await self._http.delete(f"/security/jails/{jail}/banned/{ip}")
        resp.raise_for_status()

    async def security_activity(self, limit: int = 100) -> list[dict]:
        resp = await self._http.get("/security/activity", params={"limit": limit})
        resp.raise_for_status()
        return resp.json()

    async def ip_history(self, ip: str) -> dict:
        resp = await self._http.get(f"/security/ips/{ip}/history")
        resp.raise_for_status()
        return resp.json()

    async def auth_log(self, limit: int = 100, event_type: str | None = None) -> list[dict]:
        params: dict = {"limit": limit}
        if event_type:
            params["event_type"] = event_type
        resp = await self._http.get("/security/auth-log", params=params)
        resp.raise_for_status()
        return resp.json()

    async def auth_stats(self, hours: int = 24) -> dict:
        resp = await self._http.get("/security/auth-stats", params={"hours": hours})
        resp.raise_for_status()
        return resp.json()
