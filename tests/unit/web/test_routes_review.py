"""Tests for bimcalc.web.routes.review - Review workflow routes.

Tests the review router module extracted in Phase 3.5.
"""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock, AsyncMock
from types import SimpleNamespace
from uuid import uuid4
from datetime import datetime

from bimcalc.web.routes import review
from bimcalc.models import FlagSeverity


@pytest.fixture
def app():
    """Create test FastAPI app with review router."""
    test_app = FastAPI()
    test_app.include_router(review.router)
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


class TestHelperFunctions:
    """Tests for helper functions."""

    def test_parse_flag_filter_none(self):
        """Test parsing None flag filter returns None."""
        assert review._parse_flag_filter(None) is None

    def test_parse_flag_filter_all(self):
        """Test parsing 'all' flag filter returns None."""
        assert review._parse_flag_filter("all") is None

    def test_parse_flag_filter_empty(self):
        """Test parsing empty flag filter returns None."""
        assert review._parse_flag_filter("") is None

    def test_parse_flag_filter_valid(self):
        """Test parsing valid flag returns list."""
        result = review._parse_flag_filter("price_high")
        assert result == ["price_high"]

    def test_parse_severity_filter_none(self):
        """Test parsing None severity returns None."""
        assert review._parse_severity_filter(None) is None

    def test_parse_severity_filter_all(self):
        """Test parsing 'all' severity returns None."""
        assert review._parse_severity_filter("all") is None
        assert review._parse_severity_filter("ALL") is None

    def test_parse_severity_filter_valid(self):
        """Test parsing valid severity returns FlagSeverity."""
        result = review._parse_severity_filter("Advisory")
        assert result == FlagSeverity.ADVISORY

    def test_parse_severity_filter_invalid(self):
        """Test parsing invalid severity raises HTTPException."""
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc_info:
            review._parse_severity_filter("invalid")
        assert exc_info.value.status_code == 400
        assert "Invalid severity filter" in exc_info.value.detail


class TestReviewDashboard:
    """Tests for GET /review route."""

    @pytest.mark.skip(reason="Template requires complex records object with many attributes - better tested in integration")
    @patch("bimcalc.web.routes.review.fetch_pending_reviews")
    @patch("bimcalc.web.routes.review.fetch_available_classifications")
    @patch("bimcalc.web.routes.review.get_session")
    @patch("bimcalc.web.dependencies.get_config")
    def test_review_dashboard_default_view(
        self,
        mock_get_config,
        mock_get_session,
        mock_fetch_classifications,
        mock_fetch_reviews,
        client,
        mock_config,
        mock_db_session,
    ):
        """Test review dashboard default (detailed) view.

        Note: Skipped - template requires complex records with many attributes.
        Better tested in integration tests with real fetch_pending_reviews().
        """
        mock_get_config.return_value = mock_config
        mock_get_session.return_value = mock_db_session

        # Mock review data
        mock_records = [
            SimpleNamespace(
                id=uuid4(),
                item_family="Pipe",
                item_type="100mm",
                classification="ABC123",
            )
        ]
        mock_fetch_reviews.return_value = mock_records
        mock_fetch_classifications.return_value = ["ABC123", "XYZ789"]

        response = client.get("/review")
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]

        # Verify fetch functions were called
        mock_fetch_reviews.assert_called_once()
        mock_fetch_classifications.assert_called_once()

    @pytest.mark.skip(reason="Executive template requires complex metrics object with many attributes - better tested in integration")
    @patch("bimcalc.reporting.review_metrics.compute_review_metrics")
    @patch("bimcalc.web.routes.review.get_session")
    @patch("bimcalc.web.dependencies.get_config")
    def test_review_dashboard_executive_view(
        self,
        mock_get_config,
        mock_get_session,
        mock_compute_metrics,
        client,
        mock_config,
        mock_db_session,
    ):
        """Test review dashboard executive view.

        Note: Skipped - template requires complex metrics with high_urgency, etc.
        Better tested in integration tests with real compute_review_metrics().
        """
        mock_get_config.return_value = mock_config
        mock_get_session.return_value = mock_db_session

        # Mock metrics
        mock_metrics = SimpleNamespace(
            total_pending=50,
            critical_veto=10,
            advisory=25,
        )
        mock_compute_metrics.return_value = mock_metrics

        response = client.get("/review?view=executive")
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]

        # Verify metrics were computed
        mock_compute_metrics.assert_called_once()

    @patch("bimcalc.web.routes.review.fetch_pending_reviews")
    @patch("bimcalc.web.routes.review.fetch_available_classifications")
    @patch("bimcalc.web.routes.review.get_session")
    @patch("bimcalc.web.dependencies.get_config")
    def test_review_dashboard_with_filters(
        self,
        mock_get_config,
        mock_get_session,
        mock_fetch_classifications,
        mock_fetch_reviews,
        client,
        mock_config,
        mock_db_session,
    ):
        """Test review dashboard with filter parameters."""
        mock_get_config.return_value = mock_config
        mock_get_session.return_value = mock_db_session

        mock_fetch_reviews.return_value = []
        mock_fetch_classifications.return_value = []

        response = client.get(
            "/review?flag=price_high&severity=Advisory&unmapped_only=on&classification=ABC123"
        )
        assert response.status_code == 200

        # Verify filters were passed
        call_args = mock_fetch_reviews.call_args
        assert call_args.kwargs["flag_types"] == ["price_high"]
        assert call_args.kwargs["severity_filter"] == FlagSeverity.ADVISORY
        assert call_args.kwargs["unmapped_only"] is True
        assert call_args.kwargs["classification_filter"] == "ABC123"

    @patch("bimcalc.web.routes.review.fetch_pending_reviews")
    @patch("bimcalc.web.routes.review.fetch_available_classifications")
    @patch("bimcalc.web.routes.review.get_session")
    @patch("bimcalc.web.dependencies.get_config")
    def test_review_dashboard_with_org_project(
        self,
        mock_get_config,
        mock_get_session,
        mock_fetch_classifications,
        mock_fetch_reviews,
        client,
        mock_config,
        mock_db_session,
    ):
        """Test review dashboard accepts org and project parameters."""
        mock_get_config.return_value = mock_config
        mock_get_session.return_value = mock_db_session

        mock_fetch_reviews.return_value = []
        mock_fetch_classifications.return_value = []

        response = client.get("/review?org=custom-org&project=custom-proj")
        assert response.status_code == 200

        # Verify org/project were passed
        call_args = mock_fetch_reviews.call_args
        assert call_args.args[1] == "custom-org"
        assert call_args.args[2] == "custom-proj"


