"""Tests for bimcalc.ingestion.routes - Ingestion routes.

Tests the ingestion router module extracted in Phase 3.3.
"""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock, AsyncMock, mock_open
from io import BytesIO

from bimcalc.ingestion import routes as ingestion


@pytest.fixture
def app():
    """Create test FastAPI app with ingestion router."""
    test_app = FastAPI()
    test_app.include_router(ingestion.router)
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


class TestIngestHistoryPage:
    """Tests for GET /ingest/history route."""

    @patch("bimcalc.web.dependencies.get_config")
    def test_ingest_history_page_renders(self, mock_get_config, client, mock_config):
        """Test ingest history page renders successfully."""
        mock_get_config.return_value = mock_config

        response = client.get("/ingest/history")
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]

    @patch("bimcalc.web.dependencies.get_config")
    def test_ingest_history_with_org_project(
        self, mock_get_config, client, mock_config
    ):
        """Test ingest history accepts org and project parameters."""
        mock_get_config.return_value = mock_config

        response = client.get("/ingest/history?org=org-123&project=proj-456")
        assert response.status_code == 200


class TestIngestPage:
    """Tests for GET /ingest route."""

    @patch("bimcalc.web.dependencies.get_config")
    def test_ingest_page_renders(self, mock_get_config, client, mock_config):
        """Test ingest page renders successfully."""
        mock_get_config.return_value = mock_config

        response = client.get("/ingest")
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]

    @patch("bimcalc.web.dependencies.get_config")
    def test_ingest_page_with_org_project(self, mock_get_config, client, mock_config):
        """Test ingest page accepts org and project parameters."""
        mock_get_config.return_value = mock_config

        response = client.get("/ingest?org=org-123&project=proj-456")
        assert response.status_code == 200


class TestIngestSchedules:
    """Tests for POST /ingest/schedules route."""

    @patch("bimcalc.ingestion.routes.ingest_schedule")
    @patch("bimcalc.ingestion.routes.get_session")
    @patch("builtins.open", new_callable=mock_open)
    @patch("bimcalc.ingestion.routes.Path")
    def test_ingest_schedules_success(
        self,
        mock_path_class,
        mock_file_open,
        mock_get_session,
        mock_ingest_schedule,
        client,
    ):
        """Test successful schedule ingestion."""
        # Mock file operations
        mock_path = MagicMock()
        mock_path.exists.return_value = True
        mock_path.unlink = MagicMock()
        mock_path_class.return_value = mock_path

        # Mock database session
        mock_session = AsyncMock()
        async_cm = AsyncMock()
        async_cm.__aenter__.return_value = mock_session
        async_cm.__aexit__.return_value = None
        mock_get_session.return_value = async_cm

        # Mock ingestion result
        mock_ingest_schedule.return_value = (100, [])

        # Create test file
        file_content = b"test,schedule,data"
        files = {"file": ("schedule.csv", BytesIO(file_content), "text/csv")}
        data = {"org": "test-org", "project": "test-project"}

        response = client.post("/ingest/schedules", files=files, data=data)

        assert response.status_code == 200
        json_response = response.json()
        assert json_response["success"] is True
        assert "100" in json_response["message"]
        assert json_response["errors"] == []

        # Verify file operations
        mock_file_open.assert_called_once()
        mock_path.unlink.assert_called_once()

    @patch("bimcalc.ingestion.routes.ingest_schedule")
    @patch("bimcalc.ingestion.routes.get_session")
    @patch("bimcalc.ingestion.routes.get_email_notifier")
    @patch("bimcalc.ingestion.routes.get_slack_notifier")
    @patch("builtins.open", new_callable=mock_open)
    @patch("bimcalc.ingestion.routes.Path")
    def test_ingest_schedules_failure_sends_alerts(
        self,
        mock_path_class,
        mock_file_open,
        mock_get_slack,
        mock_get_email,
        mock_get_session,
        mock_ingest_schedule,
        client,
    ):
        """Test failed schedule ingestion sends alerts."""
        # Mock file operations
        mock_path = MagicMock()
        mock_path.exists.return_value = True
        mock_path.unlink = MagicMock()
        mock_path_class.return_value = mock_path

        # Mock database session
        mock_session = AsyncMock()
        async_cm = AsyncMock()
        async_cm.__aenter__.return_value = mock_session
        async_cm.__aexit__.return_value = None
        mock_get_session.return_value = async_cm

        # Mock ingestion failure
        mock_ingest_schedule.side_effect = Exception("Ingestion failed")

        # Mock notifiers
        mock_email_notifier = AsyncMock()
        mock_slack_notifier = AsyncMock()
        mock_get_email.return_value = mock_email_notifier
        mock_get_slack.return_value = mock_slack_notifier

        # Create test file
        file_content = b"test,schedule,data"
        files = {"file": ("schedule.csv", BytesIO(file_content), "text/csv")}
        data = {"org": "test-org", "project": "test-project"}

        response = client.post("/ingest/schedules", files=files, data=data)

        assert response.status_code == 500
        assert "Ingestion failed" in response.json()["detail"]

        # Verify alerts were sent
        mock_email_notifier.send_ingestion_failure_alert.assert_called_once()
        mock_slack_notifier.post_ingestion_failure_alert.assert_called_once()

        # Verify cleanup
        mock_path.unlink.assert_called_once()

    @patch("builtins.open", new_callable=mock_open)
    @patch("bimcalc.ingestion.routes.Path")
    def test_ingest_schedules_requires_file(
        self, mock_path_class, mock_file_open, client
    ):
        """Test that file upload is required."""
        data = {"org": "test-org", "project": "test-project"}

        response = client.post("/ingest/schedules", data=data)
        assert response.status_code == 422  # Validation error


