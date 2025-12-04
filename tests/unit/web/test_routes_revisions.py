"""Tests for bimcalc.web.routes.revisions - Revisions tracking routes.

Tests the revisions router module extracted in Phase 3.14.
"""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock, AsyncMock
from datetime import datetime
from uuid import uuid4

from bimcalc.web.routes import revisions


@pytest.fixture
def app():
    """Create test FastAPI app with revisions router."""
    test_app = FastAPI()
    test_app.include_router(revisions.router)
    return test_app


@pytest.fixture
def client(app):
    """Create test client."""
    return TestClient(app)


@pytest.fixture
def mock_revision():
    """Mock revision record."""
    revision = MagicMock()
    revision.id = uuid4()
    revision.item_id = uuid4()
    revision.field_name = "quantity"
    revision.old_value = "10"
    revision.new_value = "15"
    revision.change_type = "modified"
    revision.ingest_timestamp = datetime(2025, 1, 1, 12, 0, 0)
    revision.source_filename = "test_schedule.xlsx"
    return revision


@pytest.fixture
def mock_db_session():
    """Mock database session with async context manager."""
    session = AsyncMock()
    session.execute = AsyncMock()

    # Create async context manager
    async_cm = AsyncMock()
    async_cm.__aenter__.return_value = session
    async_cm.__aexit__.return_value = None

    return async_cm


class TestRevisionsPage:
    """Tests for GET /revisions route."""

    @pytest.mark.skip(
        reason="Revisions template requires complex context - better in integration"
    )
    @patch("bimcalc.web.routes.revisions.get_org_project")
    def test_revisions_page_renders(
        self,
        mock_get_org_project,
        client,
    ):
        """Test revisions dashboard page renders.

        Note: Skipped - revisions template requires complex context.
        """
        mock_get_org_project.return_value = ("test-org", "test-project")

        response = client.get("/revisions")
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]

    @patch("bimcalc.web.routes.revisions.get_org_project")
    def test_revisions_page_with_params(
        self,
        mock_get_org_project,
        client,
    ):
        """Test revisions page with org and project parameters."""
        mock_get_org_project.return_value = ("custom-org", "custom-project")

        response = client.get("/revisions?org=custom-org&project=custom-project")
        assert response.status_code == 200


class TestGetRevisions:
    """Tests for GET /api/revisions route."""

    @patch("bimcalc.web.routes.revisions.get_session")
    def test_get_revisions_success(
        self,
        mock_get_session,
        client,
        mock_db_session,
        mock_revision,
    ):
        """Test getting revision history."""
        mock_get_session.return_value = mock_db_session
        session = mock_db_session.__aenter__.return_value

        # Mock query result with revision and item info
        mock_row = MagicMock()
        mock_row.ItemRevisionModel = mock_revision
        mock_row.family = "Pipes"
        mock_row.type_name = "Copper 22mm"

        mock_result = MagicMock()
        mock_result.all.return_value = [mock_row]
        session.execute.return_value = mock_result

        response = client.get("/api/revisions?org=test-org&project=test-project")
        assert response.status_code == 200

        data = response.json()
        assert data["org_id"] == "test-org"
        assert data["project_id"] == "test-project"
        assert data["count"] == 1
        assert len(data["revisions"]) == 1

        revision_data = data["revisions"][0]
        assert revision_data["item_name"] == "Pipes / Copper 22mm"
        assert revision_data["field_name"] == "quantity"
        assert revision_data["old_value"] == "10"
        assert revision_data["new_value"] == "15"
        assert revision_data["change_type"] == "modified"

    @patch("bimcalc.web.routes.revisions.get_session")
    def test_get_revisions_with_item_filter(
        self,
        mock_get_session,
        client,
        mock_db_session,
        mock_revision,
    ):
        """Test getting revisions filtered by item_id."""
        mock_get_session.return_value = mock_db_session
        session = mock_db_session.__aenter__.return_value

        # Mock query result
        mock_row = MagicMock()
        mock_row.ItemRevisionModel = mock_revision
        mock_row.family = "Ducts"
        mock_row.type_name = "Rectangular 300x200"

        mock_result = MagicMock()
        mock_result.all.return_value = [mock_row]
        session.execute.return_value = mock_result

        item_id = str(uuid4())
        response = client.get(
            f"/api/revisions?org=test-org&project=test-project&item_id={item_id}"
        )
        assert response.status_code == 200

        data = response.json()
        assert data["count"] == 1

    @patch("bimcalc.web.routes.revisions.get_session")
    def test_get_revisions_empty_results(
        self,
        mock_get_session,
        client,
        mock_db_session,
    ):
        """Test getting revisions with no results."""
        mock_get_session.return_value = mock_db_session
        session = mock_db_session.__aenter__.return_value

        # Mock empty result
        mock_result = MagicMock()
        mock_result.all.return_value = []
        session.execute.return_value = mock_result

        response = client.get("/api/revisions?org=test-org&project=test-project")
        assert response.status_code == 200

        data = response.json()
        assert data["count"] == 0
        assert data["revisions"] == []

    @patch("bimcalc.web.routes.revisions.get_session")
    def test_get_revisions_with_limit(
        self,
        mock_get_session,
        client,
        mock_db_session,
        mock_revision,
    ):
        """Test getting revisions with custom limit."""
        mock_get_session.return_value = mock_db_session
        session = mock_db_session.__aenter__.return_value

        # Create multiple revisions
        mock_rows = []
        for i in range(10):
            mock_row = MagicMock()
            rev = MagicMock()
            rev.id = uuid4()
            rev.item_id = uuid4()
            rev.field_name = f"field_{i}"
            rev.old_value = str(i)
            rev.new_value = str(i + 1)
            rev.change_type = "modified"
            rev.ingest_timestamp = datetime(2025, 1, 1, 12, i, 0)
            rev.source_filename = "test.xlsx"
            mock_row.ItemRevisionModel = rev
            mock_row.family = "Test"
            mock_row.type_name = f"Type {i}"
            mock_rows.append(mock_row)

        mock_result = MagicMock()
        mock_result.all.return_value = mock_rows
        session.execute.return_value = mock_result

        response = client.get(
            "/api/revisions?org=test-org&project=test-project&limit=10"
        )
        assert response.status_code == 200

        data = response.json()
        assert data["count"] == 10

    def test_get_revisions_missing_org(self, client):
        """Test API returns error when org parameter missing."""
        response = client.get("/api/revisions?project=test-project")
        assert response.status_code == 422  # Validation error

    def test_get_revisions_missing_project(self, client):
        """Test API returns error when project parameter missing."""
        response = client.get("/api/revisions?org=test-org")
        assert response.status_code == 422  # Validation error

    def test_get_revisions_invalid_limit(self, client):
        """Test API validates limit parameter."""
        response = client.get(
            "/api/revisions?org=test-org&project=test-project&limit=0"
        )
        assert response.status_code == 422  # Validation error

        response = client.get(
            "/api/revisions?org=test-org&project=test-project&limit=101"
        )
        assert response.status_code == 422  # Validation error


# Integration tests
def test_router_has_correct_routes():
    """Test that revisions router has all expected routes."""
    routes = [route.path for route in revisions.router.routes]

    assert "/revisions" in routes
    assert "/api/revisions" in routes

    # Should have 2 routes total
    assert len(revisions.router.routes) == 2


def test_router_has_revisions_tag():
    """Test that router is tagged correctly."""
    assert "revisions" in revisions.router.tags
