import io
import json
import os
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from jinja2 import Environment, FileSystemLoader
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import settings
from app.models.ml_model import MLModel
from app.models.project import Project
from app.models.validation import Validation, ValidationResult
from app.models.validation_suite import ValidationSuite
from app.services.traceability_service import TraceabilityService

# Jinja2 environment for HTML report templates
_TEMPLATE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "templates")
_jinja_env = Environment(loader=FileSystemLoader(_TEMPLATE_DIR), autoescape=True)


class ReportGenerator:
    def __init__(self, db: AsyncSession):
        self.db = db

    def _artifact_path(self, run_id: str, filename: str) -> str:
        return os.path.join(
            settings.mlflow_artifact_location,
            "1",
            run_id,
            "artifacts",
            filename,
        )

    def _load_artifact_json(self, run_id: Optional[str], filename: str, default: Any) -> Any:
        if not run_id:
            return default
        path = self._artifact_path(run_id, filename)
        if not os.path.exists(path):
            return default
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return default

    def format_executive_summary(self, validation_results: Dict[str, Any]) -> str:
        validations = validation_results.get("validations", {})
        total_sections = 0
        passed_sections = 0
        failed_sections: List[str] = []

        for key in ["fairness", "transparency", "privacy"]:
            section = validations.get(key)
            if section and section.get("status") == "completed":
                total_sections += 1
                if key == "fairness":
                    fairness_results = section.get("results", [])
                    if fairness_results and all(r.get("passed") for r in fairness_results):
                        passed_sections += 1
                    else:
                        failed_sections.append("fairness")
                elif key == "privacy":
                    if section.get("overall_passed") is True:
                        passed_sections += 1
                    else:
                        failed_sections.append("privacy")
                else:
                    passed_sections += 1

        if total_sections == 0:
            return "No completed validation sections were found for this suite yet."

        base = f"Model passed {passed_sections} out of {total_sections} completed ethical validation sections."
        if failed_sections:
            failed_txt = ", ".join(failed_sections)
            return f"{base} Areas requiring attention: {failed_txt}."
        return f"{base} No major ethical validation failures were detected in completed sections."

    async def _suite_or_404(self, validation_suite_id: UUID) -> ValidationSuite:
        result = await self.db.execute(
            select(ValidationSuite)
            .options(
                selectinload(ValidationSuite.model),
                selectinload(ValidationSuite.dataset),
            )
            .where(ValidationSuite.id == validation_suite_id)
        )
        suite = result.scalar_one_or_none()
        if not suite:
            raise ValueError("Validation suite not found")
        return suite

    async def _fairness_results(self, validation_id: Optional[UUID]) -> List[Dict[str, Any]]:
        if not validation_id:
            return []
        result = await self.db.execute(
            select(ValidationResult).where(ValidationResult.validation_id == validation_id)
        )
        rows = result.scalars().all()
        return [
            {
                "metric_name": r.metric_name,
                "metric_value": r.metric_value,
                "threshold": r.threshold,
                "passed": r.passed,
                "details": r.details,
            }
            for r in rows
        ]

    async def generate_validation_report(self, validation_suite_id: UUID) -> Dict[str, Any]:
        suite = await self._suite_or_404(validation_suite_id)

        fairness_validation = None
        transparency_validation = None
        privacy_validation = None

        if suite.fairness_validation_id:
            result = await self.db.execute(select(Validation).where(Validation.id == suite.fairness_validation_id))
            fairness_validation = result.scalar_one_or_none()
        if suite.transparency_validation_id:
            result = await self.db.execute(select(Validation).where(Validation.id == suite.transparency_validation_id))
            transparency_validation = result.scalar_one_or_none()
        if suite.privacy_validation_id:
            result = await self.db.execute(select(Validation).where(Validation.id == suite.privacy_validation_id))
            privacy_validation = result.scalar_one_or_none()

        fairness_results = await self._fairness_results(suite.fairness_validation_id)

        transparency_data = self._load_artifact_json(
            transparency_validation.mlflow_run_id if transparency_validation else None,
            "feature_importance.json",
            {},
        )
        model_card = self._load_artifact_json(
            transparency_validation.mlflow_run_id if transparency_validation else None,
            "model_card.json",
            {},
        )
        sample_predictions_artifact = self._load_artifact_json(
            transparency_validation.mlflow_run_id if transparency_validation else None,
            "sample_predictions.json",
            {"samples": []},
        )
        sample_predictions = sample_predictions_artifact.get("samples", [])
        transparency_warning = sample_predictions_artifact.get("warning")
        if not transparency_warning:
            transparency_warning = self._load_artifact_json(
                transparency_validation.mlflow_run_id if transparency_validation else None,
                "transparency_warning.json",
                {},
            ).get("warning")

        privacy_report = self._load_artifact_json(
            privacy_validation.mlflow_run_id if privacy_validation else None,
            "privacy_report.json",
            {},
        )

        validations_payload = {
            "fairness": {
                "status": (fairness_validation.status.value if fairness_validation and hasattr(fairness_validation.status, "value") else (fairness_validation.status if fairness_validation else "not_run")),
                "results": fairness_results,
                "mlflow_run_id": fairness_validation.mlflow_run_id if fairness_validation else None,
            },
            "transparency": {
                "status": (transparency_validation.status.value if transparency_validation and hasattr(transparency_validation.status, "value") else (transparency_validation.status if transparency_validation else "not_run")),
                "feature_importance": transparency_data,
                "model_card": model_card,
                "sample_predictions": sample_predictions,
                "warning": transparency_warning,
                "mlflow_run_id": transparency_validation.mlflow_run_id if transparency_validation else None,
            },
            "privacy": {
                "status": (privacy_validation.status.value if privacy_validation and hasattr(privacy_validation.status, "value") else (privacy_validation.status if privacy_validation else "not_run")),
                "report": privacy_report,
                "overall_passed": privacy_report.get("overall_passed"),
                "mlflow_run_id": privacy_validation.mlflow_run_id if privacy_validation else None,
            },
        }

        report = {
            "validation_suite_id": str(suite.id),
            "project_id": str(suite.model.project_id) if suite.model else None,
            "project_name": None,
            "model_name": suite.model.name if suite.model else "Unknown",
            "dataset_name": suite.dataset.name if suite.dataset else "Unknown",
            "validation_date": suite.started_at.isoformat() if suite.started_at else None,
            "overall_status": "pass" if suite.overall_passed else "fail",
            "overall_passed": bool(suite.overall_passed),
            "executive_summary": self.format_executive_summary({"validations": validations_payload}),
            "validations": validations_payload,
            "recommendations": self._generate_recommendations(validations_payload),
            "generated_at": datetime.utcnow().isoformat(),
        }

        if suite.model:
            result = await self.db.execute(select(Project).where(Project.id == suite.model.project_id))
            project = result.scalar_one_or_none()
            report["project_name"] = project.name if project else "Unknown Project"

        return report

    def _generate_recommendations(self, validations: Dict[str, Any]) -> List[str]:
        recommendations: List[str] = []

        fairness_results = validations.get("fairness", {}).get("results", [])
        failed_fairness = [r for r in fairness_results if not r.get("passed")]
        if failed_fairness:
            recommendations.append("Retrain model with fairness constraints and review sensitive-feature impact.")

        transparency = validations.get("transparency", {})
        if not transparency.get("feature_importance"):
            recommendations.append("Enable/verify explainability artifact generation (SHAP/LIME) for transparency evidence.")

        privacy = validations.get("privacy", {}).get("report", {})
        pii_detected = privacy.get("pii_detected", []) if isinstance(privacy, dict) else []
        if pii_detected:
            recommendations.append("Remove, mask, or tokenize detected PII columns before model training/inference.")

        if not recommendations:
            recommendations.append("Maintain periodic monitoring and rerun validation after any model/data updates.")

        return recommendations

    async def generate_compliance_report(self, project_id: UUID) -> Dict[str, Any]:
        result = await self.db.execute(select(Project).where(Project.id == project_id))
        project = result.scalar_one_or_none()
        if not project:
            raise ValueError("Project not found")

        suites_result = await self.db.execute(
            select(ValidationSuite)
            .join(MLModel, ValidationSuite.model_id == MLModel.id)
            .where(MLModel.project_id == project_id)
            .order_by(ValidationSuite.started_at.desc())
        )
        suites = suites_result.scalars().all()

        suite_summaries = [
            {
                "suite_id": str(s.id),
                "status": s.status,
                "overall_passed": bool(s.overall_passed),
                "started_at": s.started_at.isoformat() if s.started_at else None,
                "completed_at": s.completed_at.isoformat() if s.completed_at else None,
                "error_message": s.error_message,
            }
            for s in suites
        ]

        total = len(suites)
        passed = sum(1 for s in suites if s.overall_passed)

        traceability = await TraceabilityService.build_traceability_matrix(self.db, project_id)

        return {
            "project_id": str(project.id),
            "project_name": project.name,
            "total_validation_suites": total,
            "passed_validation_suites": passed,
            "compliance_rate": (passed / total) if total else 0,
            "validation_history": suite_summaries,
            "traceability": traceability,
            "generated_at": datetime.utcnow().isoformat(),
        }

    def _simple_pdf_bytes(self, title: str, body_lines: List[str]) -> bytes:
        """
        Generate a readable PDF with proper text layout.
        Creates a minimal PDF with correct positioning and line spacing.
        """
        def esc(s: str) -> str:
            """Escape special characters for PDF strings."""
            return s.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
        
        # PDF page dimensions (US Letter: 612x792 points)
        page_width = 612
        page_height = 792
        margin_left = 50
        margin_top = 50
        line_height = 16  # Proper line spacing
        font_size = 12
        title_font_size = 16
        
        # Build text content with proper positioning
        content_parts = []
        y_position = page_height - margin_top
        
        # Title (larger font)
        content_parts.append(f"BT")  # Begin text
        content_parts.append(f"/F1 {title_font_size} Tf")  # Font and size
        content_parts.append(f"{margin_left} {y_position} Td")  # Position
        content_parts.append(f"({esc(title[:80])}) Tj")  # Draw title
        content_parts.append("ET")  # End text
        
        y_position -= line_height * 2  # Add spacing after title
        
        # Body lines (regular font)
        for line in body_lines:
            if y_position < 50:  # Bottom margin check
                break  # Would need multi-page support here
            
            # Wrap long lines
            line_str = str(line)
            if len(line_str) > 90:
                line_str = line_str[:87] + "..."
            
            content_parts.append("BT")
            content_parts.append(f"/F1 {font_size} Tf")
            content_parts.append(f"{margin_left} {y_position} Td")
            content_parts.append(f"({esc(line_str)}) Tj")
            content_parts.append("ET")
            
            y_position -= line_height
        
        content_stream = "\n".join(content_parts).encode("latin-1", errors="replace")
        
        # Build PDF structure
        objs: List[bytes] = []
        
        # Object 1: Catalog
        objs.append(b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n")
        
        # Object 2: Pages
        objs.append(b"2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n")
        
        # Object 3: Page
        objs.append(
            f"3 0 obj\n<< /Type /Page /Parent 2 0 R "
            f"/MediaBox [0 0 {page_width} {page_height}] "
            f"/Resources << /Font << /F1 5 0 R >> >> "
            f"/Contents 4 0 R >>\nendobj\n".encode()
        )
        
        # Object 4: Content stream
        objs.append(
            b"4 0 obj\n<< /Length " + str(len(content_stream)).encode() + 
            b" >>\nstream\n" + content_stream + b"\nendstream\nendobj\n"
        )
        
        # Object 5: Font
        objs.append(b"5 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>\nendobj\n")
        
        # Assemble PDF
        pdf = b"%PDF-1.4\n"
        offsets = [0]
        
        for obj in objs:
            offsets.append(len(pdf))
            pdf += obj
        
        # Cross-reference table
        xref_pos = len(pdf)
        pdf += f"xref\n0 {len(objs) + 1}\n".encode()
        pdf += b"0000000000 65535 f \n"
        for off in offsets[1:]:
            pdf += f"{off:010d} 00000 n \n".encode()
        
        # Trailer
        pdf += f"trailer\n<< /Size {len(objs) + 1} /Root 1 0 R >>\nstartxref\n{xref_pos}\n%%EOF\n".encode()
        
        return pdf

    async def generate_pdf_report(self, report_data: Dict[str, Any]) -> bytes:
        """Generate a validation report PDF with proper formatting."""
        title = f"Validation Report - {report_data.get('project_name', 'Project')}"
        
        lines = [
            "",
            f"Model: {report_data.get('model_name', 'N/A')}",
            f"Dataset: {report_data.get('dataset_name', 'N/A')}",
            f"Date: {report_data.get('validation_date', 'N/A')[:10] if report_data.get('validation_date') else 'N/A'}",
            f"Overall Status: {report_data.get('overall_status', 'N/A').upper()}",
            "",
            "=" * 70,
            "EXECUTIVE SUMMARY",
            "=" * 70,
            "",
        ]
        
        # Add executive summary with line wrapping
        summary = report_data.get("executive_summary", "N/A")
        if len(summary) > 85:
            # Simple word wrapping
            words = summary.split()
            current_line = ""
            for word in words:
                if len(current_line) + len(word) + 1 <= 85:
                    current_line += (" " if current_line else "") + word
                else:
                    lines.append(current_line)
                    current_line = word
            if current_line:
                lines.append(current_line)
        else:
            lines.append(summary)
        
        lines.extend([
            "",
            "=" * 70,
            "VALIDATION RESULTS",
            "=" * 70,
            ""
        ])
        
        # Add fairness results
        validations = report_data.get("validations", {})
        fairness = validations.get("fairness", {})
        if fairness.get("status") == "completed":
            lines.append("FAIRNESS:")
            for result in fairness.get("results", [])[:10]:  # Limit to prevent overflow
                status = "PASS" if result.get("passed") else "FAIL"
                metric = result.get("metric_name", "unknown")
                value = result.get("metric_value", 0)
                lines.append(f"  {metric}: {value:.3f} [{status}]")
            lines.append("")
        
        # Add transparency status
        transparency = validations.get("transparency", {})
        if transparency.get("status") == "completed":
            lines.append("TRANSPARENCY: COMPLETED")
            lines.append("")
        
        # Add privacy status
        privacy = validations.get("privacy", {})
        if privacy.get("status") == "completed":
            passed = privacy.get("report", {}).get("overall_passed")
            status = "PASS" if passed else "FAIL"
            lines.append(f"PRIVACY: {status}")
            lines.append("")
        
        lines.extend([
            "=" * 70,
            "RECOMMENDATIONS",
            "=" * 70,
            ""
        ])
        
        for rec in report_data.get("recommendations", [])[:8]:  # Limit recommendations
            # Wrap long recommendations
            if len(rec) > 80:
                lines.append(f"- {rec[:77]}...")
            else:
                lines.append(f"- {rec}")
        
        lines.extend([
            "",
            "=" * 70,
            "End of Report",
            "=" * 70
        ])
        
        return self._simple_pdf_bytes(title, lines)

    # ── Compliance Certificate PDF ──────────────────────────────────────
    async def generate_html_report(self, validation_suite_id: UUID) -> str:
        """Render a self-contained HTML report using Jinja2."""
        report = await self.generate_validation_report(validation_suite_id)
        validations = report.get("validations", {})

        # Gather transparency extras
        transparency = validations.get("transparency", {})
        feature_importance = transparency.get("feature_importance", {})
        explanation_fidelity = transparency.get("explanation_fidelity")

        # Privacy report (from artifact JSON)
        privacy_section = validations.get("privacy", {})
        privacy_report_raw = privacy_section.get("report", {})

        template = _jinja_env.get_template("report.html")
        html = template.render(
            project_name=report.get("project_name", "Unknown"),
            model_name=report.get("model_name", "Unknown"),
            dataset_name=report.get("dataset_name", "Unknown"),
            validation_date=report.get("validation_date", "")[:10] if report.get("validation_date") else "",
            overall_passed=report.get("overall_passed", False),
            executive_summary=report.get("executive_summary", ""),
            fairness_results=validations.get("fairness", {}).get("results", []),
            feature_importance=feature_importance,
            explanation_fidelity=explanation_fidelity,
            privacy_report=privacy_report_raw,
            recommendations=report.get("recommendations", []),
            validation_suite_id=str(validation_suite_id),
            generated_at=datetime.utcnow().isoformat(),
        )
        return html

    # ── Compliance Certificate PDF ──────────────────────────────────────
    async def generate_certificate_pdf(self, validation_suite_id: UUID) -> bytes:
        """Generate a visually-distinct compliance certificate PDF for a suite."""
        suite = await self._suite_or_404(validation_suite_id)
        report = await self.generate_validation_report(validation_suite_id)

        project_name = report.get("project_name", "Unknown Project")
        model_name = report.get("model_name", "Unknown Model")
        dataset_name = report.get("dataset_name", "Unknown Dataset")
        validation_date = report.get("validation_date", datetime.utcnow().isoformat())
        overall_passed = report.get("overall_passed", False)
        verdict = "PASS" if overall_passed else "FAIL"

        validations = report.get("validations", {})

        # Determine per-principle scores
        def _principle_status(key: str) -> str:
            section = validations.get(key, {})
            st = section.get("status", "not_run")
            if st == "not_run":
                return "NOT RUN"
            if key == "fairness":
                results = section.get("results", [])
                if results and all(r.get("passed") for r in results):
                    return "PASS"
                return "FAIL"
            if key == "privacy":
                if section.get("overall_passed") is True:
                    return "PASS"
                return "FAIL"
            if key == "transparency":
                return "PASS" if st == "completed" else "FAIL"
            return "N/A"

        fairness_status = _principle_status("fairness")
        transparency_status = _principle_status("transparency")
        privacy_status = _principle_status("privacy")
        accountability_status = "PASS" if validations.get("accountability") else "RECORDED"

        # Build certificate body with proper formatting
        lines = [
            "",
            "",
            "=" * 70,
            "          ETHICAL AI COMPLIANCE CERTIFICATE",
            "=" * 70,
            "",
            "",
            "PROJECT INFORMATION",
            "-" * 70,
            "",
            f"  Project:        {project_name[:50]}",
            f"  Model:          {model_name[:50]}",
            f"  Dataset:        {dataset_name[:50]}",
            f"  Validation Date: {validation_date[:10] if len(validation_date) >= 10 else validation_date}",
            "",
            "",
            "OVERALL VERDICT",
            "-" * 70,
            "",
            f"       >>> {verdict} <<<",
            "",
            "",
            "ETHICAL PRINCIPLE SCORES",
            "-" * 70,
            "",
            f"  Fairness:           {fairness_status:>15}",
            f"  Transparency:       {transparency_status:>15}",
            f"  Privacy:            {privacy_status:>15}",
            f"  Accountability:     {accountability_status:>15}",
            "",
            "",
            "REGULATORY COMPLIANCE CHECKS",
            "-" * 70,
            "",
            "  * ECOA 80% Rule (Demographic Parity >= 0.80)",
            "  * EEOC Four-Fifths Rule",
            "  * GDPR Privacy Requirements",
            "  * PII Detection and Data Protection",
            "  * HIPAA Safe Harbor (if enabled)",
            "",
            "",
            "RECOMMENDATIONS",
            "-" * 70,
            "",
        ]
        
        # Add recommendations with proper formatting
        for rec in report.get("recommendations", [])[:6]:  # Limit to 6 recommendations
            if len(rec) > 65:
                lines.append(f"  * {rec[:62]}...")
            else:
                lines.append(f"  * {rec}")
        
        lines.extend([
            "",
            "",
            "=" * 70,
            "",
            "  This certificate was automatically generated by",
            "  EthicScan AI Validator",
            "",
            f"  Suite ID: {str(validation_suite_id)[:36]}",
            "",
            "=" * 70,
        ])

        title = "COMPLIANCE CERTIFICATE"
        return self._simple_pdf_bytes(title, lines)
