"""
Requirement model for ethical validation requirements.
"""

import uuid
from datetime import datetime
from enum import Enum as PyEnum
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from sqlalchemy import String, Text, DateTime, ForeignKey, Integer, Boolean, Float, func
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.project import Project
    from app.models.user import User
    from app.models.validation import Validation


class EthicalPrinciple(str, PyEnum):
    """The four core ethical principles."""
    FAIRNESS = "fairness"
    TRANSPARENCY = "transparency"
    PRIVACY = "privacy"
    ACCOUNTABILITY = "accountability"


class RequirementStatus(str, PyEnum):
    """Status of a requirement definition."""
    DRAFT = "draft"
    ACTIVE = "active"
    ARCHIVED = "archived"


class Requirement(Base):
    """
    Ethical requirement definition.
    
    Defines specific ethical requirements that models must satisfy.
    Can be based on a template or custom-defined.
    
    Attributes:
        id: Unique identifier (UUID)
        project_id: Foreign key to parent project
        name: Requirement name
        description: Detailed description
        principle: Which ethical principle this addresses
        specification: JSONB containing detailed rules
        based_on_template_id: Optional template this is based on
        status: Current status (draft, active, archived)
        version: Requirement version for tracking changes
        created_at: Creation timestamp
        created_by_id: User who created the requirement
    """
    
    __tablename__ = "requirements"
    
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False
    )
    description: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True
    )
    principle: Mapped[EthicalPrinciple] = mapped_column(
        String(50),
        nullable=False,
        index=True
    )
    specification: Mapped[Dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict
    )
    based_on_template_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("templates.id", ondelete="SET NULL"),
        nullable=True
    )
    status: Mapped[RequirementStatus] = mapped_column(
        String(50),
        default=RequirementStatus.DRAFT,
        nullable=False
    )
    version: Mapped[int] = mapped_column(
        Integer,
        default=1,
        nullable=False
    )
    # Phase 2: auto-elicitation fields
    elicited_automatically: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        server_default='false'
    )
    elicitation_reason: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True
    )
    confidence_score: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False
    )
    created_by_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True
    )
    
    # Relationships
    project: Mapped["Project"] = relationship(
        "Project",
        back_populates="requirements"
    )
    validations: Mapped[List["Validation"]] = relationship(
        "Validation",
        back_populates="requirement",
        cascade="all, delete-orphan"
    )
    
    def __repr__(self) -> str:
        return f"<Requirement(id={self.id}, name={self.name}, principle={self.principle})>"
