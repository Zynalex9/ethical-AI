"""
Audit log model for tracking all platform activities.
"""

import uuid
from datetime import datetime
from enum import Enum as PyEnum
from typing import TYPE_CHECKING, Any, Dict, Optional

from sqlalchemy import String, DateTime, ForeignKey, func
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.user import User


class AuditAction(str, PyEnum):
    """Types of auditable actions."""
    # Authentication
    USER_LOGIN = "user_login"
    USER_LOGOUT = "user_logout"
    USER_REGISTER = "user_register"
    
    # Project operations
    PROJECT_CREATE = "project_create"
    PROJECT_UPDATE = "project_update"
    PROJECT_DELETE = "project_delete"
    
    # Model operations
    MODEL_UPLOAD = "model_upload"
    MODEL_DELETE = "model_delete"
    
    # Dataset operations
    DATASET_UPLOAD = "dataset_upload"
    DATASET_DELETE = "dataset_delete"
    
    # Requirement operations
    REQUIREMENT_CREATE = "requirement_create"
    REQUIREMENT_UPDATE = "requirement_update"
    REQUIREMENT_DELETE = "requirement_delete"
    
    # Validation operations
    VALIDATION_START = "validation_start"
    VALIDATION_COMPLETE = "validation_complete"
    VALIDATION_FAIL = "validation_fail"
    
    # Template operations
    TEMPLATE_CREATE = "template_create"
    TEMPLATE_UPDATE = "template_update"


class ResourceType(str, PyEnum):
    """Types of resources that can be audited."""
    USER = "user"
    PROJECT = "project"
    MODEL = "model"
    DATASET = "dataset"
    REQUIREMENT = "requirement"
    VALIDATION = "validation"
    TEMPLATE = "template"


class AuditLog(Base):
    """
    Audit log for tracking all platform activities.
    
    Provides complete traceability for regulatory compliance
    and debugging purposes.
    
    Attributes:
        id: Unique identifier (auto-increment for efficiency)
        timestamp: When the action occurred
        user_id: Who performed the action
        action: Type of action performed
        resource_type: Type of resource affected
        resource_id: ID of the affected resource
        details: JSONB with additional context (before/after states)
        ip_address: Client IP address
        user_agent: Client user agent string
    """
    
    __tablename__ = "audit_logs"
    
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True
    )
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True
    )
    action: Mapped[AuditAction] = mapped_column(
        String(50),
        nullable=False,
        index=True
    )
    resource_type: Mapped[ResourceType] = mapped_column(
        String(50),
        nullable=False
    )
    resource_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        nullable=True
    )
    details: Mapped[Dict[str, Any]] = mapped_column(
        JSONB,
        default=dict,
        nullable=False
    )
    ip_address: Mapped[Optional[str]] = mapped_column(
        String(45),  # Supports IPv6
        nullable=True
    )
    user_agent: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True
    )
    
    # Relationships
    user: Mapped[Optional["User"]] = relationship(
        "User",
        back_populates="audit_logs"
    )
    
    def __repr__(self) -> str:
        return f"<AuditLog(action={self.action}, resource={self.resource_type}:{self.resource_id})>"
