"""
Template model for predefined ethical requirement templates.
"""

import uuid
from datetime import datetime
from enum import Enum as PyEnum
from typing import Any, Dict, Optional

from sqlalchemy import String, Text, DateTime, Integer, func
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class TemplateDomain(str, PyEnum):
    """Domain categories for templates."""
    FINANCE = "finance"
    HEALTHCARE = "healthcare"
    CRIMINAL_JUSTICE = "criminal_justice"
    EDUCATION = "education"
    EMPLOYMENT = "employment"
    GENERAL = "general"


class Template(Base):
    """
    Ethical requirement template for common use cases.
    
    Templates are predefined sets of ethical requirements that users
    can select instead of defining custom rules. Examples:
    - ETH1: Financial Services (lending, credit scoring)
    - ETH2: Healthcare (medical diagnosis, treatment)
    - ETH3: Criminal Justice (recidivism, risk assessment)
    
    Attributes:
        id: Unique identifier (UUID)
        template_id: Human-readable template identifier (e.g., "ETH1")
        name: Template name
        description: Detailed template description
        domain: Domain category (finance, healthcare, etc.)
        rules: JSONB field containing all requirement specifications
        version: Template version number
        is_active: Whether template is currently available
        created_at: Creation timestamp
        updated_at: Last update timestamp
    """
    
    __tablename__ = "templates"
    
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )
    template_id: Mapped[str] = mapped_column(
        String(50),
        unique=True,
        index=True,
        nullable=False
    )
    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False
    )
    description: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True
    )
    domain: Mapped[TemplateDomain] = mapped_column(
        String(50),
        default=TemplateDomain.GENERAL,
        nullable=False
    )
    rules: Mapped[Dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict
    )
    version: Mapped[int] = mapped_column(
        Integer,
        default=1,
        nullable=False
    )
    is_active: Mapped[bool] = mapped_column(
        default=True,
        nullable=False
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
    
    def __repr__(self) -> str:
        return f"<Template(id={self.template_id}, name={self.name}, domain={self.domain})>"
