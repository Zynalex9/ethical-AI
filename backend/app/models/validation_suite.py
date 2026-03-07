"""
ValidationSuite model for tracking aggregate validation runs.

A ValidationSuite represents a complete validation workflow that runs
all 4 ethical validations (fairness, transparency, privacy, accountability).
"""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import String, Text, DateTime, Boolean, ForeignKey, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.validation import Validation
    from app.models.ml_model import MLModel
    from app.models.dataset import Dataset
    from app.models.user import User


class ValidationSuite(Base):
    """
    Validation suite tracking for running all validations together.
    
    Represents a complete validation workflow that includes:
    - Fairness validation
    - Transparency/Explainability validation
    - Privacy validation
    - Accountability tracking (via MLflow)
    
    Attributes:
        id: Unique identifier (UUID)
        model_id: Model being validated
        dataset_id: Dataset used for validation
        celery_task_id: ID of the orchestrator Celery task
        status: Current suite status (pending/running/completed/failed)
        overall_passed: Whether all validations passed
        fairness_validation_id: Link to fairness validation
        transparency_validation_id: Link to transparency validation
        privacy_validation_id: Link to privacy validation
        started_at: When suite started
        completed_at: When suite completed
        error_message: Error details if suite failed
        created_by_id: User who initiated the suite
    """
    
    __tablename__ = "validation_suites"
    
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )
    model_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("ml_models.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    dataset_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("datasets.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    celery_task_id: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True
    )
    status: Mapped[str] = mapped_column(
        String(50),
        default="pending",
        nullable=False,
        index=True
    )
    overall_passed: Mapped[Optional[bool]] = mapped_column(
        Boolean,
        nullable=True
    )
    fairness_validation_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("validations.id", ondelete="SET NULL"),
        nullable=True
    )
    transparency_validation_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("validations.id", ondelete="SET NULL"),
        nullable=True
    )
    privacy_validation_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("validations.id", ondelete="SET NULL"),
        nullable=True
    )
    started_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )
    error_message: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True
    )
    created_by_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )
    
    # Relationships
    model: Mapped["MLModel"] = relationship(
        "MLModel",
        foreign_keys=[model_id]
    )
    dataset: Mapped["Dataset"] = relationship(
        "Dataset",
        foreign_keys=[dataset_id]
    )
    created_by: Mapped["User"] = relationship(
        "User",
        foreign_keys=[created_by_id]
    )
    fairness_validation: Mapped[Optional["Validation"]] = relationship(
        "Validation",
        foreign_keys=[fairness_validation_id]
    )
    transparency_validation: Mapped[Optional["Validation"]] = relationship(
        "Validation",
        foreign_keys=[transparency_validation_id]
    )
    privacy_validation: Mapped[Optional["Validation"]] = relationship(
        "Validation",
        foreign_keys=[privacy_validation_id]
    )
    
    def __repr__(self) -> str:
        return f"<ValidationSuite(id={self.id}, status={self.status})>"
