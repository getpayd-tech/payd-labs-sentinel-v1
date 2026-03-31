"""APScheduler setup for background tasks.

Currently a placeholder that initialises the scheduler infrastructure.
Tasks such as periodic metrics snapshots can be registered here.
"""
from __future__ import annotations

import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler

logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler()


def start_scheduler():
    """Configure and start the background scheduler."""
    # ------------------------------------------------------------------
    # Register recurring jobs here. Example:
    #
    # from app.tasks.metrics_collector import collect_metrics_snapshot
    # scheduler.add_job(
    #     collect_metrics_snapshot,
    #     "interval",
    #     seconds=60,
    #     id="metrics_snapshot",
    #     replace_existing=True,
    #     max_instances=1,
    # )
    # ------------------------------------------------------------------

    scheduler.start()
    logger.info("Background scheduler started with %d jobs", len(scheduler.get_jobs()))


def stop_scheduler():
    """Shut down the scheduler gracefully."""
    if scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("Background scheduler stopped")
