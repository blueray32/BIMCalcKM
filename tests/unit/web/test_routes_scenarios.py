"""Tests for bimcalc.web.routes.scenarios - Scenario planning routes.

Tests the scenarios router module extracted in Phase 3.12.
"""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock, AsyncMock
from io import BytesIO

from bimcalc.web.routes import scenarios


@pytest.fixture
def app():
    """Create test FastAPI app with scenarios router."""
    test_app = FastAPI()
    test_app.include_router(scenarios.router)
    return test_app


@pytest.fixture
def client(app):
    """Create test client."""
    return TestClient(app)


@pytest.fixture
def mock_scenario_result():
    """Mock vendor scenario result."""
    scenario = MagicMock()
    scenario.vendor_name = "TEST-VENDOR"
    scenario.total_cost = 10000.00
    scenario.coverage_percent = 85.5
    scenario.matched_items_count = 42
    scenario.missing_items_count = 8
    scenario.matched_items = []
    scenario.missing_items = []
    return scenario


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


class TestScenarioPage:
    """Tests for GET /scenarios route."""

    @pytest.mark.skip(reason="Scenario template requires complex context - better in integration")
    @patch("bimcalc.web.routes.scenarios.get_org_project")
    def test_scenario_page_renders(
        self,
        mock_get_org_project,
        client,
    ):
        """Test scenario planning dashboard renders.

        Note: Skipped - scenario template requires complex context.
        """
        mock_get_org_project.return_value = ("test-org", "test-project")

        response = client.get("/scenarios")
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]

    @patch("bimcalc.web.routes.scenarios.get_org_project")
    def test_scenario_page_with_params(
        self,
        mock_get_org_project,
        client,
    ):
        """Test scenario page with org and project parameters."""
        mock_get_org_project.return_value = ("custom-org", "custom-project")

        response = client.get("/scenarios?org=custom-org&project=custom-project")
        assert response.status_code == 200


class TestCompareScenarios:
    """Tests for GET /api/scenarios/compare route."""

    @patch("bimcalc.web.routes.scenarios.get_session")
    @patch("bimcalc.reporting.scenario.get_available_vendors")
    @patch("bimcalc.reporting.scenario.compute_vendor_scenario")
    def test_compare_scenarios_with_vendors(
        self,
        mock_compute_scenario,
        mock_get_vendors,
        mock_get_session,
        client,
        mock_db_session,
        mock_scenario_result,
    ):
        """Test scenario comparison with specified vendors."""
        mock_get_session.return_value = mock_db_session
        mock_get_vendors.return_value = ["VENDOR1", "VENDOR2", "VENDOR3"]
        mock_compute_scenario.return_value = mock_scenario_result

        response = client.get("/api/scenarios/compare?org=test-org&project=test-project&vendors=VENDOR1&vendors=VENDOR2")
        assert response.status_code == 200

        data = response.json()
        assert "scenarios" in data
        assert "all_vendors" in data
        assert len(data["scenarios"]) == 2  # 2 vendors requested
        assert data["scenarios"][0]["vendor"] == "TEST-VENDOR"
        assert data["scenarios"][0]["total_cost"] == 10000.00

    @patch("bimcalc.web.routes.scenarios.get_session")
    @patch("bimcalc.reporting.scenario.get_available_vendors")
    @patch("bimcalc.reporting.scenario.compute_vendor_scenario")
    def test_compare_scenarios_default_top_3(
        self,
        mock_compute_scenario,
        mock_get_vendors,
        mock_get_session,
        client,
        mock_db_session,
        mock_scenario_result,
    ):
        """Test scenario comparison defaults to top 3 vendors."""
        mock_get_session.return_value = mock_db_session
        mock_get_vendors.return_value = ["VENDOR1", "VENDOR2", "VENDOR3", "VENDOR4"]
        mock_compute_scenario.return_value = mock_scenario_result

        response = client.get("/api/scenarios/compare?org=test-org&project=test-project")
        assert response.status_code == 200

        data = response.json()
        assert "scenarios" in data
        # Should compare top 3 vendors
        assert len(data["scenarios"]) == 3

    @patch("bimcalc.web.routes.scenarios.get_session")
    @patch("bimcalc.reporting.scenario.get_available_vendors")
    @patch("bimcalc.reporting.scenario.compute_vendor_scenario")
    def test_compare_scenarios_empty_vendors(
        self,
        mock_compute_scenario,
        mock_get_vendors,
        mock_get_session,
        client,
        mock_db_session,
    ):
        """Test scenario comparison with no available vendors."""
        mock_get_session.return_value = mock_db_session
        mock_get_vendors.return_value = []

        response = client.get("/api/scenarios/compare?org=test-org&project=test-project")
        assert response.status_code == 200

        data = response.json()
        assert data["scenarios"] == []
        assert data["all_vendors"] == []


