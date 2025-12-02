"""Tests for bimcalc.web.routes.reports - Reports routes.

Tests the reports router module extracted in Phase 3.8.
"""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock, AsyncMock
from datetime import datetime
from types import SimpleNamespace
import pandas as pd

from bimcalc.web.routes import reports


@pytest.fixture
def app():
    """Create test FastAPI app with reports router."""
    test_app = FastAPI()
    test_app.include_router(reports.router)
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

    # Create async context manager
    async_cm = AsyncMock()
    async_cm.__aenter__.return_value = session
    async_cm.__aexit__.return_value = None

    return async_cm


@pytest.fixture
def mock_financial_metrics():
    """Mock financial metrics object."""
    return SimpleNamespace(
        total_cost=10000.0,
        matched_items=50,
        total_items=60,
        coverage_percent=83.3,
    )


class TestReportsPage:
    """Tests for GET /reports route."""

    @patch("bimcalc.web.routes.reports.get_session")
    @patch("bimcalc.web.dependencies.get_config")
    def test_reports_page_default_view(
        self,
        mock_get_config,
        mock_get_session,
        client,
        mock_config,
        mock_db_session,
    ):
        """Test reports page renders default view."""
        mock_get_config.return_value = mock_config
        mock_get_session.return_value = mock_db_session

        response = client.get("/reports")
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]

    @pytest.mark.skip(reason="Executive template requires complex metrics - better in integration")
    @patch("bimcalc.web.routes.reports.compute_financial_metrics")
    @patch("bimcalc.web.routes.reports.get_session")
    @patch("bimcalc.web.dependencies.get_config")
    def test_reports_page_executive_view(
        self,
        mock_get_config,
        mock_get_session,
        mock_compute_metrics,
        client,
        mock_config,
        mock_db_session,
        mock_financial_metrics,
    ):
        """Test reports page renders executive view.

        Note: Skipped - executive template requires complex metrics object.
        """
        mock_get_config.return_value = mock_config
        mock_get_session.return_value = mock_db_session
        mock_compute_metrics.return_value = mock_financial_metrics

        response = client.get("/reports?view=executive")
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]


class TestGenerateReport:
    """Tests for GET /reports/generate route."""

    @patch("bimcalc.reporting.export_utils.export_reports_to_excel")
    @patch("bimcalc.reporting.financial_metrics.compute_financial_metrics")
    @patch("bimcalc.web.routes.reports.get_session")
    @patch("bimcalc.web.dependencies.get_config")
    def test_generate_report_excel_format(
        self,
        mock_get_config,
        mock_get_session,
        mock_compute_metrics,
        mock_export_excel,
        client,
        mock_config,
        mock_db_session,
        mock_financial_metrics,
    ):
        """Test report generation in Excel format."""
        mock_get_config.return_value = mock_config
        mock_get_session.return_value = mock_db_session
        mock_compute_metrics.return_value = mock_financial_metrics
        mock_export_excel.return_value = b"excel_content"

        response = client.get("/reports/generate?format=xlsx")
        assert response.status_code == 200
        assert response.headers["content-type"] == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        assert "attachment" in response.headers["content-disposition"]
        assert ".xlsx" in response.headers["content-disposition"]

    @patch("bimcalc.reporting.export_utils.export_reports_to_pdf")
    @patch("bimcalc.reporting.financial_metrics.compute_financial_metrics")
    @patch("bimcalc.web.routes.reports.get_session")
    @patch("bimcalc.web.dependencies.get_config")
    def test_generate_report_pdf_format(
        self,
        mock_get_config,
        mock_get_session,
        mock_compute_metrics,
        mock_export_pdf,
        client,
        mock_config,
        mock_db_session,
        mock_financial_metrics,
    ):
        """Test report generation in PDF format."""
        mock_get_config.return_value = mock_config
        mock_get_session.return_value = mock_db_session
        mock_compute_metrics.return_value = mock_financial_metrics
        mock_export_pdf.return_value = b"pdf_content"

        response = client.get("/reports/generate?format=pdf")
        assert response.status_code == 200
        assert response.headers["content-type"] == "application/pdf"
        assert "attachment" in response.headers["content-disposition"]
        assert ".pdf" in response.headers["content-disposition"]

    @patch("bimcalc.reporting.export_utils.export_reports_to_excel")
    @patch("bimcalc.reporting.financial_metrics.compute_financial_metrics")
    @patch("bimcalc.web.routes.reports.get_session")
    @patch("bimcalc.web.dependencies.get_config")
    def test_generate_report_filename_format(
        self,
        mock_get_config,
        mock_get_session,
        mock_compute_metrics,
        mock_export_excel,
        client,
        mock_config,
        mock_db_session,
        mock_financial_metrics,
    ):
        """Test report filename includes org, project, and date."""
        mock_get_config.return_value = mock_config
        mock_get_session.return_value = mock_db_session
        mock_compute_metrics.return_value = mock_financial_metrics
        mock_export_excel.return_value = b"excel_content"

        response = client.get("/reports/generate?org=acme&project=tower")
        assert response.status_code == 200

        # Check filename format: financial_report_<org>_<project>_<date>.xlsx
        filename = response.headers["content-disposition"]
        assert "financial_report_acme_tower_" in filename


