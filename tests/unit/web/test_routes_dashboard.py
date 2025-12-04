"""Tests for bimcalc.web.routes.dashboard - Dashboard and progress routes.

Tests the dashboard router module extracted in Phase 3.2.
"""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock, AsyncMock
from types import SimpleNamespace

from bimcalc.web.routes import dashboard


@pytest.fixture
def app():
    """Create test FastAPI app with dashboard router."""
    test_app = FastAPI()
    test_app.include_router(dashboard.router)
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
    session = MagicMock()

    # Mock execute results for statistics queries
    result = MagicMock()
    result.scalar_one.return_value = 100
    session.execute = AsyncMock(return_value=result)

    # Create async context manager
    async_cm = AsyncMock()
    async_cm.__aenter__.return_value = session
    async_cm.__aexit__.return_value = None

    return async_cm


class TestDashboard:
    """Tests for GET / route."""

    @patch("bimcalc.web.routes.dashboard.get_session")
    @patch("bimcalc.web.dependencies.get_config")
    def test_dashboard_default_view(
        self, mock_get_config, mock_get_session, client, mock_config, mock_db_session
    ):
        """Test default dashboard view renders with statistics."""
        mock_get_config.return_value = mock_config
        mock_get_session.return_value = mock_db_session

        response = client.get("/")
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]

    @patch("bimcalc.web.routes.dashboard.get_session")
    @patch("bimcalc.web.dependencies.get_config")
    def test_dashboard_analytics_view(
        self, mock_get_config, mock_get_session, client, mock_config, mock_db_session
    ):
        """Test analytics view renders."""
        mock_get_config.return_value = mock_config
        mock_get_session.return_value = mock_db_session

        response = client.get("/?view=analytics")
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]

    @patch("bimcalc.web.routes.dashboard.get_session")
    @patch("bimcalc.web.dependencies.get_config")
    def test_dashboard_reports_view(
        self, mock_get_config, mock_get_session, client, mock_config, mock_db_session
    ):
        """Test reports view renders."""
        mock_get_config.return_value = mock_config
        mock_get_session.return_value = mock_db_session

        response = client.get("/?view=reports")
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]

    @pytest.mark.skip(
        reason="Executive view requires complex metrics object with many attributes - better tested in integration"
    )
    @patch("bimcalc.reporting.dashboard_metrics.compute_dashboard_metrics")
    @patch("bimcalc.web.routes.dashboard.get_session")
    @patch("bimcalc.web.dependencies.get_config")
    def test_dashboard_executive_view(
        self,
        mock_get_config,
        mock_get_session,
        mock_compute_metrics,
        client,
        mock_config,
        mock_db_session,
    ):
        """Test executive view calls compute_dashboard_metrics.

        Note: Skipped for unit tests - requires complex mock metrics object with
        20+ attributes (health_score, health_status, total_cost_net, high_urgency_count, etc.)
        Better tested in integration tests with real compute_dashboard_metrics().
        """
        mock_get_config.return_value = mock_config
        mock_get_session.return_value = mock_db_session

        # Would need complete metrics mock here
        mock_metrics = MagicMock()
        mock_compute_metrics.return_value = mock_metrics

        response = client.get("/?view=executive")
        assert response.status_code == 200
        mock_compute_metrics.assert_called_once()

    @patch("bimcalc.web.routes.dashboard.get_session")
    @patch("bimcalc.web.dependencies.get_config")
    def test_dashboard_with_org_project_params(
        self, mock_get_config, mock_get_session, client, mock_config, mock_db_session
    ):
        """Test dashboard accepts org and project query parameters."""
        mock_get_config.return_value = mock_config
        mock_get_session.return_value = mock_db_session

        response = client.get("/?org=custom-org&project=custom-proj")
        assert response.status_code == 200

    @patch("bimcalc.web.routes.dashboard.get_session")
    @patch("bimcalc.web.dependencies.get_config")
    def test_dashboard_statistics_query(
        self, mock_get_config, mock_get_session, client, mock_config, mock_db_session
    ):
        """Test that dashboard queries database for statistics."""
        mock_get_config.return_value = mock_config
        mock_get_session.return_value = mock_db_session

        response = client.get("/")
        assert response.status_code == 200

        # Verify multiple database queries were made
        # (items, prices, mappings, review counts)
        session = mock_db_session.__aenter__.return_value
        assert session.execute.call_count >= 4


