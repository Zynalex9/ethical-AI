"""
Remediation Workflow router.

Provides endpoints for:
- Generating a remediation checklist for a failing validation suite
- Updating step completion state
- Fetching checklist for a suite/user
"""

from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.models.remediation import RemediationChecklist
from app.models.user import User

router = APIRouter(prefix="/remediation", tags=["remediation"])


# ──────────────────────────────────────────────────────────────────
# Default remediation step templates per principle
# ──────────────────────────────────────────────────────────────────

DEFAULT_STEPS: Dict[str, List[Dict[str, Any]]] = {
    "fairness": [
        {
            "id": "fair-1",
            "description": "Review sensitive-feature correlation with target variable",
            "done": False,
            "doc_link": "/docs#fairness-correlation",
        },
        {
            "id": "fair-2",
            "description": "Check for proxy variables that correlate with the sensitive feature",
            "done": False,
            "doc_link": "/docs#proxy-variables",
        },
        {
            "id": "fair-3",
            "description": "Apply reweighing or other pre-processing mitigation technique",
            "done": False,
            "doc_link": "/docs#fairness-mitigation",
        },
        {
            "id": "fair-4",
            "description": "Retrain model with fairness constraints (e.g., equalized odds post-processing)",
            "done": False,
            "doc_link": "/docs#fairness-constraints",
        },
        {
            "id": "fair-5",
            "description": "Re-validate fairness metrics after mitigation",
            "done": False,
            "doc_link": None,
        },
    ],
    "privacy": [
        {
            "id": "priv-1",
            "description": "Identify and remove or mask all PII columns flagged by the validator",
            "done": False,
            "doc_link": "/docs#pii-removal",
        },
        {
            "id": "priv-2",
            "description": "Increase k-anonymity by generalizing quasi-identifier columns (binning, rounding)",
            "done": False,
            "doc_link": "/docs#k-anonymity",
        },
        {
            "id": "priv-3",
            "description": "Apply differential privacy noise if ε budget was exceeded",
            "done": False,
            "doc_link": "/docs#differential-privacy",
        },
        {
            "id": "priv-4",
            "description": "Remove HIPAA Safe Harbor identifiers flagged by the HIPAA checker",
            "done": False,
            "doc_link": "/docs#hipaa",
        },
        {
            "id": "priv-5",
            "description": "Re-validate privacy checks after data anonymization",
            "done": False,
            "doc_link": None,
        },
    ],
    "transparency": [
        {
            "id": "trans-1",
            "description": "Review SHAP feature importance — ensure no unexpected features dominate",
            "done": False,
            "doc_link": "/docs#shap-review",
        },
        {
            "id": "trans-2",
            "description": "Review LIME local explanations for edge-case samples",
            "done": False,
            "doc_link": "/docs#lime-review",
        },
        {
            "id": "trans-3",
            "description": "Improve explanation fidelity by simplifying model or using a more faithful surrogate",
            "done": False,
            "doc_link": "/docs#explanation-fidelity",
        },
        {
            "id": "trans-4",
            "description": "Update model card documentation with accurate intended use and limitations",
            "done": False,
            "doc_link": "/docs#model-card",
        },
        {
            "id": "trans-5",
            "description": "Re-validate transparency after model / documentation changes",
            "done": False,
            "doc_link": None,
        },
    ],
    "accountability": [
        {
            "id": "acc-1",
            "description": "Verify that all validation runs are logged in the audit trail (MLflow)",
            "done": False,
            "doc_link": "/docs#audit-trail",
        },
        {
            "id": "acc-2",
            "description": "Ensure traceability matrix links every requirement to at least one validation",
            "done": False,
            "doc_link": "/docs#traceability",
        },
        {
            "id": "acc-3",
            "description": "Assign an owner / reviewer for each failing metric",
            "done": False,
            "doc_link": "/docs#accountability-owner",
        },
        {
            "id": "acc-4",
            "description": "Re-validate after remediation to close the audit loop",
            "done": False,
            "doc_link": None,
        },
    ],
}


# ──────────────────────────────────────────────────────────────────
# Schemas
# ──────────────────────────────────────────────────────────────────

class StepOut(BaseModel):
    id: str
    description: str
    done: bool
    doc_link: Optional[str] = None


