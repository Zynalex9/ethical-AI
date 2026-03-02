"""
Tests for health check and root endpoints + middleware behavior.
"""

import pytest
from httpx import AsyncClient


class TestHealthCheck:
    """GET /health"""

    async def test_health(self, client: AsyncClient):
        resp = await client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "healthy"

    async def test_root(self, client: AsyncClient):
        resp = await client.get("/")
        assert resp.status_code == 200
        data = resp.json()
        assert "name" in data
        assert "version" in data


class TestRequestIdMiddleware:
    """Verify X-Request-ID header is set on responses."""

    async def test_response_has_request_id(self, client: AsyncClient):
        resp = await client.get("/health")
        # The middleware should attach an X-Request-ID header
        assert "x-request-id" in resp.headers

    async def test_custom_request_id_echoed(self, client: AsyncClient):
        resp = await client.get("/health", headers={"X-Request-ID": "my-custom-id"})
        assert resp.headers.get("x-request-id") == "my-custom-id"


class TestStructuredErrorResponse:
    """Verify error responses use structured format."""

    async def test_422_validation_error_format(self, client: AsyncClient):
        # Send invalid JSON to a validated endpoint
        resp = await client.post("/api/v1/auth/register", json={})
        assert resp.status_code == 422
        data = resp.json()
        assert "error" in data
        assert "message" in data
        assert "timestamp" in data

    async def test_404_format(self, auth_client: AsyncClient):
        resp = await auth_client.get("/api/v1/projects/00000000-0000-0000-0000-000000000000")
        assert resp.status_code == 404
