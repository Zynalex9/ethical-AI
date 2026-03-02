"""
Admin router – system statistics, user management, and health checks.

All endpoints require admin role.
"""

from typing import List, Optional
from uuid import UUID
from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..dependencies import get_current_user
from ..models.user import User, UserRole
from ..models.project import Project
from ..models.ml_model import MLModel
from ..models.dataset import Dataset
from ..models.validation import Validation, ValidationStatus
from ..models.audit_log import AuditLog
from ..middleware.logging_config import get_logger

logger = get_logger("routers.admin")
router = APIRouter(prefix="/admin", tags=["admin"])


# ── Helpers ────────────────────────────────────────────────────
def _require_admin(current_user: User) -> None:
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Admin access required")


# ── Schemas ────────────────────────────────────────────────────
class SystemStats(BaseModel):
    total_users: int
    total_projects: int
    total_models: int
    total_datasets: int
    total_validations: int
    validations_passed: int
    validations_failed: int
    validations_running: int


class UserRow(BaseModel):
    id: UUID
    email: str
    name: str
    role: str
    is_active: bool
    created_at: datetime
    last_login: Optional[datetime] = None

    class Config:
        from_attributes = True


class UserRoleUpdate(BaseModel):
    role: str  # "user" | "admin" | "auditor"


class UserStatusUpdate(BaseModel):
    is_active: bool


class HealthStatus(BaseModel):
    database: str  # "ok" | "error"
    redis: str
    celery: str


class ActivityItem(BaseModel):
    id: UUID
    action: str
    resource_type: str
    user_email: Optional[str] = None
    created_at: datetime


# ── Endpoints ──────────────────────────────────────────────────
@router.get("/stats", response_model=SystemStats)
async def get_system_stats(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get platform-wide statistics (admin only)."""
    _require_admin(current_user)

    users = await db.scalar(select(func.count(User.id))) or 0
    projects = await db.scalar(
        select(func.count(Project.id)).where(Project.deleted_at.is_(None))
    ) or 0
    models = await db.scalar(select(func.count(MLModel.id))) or 0
    datasets = await db.scalar(select(func.count(Dataset.id))) or 0
    validations = await db.scalar(select(func.count(Validation.id))) or 0
    passed = await db.scalar(
        select(func.count(Validation.id)).where(Validation.status == ValidationStatus.COMPLETED)
    ) or 0
    failed = await db.scalar(
        select(func.count(Validation.id)).where(Validation.status == ValidationStatus.FAILED)
    ) or 0
    running = await db.scalar(
        select(func.count(Validation.id)).where(Validation.status == ValidationStatus.RUNNING)
    ) or 0

    return SystemStats(
        total_users=users,
        total_projects=projects,
        total_models=models,
        total_datasets=datasets,
        total_validations=validations,
        validations_passed=passed,
        validations_failed=failed,
        validations_running=running,
    )


@router.get("/users", response_model=List[UserRow])
async def list_users(
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all users (admin only)."""
    _require_admin(current_user)
    result = await db.execute(
        select(User).order_by(User.created_at.desc()).offset(skip).limit(limit)
    )
    users = result.scalars().all()
    return [
        UserRow(
            id=u.id,
            email=u.email,
            name=u.name,
            role=u.role.value if hasattr(u.role, "value") else str(u.role),
            is_active=u.is_active,
            created_at=u.created_at,
            last_login=u.last_login,
        )
        for u in users
    ]


@router.patch("/users/{user_id}/role")
async def update_user_role(
    user_id: UUID,
    body: UserRoleUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Change a user's role (admin only)."""
    _require_admin(current_user)

    if body.role not in ("user", "admin", "auditor"):
        raise HTTPException(status_code=400, detail="Invalid role")

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    user.role = UserRole(body.role)
    await db.commit()
    logger.info("Admin %s changed user %s role to %s", current_user.email, user.email, body.role)
    return {"message": f"Role updated to {body.role}"}


@router.patch("/users/{user_id}/status")
async def update_user_status(
    user_id: UUID,
    body: UserStatusUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Activate or deactivate a user (admin only)."""
    _require_admin(current_user)

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if user.id == current_user.id:
        raise HTTPException(status_code=400, detail="Cannot deactivate yourself")

    user.is_active = body.is_active
    await db.commit()
    action = "activated" if body.is_active else "deactivated"
    logger.info("Admin %s %s user %s", current_user.email, action, user.email)
    return {"message": f"User {action}"}


@router.get("/health", response_model=HealthStatus)
async def get_system_health(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Check system component health (admin only)."""
    _require_admin(current_user)

    # Database check
    db_status = "ok"
    try:
        await db.execute(select(func.count(User.id)))
    except Exception:
        db_status = "error"

    # Redis check
    redis_status = "ok"
    try:
        import redis as _redis
        from ..config import settings
        r = _redis.from_url(settings.redis_url, socket_timeout=2)
        r.ping()
    except Exception:
        redis_status = "error"

    # Celery check
    celery_status = "ok"
    try:
        from ..celery_app import celery_app
        insp = celery_app.control.inspect(timeout=2)
        if not insp.ping():
            celery_status = "error"
    except Exception:
        celery_status = "error"

    return HealthStatus(database=db_status, redis=redis_status, celery=celery_status)


@router.get("/activity", response_model=List[ActivityItem])
async def get_recent_activity(
    limit: int = 20,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get recent platform activity (admin only)."""
    _require_admin(current_user)

    result = await db.execute(
        select(AuditLog).order_by(AuditLog.created_at.desc()).limit(limit)
    )
    logs = result.scalars().all()

    return [
        ActivityItem(
            id=log.id,
            action=log.action.value if hasattr(log.action, "value") else str(log.action),
            resource_type=log.resource_type.value if hasattr(log.resource_type, "value") else str(log.resource_type),
            user_email=None,
            created_at=log.created_at,
        )
        for log in logs
    ]
