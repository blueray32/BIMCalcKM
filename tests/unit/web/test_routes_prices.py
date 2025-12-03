"""Tests for bimcalc.web.routes.prices - Prices management routes.

Tests the prices router module extracted in Phase 3.11.
"""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock, AsyncMock
from datetime import datetime
from uuid import uuid4
from decimal import Decimal

from bimcalc.web.routes import prices


@pytest.fixture
def app():
    """Create test FastAPI app with prices router."""
    test_app = FastAPI()
    test_app.include_router(prices.router)
    return test_app


@pytest.fixture
def client(app):
    """Create test client."""
    return TestClient(app)


@pytest.fixture
def mock_price_item():
    """Mock price item for testing."""
    price = MagicMock()
    price.id = uuid4()
    price.item_code = "TEST-001"
    price.sku = "SKU-001"
    price.description = "Test Item"
    price.classification_code = "TEST"
    price.unit = "EA"
    price.unit_price = Decimal("10.00")
    price.currency = "EUR"
    price.vat_rate = Decimal("0.23")
    price.region = "UK"
    price.vendor_id = "TEST-VENDOR"
    price.width_mm = 100
    price.height_mm = 200
    price.dn_mm = None
    price.angle_deg = None
    price.material = "Steel"
    price.valid_from = datetime(2025, 1, 1)
    price.valid_to = None
    price.is_current = True
    price.source_name = "Test Source"
    price.last_updated = datetime(2025, 1, 1, 12, 0, 0)
    price.org_id = "test-org"
    return price


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


class TestPriceHistory:
    """Tests for GET /prices/history/{item_code} route."""

    @patch("bimcalc.web.routes.prices.get_session")
    def test_price_history_success(
        self,
        mock_get_session,
        client,
        mock_db_session,
        mock_price_item,
    ):
        """Test price history view with results."""
        mock_get_session.return_value = mock_db_session
        session = mock_db_session.__aenter__.return_value

        # Mock query result
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_price_item]
        session.execute.return_value = mock_result

        response = client.get("/prices/history/TEST-001?region=UK")
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]

    @patch("bimcalc.web.routes.prices.get_session")
    def test_price_history_not_found(
        self,
        mock_get_session,
        client,
        mock_db_session,
    ):
        """Test price history when no records found."""
        mock_get_session.return_value = mock_db_session
        session = mock_db_session.__aenter__.return_value

        # Mock empty result
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        session.execute.return_value = mock_result

        response = client.get("/prices/history/NONEXISTENT?region=UK")
        assert response.status_code == 404


class TestPricesList:
    """Tests for GET /prices-legacy route."""

    @pytest.mark.skip(reason="Prices template requires complex context - better in integration")
    @patch("bimcalc.web.routes.prices.get_session")
    @patch("bimcalc.web.routes.prices.get_org_project")
    def test_prices_list_default_view(
        self,
        mock_get_org_project,
        mock_get_session,
        client,
        mock_db_session,
        mock_price_item,
    ):
        """Test prices list default view.

        Note: Skipped - prices template requires complex context.
        """
        mock_get_org_project.return_value = ("test-org", "test-project")
        mock_get_session.return_value = mock_db_session
        session = mock_db_session.__aenter__.return_value

        # Mock query results
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_price_item]

        mock_count = MagicMock()
        mock_count.scalar_one.return_value = 1

        mock_vendors = MagicMock()
        mock_vendors.scalars.return_value.all.return_value = ["TEST-VENDOR"]

        mock_classifications = MagicMock()
        mock_classifications.scalars.return_value.all.return_value = ["TEST"]

        mock_regions = MagicMock()
        mock_regions.scalars.return_value.all.return_value = ["UK"]

        session.execute.side_effect = [
            mock_count,  # count
            mock_result,  # prices
            mock_vendors,  # vendors
            mock_classifications,  # classifications
            mock_regions,  # regions
        ]

        response = client.get("/prices-legacy")
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]

    @pytest.mark.skip(reason="Executive view requires price_metrics module - better in integration")
    @patch("bimcalc.web.routes.prices.compute_price_metrics")
    @patch("bimcalc.web.routes.prices.get_session")
    @patch("bimcalc.web.routes.prices.get_org_project")
    def test_prices_list_executive_view(
        self,
        mock_get_org_project,
        mock_get_session,
        mock_compute_metrics,
        client,
        mock_db_session,
    ):
        """Test prices list executive view.

        Note: Skipped - executive view requires complex metrics.
        """
        mock_get_org_project.return_value = ("test-org", "test-project")
        mock_get_session.return_value = mock_db_session
        session = mock_db_session.__aenter__.return_value

        # Mock metrics
        mock_metrics = MagicMock()
        mock_metrics.unique_vendors = 5
        mock_compute_metrics.return_value = mock_metrics

        # Mock pending count
        mock_pending = MagicMock()
        mock_pending.scalar_one.return_value = 10
        session.execute.return_value = mock_pending

        response = client.get("/prices-legacy?view=executive")
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]

    @patch("bimcalc.web.routes.prices.get_session")
    @patch("bimcalc.web.routes.prices.get_org_project")
    def test_prices_list_with_filters(
        self,
        mock_get_org_project,
        mock_get_session,
        client,
        mock_db_session,
    ):
        """Test prices list with search and filter parameters."""
        mock_get_org_project.return_value = ("test-org", "test-project")
        mock_get_session.return_value = mock_db_session
        session = mock_db_session.__aenter__.return_value

        # Mock empty results
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []

        mock_count = MagicMock()
        mock_count.scalar_one.return_value = 0

        session.execute.return_value = mock_count

        response = client.get(
            "/prices-legacy?search=test&vendor=TEST-VENDOR&classification=TEST&region=UK&current_only=true&page=1"
        )
        assert response.status_code == 200


