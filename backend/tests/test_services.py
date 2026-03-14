"""
Unit tests for services (auth, model_loader, requirement_elicitor).
"""

import asyncio
import pytest
from app.services.auth_service import hash_password, verify_password, create_access_token, decode_token


class TestAuthService:
    """Tests for password hashing and JWT tokens."""

    def test_hash_and_verify(self):
        hashed = hash_password("MySecretPassword")
        assert hashed != "MySecretPassword"
        assert verify_password("MySecretPassword", hashed)
        assert not verify_password("WrongPassword", hashed)

    def test_create_access_token(self):
        token = create_access_token("user-123")
        assert isinstance(token, str)
        assert len(token) > 20

    def test_decode_valid_token(self):
        token = create_access_token("user-456")
        payload = decode_token(token)
        assert payload is not None
        assert payload.sub == "user-456"
        assert payload.type == "access"

    def test_decode_invalid_token(self):
        payload = decode_token("this-is-not-a-jwt")
        assert payload is None


class TestMiddlewareErrors:
    """Tests for structured error helper."""

    def test_error_response_format(self):
        from app.middleware.error_handler import error_response
        resp = error_response(
            status_code=404,
            error="NotFoundError",
            message="Project not found",
            details={"resource": "project", "id": "abc"},
            request_id="req-123",
        )
        body = resp.body
        import json
        data = json.loads(body)
        assert data["error"] == "NotFoundError"
        assert data["message"] == "Project not found"
        assert data["request_id"] == "req-123"
        assert "timestamp" in data

    def test_app_error_subclasses(self):
        from app.middleware.error_handler import NotFoundError, AccessDeniedError, ValidationError

        e = NotFoundError("Dataset", "abc-123")
        assert e.status_code == 404
        assert "Dataset" in e.message

        e = AccessDeniedError()
        assert e.status_code == 403

        e = ValidationError("Invalid column", details={"column": "foo"})
        assert e.status_code == 400
        assert e.details == {"column": "foo"}


class TestReportGenerator:
    """Regression tests for report generation."""

    def test_format_metric_value_handles_none(self):
        from app.services.report_generator import ReportGenerator

        assert ReportGenerator._format_metric_value(None) == "N/A"

    def test_generate_pdf_report_handles_none_metric_value(self):
        from app.services.report_generator import ReportGenerator

        generator = ReportGenerator(db=None)
        report_data = {
            "project_name": "Demo Project",
            "model_name": "Demo Model",
            "dataset_name": "Demo Dataset",
            "overall_status": "fail",
            "executive_summary": "Demo summary",
            "validations": {
                "fairness": {
                    "status": "completed",
                    "results": [
                        {
                            "metric_name": "equalized_odds_ratio",
                            "metric_value": None,
                            "passed": False,
                        }
                    ],
                }
            },
            "recommendations": ["Review fairness thresholds."],
        }

        pdf_bytes = asyncio.run(generator.generate_pdf_report(report_data))

        assert isinstance(pdf_bytes, bytes)
        assert len(pdf_bytes) > 0

    def test_generate_pdf_report_handles_nullable_summary_and_recommendations(self):
        from app.services.report_generator import ReportGenerator

        generator = ReportGenerator(db=None)
        report_data = {
            "project_name": "Demo Project",
            "model_name": "Demo Model",
            "dataset_name": "Demo Dataset",
            "overall_status": None,
            "executive_summary": None,
            "validations": {},
            "recommendations": [None, "Use stronger guardrails."],
        }

        pdf_bytes = asyncio.run(generator.generate_pdf_report(report_data))

        assert isinstance(pdf_bytes, bytes)
        assert len(pdf_bytes) > 0

    def test_normalize_recommendations_filters_empty_values(self):
        from app.services.report_generator import ReportGenerator

        cleaned = ReportGenerator._normalize_recommendations([None, "", "  ", "Keep monitoring"])
        assert cleaned == ["Keep monitoring"]

    def test_generate_recommendations_returns_fallback_when_empty(self):
        from app.services.report_generator import ReportGenerator

        generator = ReportGenerator(db=None)
        recs = generator._generate_recommendations({})

        assert isinstance(recs, list)
        assert len(recs) >= 1
        assert any("monitoring" in r.lower() or "run" in r.lower() for r in recs)

    def test_generate_recommendations_includes_failed_fairness_metric_names(self):
        from app.services.report_generator import ReportGenerator

        generator = ReportGenerator(db=None)
        recs = generator._generate_recommendations(
            {
                "fairness": {
                    "status": "completed",
                    "results": [
                        {"metric_name": "demographic_parity_ratio", "passed": False},
                    ],
                }
            }
        )

        joined = " ".join(recs).lower()
        assert "demographic_parity_ratio" in joined