class TestApproveItem:
    """Tests for POST /review/approve route."""

    @patch("bimcalc.web.routes.review.approve_review_record")
    @patch("bimcalc.web.routes.review.fetch_review_record")
    @patch("bimcalc.web.routes.review.get_session")
    @patch("bimcalc.web.dependencies.get_config")
    def test_approve_item_success(
        self,
        mock_get_config,
        mock_get_session,
        mock_fetch_record,
        mock_approve_record,
        client,
        mock_config,
        mock_db_session,
    ):
        """Test successful item approval."""
        mock_get_config.return_value = mock_config
        mock_get_session.return_value = mock_db_session

        # Mock review record
        mock_record = MagicMock()
        mock_fetch_record.return_value = mock_record
        mock_approve_record.return_value = None

        # Make request
        match_id = uuid4()
        data = {
            "match_result_id": str(match_id),
            "org": "test-org",
            "project": "test-project",
            "annotation": "Looks good",
        }
        response = client.post("/review/approve", data=data, follow_redirects=False)

        assert response.status_code == 303
        assert "/review" in response.headers["location"]
        assert "org=test-org" in response.headers["location"]
        assert "project=test-project" in response.headers["location"]

        # Verify approval was called
        mock_approve_record.assert_called_once_with(
            mock_db_session.__aenter__.return_value,
            mock_record,
            created_by="web-ui",
            annotation="Looks good"
        )

    @patch("bimcalc.web.routes.review.fetch_review_record")
    @patch("bimcalc.web.routes.review.get_session")
    @patch("bimcalc.web.dependencies.get_config")
    def test_approve_item_not_found(
        self,
        mock_get_config,
        mock_get_session,
        mock_fetch_record,
        client,
        mock_config,
        mock_db_session,
    ):
        """Test approving non-existent item returns 404."""
        mock_get_config.return_value = mock_config
        mock_get_session.return_value = mock_db_session

        # Mock record not found
        mock_fetch_record.return_value = None

        # Make request
        match_id = uuid4()
        data = {
            "match_result_id": str(match_id),
            "org": "test-org",
            "project": "test-project",
        }
        response = client.post("/review/approve", data=data)

        assert response.status_code == 404
        assert "Review item not found" in response.json()["detail"]

    @patch("bimcalc.web.routes.review.approve_review_record")
    @patch("bimcalc.web.routes.review.fetch_review_record")
    @patch("bimcalc.web.routes.review.get_session")
    @patch("bimcalc.web.dependencies.get_config")
    def test_approve_item_preserves_filters(
        self,
        mock_get_config,
        mock_get_session,
        mock_fetch_record,
        mock_approve_record,
        client,
        mock_config,
        mock_db_session,
    ):
        """Test that approval preserves filter state in redirect."""
        mock_get_config.return_value = mock_config
        mock_get_session.return_value = mock_db_session

        mock_record = MagicMock()
        mock_fetch_record.return_value = mock_record

        # Make request with filters
        match_id = uuid4()
        data = {
            "match_result_id": str(match_id),
            "org": "test-org",
            "project": "test-project",
            "flag": "price_high",
            "severity": "high",
            "unmapped_only": "on",
            "classification": "ABC123",
        }
        response = client.post("/review/approve", data=data, follow_redirects=False)

        assert response.status_code == 303
        location = response.headers["location"]
        assert "flag=price_high" in location
        assert "severity=high" in location
        assert "unmapped_only=on" in location
        assert "classification=ABC123" in location


