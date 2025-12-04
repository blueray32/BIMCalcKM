"""Tests for bimcalc.web.routes.price_scout - Crail4 integration routes.

Tests the Crail4 router module extracted in Phase 3.13.
"""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock, AsyncMock

from bimcalc.web.routes import price_scout


from bimcalc.web.auth import require_auth


@pytest.fixture(autouse=True)
def mock_arq():
    """Mock arq module."""
    mock_arq_mod = MagicMock()
    mock_arq_jobs = MagicMock()
    mock_arq_conn = MagicMock()

    with patch.dict(
        "sys.modules",
        {
            "arq": mock_arq_mod,
            "arq.jobs": mock_arq_jobs,
            "arq.connections": mock_arq_conn,
        },
    ):
        yield


@pytest.fixture
def app():
    """Create test FastAPI app with crail4 router."""
    test_app = FastAPI()
    test_app.include_router(price_scout.router)
    test_app.dependency_overrides[require_auth] = lambda: {"username": "test-user"}
    return test_app


@pytest.fixture
def client(app):
    """Create test client."""
    return TestClient(app)


@pytest.fixture
def mock_db_session():
    """Mock database session with async context manager."""
    session = AsyncMock()
    session.execute = AsyncMock()
    session.add = MagicMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()

    # Create async context manager
    async_cm = AsyncMock()
    async_cm.__aenter__.return_value = session
    async_cm.__aexit__.return_value = None

    return async_cm


class TestCrail4ConfigPage:
    """Tests for GET /crail4-config route."""

    @pytest.mark.skip(
        reason="Crail4 config template requires complex context - better in integration"
    )
    @patch("bimcalc.web.routes.price_scout.get_session")
    @patch("bimcalc.web.routes.price_scout.get_org_project")
    def test_config_page_renders(
        self,
        mock_get_org_project,
        mock_get_session,
        client,
        mock_db_session,
    ):
        """Test Crail4 configuration page renders.

        Note: Skipped - crail4 config template requires complex context.
        """
        mock_get_org_project.return_value = ("test-org", "test-project")
        mock_get_session.return_value = mock_db_session

        response = client.get("/price-scout")
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]


class TestSaveCrail4Config:
    """Tests for POST /crail4-config/save route."""

    @patch("bimcalc.web.routes.price_scout.Path")
    @patch.dict("os.environ", {}, clear=True)
    def test_save_config_creates_new_env_file(
        self,
        mock_path_class,
        client,
    ):
        """Test saving configuration creates new .env file."""
        # Mock Path to simulate non-existent .env
        mock_env_path = MagicMock()
        mock_env_path.exists.return_value = False
        mock_path_class.return_value = mock_env_path

        response = client.post(
            "/price-scout/save",
            data={
                "api_key": "test-key-123",
                "source_url": "https://test.com",
                "base_url": "https://api.test.com",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"

    @patch("bimcalc.web.routes.price_scout.Path")
    @patch.dict("os.environ", {}, clear=True)
    def test_save_config_updates_existing_env_file(
        self,
        mock_path_class,
        client,
    ):
        """Test saving configuration updates existing .env file."""
        # Mock Path with existing .env content
        existing_content = "EXISTING_VAR=value\nCRAIL4_API_KEY=old-key\n"
        mock_env_path = MagicMock()
        mock_env_path.exists.return_value = True
        mock_env_path.read_text.return_value = existing_content
        mock_path_class.return_value = mock_env_path

        response = client.post(
            "/price-scout/save",
            data={
                "api_key": "new-key-456",
                "source_url": "https://new.com",
                "base_url": "https://api.new.com",
            },
        )

        assert response.status_code == 200
        # Verify write_text was called
        assert mock_env_path.write_text.called


class TestTestCrail4Connection:
    """Tests for POST /crail4-config/test route."""

    @patch("bimcalc.intelligence.price_scout.SmartPriceScout")
    @patch.dict(
        "os.environ",
        {"CRAIL4_API_KEY": "", "OPENAI_API_KEY": "", "PRICE_SCOUT_API_KEY": ""},
    )
    def test_test_connection_missing_api_key(self, mock_scout_class, client):
        """Test connection test fails when API key not configured."""
        mock_scout_class.side_effect = ValueError("OPENAI_API_KEY is required")

        response = client.post("/price-scout/test")
        # Expect 500 if API key is missing and validation is strict
        assert response.status_code == 500
        data = response.json()
        assert data["status"] == "error"

    @patch("bimcalc.intelligence.price_scout.SmartPriceScout")
    @patch.dict("os.environ", {"CRAIL4_API_KEY": "test-key"})
    def test_test_connection_success(self, mock_scout_class, client):
        """Test successful connection test."""
        mock_scout = AsyncMock()
        mock_scout.__aenter__.return_value = mock_scout
        mock_scout.__aexit__.return_value = None
        mock_scout_class.return_value = mock_scout

        response = client.post("/price-scout/test")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"

    @patch("bimcalc.intelligence.price_scout.SmartPriceScout")
    @patch.dict("os.environ", {"CRAIL4_API_KEY": "test-key"})
    def test_test_connection_failure(self, mock_scout_class, client):
        """Test connection test handles API errors."""
        mock_scout_class.side_effect = Exception("API error")

        response = client.post("/price-scout/test")
        assert response.status_code == 500
        data = response.json()
        assert data["status"] == "error"
        assert "failed" in data["message"].lower()


class TestTriggerCrail4Sync:
    """Tests for POST /crail4-config/sync route."""

    @patch("bimcalc.core.queue.get_queue")
    @patch("bimcalc.web.routes.price_scout.get_config")
    def test_trigger_sync_success(self, mock_get_config, mock_get_queue, client):
        """Test triggering sync job successfully."""
        # Mock config
        mock_config = MagicMock()
        mock_config.org_id = "test-org"
        mock_get_config.return_value = mock_config

        # Mock queue
        mock_redis = AsyncMock()
        mock_job = MagicMock()
        mock_job.job_id = "job-123"
        mock_redis.enqueue_job = AsyncMock(return_value=mock_job)
        mock_get_queue.return_value = mock_redis

        response = client.post("/price-scout/sync", data={"full_sync": "false"})
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]
        assert "job-123" in response.text

    @patch("bimcalc.core.queue.get_queue")
    @patch("bimcalc.web.routes.price_scout.get_config")
    def test_trigger_sync_error(self, mock_get_config, mock_get_queue, client):
        """Test sync trigger handles errors."""
        mock_config = MagicMock()
        mock_config.org_id = "test-org"
        mock_get_config.return_value = mock_config

        # Mock queue error
        mock_get_queue.side_effect = Exception("Queue error")

        response = client.post("/price-scout/sync", data={"full_sync": "false"})
        assert response.status_code == 200
        assert "error" in response.text.lower()


class TestGetSyncStatus:
    """Tests for GET /crail4-config/status/{job_id} route."""

    @patch("bimcalc.core.queue.get_queue")
    @patch("arq.jobs.Job")
    def test_get_status_complete(self, mock_job_class, mock_get_queue, client):
        """Test getting status for completed job."""
        mock_redis = AsyncMock()
        mock_get_queue.return_value = mock_redis

        mock_job = MagicMock()
        mock_job.status = AsyncMock(return_value="complete")
        mock_job.result = AsyncMock(
            return_value={"items_loaded": 100, "items_fetched": 120}
        )
        mock_job_class.return_value = mock_job

        response = client.get("/price-scout/crail4-config/status/job-123")
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]
        assert "Sync Complete" in response.text
        assert "100" in response.text

    @patch("bimcalc.core.queue.get_queue")
    @patch("arq.jobs.Job")
    def test_get_status_in_progress(self, mock_job_class, mock_get_queue, client):
        """Test getting status for running job."""
        mock_redis = AsyncMock()
        mock_get_queue.return_value = mock_redis

        mock_job = MagicMock()
        mock_job.status = AsyncMock(return_value="in_progress")
        mock_job_class.return_value = mock_job

        response = client.get("/price-scout/crail4-config/status/job-123")
        assert response.status_code == 200
        assert "Syncing" in response.text

    @patch("bimcalc.core.queue.get_queue")
    @patch("arq.jobs.Job")
    def test_get_status_failed(self, mock_job_class, mock_get_queue, client):
        """Test getting status for failed job."""
        mock_redis = AsyncMock()
        mock_get_queue.return_value = mock_redis

        mock_job = MagicMock()
        mock_job.status = AsyncMock(return_value="failed")
        mock_job_class.return_value = mock_job

        response = client.get("/price-scout/crail4-config/status/job-123")
        assert response.status_code == 200
        assert "Failed" in response.text


