"""Audit log routes — paginated audit log with filters."""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import require_admin
from app.database import get_db
from app.models.audit_log import AuditLog

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/audit", tags=["Audit"])


# ---------------------------------------------------------------------------
# Response schemas (inline to avoid circular imports)
# ---------------------------------------------------------------------------

from pydantic import BaseModel


class AuditLogEntry(BaseModel):
    id: str
    user_id: Optional[str] = None
    action: str
    target: Optional[str] = None
    details: Optional[dict[str, Any]] = None
    ip_address: Optional[str] = None
    created_at: Optional[str] = None

    model_config = {"from_attributes": True}


class AuditLogList(BaseModel):
    items: list[AuditLogEntry]
    total: int
    page: int
    page_size: int


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.get("", response_model=AuditLogList)
async def get_audit_logs(
    action: Optional[str] = Query(None, description="Filter by action (e.g. 'deployment.trigger')"),
    target: Optional[str] = Query(None, description="Filter by target"),
    user_id: Optional[str] = Query(None, description="Filter by user ID"),
    date_from: Optional[str] = Query(None, description="ISO date — only entries after this date"),
    date_to: Optional[str] = Query(None, description="ISO date — only entries before this date"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    claims: dict = Depends(require_admin),
):
    """Retrieve paginated audit log entries with optional filters."""
    conditions = []

    if action:
        conditions.append(AuditLog.action == action)
    if target:
        conditions.append(AuditLog.target.ilike(f"%{target}%"))
    if user_id:
        conditions.append(AuditLog.user_id == user_id)
    if date_from:
        try:
            dt_from = datetime.fromisoformat(date_from)
            conditions.append(AuditLog.created_at >= dt_from)
        except ValueError:
            pass
    if date_to:
        try:
            dt_to = datetime.fromisoformat(date_to)
            conditions.append(AuditLog.created_at <= dt_to)
        except ValueError:
            pass

    where_clause = and_(*conditions) if conditions else True

    # Total count
    count_q = select(func.count()).select_from(AuditLog).where(where_clause)
    total_result = await db.execute(count_q)
    total = total_result.scalar() or 0

    # Paginated results
    q = (
        select(AuditLog)
        .where(where_clause)
        .order_by(AuditLog.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    result = await db.execute(q)
    items = list(result.scalars().all())

    return AuditLogList(
        items=[
            AuditLogEntry(
                id=entry.id,
                user_id=entry.user_id,
                action=entry.action,
                target=entry.target,
                details=entry.details,
                ip_address=entry.ip_address,
                created_at=entry.created_at.isoformat() if entry.created_at else None,
            )
            for entry in items
        ],
        total=total,
        page=page,
        page_size=page_size,
    )
