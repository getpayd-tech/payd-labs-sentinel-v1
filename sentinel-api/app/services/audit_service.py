"""Audit logging service.

Provides helpers for recording user actions and retrieving paginated
audit logs from the database.
"""
from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit_log import AuditLog

logger = logging.getLogger(__name__)


async def log_action(
    db: AsyncSession,
    user_id: str | None,
    action: str,
    target: str | None = None,
    details: dict[str, Any] | None = None,
    ip_address: str | None = None,
) -> AuditLog:
    """Create an audit log entry.

    Args:
        db: Active database session.
        user_id: ID of the user who performed the action (None for system events).
        action: Short action identifier, e.g. "container.restart".
        target: What the action was performed on, e.g. container name.
        details: Optional JSON-serialisable metadata.
        ip_address: Client IP address.

    Returns the created AuditLog instance.
    """
    entry = AuditLog(
        user_id=user_id,
        action=action,
        target=target,
        details=details,
        ip_address=ip_address,
    )
    db.add(entry)
    await db.flush()
    logger.info(
        "Audit: user=%s action=%s target=%s",
        user_id or "system",
        action,
        target or "-",
    )
    return entry


async def get_audit_logs(
    db: AsyncSession,
    limit: int = 50,
    offset: int = 0,
) -> dict[str, Any]:
    """Retrieve paginated audit log entries, newest first.

    Returns a dict with 'items' (list of AuditLog) and 'total' count.
    """
    # Total count
    count_q = select(func.count()).select_from(AuditLog)
    total_result = await db.execute(count_q)
    total = total_result.scalar() or 0

    # Paginated results
    q = (
        select(AuditLog)
        .order_by(AuditLog.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    result = await db.execute(q)
    items = list(result.scalars().all())

    return {"items": items, "total": total}
