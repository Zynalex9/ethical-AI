"""
Tests for the projects router (CRUD operations).
"""

import pytest
from httpx import AsyncClient


class TestListProjects:
    """GET /api/v1/projects"""

    async def test_list_empty(self, auth_client: AsyncClient):
        resp = await auth_client.get("/api/v1/projects")
        assert resp.status_code == 200
        assert resp.json() == []

    async def test_list_returns_own_projects(self, auth_client: AsyncClient):
        # Create a project first
        await auth_client.post("/api/v1/projects", json={
            "name": "My Project",
            "description": "Test",
        })
        resp = await auth_client.get("/api/v1/projects")
        assert resp.status_code == 200
        projects = resp.json()
        assert len(projects) >= 1
        assert projects[0]["name"] == "My Project"

    async def test_list_unauthenticated(self, client: AsyncClient):
        resp = await client.get("/api/v1/projects")
        assert resp.status_code == 403


class TestCreateProject:
    """POST /api/v1/projects"""

    async def test_create_success(self, auth_client: AsyncClient):
        resp = await auth_client.post("/api/v1/projects", json={
            "name": "New Project",
            "description": "A test project",
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "New Project"
        assert "id" in data
        assert data["model_count"] == 0
        assert data["dataset_count"] == 0

    async def test_create_missing_name(self, auth_client: AsyncClient):
        resp = await auth_client.post("/api/v1/projects", json={
            "description": "No name",
        })
        assert resp.status_code == 422

    async def test_create_empty_name(self, auth_client: AsyncClient):
        resp = await auth_client.post("/api/v1/projects", json={
            "name": "",
            "description": "Empty name",
        })
        assert resp.status_code == 422


class TestGetProject:
    """GET /api/v1/projects/{id}"""

    async def test_get_own_project(self, auth_client: AsyncClient):
        create_resp = await auth_client.post("/api/v1/projects", json={
            "name": "Fetch Me",
        })
        project_id = create_resp.json()["id"]

        resp = await auth_client.get(f"/api/v1/projects/{project_id}")
        assert resp.status_code == 200
        assert resp.json()["name"] == "Fetch Me"

    async def test_get_nonexistent(self, auth_client: AsyncClient):
        resp = await auth_client.get("/api/v1/projects/00000000-0000-0000-0000-000000000000")
        assert resp.status_code == 404


class TestDeleteProject:
    """DELETE /api/v1/projects/{id}"""

    async def test_soft_delete(self, auth_client: AsyncClient):
        create_resp = await auth_client.post("/api/v1/projects", json={
            "name": "Delete Me",
        })
        project_id = create_resp.json()["id"]

        resp = await auth_client.delete(f"/api/v1/projects/{project_id}")
        assert resp.status_code == 200

        # Should not appear in list anymore
        list_resp = await auth_client.get("/api/v1/projects")
        ids = [p["id"] for p in list_resp.json()]
        assert project_id not in ids