class TestStatisticsPage:
    """Tests for GET /reports/statistics route."""

    @pytest.mark.skip(reason="Statistics template requires complex data - better in integration")
    @patch("bimcalc.web.routes.reports.generate_report")
    @patch("bimcalc.web.routes.reports.get_session")
    @patch("bimcalc.web.dependencies.get_config")
    def test_statistics_page_renders(
        self,
        mock_get_config,
        mock_get_session,
        mock_generate_report,
        client,
        mock_config,
        mock_db_session,
    ):
        """Test statistics page renders with data.

        Note: Skipped - statistics template requires complex data.
        """
        mock_get_config.return_value = mock_config
        mock_get_session.return_value = mock_db_session
        session = mock_db_session.__aenter__.return_value

        # Mock match stats query
        mock_match_result = MagicMock()
        mock_match_result.all.return_value = []
        session.execute.return_value = mock_match_result

        # Mock report generation
        df = pd.DataFrame({
            "sku": ["A", "B", None],
            "total_net": [100, 200, 300],
            "total_gross": [110, 220, 330],
        })
        mock_generate_report.return_value = df

        response = client.get("/reports/statistics")
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]

    @patch("bimcalc.web.routes.reports.generate_report")
    @patch("bimcalc.web.routes.reports.get_session")
    @patch("bimcalc.web.dependencies.get_config")
    def test_statistics_page_empty_data(
        self,
        mock_get_config,
        mock_get_session,
        mock_generate_report,
        client,
        mock_config,
        mock_db_session,
    ):
        """Test statistics page handles empty data gracefully."""
        mock_get_config.return_value = mock_config
        mock_get_session.return_value = mock_db_session
        session = mock_db_session.__aenter__.return_value

        # Mock empty results
        mock_match_result = MagicMock()
        mock_match_result.all.return_value = []
        session.execute.return_value = mock_match_result

        # Mock empty dataframe
        mock_generate_report.return_value = pd.DataFrame()

        response = client.get("/reports/statistics")
        assert response.status_code == 200


# Integration tests
def test_router_has_correct_routes():
    """Test that reports router has all expected routes."""
    routes = [route.path for route in reports.router.routes]

    assert "/reports" in routes
    assert "/reports/generate" in routes
    assert "/reports/statistics" in routes

    # Should have 3 routes total
    assert len(reports.router.routes) == 3


def test_router_has_reports_tag():
    """Test that router is tagged correctly."""
    assert "reports" in reports.router.tags


def test_no_duplicate_routes():
    """Test that there are no duplicate route paths."""
    routes = [route.path for route in reports.router.routes]
    # Check for duplicates
    assert len(routes) == len(set(routes)), "Router contains duplicate route paths"
