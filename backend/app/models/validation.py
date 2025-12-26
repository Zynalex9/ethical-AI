"""
Validation and ValidationResult models for tracking validation runs.
"""

import uuid
from datetime import datetime
from enum import Enum as PyEnum
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from sqlalchemy import String, DateTime, ForeignKey, Boolean, Float, func
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.requirement import Requirement
    from app.models.ml_model import MLModel
    from app.models.dataset import Dataset


class ValidationStatus(str, PyEnum):
    """Status of a validation run."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class Validation(Base):
    """
    Validation run tracking.
    
    Represents a single validation execution that tests a model
    against requirements using a specific dataset.
    
    Attributes:
        id: Unique identifier (UUID)
        requirement_id: The requirement being validated
        model_id: The model being tested
        dataset_id: The dataset used for testing
        celery_task_id: ID of the async Celery task
        status: Current validation status
        progress: Progress percentage (0-100)
        started_at: When validation started
        completed_at: When validation completed
        mlflow_run_id: Link to MLflow experiment run
        error_message: Error details if validation failed
    """
    
    __tablename__ = "validations"
    
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )
    requirement_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("requirements.id", ondelete="CASCADE"),
        nullable=False,
        index=True
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
    status: Mapped[ValidationStatus] = mapped_column(
        String(50),
        default=ValidationStatus.PENDING,
        nullable=False,
        index=True
    )
    progress: Mapped[int] = mapped_column(
        default=0,
        nullable=False
    )
    started_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )
    mlflow_run_id: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True
    )
    error_message: Mapped[Optional[str]] = mapped_column(
        String(1000),
        nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )
    
    # Relationships
    requirement: Mapped["Requirement"] = relationship(
        "Requirement",
        back_populates="validations"
    )
    model: Mapped["MLModel"] = relationship(
        "MLModel",
        back_populates="validations"
    )
    dataset: Mapped["Dataset"] = relationship(
        "Dataset",
        back_populates="validations"
    )
    results: Mapped[List["ValidationResult"]] = relationship(
        "ValidationResult",
        back_populates="validation",
        cascade="all, delete-orphan"
    )
    
    def __repr__(self) -> str:
        return f"<Validation(id={self.id}, status={self.status})>"


class ValidationResult(Base):
    """
    Individual validation result metrics.
    
    Stores individual metric results from a validation run.
    Each validation can have multiple results (one per metric).
    
    Attributes:
        id: Unique identifier (UUID)
        validation_id: Parent validation run
        principle: Which ethical principle was tested
        metric_name: Name of the metric (e.g., "demographic_parity_ratio")
        metric_value: Computed metric value
        threshold: Required threshold for passing
        passed: Whether the metric passed the threshold
        details: JSONB for additional context (visualizations, breakdowns)
        created_at: Result creation timestamp
    """
    
    __tablename__ = "validation_results"
    
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )
    validation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("validations.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    principle: Mapped[str] = mapped_column(
        String(50),
        nullable=False
    )
    metric_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False
    )
    metric_value: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True
    )
    threshold: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True
    )
    passed: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False
    )
    details: Mapped[Dict[str, Any]] = mapped_column(
        JSONB,
        default=dict,
        nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )
    
    # Relationships
    validation: Mapped["Validation"] = relationship(
        "Validation",
        back_populates="results"
    )
    
    def __repr__(self) -> str:
        status = "✓" if self.passed else "✗"
        return f"<ValidationResult({self.metric_name}={self.metric_value} {status})>"
