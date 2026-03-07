"""
Project model for organizing models, datasets, and validations.
"""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import String, Text, DateTime, ForeignKey, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.ml_model import MLModel
    from app.models.dataset import Dataset
    from app.models.requirement import Requirement


class Project(Base):
    """
    Project model for grouping related AI validation work.
    
    Attributes:
        id: Unique identifier (UUID)
        name: Project name
        description: Optional project description
        owner_id: Foreign key to the owner (User)
        created_at: Project creation timestamp
        updated_at: Last modification timestamp
        deleted_at: Soft delete timestamp (null if not deleted)
    """
    
    __tablename__ = "projects"
    
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False
    )
    description: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True
    )
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True
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
    deleted_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )
    
    # Relationships
    owner: Mapped["User"] = relationship(
        "User",
        back_populates="projects"
    )
    models: Mapped[List["MLModel"]] = relationship(
        "MLModel",
        back_populates="project",
        cascade="all, delete-orphan"
    )
    datasets: Mapped[List["Dataset"]] = relationship(
        "Dataset",
        back_populates="project",
        cascade="all, delete-orphan"
    )
    requirements: Mapped[List["Requirement"]] = relationship(
        "Requirement",
        back_populates="project",
        cascade="all, delete-orphan"
    )
    
    @property
    def is_deleted(self) -> bool:
        """Check if project has been soft deleted."""
        return self.deleted_at is not None
    
    def __repr__(self) -> str:
        return f"<Project(id={self.id}, name={self.name})>"
