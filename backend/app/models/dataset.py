"""
Dataset model for storing uploaded datasets used in validation.
"""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from sqlalchemy import String, Text, DateTime, ForeignKey, Integer, func
from sqlalchemy.dialects.postgresql import UUID, JSONB, ARRAY
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.project import Project
    from app.models.user import User
    from app.models.validation import Validation


class Dataset(Base):
    """
    Dataset entity for storing uploaded datasets.
    
    Contains metadata about the dataset including schema information,
    detected sensitive attributes, and profiling results.
    
    Attributes:
        id: Unique identifier (UUID)
        project_id: Foreign key to parent project
        name: Dataset name
        description: Optional description
        file_path: Path to stored CSV/Parquet file
        row_count: Number of rows in dataset
        column_count: Number of columns
        columns: List of column names
        sensitive_attributes: Detected/specified sensitive columns
        target_column: The prediction target column
        profile_data: JSONB field with profiling results (distributions, stats)
        uploaded_at: Upload timestamp
        uploaded_by_id: User who uploaded the dataset
    """
    
    __tablename__ = "datasets"
    
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
    file_path: Mapped[str] = mapped_column(
        String(500),
        nullable=False
    )
    row_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0
    )
    column_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0
    )
    columns: Mapped[List[str]] = mapped_column(
        ARRAY(String),
        nullable=False,
        default=list
    )
    sensitive_attributes: Mapped[List[str]] = mapped_column(
        ARRAY(String),
        nullable=False,
        default=list
    )
    target_column: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True
    )
    profile_data: Mapped[Dict[str, Any]] = mapped_column(
        JSONB,
        default=dict,
        nullable=False
    )
    uploaded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )
    uploaded_by_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True
    )
    
    # Relationships
    project: Mapped["Project"] = relationship(
        "Project",
        back_populates="datasets"
    )
    validations: Mapped[List["Validation"]] = relationship(
        "Validation",
        back_populates="dataset",
        cascade="all, delete-orphan"
    )
    
    def __repr__(self) -> str:
        return f"<Dataset(id={self.id}, name={self.name}, rows={self.row_count})>"
