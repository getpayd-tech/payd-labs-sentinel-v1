"""APScheduler setup for background tasks."""
from __future__ import annotations

import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler

logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler()


def start_scheduler():
    """Configure and start the background scheduler."""
    from app.services.docker_service import refresh_stats_cache

    scheduler.add_job(
        refresh_stats_cache,
        "interval",
        seconds=30,
        id="stats_cache_refresh",
        replace_existing=True,
        max_instances=1,
    )

    scheduler.start()
    logger.info("Background scheduler started with %d jobs", len(scheduler.get_jobs()))


def stop_scheduler():
    """Shut down the scheduler gracefully."""
    if scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("Background scheduler stopped")
