"""
Remediation Workflow router.

Provides endpoints for:
- Generating dynamic remediation checklists from actual validation outcomes
- Updating step completion state
- Fetching checklist for a suite/user
"""

import json
import os
from typing import Any, Dict, List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.dependencies import get_current_user
from app.models.remediation import RemediationChecklist
from app.models.user import User
from app.models.validation import Validation, ValidationResult
from app.models.validation_suite import ValidationSuite

router = APIRouter(prefix="/remediation", tags=["remediation"])


def _step(step_id: str, description: str, doc_link: Optional[str] = None) -> Dict[str, Any]:
    return {
        "id": step_id,
        "description": description,
        "done": False,
        "doc_link": doc_link,
    }


def _artifact_path(run_id: str, filename: str) -> str:
    return os.path.join(settings.mlflow_artifact_location, "1", run_id, "artifacts", filename)


def _load_artifact_json(run_id: Optional[str], filename: str, default: Any) -> Any:
    if not run_id:
        return default
    path = _artifact_path(run_id, filename)
    if not os.path.exists(path):
        return default
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def _fmt_num(value: Any, precision: int = 3) -> str:
    if value is None:
        return "N/A"
    try:
        return f"{float(value):.{precision}f}"
    except (TypeError, ValueError):
        return str(value)


async def _get_validation_results(db: AsyncSession, validation_id: Optional[UUID]) -> List[ValidationResult]:
    if not validation_id:
        return []
    result = await db.execute(select(ValidationResult).where(ValidationResult.validation_id == validation_id))
    return result.scalars().all()


async def _get_validation(db: AsyncSession, validation_id: Optional[UUID]) -> Optional[Validation]:
    if not validation_id:
        return None
    result = await db.execute(select(Validation).where(Validation.id == validation_id))
    return result.scalar_one_or_none()


def _build_fairness_steps(failed_results: List[ValidationResult]) -> List[Dict[str, Any]]:
    steps: List[Dict[str, Any]] = []
    for r in failed_results:
        metric = r.metric_name
        val = _fmt_num(r.metric_value)
        thr = _fmt_num(r.threshold)
        steps.append(
            _step(
                f"fair-{metric}",
                f"Fix failed fairness metric '{metric}' (value={val}, threshold={thr}); apply bias mitigation and reassess group impacts.",
                "/knowledge-base#fairness",
            )
        )

    if steps:
        steps.append(_step("fair-revalidate", "Re-run fairness validation to confirm all fairness metrics pass."))
    return steps


def _build_privacy_steps(privacy_report: Dict[str, Any]) -> List[Dict[str, Any]]:
    steps: List[Dict[str, Any]] = []
    pii_results = privacy_report.get("pii_results", []) if isinstance(privacy_report, dict) else []
    pii_cols = [p.get("column") for p in pii_results if isinstance(p, dict) and p.get("is_pii") and p.get("column")]
    if pii_cols:
        steps.append(
            _step(
                "priv-pii",
                f"Mask/remove detected PII columns: {', '.join(pii_cols[:5])}.",
                "/knowledge-base#privacy",
            )
        )

    k = privacy_report.get("k_anonymity") if isinstance(privacy_report, dict) else None
    if isinstance(k, dict) and k and not k.get("satisfies_k"):
        steps.append(
            _step(
                "priv-k-anonymity",
                f"Increase k-anonymity: actual min k={_fmt_num(k.get('actual_min_k'), 0)}, required k={_fmt_num(k.get('k_value'), 0)}.",
                "/knowledge-base#privacy",
            )
        )

    l = privacy_report.get("l_diversity") if isinstance(privacy_report, dict) else None
    if isinstance(l, dict) and l and not l.get("satisfies_l"):
        steps.append(
            _step(
                "priv-l-diversity",
                f"Increase l-diversity: actual min l={_fmt_num(l.get('actual_min_l'), 0)}, required l={_fmt_num(l.get('l_value'), 0)}.",
                "/knowledge-base#privacy",
            )
        )

    dp = privacy_report.get("differential_privacy") if isinstance(privacy_report, dict) else None
    if isinstance(dp, dict) and dp and not dp.get("budget_satisfied"):
        steps.append(
            _step(
                "priv-dp",
                f"Mitigate DP budget issue: measured ε={_fmt_num(dp.get('measured_epsilon'), 4)} exceeds target ε={_fmt_num(dp.get('target_epsilon'), 4)}.",
                "/knowledge-base#privacy",
            )
        )

    hipaa = privacy_report.get("hipaa") if isinstance(privacy_report, dict) else None
    if isinstance(hipaa, dict) and hipaa and not hipaa.get("overall_passed"):
        failed_identifiers = []
        for item in hipaa.get("results", []):
            if isinstance(item, dict) and not item.get("passed") and item.get("identifier"):
                failed_identifiers.append(str(item.get("identifier")))
        details = f" Failed checks: {', '.join(failed_identifiers[:5])}." if failed_identifiers else ""
        steps.append(
            _step(
                "priv-hipaa",
                f"Resolve HIPAA Safe Harbor violations by de-identifying flagged identifiers.{details}",
                "/knowledge-base#privacy",
            )
        )

    if steps:
        steps.append(_step("priv-revalidate", "Re-run privacy validation to verify all privacy checks pass."))
    return steps


