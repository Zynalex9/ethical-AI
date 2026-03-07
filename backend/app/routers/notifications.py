"""
Notifications & Scheduled Validations router.

Provides endpoints for:
- Listing / reading / marking notifications as read
- Creating / updating / deleting scheduled validation schedules
"""

from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select, func, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.models.notification import Notification
from app.models.scheduled_validation import ScheduledValidation
from app.models.project import Project
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


class ScheduledValidationOut(BaseModel):
    id: str
    project_id: str
    enabled: bool
    frequency: str
    last_config: Optional[Dict[str, Any]] = None
    last_run_at: Optional[str] = None
    next_run_at: Optional[str] = None
    created_at: str
    updated_at: str


class ScheduleCreateRequest(BaseModel):
    project_id: UUID
    frequency: str = "weekly"  # daily / weekly / monthly
    enabled: bool = True
    last_config: Optional[Dict[str, Any]] = None


class ScheduleUpdateRequest(BaseModel):
    frequency: Optional[str] = None
    enabled: Optional[bool] = None
    last_config: Optional[Dict[str, Any]] = None


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


# ──────────────────────────────────────────────────────────────────
# Scheduled Validation endpoints
# ──────────────────────────────────────────────────────────────────

async def _verify_project_access(db: AsyncSession, project_id: UUID, user: User) -> Project:
    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    if user.role.value != "admin" and project.owner_id != user.id:
        raise HTTPException(status_code=403, detail="Access denied")
    return project


def _compute_next_run(frequency: str, from_dt: Optional[datetime] = None) -> datetime:
    base = from_dt or datetime.now(timezone.utc)
    if frequency == "daily":
        return base + timedelta(days=1)
    elif frequency == "monthly":
        return base + timedelta(days=30)
    else:  # weekly default
        return base + timedelta(weeks=1)


@router.get("/scheduled-validations/{project_id}", response_model=Optional[ScheduledValidationOut])
async def get_schedule(
    project_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get the scheduled validation config for a project (one per project)."""
    await _verify_project_access(db, project_id, current_user)
    result = await db.execute(
        select(ScheduledValidation).where(ScheduledValidation.project_id == project_id)
    )
    sched = result.scalar_one_or_none()
    if not sched:
        return None
    return ScheduledValidationOut(
        id=str(sched.id),
        project_id=str(sched.project_id),
        enabled=sched.enabled,
        frequency=sched.frequency,
        last_config=sched.last_config,
        last_run_at=sched.last_run_at.isoformat() if sched.last_run_at else None,
        next_run_at=sched.next_run_at.isoformat() if sched.next_run_at else None,
        created_at=sched.created_at.isoformat(),
        updated_at=sched.updated_at.isoformat(),
    )


@router.post("/scheduled-validations", response_model=ScheduledValidationOut)
async def create_schedule(
    body: ScheduleCreateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create or replace the scheduled validation for a project."""
    await _verify_project_access(db, body.project_id, current_user)

    if body.frequency not in ("daily", "weekly", "monthly"):
        raise HTTPException(status_code=400, detail="frequency must be daily, weekly, or monthly")

    # Upsert — delete any existing schedule first
    existing_q = await db.execute(
        select(ScheduledValidation).where(ScheduledValidation.project_id == body.project_id)
    )
    existing = existing_q.scalar_one_or_none()
    if existing:
        await db.delete(existing)
        await db.flush()

    sched = ScheduledValidation(
        project_id=body.project_id,
        enabled=body.enabled,
        frequency=body.frequency,
        last_config=body.last_config,
        next_run_at=_compute_next_run(body.frequency) if body.enabled else None,
        created_by_id=current_user.id,
    )
    db.add(sched)
    await db.commit()
    await db.refresh(sched)

    return ScheduledValidationOut(
        id=str(sched.id),
        project_id=str(sched.project_id),
        enabled=sched.enabled,
        frequency=sched.frequency,
        last_config=sched.last_config,
        last_run_at=None,
        next_run_at=sched.next_run_at.isoformat() if sched.next_run_at else None,
        created_at=sched.created_at.isoformat(),
        updated_at=sched.updated_at.isoformat(),
    )


@router.put("/scheduled-validations/{project_id}", response_model=ScheduledValidationOut)
async def update_schedule(
    project_id: UUID,
    body: ScheduleUpdateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update the scheduled validation for a project."""
    await _verify_project_access(db, project_id, current_user)

    result = await db.execute(
        select(ScheduledValidation).where(ScheduledValidation.project_id == project_id)
    )
    sched = result.scalar_one_or_none()
    if not sched:
        raise HTTPException(status_code=404, detail="No schedule found for this project")

    if body.frequency is not None:
        if body.frequency not in ("daily", "weekly", "monthly"):
            raise HTTPException(status_code=400, detail="frequency must be daily, weekly, or monthly")
        sched.frequency = body.frequency
    if body.enabled is not None:
        sched.enabled = body.enabled
        if body.enabled:
            sched.next_run_at = _compute_next_run(sched.frequency)
        else:
            sched.next_run_at = None
    if body.last_config is not None:
        sched.last_config = body.last_config

    await db.commit()
    await db.refresh(sched)

    return ScheduledValidationOut(
        id=str(sched.id),
        project_id=str(sched.project_id),
        enabled=sched.enabled,
        frequency=sched.frequency,
        last_config=sched.last_config,
        last_run_at=sched.last_run_at.isoformat() if sched.last_run_at else None,
        next_run_at=sched.next_run_at.isoformat() if sched.next_run_at else None,
        created_at=sched.created_at.isoformat(),
        updated_at=sched.updated_at.isoformat(),
    )


@router.delete("/scheduled-validations/{project_id}")
async def delete_schedule(
    project_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete the scheduled validation for a project."""
    await _verify_project_access(db, project_id, current_user)
    result = await db.execute(
        select(ScheduledValidation).where(ScheduledValidation.project_id == project_id)
    )
    sched = result.scalar_one_or_none()
    if sched:
        await db.delete(sched)
        await db.commit()
    return {"deleted": True}
