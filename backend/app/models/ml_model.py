"""
ML Model entity for storing uploaded machine learning models.
"""

import uuid
from datetime import datetime
from enum import Enum as PyEnum
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from sqlalchemy import String, Text, DateTime, ForeignKey, BigInteger, func
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.project import Project
    from app.models.user import User
    from app.models.validation import Validation


class ModelType(str, PyEnum):
    """Supported ML model types/frameworks."""
    SKLEARN = "sklearn"
    TENSORFLOW = "tensorflow"
    PYTORCH = "pytorch"
    ONNX = "onnx"
    XGBOOST = "xgboost"
    LIGHTGBM = "lightgbm"
    UNKNOWN = "unknown"


class MLModel(Base):
    """
    Machine Learning Model entity.
    
    Stores metadata about uploaded ML models including their
    file location, type, and extracted metadata.
    
    Attributes:
        id: Unique identifier (UUID)
        project_id: Foreign key to parent project
        name: Model name
        description: Optional model description
        file_path: Path to stored model file
        file_size: Size of model file in bytes
        model_type: Type of ML framework (sklearn, tensorflow, etc.)
        model_metadata: JSONB field for framework-specific metadata
        version: Model version string
        uploaded_at: Upload timestamp
        uploaded_by_id: User who uploaded the model
    """
    
    __tablename__ = "ml_models"
    
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
    file_size: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False
    )
    model_type: Mapped[ModelType] = mapped_column(
        String(50),
        default=ModelType.UNKNOWN,
        nullable=False
    )
    model_metadata: Mapped[Dict[str, Any]] = mapped_column(
        JSONB,
        default=dict,
        nullable=False
    )
    version: Mapped[str] = mapped_column(
        String(50),
        default="1.0.0",
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
        back_populates="models"
    )
    validations: Mapped[List["Validation"]] = relationship(
        "Validation",
        back_populates="model",
        cascade="all, delete-orphan"
    )
    
    def __repr__(self) -> str:
        return f"<MLModel(id={self.id}, name={self.name}, type={self.model_type})>"
