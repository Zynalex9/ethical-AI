"""
Traceability API endpoints – Phase 3

Provides REST endpoints for querying the Requirement Traceability Matrix,
requirement compliance history, root-cause analysis, and dataset impact.
"""

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from ..database import get_db
from ..dependencies import get_current_user
from ..models.user import User
from ..models.project import Project
from ..models.requirement import Requirement
from ..models.validation import Validation
from ..models.ml_model import MLModel
from ..models.dataset import Dataset
from ..services.traceability_service import TraceabilityService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/traceability", tags=["traceability"])

_service = TraceabilityService()


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------
async def _verify_project_access(
    db: AsyncSession, current_user: User, project_id: UUID
) -> Project:
    result = await db.execute(
        select(Project).where(Project.id == project_id)
    )
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    if project.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")
    return project


# ------------------------------------------------------------------
# 3.2.1  GET /traceability/project/{project_id}/matrix
# ------------------------------------------------------------------
@router.get("/project/{project_id}/matrix")
async def get_traceability_matrix(
    project_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Return the full Requirement Traceability Matrix for a project.

    Each entry maps a *requirement* to the *dataset*, *model*, and
    *validation result* that together form a traceable chain.
    """
    await _verify_project_access(db, current_user, project_id)
    matrix = await _service.build_traceability_matrix(db, project_id)
    return matrix


# ------------------------------------------------------------------
# 3.2.2  GET /traceability/requirement/{requirement_id}/history
# ------------------------------------------------------------------
@router.get("/requirement/{requirement_id}/history")
async def get_requirement_compliance_history(
    requirement_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Return compliance history for a specific requirement.

    Shows all past validation runs and their pass/fail transitions,
    enabling trend analysis and regression detection.
    """
    # Verify ownership via requirement → project → owner
    req_result = await db.execute(
        select(Requirement).where(Requirement.id == requirement_id)
    )
    requirement = req_result.scalar_one_or_none()
    if not requirement:
        raise HTTPException(status_code=404, detail="Requirement not found")

    await _verify_project_access(db, current_user, requirement.project_id)

    history = await _service.trace_requirement_to_results(db, requirement_id)
    return {
        "requirement_id": str(requirement_id),
        "requirement_name": requirement.name,
        "principle": requirement.principle if isinstance(requirement.principle, str) else requirement.principle.value,
        "history": history,
    }


# ------------------------------------------------------------------
# 3.2.3  GET /traceability/validation/{validation_id}/root-cause
# ------------------------------------------------------------------
@router.get("/validation/{validation_id}/root-cause")
async def get_root_cause_analysis(
    validation_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Return root-cause analysis for a (failed) validation.

    Traces back to the violated requirement, the contributing
    dataset features, and the model behavior pattern.
    """
    # Verify ownership via validation → model → project → owner
    val_result = await db.execute(
        select(Validation).where(Validation.id == validation_id)
    )
    validation = val_result.scalar_one_or_none()
    if not validation:
        raise HTTPException(status_code=404, detail="Validation not found")

    if validation.model_id:
        model = await db.get(MLModel, validation.model_id)
        if model:
            await _verify_project_access(db, current_user, model.project_id)

    analysis = await _service.trace_validation_failure_to_root_cause(db, validation_id)
    return analysis


# ------------------------------------------------------------------
# 3.2.4  GET /traceability/dataset/{dataset_id}/impact
# ------------------------------------------------------------------
@router.get("/dataset/{dataset_id}/impact")
async def get_dataset_impact(
    dataset_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Show which requirements were elicited from this dataset and
    which validations have used it.
    """
    dataset = await db.get(Dataset, dataset_id)
    if not dataset:
        raise HTTPException(status_code=404, detail="Dataset not found")

    await _verify_project_access(db, current_user, dataset.project_id)

    impact = await _service.trace_dataset_to_requirements(db, dataset_id)
    return impact