def _build_transparency_steps(
    failed_results: List[ValidationResult],
    warning_text: Optional[str],
) -> List[Dict[str, Any]]:
    steps: List[Dict[str, Any]] = []

    for r in failed_results:
        metric = r.metric_name
        val = _fmt_num(r.metric_value)
        thr = _fmt_num(r.threshold)
        steps.append(
            _step(
                f"trans-{metric}",
                f"Fix transparency metric '{metric}' (value={val}, threshold={thr}); improve explainability artifacts/model-card quality.",
                "/knowledge-base#transparency",
            )
        )

    if warning_text:
        steps.append(
            _step(
                "trans-warning",
                f"Address transparency warning: {warning_text}",
                "/knowledge-base#transparency",
            )
        )

    if steps:
        steps.append(_step("trans-revalidate", "Re-run transparency validation after remediation updates."))
    return steps


async def _build_dynamic_steps_by_principle(
    db: AsyncSession,
    suite: ValidationSuite,
    principles: Optional[List[str]],
) -> Dict[str, List[Dict[str, Any]]]:
    requested = set((principles or ["fairness", "privacy", "transparency"]))
    output: Dict[str, List[Dict[str, Any]]] = {}

    if "fairness" in requested:
        fairness_results = await _get_validation_results(db, suite.fairness_validation_id)
        failed_fairness = [r for r in fairness_results if not r.passed]
        fairness_steps = _build_fairness_steps(failed_fairness)
        if fairness_steps:
            output["fairness"] = fairness_steps

    if "privacy" in requested and suite.privacy_validation_id:
        privacy_validation = await _get_validation(db, suite.privacy_validation_id)
        privacy_report = _load_artifact_json(
            privacy_validation.mlflow_run_id if privacy_validation else None,
            "privacy_report.json",
            {},
        )
        privacy_steps = _build_privacy_steps(privacy_report if isinstance(privacy_report, dict) else {})
        if privacy_steps:
            output["privacy"] = privacy_steps

    if "transparency" in requested:
        transparency_results = await _get_validation_results(db, suite.transparency_validation_id)
        failed_transparency = [r for r in transparency_results if not r.passed]

        transparency_validation = await _get_validation(db, suite.transparency_validation_id)
        warning_text = None
        if transparency_validation:
            warning_text = _load_artifact_json(
                transparency_validation.mlflow_run_id,
                "transparency_warning.json",
                {},
            ).get("warning") if transparency_validation.mlflow_run_id else None

        transparency_steps = _build_transparency_steps(failed_transparency, warning_text)
        if transparency_steps:
            output["transparency"] = transparency_steps

    return output


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
    """Generate (or refresh) dynamic remediation checklists from real validation outcomes."""
    suite_result = await db.execute(select(ValidationSuite).where(ValidationSuite.id == suite_id))
    suite = suite_result.scalar_one_or_none()
    if not suite:
        raise HTTPException(status_code=404, detail="Validation suite not found")

    if suite.created_by_id != current_user.id and current_user.role.value != "admin":
        raise HTTPException(status_code=403, detail="Access denied")

    dynamic_steps = await _build_dynamic_steps_by_principle(db, suite, principles)

    existing_result = await db.execute(
        select(RemediationChecklist).where(
            RemediationChecklist.validation_suite_id == suite_id,
            RemediationChecklist.user_id == current_user.id,
        )
    )
    existing_rows = existing_result.scalars().all()
    existing_by_principle = {row.principle: row for row in existing_rows}

    # Remove stale checklists that are no longer relevant.
    stale = [row for row in existing_rows if row.principle not in dynamic_steps]
    for row in stale:
        await db.delete(row)

    # Upsert fresh dynamic checklists.
    from sqlalchemy.orm.attributes import flag_modified

    for principle, steps in dynamic_steps.items():
        if principle in existing_by_principle:
            checklist = existing_by_principle[principle]
            checklist.steps = [dict(s) for s in steps]
            flag_modified(checklist, "steps")
        else:
            checklist = RemediationChecklist(
                user_id=current_user.id,
                validation_suite_id=suite_id,
                principle=principle,
                steps=[dict(s) for s in steps],
            )
            db.add(checklist)

    await db.commit()

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
