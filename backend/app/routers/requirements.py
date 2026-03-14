"""
Requirements router — Phase 2 (Cognitive RE)

Endpoints:
  POST /requirements/elicit-from-dataset    → analyse dataset, return suggestions
  POST /requirements/elicit-from-model      → analyse model+dataset, return suggestions
  POST /requirements/accept-elicited        → save accepted suggestion to DB
  GET  /requirements/project/{project_id}   → list all requirements for a project
  POST /requirements/project/{project_id}   → manually create a requirement
  PUT  /requirements/{requirement_id}        → update a requirement
  DELETE /requirements/{requirement_id}      → delete a requirement
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..dependencies import get_current_user
from ..models.project import Project
from ..models.requirement import EthicalPrinciple, Requirement, RequirementStatus
from ..models.user import User
from ..services.requirement_elicitor import RequirementElicitor, ElicitationFeatureMismatchError
from ..middleware.logging_config import get_logger

logger = get_logger("routers.requirements")
router = APIRouter(prefix="/requirements", tags=["requirements"])

ALLOWED_OPERATORS = {">=", "<=", ">", "<", "=="}
SUPPORTED_RULE_METRICS: Dict[str, set[str]] = {
    "fairness": {
        "demographic_parity_ratio",
        "demographic_parity_difference",
        "equalized_odds_ratio",
        "equalized_odds_difference",
        "equal_opportunity_difference",
        "disparate_impact_ratio",
    },
    "transparency": {
        "shap_explanation_coverage",
        "model_card_generated",
    },
    "privacy": {
        "pii_detection",
        "pii_columns_detected",
        "k_anonymity_k",
        "l_diversity_l",
    },
    "accountability": {
        "audit_trail_exists",
        "mlflow_run_logged",
    },
}

# ── Pydantic schemas ──────────────────────────────────────────────────────────

class ElicitFromDatasetRequest(BaseModel):
    dataset_id: UUID
    project_id: UUID
    mode: Optional[str] = "normal"


class ElicitFromModelRequest(BaseModel):
    model_id: UUID
    dataset_id: UUID
    project_id: UUID
    mode: Optional[str] = "normal"


class ElicitedRequirementSuggestion(BaseModel):
    """A single auto-generated requirement suggestion returned to the frontend."""
    name: str
    principle: str
    description: str
    specification: Dict[str, Any]
    elicited_automatically: bool = True
    elicitation_reason: str
    confidence_score: float
    status: str = "draft"


class ElicitationCheck(BaseModel):
    check_id: str
    status: str
    reason: str
    value: Optional[Any] = None
    threshold: Optional[Any] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ElicitationResponse(BaseModel):
    mode: str
    suggestions: List[ElicitedRequirementSuggestion]
    evaluated_checks: List[ElicitationCheck]


class AcceptElicitedRequest(BaseModel):
    """Accept (and optionally modify) an elicited requirement and save to DB."""
    project_id: UUID
    name: str
    principle: str
    description: Optional[str] = None
    specification: Dict[str, Any] = Field(default_factory=dict)
    elicitation_reason: Optional[str] = None
    confidence_score: Optional[float] = None


class RequirementCreate(BaseModel):
    name: str
    principle: str
    description: Optional[str] = None
    specification: Dict[str, Any] = Field(default_factory=dict)
    based_on_template_id: Optional[UUID] = None


class RequirementUpdate(BaseModel):
    name: Optional[str] = None
    principle: Optional[str] = None
    description: Optional[str] = None
    specification: Optional[Dict[str, Any]] = None
    status: Optional[str] = None


class RequirementResponse(BaseModel):
    id: UUID
    project_id: UUID
    name: str
    principle: str
    description: Optional[str]
    specification: Dict[str, Any]
    status: str
    version: int
    elicited_automatically: bool
    elicitation_reason: Optional[str]
    confidence_score: Optional[float]
    based_on_template_id: Optional[UUID]
    created_at: Any
    updated_at: Any

    class Config:
        from_attributes = True


# ── helper ───────────────────────────────────────────────────────────────────

async def _get_project_or_403(
    project_id: UUID,
    user: User,
    db: AsyncSession,
) -> Project:
    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    if project.owner_id != user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
    return project


def _validate_specification_rules(principle: str, specification: Dict[str, Any]) -> None:
    rules = specification.get("rules", []) if isinstance(specification, dict) else []
    if rules is None:
        rules = []
    if not isinstance(rules, list):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="specification.rules must be a list",
        )

    supported = SUPPORTED_RULE_METRICS.get(principle, set())
    for idx, rule in enumerate(rules):
        if not isinstance(rule, dict):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Rule #{idx + 1} must be an object",
            )
        metric = rule.get("metric")
        operator = rule.get("operator")
        value = rule.get("value")

        if metric not in supported:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=(
                    f"Unsupported metric '{metric}' for principle '{principle}'. "
                    f"Supported metrics: {sorted(list(supported))}"
                ),
            )
        if operator not in ALLOWED_OPERATORS:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=(
                    f"Unsupported operator '{operator}' in rule #{idx + 1}. "
                    f"Allowed operators: {sorted(list(ALLOWED_OPERATORS))}"
                ),
            )
        if value is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Rule #{idx + 1} is missing a value",
            )


# ── endpoints ────────────────────────────────────────────────────────────────

@router.post("/elicit-from-dataset", response_model=ElicitationResponse)
async def elicit_from_dataset(
    body: ElicitFromDatasetRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Analyse a dataset and return auto-generated requirement suggestions.
    Results are NOT saved to the database — the user must call
    /requirements/accept-elicited for each one they want to keep.
    """
    await _get_project_or_403(body.project_id, current_user, db)
    elicitor = RequirementElicitor()
    try:
        response = await elicitor.elicit_from_dataset(body.dataset_id, db, mode=body.mode)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except Exception as exc:
        logger.exception("Elicitation from dataset failed")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Elicitation error: {exc}",
        )
    return response