class TestAddClassificationMapping:
    """Tests for POST /crail4-config/mappings/add route."""

    @patch("bimcalc.web.routes.price_scout.get_session")
    @patch("bimcalc.web.routes.price_scout.get_config")
    def test_add_mapping_success(
        self, mock_get_config, mock_get_session, client, mock_db_session
    ):
        """Test adding new classification mapping."""
        mock_config = MagicMock()
        mock_config.org_id = "test-org"
        mock_get_config.return_value = mock_config

        mock_get_session.return_value = mock_db_session
        session = mock_db_session.__aenter__.return_value

        # Mock no existing mapping
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        session.execute.return_value = mock_result

        response = client.post(
            "/price-scout/crail4-config/mappings/add",
            data={
                "source_scheme": "Vendor",
                "source_code": "V123",
                "target_scheme": "UniClass2015",
                "target_code": "Ss_20_10_20",
                "confidence": "0.95",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert session.add.called
        assert session.commit.called

    @patch("bimcalc.web.routes.price_scout.get_session")
    @patch("bimcalc.web.routes.price_scout.get_config")
    def test_add_mapping_duplicate(
        self, mock_get_config, mock_get_session, client, mock_db_session
    ):
        """Test adding duplicate mapping fails."""
        mock_config = MagicMock()
        mock_config.org_id = "test-org"
        mock_get_config.return_value = mock_config

        mock_get_session.return_value = mock_db_session
        session = mock_db_session.__aenter__.return_value

        # Mock existing mapping
        existing_mapping = MagicMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = existing_mapping
        session.execute.return_value = mock_result

        response = client.post(
            "/price-scout/crail4-config/mappings/add",
            data={
                "source_scheme": "Vendor",
                "source_code": "V123",
                "target_scheme": "UniClass2015",
                "target_code": "Ss_20_10_20",
            },
        )

        assert response.status_code == 400
        data = response.json()
        assert data["status"] == "error"
        assert "already exists" in data["message"].lower()


# Integration tests
def test_router_has_correct_routes():
    """Test that crail4 router has all expected routes."""
    routes = [route.path for route in price_scout.router.routes]

    assert "/price-scout" in routes
    assert "/price-scout/save" in routes
    assert "/price-scout/test" in routes
    assert "/price-scout/sync" in routes
    assert "/price-scout/crail4-config/status/{job_id}" in routes
    assert "/price-scout/crail4-config/mappings/add" in routes

    # Should have 6 routes total
    assert len(price_scout.router.routes) >= 6


def test_router_has_crail4_tag():
    """Test that router is tagged correctly."""
    assert "price-scout" in price_scout.router.tags
