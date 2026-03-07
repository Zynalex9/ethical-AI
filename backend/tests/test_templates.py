"""
Tests for the templates router (list, create, apply, seed).
"""

import pytest
from httpx import AsyncClient


class TestListTemplates:
    """GET /api/v1/templates"""

    async def test_list_all(self, auth_client: AsyncClient):
        resp = await auth_client.get("/api/v1/templates")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    async def test_filter_by_domain(self, auth_client: AsyncClient):
        resp = await auth_client.get("/api/v1/templates", params={"domain": "finance"})
        assert resp.status_code == 200
        for tpl in resp.json():
            assert tpl["domain"] == "finance"

    async def test_filter_by_principle(self, auth_client: AsyncClient):
        resp = await auth_client.get("/api/v1/templates", params={"principle": "fairness"})
        assert resp.status_code == 200


class TestSeedTemplates:
    """POST /api/v1/templates/seed-defaults"""

    async def test_seed_defaults(self, admin_client: AsyncClient):
        resp = await admin_client.post("/api/v1/templates/seed-defaults")
        assert resp.status_code == 200
        data = resp.json()
        assert "seeded" in data or "message" in data


class TestCreateTemplate:
    """POST /api/v1/templates"""

    async def test_create_custom(self, auth_client: AsyncClient):
        resp = await auth_client.post("/api/v1/templates", json={
            "template_id": "CUSTOM-TEST-001",
            "name": "Test Custom Template",
            "description": "A test template",
            "domain": "general",
            "rules": {
                "principles": ["fairness"],
                "items": [
                    {"metric": "demographic_parity_ratio", "operator": ">=", "value": 0.80}
                ]
            }
        })
        assert resp.status_code == 201
        assert resp.json()["template_id"] == "CUSTOM-TEST-001"


class TestGetTemplate:
    """GET /api/v1/templates/{id}"""

    async def test_get_nonexistent(self, auth_client: AsyncClient):
        resp = await auth_client.get("/api/v1/templates/00000000-0000-0000-0000-000000000000")
        assert resp.status_code == 404