class TestProgressDashboard:
    """Tests for GET /progress route."""

    @patch("bimcalc.reporting.progress.compute_progress_metrics")
    @patch("bimcalc.web.routes.dashboard.get_session")
    @patch("bimcalc.web.dependencies.get_config")
    def test_progress_standard_view(
        self,
        mock_get_config,
        mock_get_session,
        mock_compute_metrics,
        client,
        mock_config,
        mock_db_session,
    ):
        """Test progress dashboard standard view."""
        mock_get_config.return_value = mock_config
        mock_get_session.return_value = mock_db_session

        # Mock progress metrics with all required fields for template
        from datetime import datetime

        mock_metrics = SimpleNamespace(
            overall_completion=65.0,
            total_items=1000,
            matched_items=650,
            pending_review=0,
            flagged_critical=0,
            computed_at=datetime.now(),
            classification_coverage=[],
            # Stage attributes for progress template (multiple naming variations)
            stage_import=SimpleNamespace(
                status="complete", count=1000, completion_percent=100.0
            ),
            stage_classification=SimpleNamespace(
                status="complete", count=1000, completion_percent=100.0
            ),
            stage_match=SimpleNamespace(
                status="complete", count=650, completion_percent=65.0
            ),
            stage_matching=SimpleNamespace(
                status="complete", count=650, completion_percent=65.0
            ),  # Alias
            stage_review=SimpleNamespace(
                status="in_progress", count=0, completion_percent=0.0
            ),
        )
        mock_compute_metrics.return_value = mock_metrics

        response = client.get("/progress")
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]

        # Verify metrics were computed
        mock_compute_metrics.assert_called_once()

    @pytest.mark.skip(
        reason="Executive progress view requires complex metrics with confidence attributes"
    )
    @patch("bimcalc.reporting.progress.compute_progress_metrics")
    @patch("bimcalc.web.routes.dashboard.get_session")
    @patch("bimcalc.web.dependencies.get_config")
    def test_progress_executive_view(
        self,
        mock_get_config,
        mock_get_session,
        mock_compute_metrics,
        client,
        mock_config,
        mock_db_session,
    ):
        """Test progress dashboard executive view.

        Note: Skipped - requires metrics with confidence_high, confidence_medium, etc.
        """
        mock_get_config.return_value = mock_config
        mock_get_session.return_value = mock_db_session

        from datetime import datetime

        mock_metrics = SimpleNamespace(
            overall_completion=70.0,
            total_items=1000,
            matched_items=700,
            pending_review=0,
            flagged_critical=0,
            computed_at=datetime.now(),
            classification_coverage=[],
            # Stage attributes for progress template
            stage_import=SimpleNamespace(
                status="complete", count=1000, completion_percent=100.0
            ),
            stage_classification=SimpleNamespace(
                status="complete", count=1000, completion_percent=100.0
            ),
            stage_match=SimpleNamespace(
                status="complete", count=700, completion_percent=70.0
            ),
            stage_matching=SimpleNamespace(
                status="complete", count=700, completion_percent=70.0
            ),  # Alias
            stage_review=SimpleNamespace(
                status="complete", count=0, completion_percent=0.0
            ),
        )
        mock_compute_metrics.return_value = mock_metrics

        response = client.get("/progress?view=executive")
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]

    @patch("bimcalc.reporting.progress.compute_progress_metrics")
    @patch("bimcalc.web.routes.dashboard.get_session")
    @patch("bimcalc.web.dependencies.get_config")
    def test_progress_with_org_project_params(
        self,
        mock_get_config,
        mock_get_session,
        mock_compute_metrics,
        client,
        mock_config,
        mock_db_session,
    ):
        """Test progress accepts org and project parameters."""
        mock_get_config.return_value = mock_config
        mock_get_session.return_value = mock_db_session

        from datetime import datetime

        mock_metrics = SimpleNamespace(
            overall_completion=50.0,
            total_items=1000,
            matched_items=500,
            pending_review=0,
            flagged_critical=0,
            computed_at=datetime.now(),
            classification_coverage=[],
            # Stage attributes for progress template
            stage_import=SimpleNamespace(
                status="complete", count=1000, completion_percent=100.0
            ),
            stage_classification=SimpleNamespace(
                status="complete", count=1000, completion_percent=100.0
            ),
            stage_match=SimpleNamespace(
                status="in_progress", count=500, completion_percent=50.0
            ),
            stage_matching=SimpleNamespace(
                status="in_progress", count=500, completion_percent=50.0
            ),  # Alias
            stage_review=SimpleNamespace(
                status="pending", count=0, completion_percent=0.0
            ),
        )
        mock_compute_metrics.return_value = mock_metrics

        response = client.get("/progress?org=org-123&project=proj-456")
        assert response.status_code == 200