@router.post("/elicit-from-model", response_model=ElicitationResponse)
async def elicit_from_model(
    body: ElicitFromModelRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Run the model on the dataset and generate behaviour-based requirement suggestions.
    Results are NOT saved — call /requirements/accept-elicited to persist them.
    """
    await _get_project_or_403(body.project_id, current_user, db)
    elicitor = RequirementElicitor()
    try:
        response = await elicitor.elicit_from_model_and_dataset(
            body.model_id, body.dataset_id, db, mode=body.mode
        )
    except ElicitationFeatureMismatchError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        )
    except ValueError as exc:
        detail = str(exc)
        status_code = status.HTTP_404_NOT_FOUND if "not found" in detail.lower() else status.HTTP_400_BAD_REQUEST
        raise HTTPException(status_code=status_code, detail=detail)
    except Exception as exc:
        logger.exception("Elicitation from model failed")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Elicitation error: {exc}",
        )
    return response


@router.post("/accept-elicited", response_model=RequirementResponse, status_code=status.HTTP_201_CREATED)
async def accept_elicited(
    body: AcceptElicitedRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Save an accepted (possibly edited) elicited requirement to the database."""
    await _get_project_or_403(body.project_id, current_user, db)
    _validate_specification_rules(body.principle, body.specification)

    req = Requirement(
        project_id=body.project_id,
        name=body.name,
        principle=EthicalPrinciple(body.principle),
        description=body.description,
        specification=body.specification,
        elicited_automatically=True,
        elicitation_reason=body.elicitation_reason,
        confidence_score=body.confidence_score,
        status=RequirementStatus.ACTIVE,
        created_by_id=current_user.id,
    )
    db.add(req)
    await db.commit()
    await db.refresh(req)
    logger.info("Accepted elicited requirement %s for project %s", req.id, body.project_id)
    return req


@router.get("/project/{project_id}", response_model=List[RequirementResponse])
async def list_requirements(
    project_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all requirements for a project (manual + auto-elicited)."""
    await _get_project_or_403(project_id, current_user, db)
    result = await db.execute(
        select(Requirement)
        .where(Requirement.project_id == project_id)
        .order_by(Requirement.created_at.desc())
    )
    return result.scalars().all()


@router.post("/project/{project_id}", response_model=RequirementResponse, status_code=status.HTTP_201_CREATED)
async def create_requirement(
    project_id: UUID,
    body: RequirementCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Manually create a new requirement for a project."""
    await _get_project_or_403(project_id, current_user, db)

    try:
        principle_enum = EthicalPrinciple(body.principle)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid principle '{body.principle}'. "
                   f"Choose from: {[p.value for p in EthicalPrinciple]}",
        )

    _validate_specification_rules(principle_enum.value, body.specification)

    req = Requirement(
        project_id=project_id,
        name=body.name,
        principle=principle_enum,
        description=body.description,
        specification=body.specification,
        based_on_template_id=body.based_on_template_id,
        status=RequirementStatus.ACTIVE,
        elicited_automatically=False,
        created_by_id=current_user.id,
    )
    db.add(req)
    await db.commit()
    await db.refresh(req)
    return req


@router.put("/{requirement_id}", response_model=RequirementResponse)
async def update_requirement(
    requirement_id: UUID,
    body: RequirementUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update an existing requirement (name, description, thresholds, status)."""
    result = await db.execute(select(Requirement).where(Requirement.id == requirement_id))
    req = result.scalar_one_or_none()
    if req is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Requirement not found")

    # Authorise — check via project
    await _get_project_or_403(req.project_id, current_user, db)

    effective_principle = req.principle.value if isinstance(req.principle, EthicalPrinciple) else str(req.principle)
    effective_specification = req.specification

    if body.name is not None:
        req.name = body.name
    if body.principle is not None:
        try:
            req.principle = EthicalPrinciple(body.principle)
            effective_principle = req.principle.value
        except ValueError:
            raise HTTPException(status_code=422, detail=f"Invalid principle '{body.principle}'")
    if body.description is not None:
        req.description = body.description
    if body.specification is not None:
        req.specification = body.specification
        effective_specification = body.specification

    _validate_specification_rules(effective_principle, effective_specification)
    if body.status is not None:
        try:
            req.status = RequirementStatus(body.status)
        except ValueError:
            raise HTTPException(status_code=422, detail=f"Invalid status '{body.status}'")
    req.version += 1

    await db.commit()
    await db.refresh(req)
    return req


@router.delete("/{requirement_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_requirement(
    requirement_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete a requirement."""
    result = await db.execute(select(Requirement).where(Requirement.id == requirement_id))
    req = result.scalar_one_or_none()
    if req is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Requirement not found")
    await _get_project_or_403(req.project_id, current_user, db)
    await db.delete(req)
    await db.commit()
