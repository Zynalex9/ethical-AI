# Custom Rules router — CRUD for user-defined validation rules

import math
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel, Field

from ..database import get_db
from ..dependencies import get_current_user
from ..models.user import User
from ..models.project import Project
from ..models.custom_rule import CustomRule
from ..validators.fairness_validator import SUPPORTED_BASE_METRICS, SUPPORTED_AGGREGATIONS
from ..middleware.logging_config import get_logger

logger = get_logger("routers.custom_rules")
router = APIRouter(prefix="/custom-rules", tags=["custom-rules"])


# ---------- Schemas ----------

class CustomRuleCreate(BaseModel):
    project_id: UUID
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    principle: str = Field(default="fairness", pattern="^(fairness|privacy)$")
    base_metric: str
    aggregation: str
    comparison: str = Field(default=">=", pattern="^(>=|<=)$")
    default_threshold: float = 0.8


class CustomRuleUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    base_metric: Optional[str] = None
    aggregation: Optional[str] = None
    comparison: Optional[str] = Field(None, pattern="^(>=|<=)$")
    default_threshold: Optional[float] = None


class CustomRuleResponse(BaseModel):
    id: UUID
    project_id: UUID
    name: str
    description: Optional[str]
    principle: str
    base_metric: str
    aggregation: str
    comparison: str
    default_threshold: float
    created_by_id: Optional[UUID]

    model_config = {"from_attributes": True}


# ---------- Helpers ----------

async def _verify_project_access(
    db: AsyncSession, current_user: User, project_id: UUID
) -> Project:
    result = await db.execute(
        select(Project).where(Project.id == project_id, Project.deleted_at.is_(None))
    )
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    if current_user.role.value != "admin" and project.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")
    return project


def _validate_rule_fields(base_metric: str, aggregation: str) -> None:
    if base_metric not in SUPPORTED_BASE_METRICS:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Unsupported base_metric '{base_metric}'. "
                f"Choose from: {sorted(SUPPORTED_BASE_METRICS.keys())}"
            ),
        )
    if aggregation not in SUPPORTED_AGGREGATIONS:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Unsupported aggregation '{aggregation}'. "
                f"Choose from: {sorted(SUPPORTED_AGGREGATIONS)}"
            ),
        )


def _normalize_rule_name(name: str) -> str:
    normalized = name.strip()
    if not normalized:
        raise HTTPException(status_code=400, detail="Rule name cannot be empty")
    return normalized


def _validate_threshold_value(default_threshold: float) -> None:
    if not math.isfinite(default_threshold):
        raise HTTPException(status_code=400, detail="default_threshold must be a finite number")


async def _assert_unique_rule_name(
    db: AsyncSession,
    *,
    project_id: UUID,
    principle: str,
    name: str,
    exclude_rule_id: Optional[UUID] = None,
) -> None:
    query = select(CustomRule).where(
        CustomRule.project_id == project_id,
        CustomRule.principle == principle,
        CustomRule.name == name,
    )
    if exclude_rule_id:
        query = query.where(CustomRule.id != exclude_rule_id)

    existing = (await db.execute(query)).scalar_one_or_none()
    if existing:
        raise HTTPException(
            status_code=409,
            detail=f"A {principle} custom rule named '{name}' already exists for this project",
        )


# ---------- Endpoints ----------

@router.post("", response_model=CustomRuleResponse, status_code=status.HTTP_201_CREATED)
async def create_custom_rule(
    body: CustomRuleCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a new custom validation rule for a project."""
    await _verify_project_access(db, current_user, body.project_id)
    normalized_name = _normalize_rule_name(body.name)
    _validate_rule_fields(body.base_metric, body.aggregation)
    _validate_threshold_value(body.default_threshold)
    await _assert_unique_rule_name(
        db,
        project_id=body.project_id,
        principle=body.principle,
        name=normalized_name,
    )

    rule = CustomRule(
        project_id=body.project_id,
        name=normalized_name,
        description=body.description,
        principle=body.principle,
        base_metric=body.base_metric,
        aggregation=body.aggregation,
        comparison=body.comparison,
        default_threshold=body.default_threshold,
        created_by_id=current_user.id,
    )
    db.add(rule)
    await db.commit()
    await db.refresh(rule)

    logger.info("Custom rule created: id=%s name=%s project=%s", rule.id, rule.name, body.project_id)
    return rule


@router.get("", response_model=List[CustomRuleResponse])
async def list_custom_rules(
    project_id: UUID,
    principle: Optional[str] = Query(default=None, pattern="^(fairness|privacy)$"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List custom rules for a project, optionally filtered by principle."""
    await _verify_project_access(db, current_user, project_id)

    query = select(CustomRule).where(CustomRule.project_id == project_id)
    if principle:
        query = query.where(CustomRule.principle == principle)
    query = query.order_by(CustomRule.created_at.desc())

    result = await db.execute(query)
    return result.scalars().all()


@router.get("/supported/base-metrics")
async def list_supported_base_metrics(
    current_user: User = Depends(get_current_user),
):
    """Return supported base metric and aggregation options for custom rules."""
    return {
        "base_metrics": sorted(SUPPORTED_BASE_METRICS.keys()),
        "aggregations": sorted(SUPPORTED_AGGREGATIONS),
        "comparisons": [">=", "<="],
    }


@router.get("/{rule_id}", response_model=CustomRuleResponse)
async def get_custom_rule(
    rule_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get a single custom rule by ID."""
    result = await db.execute(select(CustomRule).where(CustomRule.id == rule_id))
    rule = result.scalar_one_or_none()
    if not rule:
        raise HTTPException(status_code=404, detail="Custom rule not found")

    await _verify_project_access(db, current_user, rule.project_id)
    return rule


@router.put("/{rule_id}", response_model=CustomRuleResponse)
async def update_custom_rule(
    rule_id: UUID,
    body: CustomRuleUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update an existing custom rule."""
    result = await db.execute(select(CustomRule).where(CustomRule.id == rule_id))
    rule = result.scalar_one_or_none()
    if not rule:
        raise HTTPException(status_code=404, detail="Custom rule not found")

    await _verify_project_access(db, current_user, rule.project_id)

    # Validate changed fields
    new_base = body.base_metric or rule.base_metric
    new_agg = body.aggregation or rule.aggregation
    new_name = _normalize_rule_name(body.name) if body.name is not None else rule.name
    _validate_rule_fields(new_base, new_agg)
    if body.default_threshold is not None:
        _validate_threshold_value(body.default_threshold)

    await _assert_unique_rule_name(
        db,
        project_id=rule.project_id,
        principle=rule.principle,
        name=new_name,
        exclude_rule_id=rule.id,
    )

    # Apply updates
    for field_name, value in body.model_dump(exclude_unset=True).items():
        if field_name == "name" and value is not None:
            value = value.strip()
        setattr(rule, field_name, value)

    await db.commit()
    await db.refresh(rule)

    logger.info("Custom rule updated: id=%s name=%s", rule.id, rule.name)
    return rule


@router.delete("/{rule_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_custom_rule(
    rule_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete a custom rule."""
    result = await db.execute(select(CustomRule).where(CustomRule.id == rule_id))
    rule = result.scalar_one_or_none()
    if not rule:
        raise HTTPException(status_code=404, detail="Custom rule not found")

    await _verify_project_access(db, current_user, rule.project_id)

    await db.delete(rule)
    await db.commit()
    logger.info("Custom rule deleted: id=%s", rule_id)