class TestIngestPrices:
    """Tests for POST /ingest/prices route."""

    @patch("bimcalc.ingestion.routes.ingest_pricebook")
    @patch("bimcalc.ingestion.routes.get_session")
    @patch("builtins.open", new_callable=mock_open)
    @patch("bimcalc.ingestion.routes.Path")
    def test_ingest_prices_success_with_cmm(
        self,
        mock_path_class,
        mock_file_open,
        mock_get_session,
        mock_ingest_pricebook,
        client,
    ):
        """Test successful price ingestion with CMM enabled."""
        # Mock file operations
        mock_path = MagicMock()
        mock_path.exists.return_value = True
        mock_path.unlink = MagicMock()
        mock_path_class.return_value = mock_path

        # Mock database session
        mock_session = AsyncMock()
        async_cm = AsyncMock()
        async_cm.__aenter__.return_value = mock_session
        async_cm.__aexit__.return_value = None
        mock_get_session.return_value = async_cm

        # Mock ingestion result
        mock_ingest_pricebook.return_value = (500, [])

        # Create test file
        file_content = b"code,description,price"
        files = {"file": ("prices.csv", BytesIO(file_content), "text/csv")}
        data = {"vendor": "acme", "use_cmm": "true"}

        response = client.post("/ingest/prices", files=files, data=data)

        assert response.status_code == 200
        json_response = response.json()
        assert json_response["success"] is True
        assert "500" in json_response["message"]
        assert "with CMM enabled" in json_response["message"]
        assert json_response["errors"] == []

        # Verify file cleanup
        mock_path.unlink.assert_called_once()

    @patch("bimcalc.ingestion.routes.ingest_pricebook")
    @patch("bimcalc.ingestion.routes.get_session")
    @patch("builtins.open", new_callable=mock_open)
    @patch("bimcalc.ingestion.routes.Path")
    def test_ingest_prices_success_without_cmm(
        self,
        mock_path_class,
        mock_file_open,
        mock_get_session,
        mock_ingest_pricebook,
        client,
    ):
        """Test successful price ingestion without CMM."""
        # Mock file operations
        mock_path = MagicMock()
        mock_path.exists.return_value = True
        mock_path.unlink = MagicMock()
        mock_path_class.return_value = mock_path

        # Mock database session
        mock_session = AsyncMock()
        async_cm = AsyncMock()
        async_cm.__aenter__.return_value = mock_session
        async_cm.__aexit__.return_value = None
        mock_get_session.return_value = async_cm

        # Mock ingestion result
        mock_ingest_pricebook.return_value = (250, ["Warning: Missing classifications"])

        # Create test file
        file_content = b"code,description,price"
        files = {"file": ("prices.csv", BytesIO(file_content), "text/csv")}
        data = {"vendor": "default", "use_cmm": "false"}

        response = client.post("/ingest/prices", files=files, data=data)

        assert response.status_code == 200
        json_response = response.json()
        assert json_response["success"] is True
        assert "250" in json_response["message"]
        assert "without CMM" in json_response["message"]
        assert len(json_response["errors"]) == 1

    @patch("bimcalc.ingestion.routes.ingest_pricebook")
    @patch("bimcalc.ingestion.routes.get_session")
    @patch("builtins.open", new_callable=mock_open)
    @patch("bimcalc.ingestion.routes.Path")
    def test_ingest_prices_validation_error(
        self,
        mock_path_class,
        mock_file_open,
        mock_get_session,
        mock_ingest_pricebook,
        client,
    ):
        """Test price ingestion with validation error returns 400."""
        # Mock file operations
        mock_path = MagicMock()
        mock_path.exists.return_value = True
        mock_path.unlink = MagicMock()
        mock_path_class.return_value = mock_path

        # Mock database session
        mock_session = AsyncMock()
        async_cm = AsyncMock()
        async_cm.__aenter__.return_value = mock_session
        async_cm.__aexit__.return_value = None
        mock_get_session.return_value = async_cm

        # Mock validation error
        mock_ingest_pricebook.side_effect = ValueError("Invalid file format")

        # Create test file
        file_content = b"invalid data"
        files = {"file": ("prices.txt", BytesIO(file_content), "text/plain")}
        data = {"vendor": "default"}

        response = client.post("/ingest/prices", files=files, data=data)

        assert response.status_code == 400
        json_response = response.json()
        assert json_response["success"] is False
        assert "Invalid file format" in json_response["message"]

        # Verify cleanup
        mock_path.unlink.assert_called_once()

    @patch("bimcalc.ingestion.routes.ingest_pricebook")
    @patch("bimcalc.ingestion.routes.get_session")
    @patch("bimcalc.ingestion.routes.get_email_notifier")
    @patch("bimcalc.ingestion.routes.get_slack_notifier")
    @patch("builtins.open", new_callable=mock_open)
    @patch("bimcalc.ingestion.routes.Path")
    def test_ingest_prices_server_error_sends_alerts(
        self,
        mock_path_class,
        mock_file_open,
        mock_get_slack,
        mock_get_email,
        mock_get_session,
        mock_ingest_pricebook,
        client,
    ):
        """Test price ingestion server error sends alerts."""
        # Mock file operations
        mock_path = MagicMock()
        mock_path.exists.return_value = True
        mock_path.unlink = MagicMock()
        mock_path_class.return_value = mock_path

        # Mock database session
        mock_session = AsyncMock()
        async_cm = AsyncMock()
        async_cm.__aenter__.return_value = mock_session
        async_cm.__aexit__.return_value = None
        mock_get_session.return_value = async_cm

        # Mock server error
        mock_ingest_pricebook.side_effect = Exception("Database connection failed")

        # Mock notifiers
        mock_email_notifier = AsyncMock()
        mock_slack_notifier = AsyncMock()
        mock_get_email.return_value = mock_email_notifier
        mock_get_slack.return_value = mock_slack_notifier

        # Create test file
        file_content = b"code,description,price"
        files = {"file": ("prices.csv", BytesIO(file_content), "text/csv")}
        data = {"vendor": "acme"}

        response = client.post("/ingest/prices", files=files, data=data)

        assert response.status_code == 500
        assert "Database connection failed" in response.json()["detail"]

        # Verify alerts were sent
        mock_email_notifier.send_ingestion_failure_alert.assert_called_once()
        mock_slack_notifier.post_ingestion_failure_alert.assert_called_once()

        # Verify cleanup
        mock_path.unlink.assert_called_once()


# Integration test
def test_router_has_correct_routes():
    """Test that ingestion router has all expected routes."""
    routes = [route.path for route in ingestion.router.routes]

    assert "/ingest/history" in routes
    assert "/ingest" in routes
    assert "/ingest/schedules" in routes
    assert "/ingest/prices" in routes
    assert "/api/ingest/history" in routes

    # Should have 5 routes total
    assert len(ingestion.router.routes) == 5


def test_router_has_ingestion_tag():
    """Test that router is tagged correctly."""
    assert "ingestion" in ingestion.router.tags
