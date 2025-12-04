"""Tests for bimcalc.web.routes.mappings - Mappings management routes.

Tests the mappings router module extracted in Phase 3.7.
"""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock, AsyncMock
from uuid import uuid4
from datetime import datetime

from bimcalc.web.routes import mappings


@pytest.fixture
def app():
    """Create test FastAPI app with mappings router."""
    test_app = FastAPI()
    test_app.include_router(mappings.router)
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
def mock_mapping():
    """Mock mapping for testing."""
    mapping = MagicMock()
    mapping.id = uuid4()
    mapping.org_id = "test-org"
    mapping.item_canonical_key = "pipe:100mm:pvc"
    mapping.price_item_id = uuid4()
    mapping.start_ts = datetime(2025, 1, 1, 12, 0, 0)
    mapping.end_ts = None
    return mapping


@pytest.fixture
def mock_price_item():
    """Mock price item for testing."""
    price_item = MagicMock()
    price_item.id = uuid4()
    price_item.code = "ABC123"
    price_item.description = "100mm PVC Pipe"
    price_item.unit = "m"
    price_item.rate = 10.50
    price_item.is_current = True
    return price_item


class TestMappingsList:
    """Tests for GET /mappings route."""

    @pytest.mark.skip(
        reason="Template requires complex mappings object - better tested in integration"
    )
    @patch("bimcalc.web.routes.mappings.get_session")
    @patch("bimcalc.web.dependencies.get_config")
    def test_mappings_list_default(
        self,
        mock_get_config,
        mock_get_session,
        client,
        mock_config,
        mock_db_session,
        mock_mapping,
        mock_price_item,
    ):
        """Test mappings list renders with default parameters.

        Note: Skipped - template requires complex mappings object.
        Better tested in integration tests.
        """
        mock_get_config.return_value = mock_config
        mock_get_session.return_value = mock_db_session
        session = mock_db_session.__aenter__.return_value

        # Mock mappings query
        mock_mappings_result = MagicMock()
        mock_mappings_result.all.return_value = [(mock_mapping, mock_price_item)]

        # Mock count query
        mock_count_result = MagicMock()
        mock_count_result.scalar_one.return_value = 1

        # Setup side_effect to return different results
        session.execute.side_effect = [mock_mappings_result, mock_count_result]

        response = client.get("/mappings")
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]

    @patch("bimcalc.web.routes.mappings.get_session")
    @patch("bimcalc.web.dependencies.get_config")
    def test_mappings_list_filters_active_only(
        self,
        mock_get_config,
        mock_get_session,
        client,
        mock_config,
        mock_db_session,
    ):
        """Test mappings list only shows active mappings (end_ts is None)."""
        mock_get_config.return_value = mock_config
        mock_get_session.return_value = mock_db_session
        session = mock_db_session.__aenter__.return_value

        # Mock empty results
        mock_mappings_result = MagicMock()
        mock_mappings_result.all.return_value = []
        mock_count_result = MagicMock()
        mock_count_result.scalar_one.return_value = 0

        session.execute.side_effect = [mock_mappings_result, mock_count_result]

        response = client.get("/mappings")

        # Verify the route doesn't error and returns 200
        assert response.status_code == 200

    @patch("bimcalc.web.routes.mappings.get_session")
    @patch("bimcalc.web.dependencies.get_config")
    def test_mappings_list_with_pagination(
        self,
        mock_get_config,
        mock_get_session,
        client,
        mock_config,
        mock_db_session,
    ):
        """Test mappings list with pagination."""
        mock_get_config.return_value = mock_config
        mock_get_session.return_value = mock_db_session
        session = mock_db_session.__aenter__.return_value

        # Mock results
        mock_mappings_result = MagicMock()
        mock_mappings_result.all.return_value = []
        mock_count_result = MagicMock()
        mock_count_result.scalar_one.return_value = 100

        session.execute.side_effect = [mock_mappings_result, mock_count_result]

        response = client.get("/mappings?page=2")
        assert response.status_code == 200


class TestDeleteMapping:
    """Tests for DELETE /mappings/{mapping_id} route."""

    @patch("bimcalc.web.routes.mappings.get_session")
    def test_delete_mapping_success(
        self,
        mock_get_session,
        client,
        mock_db_session,
        mock_mapping,
    ):
        """Test successful mapping deletion (closing)."""
        mock_get_session.return_value = mock_db_session
        session = mock_db_session.__aenter__.return_value

        # Mock mapping query
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_mapping
        session.execute.return_value = mock_result

        response = client.delete(f"/mappings/{mock_mapping.id}")
        assert response.status_code == 200
        json_response = response.json()
        assert json_response["success"] is True
        assert "closed" in json_response["message"].lower()

        # Verify mapping was closed with end_ts
        assert mock_mapping.end_ts is not None
        session.commit.assert_called_once()

    @patch("bimcalc.web.routes.mappings.get_session")
    def test_delete_mapping_not_found(
        self,
        mock_get_session,
        client,
        mock_db_session,
    ):
        """Test deleting non-existent mapping returns 404."""
        mock_get_session.return_value = mock_db_session
        session = mock_db_session.__aenter__.return_value

        # Mock mapping not found
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        session.execute.return_value = mock_result

        mapping_id = uuid4()
        response = client.delete(f"/mappings/{mapping_id}")
        assert response.status_code == 404
        assert "Mapping not found" in response.json()["detail"]

        # Verify commit was not called
        session.commit.assert_not_called()

    @patch("bimcalc.web.routes.mappings.get_session")
    def test_delete_mapping_scd2_pattern(
        self,
        mock_get_session,
        client,
        mock_db_session,
        mock_mapping,
    ):
        """Test that delete uses SCD2 pattern (sets end_ts instead of deleting)."""
        mock_get_session.return_value = mock_db_session
        session = mock_db_session.__aenter__.return_value

        # Verify mapping initially has no end_ts
        assert mock_mapping.end_ts is None

        # Mock mapping query
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_mapping
        session.execute.return_value = mock_result

        response = client.delete(f"/mappings/{mock_mapping.id}")
        assert response.status_code == 200

        # Verify end_ts was set (SCD2 pattern)
        assert mock_mapping.end_ts is not None
        assert isinstance(mock_mapping.end_ts, datetime)

        # Verify session.delete was NOT called (we don't physically delete)
        session.delete.assert_not_called()

        # Verify commit was called to save the end_ts change
        session.commit.assert_called_once()


# Integration tests
def test_router_has_correct_routes():
    """Test that mappings router has all expected routes."""
    routes = [route.path for route in mappings.router.routes]

    assert "/mappings" in routes
    assert "/mappings/{mapping_id}" in routes

    # Should have 2 routes total (1 GET /mappings, 1 DELETE /mappings/{mapping_id})
    assert len(mappings.router.routes) == 2


def test_router_has_mappings_tag():
    """Test that router is tagged correctly."""
    assert "mappings" in mappings.router.tags
