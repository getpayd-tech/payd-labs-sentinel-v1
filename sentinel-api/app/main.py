"""Sentinel API — Payd Labs server management platform.

FastAPI application with lifespan management, structured logging, CORS,
request logging middleware, and v1 API routers.
"""
from __future__ import annotations

import logging
import time
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import select, text

from app.api.v1 import auth, dashboard, services, system
from app.auth import hash_password
from app.config import settings
from app.database import async_session_factory, engine, Base
from app.models.user import User
from app.tasks.scheduler import start_scheduler, stop_scheduler

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.DEBUG if settings.debug else logging.INFO,
    format="%(asctime)s %(levelname)-8s [%(name)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
logging.getLogger("docker").setLevel(logging.WARNING)

logger = logging.getLogger("sentinel")


# ---------------------------------------------------------------------------
# Application lifespan
# ---------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage shared resources across the application lifecycle."""
    logger.info("Starting Sentinel API (env=%s)", settings.app_env)

    # Ensure /data directory exists for SQLite database
    data_dir = Path("/data")
    try:
        data_dir.mkdir(parents=True, exist_ok=True)
        logger.info("Data directory ready: %s", data_dir)
    except OSError:
        # Running locally — data dir may be relative
        local_data = Path("data")
        local_data.mkdir(parents=True, exist_ok=True)
        logger.info("Data directory ready: %s", local_data)

    # Create tables if they don't exist (for dev / first boot)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database tables verified")

    # Seed default admin user if no users exist
    await _seed_admin_user()

    # Start background scheduler
    start_scheduler()

    logger.info("Sentinel API ready")

    yield

    # Shutdown
    stop_scheduler()
    await engine.dispose()
    logger.info("Sentinel API shut down cleanly")


async def _seed_admin_user():
    """Create a default admin user on first boot if no users exist."""
    async with async_session_factory() as db:
        result = await db.execute(select(User).limit(1))
        existing = result.scalar_one_or_none()

        if existing is not None:
            logger.debug("Users already exist — skipping admin seed")
            return

        admin_username = settings.default_admin_username
        admin_password = settings.default_admin_password

        if not admin_password:
            logger.warning(
                "DEFAULT_ADMIN_PASSWORD is not set — skipping admin seed. "
                "Set it in .env or environment to create the initial admin user."
            )
            return

        admin = User(
            username=admin_username,
            password_hash=hash_password(admin_password),
            role="admin",
        )
        db.add(admin)
        await db.commit()
        logger.info("Default admin user '%s' created", admin_username)


# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------
app = FastAPI(
    title="Sentinel API",
    description="Payd Labs Server Management Platform",
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/docs" if settings.app_env == "development" else None,
    redoc_url="/redoc" if settings.app_env == "development" else None,
)


# ---------------------------------------------------------------------------
# Middleware
# ---------------------------------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["x-auth-token", "x-auth-refresh"],
)


@app.middleware("http")
async def request_logging_middleware(request: Request, call_next):
    """Log every request with method, path, status, and duration."""
    start = time.perf_counter()
    response = await call_next(request)
    duration_ms = (time.perf_counter() - start) * 1000

    if request.url.path != "/health":
        logger.info(
            "%s %s -> %d (%.0fms)",
            request.method,
            request.url.path,
            response.status_code,
            duration_ms,
        )

    return response


# ---------------------------------------------------------------------------
# Global exception handlers
# ---------------------------------------------------------------------------
@app.exception_handler(ValueError)
async def value_error_handler(request: Request, exc: ValueError):
    logger.warning("ValueError on %s %s: %s", request.method, request.url.path, exc)
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={"detail": str(exc)},
    )


@app.exception_handler(RequestValidationError)
async def validation_error_handler(request: Request, exc: RequestValidationError):
    logger.warning("Validation error on %s %s: %s", request.method, request.url.path, exc.errors())
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"detail": exc.errors()},
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    logger.exception("Unhandled exception on %s %s: %s", request.method, request.url.path, exc)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "Internal server error"},
    )


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
app.include_router(auth.router, prefix="/api/v1", tags=["Auth"])
app.include_router(dashboard.router, prefix="/api/v1", tags=["Dashboard"])
app.include_router(services.router, prefix="/api/v1", tags=["Services"])
app.include_router(system.router, prefix="/api/v1", tags=["System"])


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------
@app.get("/health")
async def health_check():
    """Health check that verifies database connectivity."""
    checks: dict = {"service": "sentinel-api"}

    try:
        async with async_session_factory() as session:
            await session.execute(text("SELECT 1"))
        checks["database"] = "connected"
    except Exception as exc:
        logger.error("Health check — database unreachable: %s", exc)
        checks["database"] = "unreachable"

    degraded = checks["database"] == "unreachable"
    checks["status"] = "degraded" if degraded else "ok"

    if degraded:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content=checks,
        )
    return checks
