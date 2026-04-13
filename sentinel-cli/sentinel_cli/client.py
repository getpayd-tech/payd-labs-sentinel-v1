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
