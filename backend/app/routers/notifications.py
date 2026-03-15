"""Notifications router."""

from typing import Any, Dict, List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select, func, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.models.notification import Notification
from app.models.user import User

router = APIRouter(tags=["notifications"])


# ──────────────────────────────────────────────────────────────────
# Schemas
# ──────────────────────────────────────────────────────────────────

class NotificationOut(BaseModel):
    id: str
    user_id: str
    project_id: Optional[str] = None
    validation_suite_id: Optional[str] = None
    message: str
    severity: str
    read: bool
    link: Optional[str] = None
    details: Optional[Dict[str, Any]] = None
    created_at: str


class NotificationListOut(BaseModel):
    notifications: List[NotificationOut]
    unread_count: int
    total: int


class MarkReadRequest(BaseModel):
    notification_ids: List[str]


# ──────────────────────────────────────────────────────────────────
# Notification endpoints
# ──────────────────────────────────────────────────────────────────

@router.get("/notifications", response_model=NotificationListOut)
async def list_notifications(
    unread_only: bool = False,
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List notifications for the current user."""
    query = select(Notification).where(Notification.user_id == current_user.id)
    if unread_only:
        query = query.where(Notification.read == False)  # noqa: E712
    query = query.order_by(Notification.created_at.desc()).limit(limit)

    result = await db.execute(query)
    rows = result.scalars().all()

    # Unread count
    count_q = select(func.count()).select_from(Notification).where(
        Notification.user_id == current_user.id,
        Notification.read == False,  # noqa: E712
    )
    unread_count = (await db.execute(count_q)).scalar() or 0

    return NotificationListOut(
        notifications=[
            NotificationOut(
                id=str(n.id),
                user_id=str(n.user_id),
                project_id=str(n.project_id) if n.project_id else None,
                validation_suite_id=str(n.validation_suite_id) if n.validation_suite_id else None,
                message=n.message,
                severity=n.severity,
                read=n.read,
                link=n.link,
                details=n.details,
                created_at=n.created_at.isoformat(),
            )
            for n in rows
        ],
        unread_count=unread_count,
        total=len(rows),
    )


@router.post("/notifications/mark-read")
async def mark_notifications_read(
    body: MarkReadRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Mark one or more notifications as read."""
    ids = [UUID(nid) for nid in body.notification_ids]
    await db.execute(
        update(Notification)
        .where(Notification.id.in_(ids), Notification.user_id == current_user.id)
        .values(read=True)
    )
    await db.commit()
    return {"marked_read": len(ids)}


@router.post("/notifications/mark-all-read")
async def mark_all_read(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Mark all notifications as read for the current user."""
    await db.execute(
        update(Notification)
        .where(Notification.user_id == current_user.id, Notification.read == False)  # noqa: E712
        .values(read=True)
    )
    await db.commit()
    return {"status": "ok"}
