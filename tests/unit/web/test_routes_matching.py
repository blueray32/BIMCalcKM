"""Tests for bimcalc.web.routes.matching - Matching pipeline routes.

Tests the matching router module extracted in Phase 3.4.
"""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock, AsyncMock
from types import SimpleNamespace
from uuid import uuid4

from bimcalc.web.routes import matching


@pytest.fixture
def app():
    """Create test FastAPI app with matching router."""
    test_app = FastAPI()
    test_app.include_router(matching.router)
    return test_app


@pytest.fixture
def client(app):
    """Create test client."""
    return TestClient(app)


@pytest.fixture
def mock_config():
    """Mock configuration with defaults."""
    config = MagicMock()
    config.org_id = "test-org"
    return config


@pytest.fixture
def mock_db_session():
    """Mock database session with async context manager."""
    session = AsyncMock()
    session.execute = AsyncMock()
    session.commit = AsyncMock()

    # Create async context manager
    async_cm = AsyncMock()
    async_cm.__aenter__.return_value = session
    async_cm.__aexit__.return_value = None

    return async_cm


@pytest.fixture
def mock_item_model():
    """Mock ItemModel for testing."""
    item = MagicMock()
    item.id = uuid4()  # Use valid UUID
    item.org_id = "test-org"
    item.project_id = "test-project"
    item.family = "Pipe"
    item.type_name = "100mm PVC"
    item.category = "Pipes"
    item.system_type = "Drainage"
    item.quantity = 10.0
    item.unit = "m"
    item.width_mm = None
    item.height_mm = None
    item.dn_mm = 100.0
    item.angle_deg = None
    item.material = "PVC"
    item.canonical_key = None
    item.classification_code = None
    return item


class TestMatchPage:
    """Tests for GET /match route."""

    @patch("bimcalc.web.dependencies.get_config")
    def test_match_page_renders(self, mock_get_config, client, mock_config):
        """Test match page renders successfully."""
        mock_get_config.return_value = mock_config

        response = client.get("/match")
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]

    @patch("bimcalc.web.dependencies.get_config")
    def test_match_page_with_org_project(self, mock_get_config, client, mock_config):
        """Test match page accepts org and project parameters."""
        mock_get_config.return_value = mock_config

        response = client.get("/match?org=org-123&project=proj-456")
        assert response.status_code == 200