class TestExportScenarios:
    """Tests for GET /api/scenarios/export route."""

    @patch("bimcalc.web.routes.scenarios.get_session")
    @patch("bimcalc.reporting.scenario.get_available_vendors")
    @patch("bimcalc.reporting.scenario.compute_vendor_scenario")
    @patch("bimcalc.reporting.export.export_scenario_to_excel")
    def test_export_scenarios_success(
        self,
        mock_export_excel,
        mock_compute_scenario,
        mock_get_vendors,
        mock_get_session,
        client,
        mock_db_session,
        mock_scenario_result,
    ):
        """Test scenario export to Excel."""
        mock_get_session.return_value = mock_db_session
        mock_get_vendors.return_value = ["VENDOR1", "VENDOR2"]

        # Mock scenario result with matched items
        scenario = mock_scenario_result
        matched_item = MagicMock()
        matched_item.item.family = "Pipes"
        matched_item.item.type_name = "Copper"
        matched_item.item.quantity = 100
        matched_item.item.unit = "M"
        matched_item.price.unit_price = 10.50
        matched_item.line_total = 1050.00
        scenario.matched_items = [matched_item]
        mock_compute_scenario.return_value = scenario

        # Mock Excel file output
        excel_buffer = BytesIO(b"fake excel data")
        mock_export_excel.return_value = excel_buffer

        response = client.get("/api/scenarios/export?org=test-org&project=test-project&vendors=VENDOR1")
        assert response.status_code == 200
        assert "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" in response.headers["content-type"]
        assert "attachment" in response.headers["content-disposition"]
        assert "scenario_comparison_test-org_test-project" in response.headers["content-disposition"]

    @patch("bimcalc.web.routes.scenarios.get_session")
    @patch("bimcalc.reporting.scenario.get_available_vendors")
    @patch("bimcalc.reporting.scenario.compute_vendor_scenario")
    @patch("bimcalc.reporting.export.export_scenario_to_excel")
    def test_export_scenarios_default_top_3(
        self,
        mock_export_excel,
        mock_compute_scenario,
        mock_get_vendors,
        mock_get_session,
        client,
        mock_db_session,
        mock_scenario_result,
    ):
        """Test scenario export defaults to top 3 vendors."""
        mock_get_session.return_value = mock_db_session
        mock_get_vendors.return_value = ["VENDOR1", "VENDOR2", "VENDOR3", "VENDOR4"]
        mock_compute_scenario.return_value = mock_scenario_result

        # Mock Excel file output
        excel_buffer = BytesIO(b"fake excel data")
        mock_export_excel.return_value = excel_buffer

        response = client.get("/api/scenarios/export?org=test-org&project=test-project")
        assert response.status_code == 200

        # Verify compute_vendor_scenario called 3 times (top 3)
        assert mock_compute_scenario.call_count == 3

    @patch("bimcalc.web.routes.scenarios.get_session")
    @patch("bimcalc.reporting.scenario.get_available_vendors")
    @patch("bimcalc.reporting.scenario.compute_vendor_scenario")
    @patch("bimcalc.reporting.export.export_scenario_to_excel")
    def test_export_scenarios_with_multiple_vendors(
        self,
        mock_export_excel,
        mock_compute_scenario,
        mock_get_vendors,
        mock_get_session,
        client,
        mock_db_session,
        mock_scenario_result,
    ):
        """Test scenario export with multiple specified vendors."""
        mock_get_session.return_value = mock_db_session
        mock_get_vendors.return_value = ["V1", "V2", "V3"]
        mock_compute_scenario.return_value = mock_scenario_result

        # Mock Excel file output
        excel_buffer = BytesIO(b"fake excel data")
        mock_export_excel.return_value = excel_buffer

        response = client.get("/api/scenarios/export?org=test-org&project=test-project&vendors=V1&vendors=V2&vendors=V3")
        assert response.status_code == 200

        # Verify compute_vendor_scenario called for each vendor
        assert mock_compute_scenario.call_count == 3


# Integration tests
def test_router_has_correct_routes():
    """Test that scenarios router has all expected routes."""
    routes = [route.path for route in scenarios.router.routes]

    assert "/scenarios" in routes
    assert "/api/scenarios/compare" in routes
    assert "/api/scenarios/export" in routes

    # Should have 3 routes total
    assert len(scenarios.router.routes) == 3


def test_router_has_scenarios_tag():
    """Test that router is tagged correctly."""
    assert "scenarios" in scenarios.router.tags
