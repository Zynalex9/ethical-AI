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
    # Remove the role restriction - allow all authenticated users
    # Non-admins/auditors will see statistics filtered to their own logs
    
    now = datetime.now(timezone.utc)
    today = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_ago = today - timedelta(days=7)
    
    # Base query - filter by user if not admin/auditor
    base_query = select(AuditLog)
    if current_user.role.value not in ["admin", "auditor"]:
        base_query = base_query.where(AuditLog.user_id == current_user.id)
    
    # Apply base filter to all counts
    total = await db.scalar(select(func.count(AuditLog.id)).select_from(base_query.subquery()))
    
    # For today
    today_query = base_query.where(AuditLog.timestamp >= today)
    today_count = await db.scalar(select(func.count(AuditLog.id)).select_from(today_query.subquery()))
    
    # For this week
    week_query = base_query.where(AuditLog.timestamp >= week_ago)
    week_count = await db.scalar(select(func.count(AuditLog.id)).select_from(week_query.subquery()))
    
    # By action (with user filter)
    action_query = select(AuditLog.action, func.count(AuditLog.id)).group_by(AuditLog.action)
    if current_user.role.value not in ["admin", "auditor"]:
        action_query = action_query.where(AuditLog.user_id == current_user.id)
    
    action_stats = await db.execute(action_query)
    by_action = {
        (a.value if hasattr(a, 'value') else str(a)): c 
        for a, c in action_stats.all()
    }
    
    # By resource (with user filter)
    res_query = select(AuditLog.resource_type, func.count(AuditLog.id)).group_by(AuditLog.resource_type)
    if current_user.role.value not in ["admin", "auditor"]:
        res_query = res_query.where(AuditLog.user_id == current_user.id)
    
    res_stats = await db.execute(res_query)
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
