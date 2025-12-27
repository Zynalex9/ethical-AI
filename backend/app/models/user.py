"""
User model for authentication and authorization.
"""

import uuid
from datetime import datetime
from enum import Enum as PyEnum
from typing import TYPE_CHECKING, List

from sqlalchemy import String, Boolean, Enum, DateTime, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.project import Project
    from app.models.audit_log import AuditLog


class UserRole(str, PyEnum):
    """User roles for authorization."""
    USER = "user"
    ADMIN = "admin"
    AUDITOR = "auditor"


class User(Base):
    """
    User model representing platform users.
    
    Attributes:
        id: Unique identifier (UUID)
        email: User's email address (unique)
        hashed_password: Bcrypt hashed password
        name: Display name
        role: User role (user, admin, auditor)
        is_active: Whether the user account is active
        created_at: Account creation timestamp
        last_login: Last successful login timestamp
    """
    
    __tablename__ = "users"
    
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )
    email: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        index=True,
        nullable=False
    )
    hashed_password: Mapped[str] = mapped_column(
        String(255),
        nullable=False
    )
    name: Mapped[str] = mapped_column(
        String(100),
        nullable=False
    )
    role: Mapped[UserRole] = mapped_column(
        Enum(UserRole),
        default=UserRole.USER,
        nullable=False
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )
    last_login: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )
    
    # Relationships
    projects: Mapped[List["Project"]] = relationship(
        "Project",
        back_populates="owner",
        cascade="all, delete-orphan"
    )
    audit_logs: Mapped[List["AuditLog"]] = relationship(
        "AuditLog",
        back_populates="user",
        cascade="all, delete-orphan"
    )
    
    def __repr__(self) -> str:
        return f"<User(id={self.id}, email={self.email}, role={self.role})>"