class TestPricesExport:
    """Tests for GET /prices/export route."""

    @patch("bimcalc.web.routes.prices.get_session")
    @patch("bimcalc.web.routes.prices.get_org_project")
    def test_prices_export_success(
        self,
        mock_get_org_project,
        mock_get_session,
        client,
        mock_db_session,
        mock_price_item,
    ):
        """Test prices export to Excel."""
        mock_get_org_project.return_value = ("test-org", "test-project")
        mock_get_session.return_value = mock_db_session
        session = mock_db_session.__aenter__.return_value

        # Mock query result
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_price_item]
        session.execute.return_value = mock_result

        response = client.get("/prices/export")
        assert response.status_code == 200
        assert "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" in response.headers["content-type"]
        assert "attachment" in response.headers["content-disposition"]
        assert "prices_test-org" in response.headers["content-disposition"]

    @patch("bimcalc.web.routes.prices.get_session")
    @patch("bimcalc.web.routes.prices.get_org_project")
    def test_prices_export_with_filters(
        self,
        mock_get_org_project,
        mock_get_session,
        client,
        mock_db_session,
        mock_price_item,
    ):
        """Test prices export with filters."""
        mock_get_org_project.return_value = ("test-org", "test-project")
        mock_get_session.return_value = mock_db_session
        session = mock_db_session.__aenter__.return_value

        # Mock query result
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_price_item]
        session.execute.return_value = mock_result

        response = client.get(
            "/prices/export?search=test&vendor=TEST-VENDOR&classification=TEST&region=UK&current_only=true"
        )
        assert response.status_code == 200
        assert "vendor-TEST-VENDOR" in response.headers["content-disposition"]


class TestPriceDetail:
    """Tests for GET /prices/{price_id} route."""

    @pytest.mark.skip(reason="Price detail template requires complex context - better in integration")
    @patch("bimcalc.web.routes.prices.get_session")
    @patch("bimcalc.web.routes.prices.get_org_project")
    def test_price_detail_success(
        self,
        mock_get_org_project,
        mock_get_session,
        client,
        mock_db_session,
        mock_price_item,
    ):
        """Test price detail view.

        Note: Skipped - price detail template requires complex context.
        """
        mock_get_org_project.return_value = ("test-org", "test-project")
        mock_get_session.return_value = mock_db_session
        session = mock_db_session.__aenter__.return_value

        # Mock price and history results
        mock_price_result = MagicMock()
        mock_price_result.scalar_one_or_none.return_value = mock_price_item

        mock_history_result = MagicMock()
        mock_history_result.scalars.return_value.all.return_value = [mock_price_item]

        session.execute.side_effect = [mock_price_result, mock_history_result]

        response = client.get(f"/prices/{mock_price_item.id}")
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]

    @patch("bimcalc.web.routes.prices.get_session")
    @patch("bimcalc.web.routes.prices.get_org_project")
    def test_price_detail_not_found(
        self,
        mock_get_org_project,
        mock_get_session,
        client,
        mock_db_session,
    ):
        """Test price detail when price not found."""
        mock_get_org_project.return_value = ("test-org", "test-project")
        mock_get_session.return_value = mock_db_session
        session = mock_db_session.__aenter__.return_value

        # Mock not found
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        session.execute.return_value = mock_result

        price_id = uuid4()
        response = client.get(f"/prices/{price_id}")
        assert response.status_code == 404


# Integration tests
def test_router_has_correct_routes():
    """Test that prices router has all expected routes."""
    routes = [route.path for route in prices.router.routes]

    assert "/prices/history/{item_code}" in routes
    assert "/prices-legacy" in routes
    assert "/prices/export" in routes
    assert "/prices/{price_id}" in routes

    # Should have 4 routes total
    assert len(prices.router.routes) == 4


def test_router_has_prices_tag():
    """Test that router is tagged correctly."""
    assert "prices" in prices.router.tags