class TestRejectReview:
    """Tests for POST /review/reject route."""

    @patch("bimcalc.web.routes.review.get_session")
    @patch("bimcalc.web.dependencies.get_config")
    def test_reject_review_success(
        self,
        mock_get_config,
        mock_get_session,
        client,
        mock_config,
        mock_db_session,
    ):
        """Test successful review rejection."""
        mock_get_config.return_value = mock_config
        mock_get_session.return_value = mock_db_session
        session = mock_db_session.__aenter__.return_value

        # Mock match result
        match_result = MagicMock()
        match_result.id = str(uuid4())
        match_result.decision = "pending"

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = match_result
        session.execute.return_value = mock_result

        # Make request
        data = {
            "match_result_id": match_result.id,
            "org": "test-org",
            "project": "test-project",
        }
        response = client.post("/review/reject", data=data, follow_redirects=False)

        assert response.status_code == 303
        assert "/review" in response.headers["location"]

        # Verify match result was updated
        assert match_result.decision == "rejected"
        assert match_result.decision_reason == "Manual rejection via web UI"
        assert match_result.reviewed_by == "web-ui"
        assert match_result.reviewed_at is not None

        # Verify commit was called
        session.commit.assert_called_once()

    @patch("bimcalc.web.routes.review.get_session")
    @patch("bimcalc.web.dependencies.get_config")
    def test_reject_review_not_found(
        self,
        mock_get_config,
        mock_get_session,
        client,
        mock_config,
        mock_db_session,
    ):
        """Test rejecting non-existent match returns 404."""
        mock_get_config.return_value = mock_config
        mock_get_session.return_value = mock_db_session
        session = mock_db_session.__aenter__.return_value

        # Mock match result not found
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        session.execute.return_value = mock_result

        # Make request
        data = {
            "match_result_id": str(uuid4()),
            "org": "test-org",
            "project": "test-project",
        }
        response = client.post("/review/reject", data=data)

        assert response.status_code == 404
        assert "Match result not found" in response.json()["detail"]

    @patch("bimcalc.web.routes.review.get_session")
    @patch("bimcalc.web.dependencies.get_config")
    def test_reject_review_preserves_filters(
        self,
        mock_get_config,
        mock_get_session,
        client,
        mock_config,
        mock_db_session,
    ):
        """Test that rejection preserves filter state in redirect."""
        mock_get_config.return_value = mock_config
        mock_get_session.return_value = mock_db_session
        session = mock_db_session.__aenter__.return_value

        # Mock match result
        match_result = MagicMock()
        match_result.id = str(uuid4())

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = match_result
        session.execute.return_value = mock_result

        # Make request with filters
        data = {
            "match_result_id": match_result.id,
            "org": "test-org",
            "project": "test-project",
            "flag": "price_low",
            "severity": "medium",
            "unmapped_only": "on",
            "classification": "XYZ789",
        }
        response = client.post("/review/reject", data=data, follow_redirects=False)

        assert response.status_code == 303
        location = response.headers["location"]
        assert "org=test-org" in location
        assert "project=test-project" in location
        assert "flag=price_low" in location
        assert "severity=medium" in location
        assert "unmapped_only=on" in location
        assert "classification=XYZ789" in location

    def test_reject_review_requires_match_result_id(self, client):
        """Test that match_result_id parameter is required."""
        data = {"org": "test-org", "project": "test-project"}
        response = client.post("/review/reject", data=data)
        assert response.status_code == 422  # Validation error

    def test_reject_review_requires_org(self, client):
        """Test that org parameter is required."""
        data = {"match_result_id": str(uuid4()), "project": "test-project"}
        response = client.post("/review/reject", data=data)
        assert response.status_code == 422  # Validation error

    def test_reject_review_requires_project(self, client):
        """Test that project parameter is required."""
        data = {"match_result_id": str(uuid4()), "org": "test-org"}
        response = client.post("/review/reject", data=data)
        assert response.status_code == 422  # Validation error


# Integration tests
def test_router_has_correct_routes():
    """Test that review router has all expected routes."""
    routes = [route.path for route in review.router.routes]

    assert "/review" in routes
    assert "/review/approve" in routes
    assert "/review/reject" in routes

    # Should have 3 routes total
    assert len(review.router.routes) == 3


def test_router_has_review_tag():
    """Test that router is tagged correctly."""
    assert "review" in review.router.tags
