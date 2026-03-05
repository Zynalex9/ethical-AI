"""
Remediation model for tracking guided fix steps.

Stores per-user, per-validation-suite remediation checklists with
step completion state.
"""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from sqlalchemy import String, DateTime, Boolean, Integer, ForeignKey, Text, func
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.validation_suite import ValidationSuite


class RemediationChecklist(Base):
    """
    Stores a user's remediation progress for a specific validation suite.

    Attributes:
        id: Unique identifier
        user_id: The user working through remediation
        validation_suite_id: The suite that failed
        principle: fairness / privacy / transparency / accountability
        steps: JSONB array of step objects — each has id, description, done, doc_link
        created_at: When the checklist was created
        updated_at: Last modification
    """

    __tablename__ = "remediation_checklists"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    validation_suite_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, index=True
    )
    principle: Mapped[str] = mapped_column(String(50), nullable=False)
    steps: Mapped[List[Dict[str, Any]]] = mapped_column(JSONB, nullable=False, default=list)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    user: Mapped["User"] = relationship("User", foreign_keys=[user_id])

    def __repr__(self) -> str:
        return f"<RemediationChecklist(id={self.id}, suite={self.validation_suite_id}, principle={self.principle})>"
