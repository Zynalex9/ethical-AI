# Audit router - View and query audit logs

from typing import List, Optional, Dict, Any
from uuid import UUID
from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc
from pydantic import BaseModel

from ..database import get_db
from ..dependencies import get_current_user
from ..models.user import User
from ..models.audit_log import AuditLog, AuditAction, ResourceType

router = APIRouter(prefix="/audit", tags=["audit"])


# Pydantic schemas
class AuditLogResponse(BaseModel):
    id: UUID
    user_id: Optional[UUID]
    user_email: Optional[str]
    action: str
    resource_type: str
    resource_id: Optional[UUID]
    ip_address: Optional[str]
    details: Optional[Dict[str, Any]]
    created_at: datetime
    
    class Config:
        from_attributes = True


class AuditSummary(BaseModel):
    total_events: int
    events_today: int
    events_this_week: int
    by_action: Dict[str, int]
    by_resource_type: Dict[str, int]


@router.get("", response_model=List[AuditLogResponse])
async def list_audit_logs(
    skip: int = 0,
    limit: int = 100,
    action: Optional[str] = None,
    resource_type: Optional[str] = None,
    user_id: Optional[UUID] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    List audit logs with optional filters.
    """
    query = select(AuditLog)
    
    # Non-admins/auditors see only their own logs
    if current_user.role.value not in ["admin", "auditor"]:
        query = query.where(AuditLog.user_id == current_user.id)
        
    if action:
        query = query.where(AuditLog.action == action)
    if resource_type:
        query = query.where(AuditLog.resource_type == resource_type)
    if user_id:
        query = query.where(AuditLog.user_id == user_id)
    if start_date:
        query = query.where(AuditLog.created_at >= start_date)
    if end_date:
        query = query.where(AuditLog.created_at <= end_date)
        
    query = query.order_by(desc(AuditLog.created_at)).offset(skip).limit(limit)
    
    result = await db.execute(query)
    logs = result.scalars().all()
    
    return [
        AuditLogResponse(
            id=log.id,
            user_id=log.user_id,
            user_email=None,  # Optimization: skip user join for now
            action=log.action.value if hasattr(log.action, 'value') else str(log.action),
            resource_type=log.resource_type.value if hasattr(log.resource_type, 'value') else str(log.resource_type),
            resource_id=log.resource_id,
            ip_address=log.ip_address,
            details=log.details,
            created_at=log.created_at
        )
        for log in logs
    ]


@router.get("/summary", response_model=AuditSummary)
async def get_audit_summary(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get summary statistics of audit logs."""
    if current_user.role.value not in ["admin", "auditor"]:
        raise HTTPException(status_code=403, detail="Access denied")
    
    now = datetime.now(timezone.utc)
    today = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_ago = today - timedelta(days=7)
    
    total = await db.scalar(select(func.count(AuditLog.id)))
    today_count = await db.scalar(select(func.count(AuditLog.id)).where(AuditLog.created_at >= today))
    week_count = await db.scalar(select(func.count(AuditLog.id)).where(AuditLog.created_at >= week_ago))
    
    # By action
    action_stats = await db.execute(
        select(AuditLog.action, func.count(AuditLog.id)).group_by(AuditLog.action)
    )
    by_action = {
        (a.value if hasattr(a, 'value') else str(a)): c 
        for a, c in action_stats.all()
    }
    
    # By resource
    res_stats = await db.execute(
        select(AuditLog.resource_type, func.count(AuditLog.id)).group_by(AuditLog.resource_type)
    )
    by_resource = {
        (r.value if hasattr(r, 'value') else str(r)): c 
        for r, c in res_stats.all()
    }
    
    return AuditSummary(
        total_events=total or 0,
        events_today=today_count or 0,
        events_this_week=week_count or 0,
        by_action=by_action,
        by_resource_type=by_resource
    )
