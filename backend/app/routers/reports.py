from typing import Any, Dict, List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.models.ml_model import MLModel
from app.models.project import Project
from app.models.user import User
from app.models.validation_suite import ValidationSuite
from app.services.report_generator import ReportGenerator
from app.middleware.logging_config import get_logger

logger = get_logger("routers.reports")

router = APIRouter(prefix="/reports", tags=["reports"])


class CustomReportRequest(BaseModel):
    project_id: UUID
    include_sections: Optional[List[str]] = None
    date_range: Optional[Dict[str, Any]] = None


async def _verify_project_access(db: AsyncSession, project_id: UUID, current_user: User) -> Project:
    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    if current_user.role.value != "admin" and project.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")
    return project


async def _verify_suite_access(db: AsyncSession, suite_id: UUID, current_user: User) -> ValidationSuite:
    result = await db.execute(select(ValidationSuite).where(ValidationSuite.id == suite_id))
    suite = result.scalar_one_or_none()
    if not suite:
        raise HTTPException(status_code=404, detail="Validation suite not found")

    result = await db.execute(select(MLModel).where(MLModel.id == suite.model_id))
    model = result.scalar_one_or_none()
    if not model:
        raise HTTPException(status_code=404, detail="Model not found")

    await _verify_project_access(db, model.project_id, current_user)
    return suite


@router.get("/validation/{validation_suite_id}")
async def get_validation_report(
    validation_suite_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await _verify_suite_access(db, validation_suite_id, current_user)
    generator = ReportGenerator(db)
    try:
        return await generator.generate_validation_report(validation_suite_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.get("/validation/{validation_suite_id}/pdf")
async def get_validation_report_pdf(
    validation_suite_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await _verify_suite_access(db, validation_suite_id, current_user)
    generator = ReportGenerator(db)
    try:
        report = await generator.generate_validation_report(validation_suite_id)
        pdf_bytes = await generator.generate_pdf_report(report)
        filename = f"validation_report_{validation_suite_id}.pdf"
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={"Content-Disposition": f"attachment; filename={filename}"},
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.get("/project/{project_id}/compliance")
async def get_project_compliance_report(
    project_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await _verify_project_access(db, project_id, current_user)
    generator = ReportGenerator(db)
    try:
        return await generator.generate_compliance_report(project_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.get("/project/{project_id}/compliance/pdf")
async def get_project_compliance_report_pdf(
    project_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await _verify_project_access(db, project_id, current_user)
    generator = ReportGenerator(db)
    try:
        compliance = await generator.generate_compliance_report(project_id)
        # Reuse same PDF generator with compliance summary flattened
        report_like = {
            "project_name": compliance.get("project_name"),
            "model_name": "Multiple",
            "dataset_name": "Multiple",
            "overall_status": "pass" if compliance.get("compliance_rate", 0) >= 0.8 else "fail",
            "executive_summary": (
                f"Project compliance rate is {round(compliance.get('compliance_rate', 0) * 100, 2)}% "
                f"across {compliance.get('total_validation_suites', 0)} validation suites."
            ),
            "recommendations": [
                "Review failed suites and root-cause details in traceability view.",
                "Rerun validation after model/dataset updates.",
            ],
        }
        pdf_bytes = await generator.generate_pdf_report(report_like)
        filename = f"project_compliance_{project_id}.pdf"
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={"Content-Disposition": f"attachment; filename={filename}"},
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.get("/validation/{validation_suite_id}/html")
async def get_validation_report_html(
    validation_suite_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Generate and download an HTML validation report."""
    await _verify_suite_access(db, validation_suite_id, current_user)
    generator = ReportGenerator(db)
    try:
        html = await generator.generate_html_report(validation_suite_id)
        filename = f"validation_report_{validation_suite_id}.html"
        return Response(
            content=html.encode("utf-8"),
            media_type="text/html",
            headers={"Content-Disposition": f"attachment; filename={filename}"},
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.get("/validation/{validation_suite_id}/certificate")
async def get_validation_certificate_pdf(
    validation_suite_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Generate and download a compliance certificate PDF for a validation suite."""
    await _verify_suite_access(db, validation_suite_id, current_user)
    generator = ReportGenerator(db)
    try:
        pdf_bytes = await generator.generate_certificate_pdf(validation_suite_id)
        filename = f"compliance_certificate_{validation_suite_id}.pdf"
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={"Content-Disposition": f"attachment; filename={filename}"},
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.post("/custom")
async def generate_custom_report(
    body: CustomReportRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await _verify_project_access(db, body.project_id, current_user)
    generator = ReportGenerator(db)
    compliance = await generator.generate_compliance_report(body.project_id)

    include_sections = set(body.include_sections or ["summary", "history", "traceability"])

    response: Dict[str, Any] = {
        "project_id": compliance.get("project_id"),
        "project_name": compliance.get("project_name"),
        "generated_at": compliance.get("generated_at"),
    }

    if "summary" in include_sections:
        response["summary"] = {
            "total_validation_suites": compliance.get("total_validation_suites"),
            "passed_validation_suites": compliance.get("passed_validation_suites"),
            "compliance_rate": compliance.get("compliance_rate"),
        }
    if "history" in include_sections:
        response["validation_history"] = compliance.get("validation_history", [])
    if "traceability" in include_sections:
        response["traceability"] = compliance.get("traceability", {})

    if body.date_range:
        response["date_range_applied"] = body.date_range

    return response