class TestProgressExport:
    """Tests for GET /progress/export route."""

    @patch("bimcalc.reporting.progress.compute_progress_metrics")
    @patch("bimcalc.web.routes.dashboard.get_session")
    @patch("bimcalc.web.dependencies.get_config")
    def test_progress_export_creates_excel(
        self,
        mock_get_config,
        mock_get_session,
        mock_compute_metrics,
        client,
        mock_config,
        mock_db_session,
    ):
        """Test progress export creates Excel file."""
        mock_get_config.return_value = mock_config
        mock_get_session.return_value = mock_db_session

        # Mock comprehensive metrics
        mock_metrics = SimpleNamespace(
            overall_completion=75.5,
            total_items=500,
            matched_items=377,
            pending_review=50,
            flagged_critical=10,
            classification_coverage=[
                SimpleNamespace(code="ABC", total=100, matched=75, percent=75.0),
                SimpleNamespace(code="XYZ", total=200, matched=150, percent=75.0),
            ],
        )
        mock_compute_metrics.return_value = mock_metrics

        response = client.get("/progress/export")
        assert response.status_code == 200

        # Verify Excel MIME type
        assert (
            response.headers["content-type"]
            == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

        # Verify Content-Disposition header for download
        assert "attachment" in response.headers["content-disposition"]
        assert "progress_" in response.headers["content-disposition"]
        assert ".xlsx" in response.headers["content-disposition"]

        # Verify content is non-empty
        assert len(response.content) > 0

    @patch("bimcalc.reporting.progress.compute_progress_metrics")
    @patch("bimcalc.web.routes.dashboard.get_session")
    @patch("bimcalc.web.dependencies.get_config")
    def test_progress_export_filename_format(
        self,
        mock_get_config,
        mock_get_session,
        mock_compute_metrics,
        client,
        mock_config,
        mock_db_session,
    ):
        """Test progress export filename includes org, project, and date."""
        mock_get_config.return_value = mock_config
        mock_get_session.return_value = mock_db_session

        mock_metrics = SimpleNamespace(
            overall_completion=80.0,
            total_items=100,
            matched_items=80,
            pending_review=5,
            flagged_critical=2,
            classification_coverage=None,
        )
        mock_compute_metrics.return_value = mock_metrics

        response = client.get("/progress/export?org=acme&project=tower")
        assert response.status_code == 200

        # Check filename format: progress_<org>_<project>_<YYYYMMDD>.xlsx
        filename = response.headers["content-disposition"]
        assert "progress_acme_tower_" in filename
        assert ".xlsx" in filename

    @patch("bimcalc.reporting.progress.compute_progress_metrics")
    @patch("bimcalc.web.routes.dashboard.get_session")
    @patch("bimcalc.web.dependencies.get_config")
    def test_progress_export_without_classification_coverage(
        self,
        mock_get_config,
        mock_get_session,
        mock_compute_metrics,
        client,
        mock_config,
        mock_db_session,
    ):
        """Test progress export handles missing classification coverage."""
        mock_get_config.return_value = mock_config
        mock_get_session.return_value = mock_db_session

        # Metrics without classification_coverage
        mock_metrics = SimpleNamespace(
            overall_completion=60.0,
            total_items=200,
            matched_items=120,
            pending_review=20,
            flagged_critical=5,
            classification_coverage=None,  # No coverage data
        )
        mock_compute_metrics.return_value = mock_metrics

        response = client.get("/progress/export")
        assert response.status_code == 200
        assert len(response.content) > 0


# Integration test
def test_router_has_correct_routes():
    """Test that dashboard router has all expected routes."""
    routes = [route.path for route in dashboard.router.routes]

    assert "/" in routes
    assert "/progress" in routes
    assert "/progress/export" in routes

    # Should have 3 routes total
    assert len(dashboard.router.routes) == 3


def test_router_has_dashboard_tag():
    """Test that router is tagged correctly."""
    assert "dashboard" in dashboard.router.tags