class TestRunMatching:
    """Tests for POST /match/run route."""

    @patch("bimcalc.web.routes.matching.record_match_result")
    @patch("bimcalc.web.routes.matching.MatchOrchestrator")
    @patch("bimcalc.web.routes.matching.get_session")
    def test_run_matching_success(
        self,
        mock_get_session,
        mock_orchestrator_class,
        mock_record_match,
        client,
        mock_db_session,
        mock_item_model,
    ):
        """Test successful matching pipeline execution."""
        # Mock session and query results
        mock_get_session.return_value = mock_db_session
        session = mock_db_session.__aenter__.return_value

        # Mock query result
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_item_model]
        session.execute.return_value = mock_result

        # Mock orchestrator
        mock_orchestrator = AsyncMock()
        mock_match_result = SimpleNamespace(
            decision=SimpleNamespace(value="MATCH"),
            confidence_score=0.95,
            flags=[],
        )
        mock_price_item = MagicMock()
        mock_orchestrator.match.return_value = (mock_match_result, mock_price_item)
        mock_orchestrator_class.return_value = mock_orchestrator

        # Mock record_match_result
        mock_record_match.return_value = None

        # Make request
        data = {
            "org": "test-org",
            "project": "test-project",
        }
        response = client.post("/match/run", data=data)

        assert response.status_code == 200
        json_response = response.json()
        assert json_response["success"] is True
        assert "Matched 1 items" in json_response["message"]
        assert len(json_response["results"]) == 1
        assert json_response["results"][0]["decision"] == "MATCH"
        assert json_response["results"][0]["confidence"] == 0.95

        # Verify orchestrator was called
        mock_orchestrator.match.assert_called_once()

        # Verify match result was persisted
        mock_record_match.assert_called_once()

        # Verify session commit
        session.commit.assert_called_once()

    @patch("bimcalc.web.routes.matching.MatchOrchestrator")
    @patch("bimcalc.web.routes.matching.get_session")
    def test_run_matching_no_items(
        self,
        mock_get_session,
        mock_orchestrator_class,
        client,
        mock_db_session,
    ):
        """Test matching with no items in project."""
        # Mock session and empty query results
        mock_get_session.return_value = mock_db_session
        session = mock_db_session.__aenter__.return_value

        # Mock empty query result
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        session.execute.return_value = mock_result

        # Make request
        data = {
            "org": "test-org",
            "project": "empty-project",
        }
        response = client.post("/match/run", data=data)

        assert response.status_code == 200
        json_response = response.json()
        assert json_response["success"] is False
        assert "No items found" in json_response["message"]

    @patch("bimcalc.web.routes.matching.record_match_result")
    @patch("bimcalc.web.routes.matching.MatchOrchestrator")
    @patch("bimcalc.web.routes.matching.get_session")
    def test_run_matching_with_limit(
        self,
        mock_get_session,
        mock_orchestrator_class,
        mock_record_match,
        client,
        mock_db_session,
        mock_item_model,
    ):
        """Test matching with limit parameter."""
        # Mock session and query results
        mock_get_session.return_value = mock_db_session
        session = mock_db_session.__aenter__.return_value

        # Mock query result with single item
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_item_model]
        session.execute.return_value = mock_result

        # Mock orchestrator
        mock_orchestrator = AsyncMock()
        mock_match_result = SimpleNamespace(
            decision=SimpleNamespace(value="MATCH"),
            confidence_score=0.85,
            flags=[],
        )
        mock_orchestrator.match.return_value = (mock_match_result, MagicMock())
        mock_orchestrator_class.return_value = mock_orchestrator

        # Make request with limit
        data = {
            "org": "test-org",
            "project": "test-project",
            "limit": "10",
        }
        response = client.post("/match/run", data=data)

        assert response.status_code == 200
        json_response = response.json()
        assert json_response["success"] is True

        # Verify limit was applied in query (can't easily verify in mock, but at least check it doesn't error)
        session.execute.assert_called_once()

    def test_run_matching_invalid_limit(self, client):
        """Test matching with invalid limit parameter."""
        data = {
            "org": "test-org",
            "project": "test-project",
            "limit": "invalid",
        }
        response = client.post("/match/run", data=data)

        assert response.status_code == 422
        assert "limit must be an integer" in response.json()["detail"]

    @patch("bimcalc.web.routes.matching.record_match_result")
    @patch("bimcalc.web.routes.matching.MatchOrchestrator")
    @patch("bimcalc.web.routes.matching.get_session")
    def test_run_matching_persists_canonical_metadata(
        self,
        mock_get_session,
        mock_orchestrator_class,
        mock_record_match,
        client,
        mock_db_session,
        mock_item_model,
    ):
        """Test that matching persists canonical key and classification code."""
        # Mock session and query results
        mock_get_session.return_value = mock_db_session
        session = mock_db_session.__aenter__.return_value

        # Mock query result
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_item_model]
        session.execute.return_value = mock_result

        # Mock orchestrator - match will update item.canonical_key and item.classification_code
        mock_orchestrator = AsyncMock()

        async def mock_match_fn(item, source):
            # Simulate match updating canonical metadata
            item.canonical_key = "pipe:100mm:pvc"
            item.classification_code = "ABC123"
            return (
                SimpleNamespace(
                    decision=SimpleNamespace(value="MATCH"),
                    confidence_score=0.90,
                    flags=[],
                ),
                MagicMock()
            )

        mock_orchestrator.match.side_effect = mock_match_fn
        mock_orchestrator_class.return_value = mock_orchestrator

        # Make request
        data = {
            "org": "test-org",
            "project": "test-project",
        }
        response = client.post("/match/run", data=data)

        assert response.status_code == 200

        # Verify canonical metadata was persisted to item model
        assert mock_item_model.canonical_key == "pipe:100mm:pvc"
        assert mock_item_model.classification_code == "ABC123"

        # Verify commit
        session.commit.assert_called_once()

    @patch("bimcalc.web.routes.matching.record_match_result")
    @patch("bimcalc.web.routes.matching.MatchOrchestrator")
    @patch("bimcalc.web.routes.matching.get_session")
    def test_run_matching_multiple_items(
        self,
        mock_get_session,
        mock_orchestrator_class,
        mock_record_match,
        client,
        mock_db_session,
    ):
        """Test matching with multiple items."""
        # Create multiple mock items
        items = []
        for i in range(3):
            item = MagicMock()
            item.id = uuid4()  # Use valid UUID
            item.org_id = "test-org"
            item.project_id = "test-project"
            item.family = f"Pipe{i}"
            item.type_name = f"Type{i}"
            item.category = "Pipes"
            item.system_type = "Drainage"
            item.quantity = 10.0 * (i + 1)
            item.unit = "m"
            item.width_mm = None
            item.height_mm = None
            item.dn_mm = 100.0 + (i * 50)
            item.angle_deg = None
            item.material = "PVC"
            items.append(item)

        # Mock session and query results
        mock_get_session.return_value = mock_db_session
        session = mock_db_session.__aenter__.return_value

        # Mock query result with multiple items
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = items
        session.execute.return_value = mock_result

        # Mock orchestrator
        mock_orchestrator = AsyncMock()
        mock_match_result = SimpleNamespace(
            decision=SimpleNamespace(value="MATCH"),
            confidence_score=0.88,
            flags=[],
        )
        mock_orchestrator.match.return_value = (mock_match_result, MagicMock())
        mock_orchestrator_class.return_value = mock_orchestrator

        # Make request
        data = {
            "org": "test-org",
            "project": "test-project",
        }
        response = client.post("/match/run", data=data)

        assert response.status_code == 200
        json_response = response.json()
        assert json_response["success"] is True
        assert "Matched 3 items" in json_response["message"]
        assert len(json_response["results"]) == 3

        # Verify orchestrator was called for each item
        assert mock_orchestrator.match.call_count == 3

        # Verify match results were persisted for each item
        assert mock_record_match.call_count == 3

    def test_run_matching_requires_org(self, client):
        """Test that org parameter is required."""
        data = {"project": "test-project"}
        response = client.post("/match/run", data=data)
        assert response.status_code == 422  # Validation error

    def test_run_matching_requires_project(self, client):
        """Test that project parameter is required."""
        data = {"org": "test-org"}
        response = client.post("/match/run", data=data)
        assert response.status_code == 422  # Validation error


# Integration tests
def test_router_has_correct_routes():
    """Test that matching router has all expected routes."""
    routes = [route.path for route in matching.router.routes]

    assert "/match" in routes
    assert "/match/run" in routes

    # Should have 2 routes total
    assert len(matching.router.routes) == 2


def test_router_has_matching_tag():
    """Test that router is tagged correctly."""
    assert "matching" in matching.router.tags
