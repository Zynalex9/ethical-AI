"""
Unit tests for services (auth, model_loader, requirement_elicitor).
"""

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