class ChecklistOut(BaseModel):
    id: str
    validation_suite_id: str
    principle: str
    steps: List[StepOut]
    all_done: bool


class ChecklistListOut(BaseModel):
    checklists: List[ChecklistOut]


class UpdateStepRequest(BaseModel):
    step_id: str
    done: bool


# ──────────────────────────────────────────────────────────────────
# Endpoints
# ──────────────────────────────────────────────────────────────────

@router.get("/{suite_id}", response_model=ChecklistListOut)
async def get_checklists(
    suite_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Fetch remediation checklists for the current user and a given suite."""
    result = await db.execute(
        select(RemediationChecklist).where(
            RemediationChecklist.validation_suite_id == suite_id,
            RemediationChecklist.user_id == current_user.id,
        )
    )
    rows = result.scalars().all()

    return ChecklistListOut(
        checklists=[
            ChecklistOut(
                id=str(c.id),
                validation_suite_id=str(c.validation_suite_id),
                principle=c.principle,
                steps=[StepOut(**s) for s in c.steps],
                all_done=all(s.get("done", False) for s in c.steps),
            )
            for c in rows
        ]
    )


@router.post("/{suite_id}/generate", response_model=ChecklistListOut)
async def generate_checklists(
    suite_id: UUID,
    principles: Optional[List[str]] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Generate remediation checklists for the specified principles.

    If ``principles`` is not provided, generates for all four.
    Existing checklists for the same suite/user/principle are preserved
    (not overwritten).
    """
    target_principles = principles or ["fairness", "privacy", "transparency", "accountability"]
    created = []

    for p in target_principles:
        steps_template = DEFAULT_STEPS.get(p)
        if not steps_template:
            continue

        # Skip if already exists
        existing = await db.execute(
            select(RemediationChecklist).where(
                RemediationChecklist.validation_suite_id == suite_id,
                RemediationChecklist.user_id == current_user.id,
                RemediationChecklist.principle == p,
            )
        )
        if existing.scalar_one_or_none():
            continue

        checklist = RemediationChecklist(
            user_id=current_user.id,
            validation_suite_id=suite_id,
            principle=p,
            steps=[dict(s) for s in steps_template],  # deep copy
        )
        db.add(checklist)
        created.append(checklist)

    await db.commit()
    for c in created:
        await db.refresh(c)

    # Return all checklists (existing + new)
    result = await db.execute(
        select(RemediationChecklist).where(
            RemediationChecklist.validation_suite_id == suite_id,
            RemediationChecklist.user_id == current_user.id,
        )
    )
    rows = result.scalars().all()

    return ChecklistListOut(
        checklists=[
            ChecklistOut(
                id=str(c.id),
                validation_suite_id=str(c.validation_suite_id),
                principle=c.principle,
                steps=[StepOut(**s) for s in c.steps],
                all_done=all(s.get("done", False) for s in c.steps),
            )
            for c in rows
        ]
    )


@router.put("/{checklist_id}/step", response_model=ChecklistOut)
async def update_step(
    checklist_id: UUID,
    body: UpdateStepRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Toggle a step's done state in a remediation checklist."""
    result = await db.execute(
        select(RemediationChecklist).where(
            RemediationChecklist.id == checklist_id,
            RemediationChecklist.user_id == current_user.id,
        )
    )
    checklist = result.scalar_one_or_none()
    if not checklist:
        raise HTTPException(status_code=404, detail="Checklist not found")

    updated = False
    new_steps = []
    for s in checklist.steps:
        if s.get("id") == body.step_id:
            s["done"] = body.done
            updated = True
        new_steps.append(s)

    if not updated:
        raise HTTPException(status_code=404, detail=f"Step {body.step_id} not found in checklist")

    checklist.steps = new_steps
    # Force SQLAlchemy to detect the JSONB mutation
    from sqlalchemy.orm.attributes import flag_modified
    flag_modified(checklist, "steps")
    await db.commit()
    await db.refresh(checklist)

    return ChecklistOut(
        id=str(checklist.id),
        validation_suite_id=str(checklist.validation_suite_id),
        principle=checklist.principle,
        steps=[StepOut(**s) for s in checklist.steps],
        all_done=all(s.get("done", False) for s in checklist.steps),
    )
