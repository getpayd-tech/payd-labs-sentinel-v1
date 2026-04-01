"""Docker container management service.

Wraps the Docker SDK to provide container listing, inspection, lifecycle
management, log retrieval, and real-time stats for the Sentinel dashboard.

Performance note
----------------
Docker's `container.stats(stream=False)` is a blocking call that takes ~1s per
container (Docker needs two CPU samples). With 11 containers that's 11+ seconds
of *event-loop blocking* if called inline from an async handler.

Solution
--------
* `_stats_cache` — module-level dict updated by `refresh_stats_cache()`.
* `refresh_stats_cache()` — async function that fetches stats for ALL running
  containers *concurrently* (each in its own thread via asyncio.to_thread),
  completing in ~1s regardless of container count.
* `list_containers()` — fast sync function: container metadata only, no stats
  calls. Merges with `_stats_cache` which is populated by the background job.
* All routes call blocking Docker functions via `asyncio.to_thread()` to keep
  the event loop free.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any

import docker
from docker.errors import DockerException, NotFound, APIError

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# In-memory stats cache — updated every 30s by the background scheduler.
# Key: container name  Value: stats dict (cpu_percent, memory_*, network_*)
# ---------------------------------------------------------------------------
_stats_cache: dict[str, dict[str, float]] = {}


def _get_client() -> docker.DockerClient:
    """Create a Docker client from the environment (socket at /var/run/docker.sock)."""
    try:
        return docker.DockerClient.from_env()
    except DockerException as exc:
        logger.error("Failed to connect to Docker daemon: %s", exc)
        raise


def _parse_ports(ports: dict | None) -> dict:
    """Normalise the port mapping dict from Docker inspect into a simpler format."""
    if not ports:
        return {}
    result: dict[str, str | None] = {}
    for container_port, host_bindings in ports.items():
        if host_bindings:
            host_parts = [f"{b.get('HostIp', '0.0.0.0')}:{b['HostPort']}" for b in host_bindings]
            result[container_port] = ", ".join(host_parts)
        else:
            result[container_port] = None
    return result


def _calculate_cpu_percent(stats: dict) -> float:
    """Calculate CPU usage percentage from a Docker stats snapshot."""
    try:
        cpu_delta = (
            stats["cpu_stats"]["cpu_usage"]["total_usage"]
            - stats["precpu_stats"]["cpu_usage"]["total_usage"]
        )
        system_delta = (
            stats["cpu_stats"]["system_cpu_usage"]
            - stats["precpu_stats"]["system_cpu_usage"]
        )
        num_cpus = stats["cpu_stats"].get("online_cpus") or len(
            stats["cpu_stats"]["cpu_usage"].get("percpu_usage", [1])
        )
        if system_delta > 0 and cpu_delta >= 0:
            return round((cpu_delta / system_delta) * num_cpus * 100.0, 2)
    except (KeyError, TypeError, ZeroDivisionError):
        pass
    return 0.0


def _calculate_memory(stats: dict) -> tuple[float, float]:
    """Return (used_mb, limit_mb) from a Docker stats snapshot."""
    try:
        usage = stats["memory_stats"]["usage"]
        # Subtract cache if available (cgroup v1)
        cache = stats["memory_stats"].get("stats", {}).get("cache", 0)
        used = max(usage - cache, 0)
        limit = stats["memory_stats"].get("limit", 0)
        return round(used / (1024 * 1024), 2), round(limit / (1024 * 1024), 2)
    except (KeyError, TypeError):
        return 0.0, 0.0


def _calculate_network(stats: dict) -> tuple[float, float]:
    """Return (rx_mb, tx_mb) from a Docker stats snapshot."""
    try:
        networks = stats.get("networks", {})
        rx_bytes = sum(net.get("rx_bytes", 0) for net in networks.values())
        tx_bytes = sum(net.get("tx_bytes", 0) for net in networks.values())
        return round(rx_bytes / (1024 * 1024), 2), round(tx_bytes / (1024 * 1024), 2)
    except (KeyError, TypeError):
        return 0.0, 0.0


def _get_health(container_attrs: dict) -> str | None:
    """Extract health status from container attributes."""
    state = container_attrs.get("State", {})
    health = state.get("Health", {})
    return health.get("Status") if health else None


def _fetch_single_stats(container) -> tuple[str, dict[str, float]]:
    """Fetch stats for one container (blocking — meant to run in a thread)."""
    try:
        stats = container.stats(stream=False)
        cpu = _calculate_cpu_percent(stats)
        mem_used, mem_limit = _calculate_memory(stats)
        rx, tx = _calculate_network(stats)
        return container.name, {
            "cpu_percent": cpu,
            "memory_usage_mb": mem_used,
            "memory_limit_mb": mem_limit,
            "network_rx_mb": rx,
            "network_tx_mb": tx,
        }
    except Exception as exc:
        logger.debug("Stats fetch failed for %s: %s", container.name, exc)
        return container.name, {
            "cpu_percent": 0.0,
            "memory_usage_mb": 0.0,
            "memory_limit_mb": 0.0,
            "network_rx_mb": 0.0,
            "network_tx_mb": 0.0,
        }


# ---------------------------------------------------------------------------
# Background cache refresh (called by scheduler every 30s + on startup)
# ---------------------------------------------------------------------------

async def refresh_stats_cache() -> None:
    """Collect stats for all running containers *concurrently* and update cache.

    Uses asyncio.gather + asyncio.to_thread so all N containers are fetched in
    parallel. Total time ≈ 1s (single stats call duration) regardless of N.
    """
    global _stats_cache
    client = _get_client()
    try:
        running = client.containers.list()  # running only
        if not running:
            _stats_cache = {}
            return

        results = await asyncio.gather(
            *(asyncio.to_thread(_fetch_single_stats, c) for c in running),
            return_exceptions=True,
        )

        new_cache: dict[str, dict[str, float]] = {}
        for result in results:
            if isinstance(result, tuple):
                name, stats = result
                new_cache[name] = stats

        _stats_cache = new_cache
        logger.debug("Stats cache refreshed for %d containers", len(new_cache))
    except Exception as exc:
        logger.warning("Stats cache refresh failed: %s", exc)
    finally:
        client.close()


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def list_containers() -> list[dict[str, Any]]:
    """List all Docker containers with metadata + cached stats.

    This function does NOT call container.stats() — it reads from the
    module-level _stats_cache populated by refresh_stats_cache().
    As a result it completes in milliseconds.

    Call via asyncio.to_thread() from async handlers to keep the event loop
    free during the container list() HTTP call to Docker.
    """
    client = _get_client()
    containers = []

    try:
        for container in client.containers.list(all=True):
            attrs = container.attrs or {}
            config = attrs.get("Config", {})
            network_settings = attrs.get("NetworkSettings", {})
            state = attrs.get("State", {})

            cached = _stats_cache.get(container.name, {})

            info: dict[str, Any] = {
                "name": container.name,
                "status": container.status,
                "health": _get_health(attrs),
                "image": config.get("Image", str(container.image.tags[0] if container.image.tags else "")),
                "created": attrs.get("Created", ""),
                "started_at": state.get("StartedAt"),
                "ports": _parse_ports(network_settings.get("Ports")),
                "cpu_percent": cached.get("cpu_percent", 0.0),
                "memory_usage_mb": cached.get("memory_usage_mb", 0.0),
                "memory_limit_mb": cached.get("memory_limit_mb", 0.0),
                "network_rx_mb": cached.get("network_rx_mb", 0.0),
                "network_tx_mb": cached.get("network_tx_mb", 0.0),
            }

            containers.append(info)
    except DockerException as exc:
        logger.error("Failed to list containers: %s", exc)
        raise
    finally:
        client.close()

    return containers


def get_container(name: str) -> dict[str, Any]:
    """Get detailed information for a single container.

    Returns a dict matching the ContainerDetail schema fields.
    Uses cached stats — does NOT call container.stats() inline.
    """
    client = _get_client()
    try:
        container = client.containers.get(name)
        attrs = container.attrs or {}
        config = attrs.get("Config", {})
        state = attrs.get("State", {})
        network_settings = attrs.get("NetworkSettings", {})

        # Extract volume mounts
        mounts = attrs.get("Mounts", [])
        volume_list = [f"{m.get('Source', '')}:{m.get('Destination', '')}" for m in mounts]

        # Extract network names
        networks = list((network_settings.get("Networks") or {}).keys())

        # Extract environment variable keys only (no values for security)
        env_vars = config.get("Env", [])
        env_keys = [e.split("=", 1)[0] for e in env_vars if "=" in e]

        cached = _stats_cache.get(name, {})

        detail: dict[str, Any] = {
            "name": container.name,
            "id": container.short_id,
            "status": container.status,
            "health": _get_health(attrs),
            "image": config.get("Image", ""),
            "image_id": attrs.get("Image", ""),
            "created": attrs.get("Created", ""),
            "started_at": state.get("StartedAt"),
            "restart_count": state.get("RestartCount", 0),
            "platform": attrs.get("Platform"),
            "ports": _parse_ports(network_settings.get("Ports")),
            "networks": networks,
            "volumes": volume_list,
            "env_keys": env_keys,
            "labels": config.get("Labels", {}),
            "cpu_percent": cached.get("cpu_percent", 0.0),
            "memory_usage_mb": cached.get("memory_usage_mb", 0.0),
            "memory_limit_mb": cached.get("memory_limit_mb", 0.0),
        }

        return detail
    except NotFound:
        raise ValueError(f"Container '{name}' not found")
    except DockerException as exc:
        logger.error("Failed to inspect container %s: %s", name, exc)
        raise
    finally:
        client.close()


def restart_container(name: str) -> dict[str, Any]:
    """Restart a container by name. Returns action result."""
    client = _get_client()
    try:
        container = client.containers.get(name)
        container.restart(timeout=30)
        logger.info("Container %s restarted", name)
        return {"success": True, "message": f"Container '{name}' restarted successfully"}
    except NotFound:
        raise ValueError(f"Container '{name}' not found")
    except APIError as exc:
        logger.error("Failed to restart container %s: %s", name, exc)
        return {"success": False, "message": f"Failed to restart '{name}': {exc.explanation}"}
    finally:
        client.close()


def stop_container(name: str) -> dict[str, Any]:
    """Stop a running container by name. Returns action result."""
    client = _get_client()
    try:
        container = client.containers.get(name)
        container.stop(timeout=30)
        logger.info("Container %s stopped", name)
        return {"success": True, "message": f"Container '{name}' stopped successfully"}
    except NotFound:
        raise ValueError(f"Container '{name}' not found")
    except APIError as exc:
        logger.error("Failed to stop container %s: %s", name, exc)
        return {"success": False, "message": f"Failed to stop '{name}': {exc.explanation}"}
    finally:
        client.close()


def start_container(name: str) -> dict[str, Any]:
    """Start a stopped container by name. Returns action result."""
    client = _get_client()
    try:
        container = client.containers.get(name)
        container.start()
        logger.info("Container %s started", name)
        return {"success": True, "message": f"Container '{name}' started successfully"}
    except NotFound:
        raise ValueError(f"Container '{name}' not found")
    except APIError as exc:
        logger.error("Failed to start container %s: %s", name, exc)
        return {"success": False, "message": f"Failed to start '{name}': {exc.explanation}"}
    finally:
        client.close()


def get_container_logs(
    name: str,
    tail: int = 100,
    since: int | None = None,
) -> dict[str, Any]:
    """Retrieve container logs, parsed into structured entries."""
    client = _get_client()
    try:
        container = client.containers.get(name)

        kwargs: dict[str, Any] = {
            "stdout": True,
            "stderr": True,
            "timestamps": True,
            "tail": tail,
        }
        if since is not None:
            kwargs["since"] = since

        stdout_raw = container.logs(stream=False, stderr=False, **{k: v for k, v in kwargs.items() if k != "stderr"})
        stderr_raw = container.logs(stream=False, stdout=False, **{k: v for k, v in kwargs.items() if k != "stdout"})

        entries: list[dict[str, str]] = []

        for line in (stdout_raw or b"").decode("utf-8", errors="replace").splitlines():
            ts, msg = _parse_log_line(line)
            entries.append({"timestamp": ts, "message": msg, "stream": "stdout"})

        for line in (stderr_raw or b"").decode("utf-8", errors="replace").splitlines():
            ts, msg = _parse_log_line(line)
            entries.append({"timestamp": ts, "message": msg, "stream": "stderr"})

        entries.sort(key=lambda e: e["timestamp"])

        return {
            "container_name": name,
            "logs": entries,
            "total": len(entries),
        }
    except NotFound:
        raise ValueError(f"Container '{name}' not found")
    except DockerException as exc:
        logger.error("Failed to get logs for %s: %s", name, exc)
        raise
    finally:
        client.close()


def _parse_log_line(line: str) -> tuple[str, str]:
    """Split a Docker log line (with timestamps enabled) into (timestamp, message)."""
    if line and len(line) > 30 and line[4] == "-" and "T" in line[:25]:
        space_idx = line.find(" ")
        if space_idx > 0:
            return line[:space_idx], line[space_idx + 1:]
    return datetime.now(timezone.utc).isoformat(), line


def get_container_stats(name: str) -> dict[str, Any]:
    """Get stats for a container from the cache.

    Returns cached values — does not make a live Docker stats call.
    For a live call use refresh_stats_cache() then read from cache.
    """
    cached = _stats_cache.get(name, {})
    return {
        "cpu_percent": cached.get("cpu_percent", 0.0),
        "memory_usage_mb": cached.get("memory_usage_mb", 0.0),
        "memory_limit_mb": cached.get("memory_limit_mb", 0.0),
        "network_rx_mb": cached.get("network_rx_mb", 0.0),
        "network_tx_mb": cached.get("network_tx_mb", 0.0),
    }
