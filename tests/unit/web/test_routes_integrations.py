"""Tests for bimcalc.web.routes.integrations - External integrations routes.

Tests the integrations router module extracted in Phase 3.15.
"""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock, AsyncMock

from bimcalc.web.routes import integrations


@pytest.fixture
def app():
    """Create test FastAPI app with integrations router."""
    test_app = FastAPI()
    test_app.include_router(integrations.router)
    return test_app


@pytest.fixture
def client(app):
    """Create test client."""
    return TestClient(app)


@pytest.fixture
def mock_acc_client():
    """Mock ACC client."""
    client = MagicMock()
    client.get_auth_url = MagicMock(
        return_value="https://acc.autodesk.com/oauth?client_id=test"
    )
    client.exchange_code = AsyncMock(
        return_value={"access_token": "test-token-123", "expires_in": 3600}
    )
    client.list_projects = AsyncMock(
        return_value=[
            {"id": "proj-1", "name": "Project Alpha"},
            {"id": "proj-2", "name": "Project Beta"},
        ]
    )
    client.list_files = AsyncMock(
        return_value=[
            MagicMock(id="file-1", name="Building A.rvt", version=5),
            MagicMock(id="file-2", name="MEP Systems.rvt", version=3),
        ]
    )
    return client


class TestAccConnect:
    """Tests for GET /api/integrations/acc/connect route."""

    @patch("bimcalc.integrations.acc.get_acc_client")
    def test_acc_connect_redirects_to_auth(
        self, mock_get_client, client, mock_acc_client
    ):
        """Test ACC connect initiates OAuth flow."""
        mock_get_client.return_value = mock_acc_client

        response = client.get("/api/integrations/acc/connect", follow_redirects=False)

        assert response.status_code == 307  # Redirect
        assert "acc.autodesk.com" in response.headers["location"]
        assert mock_acc_client.get_auth_url.called


class TestAccCallback:
    """Tests for GET /api/integrations/acc/callback route."""

    @patch("bimcalc.integrations.acc.get_acc_client")
    def test_acc_callback_success(self, mock_get_client, client, mock_acc_client):
        """Test successful ACC OAuth callback."""
        mock_get_client.return_value = mock_acc_client

        response = client.get(
            "/api/integrations/acc/callback?code=test-auth-code", follow_redirects=False
        )

        assert response.status_code == 307  # Redirect
        assert "/integrations/acc/browser" in response.headers["location"]

        # Verify token stored in cookie
        cookies = response.cookies
        assert "acc_token" in cookies
        assert cookies["acc_token"] == "test-token-123"

        # Verify exchange_code was called
        mock_acc_client.exchange_code.assert_called_once_with("test-auth-code")

    @patch("bimcalc.integrations.acc.get_acc_client")
    def test_acc_callback_sets_httponly_cookie(
        self, mock_get_client, client, mock_acc_client
    ):
        """Test callback sets httponly cookie for security."""
        mock_get_client.return_value = mock_acc_client

        response = client.get(
            "/api/integrations/acc/callback?code=test-code", follow_redirects=False
        )

        # Check cookie attributes
        set_cookie_header = response.headers.get("set-cookie", "")
        assert "httponly" in set_cookie_header.lower()

    @patch("bimcalc.integrations.acc.get_acc_client")
    def test_acc_callback_exchange_error(
        self, mock_get_client, client, mock_acc_client
    ):
        """Test callback handles token exchange errors."""
        mock_acc_client.exchange_code = AsyncMock(side_effect=Exception("Invalid code"))
        mock_get_client.return_value = mock_acc_client

        with pytest.raises(Exception, match="Invalid code"):
            client.get("/api/integrations/acc/callback?code=bad-code")


class TestAccBrowser:
    """Tests for GET /integrations/acc/browser route."""

    @patch("bimcalc.integrations.acc.get_acc_client")
    def test_acc_browser_without_token_redirects(
        self, mock_get_client, client, mock_acc_client
    ):
        """Test browser redirects to connect when no token present."""
        mock_get_client.return_value = mock_acc_client

        response = client.get("/integrations/acc/browser", follow_redirects=False)

        assert response.status_code == 307  # Redirect
        assert "/api/integrations/acc/connect" in response.headers["location"]

    @patch("bimcalc.integrations.acc.get_acc_client")
    def test_acc_browser_shows_projects(self, mock_get_client, client, mock_acc_client):
        """Test browser displays list of projects."""
        mock_get_client.return_value = mock_acc_client

        # Set cookie with token
        client.cookies.set("acc_token", "valid-token")

        response = client.get("/integrations/acc/browser")

        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]
        assert "Autodesk Construction Cloud" in response.text
        assert "Project Alpha" in response.text
        assert "Project Beta" in response.text

        # Verify list_projects was called
        mock_acc_client.list_projects.assert_called_once_with("valid-token")

    @patch("bimcalc.integrations.acc.get_acc_client")
    def test_acc_browser_shows_files_for_project(
        self, mock_get_client, client, mock_acc_client
    ):
        """Test browser displays files when project selected."""
        mock_get_client.return_value = mock_acc_client

        # Set cookie with token
        client.cookies.set("acc_token", "valid-token")

        response = client.get("/integrations/acc/browser?project_id=proj-1")

        assert response.status_code == 200
        assert "Building A.rvt" in response.text
        assert "MEP Systems.rvt" in response.text
        assert "v5" in response.text  # version
        assert "v3" in response.text

        # Verify list_files was called with correct project_id
        mock_acc_client.list_files.assert_called_once_with("valid-token", "proj-1")

    @patch("bimcalc.integrations.acc.get_acc_client")
    def test_acc_browser_includes_import_buttons(
        self, mock_get_client, client, mock_acc_client
    ):
        """Test browser includes import buttons for files."""
        mock_get_client.return_value = mock_acc_client

        client.cookies.set("acc_token", "valid-token")

        response = client.get("/integrations/acc/browser?project_id=proj-1")

        assert response.status_code == 200
        assert "Import</button>" in response.text
        assert "importFile" in response.text  # JavaScript function

    @patch("bimcalc.integrations.acc.get_acc_client")
    def test_acc_browser_without_project_shows_only_projects(
        self, mock_get_client, client, mock_acc_client
    ):
        """Test browser without project_id shows only projects."""
        mock_get_client.return_value = mock_acc_client

        client.cookies.set("acc_token", "valid-token")

        response = client.get("/integrations/acc/browser")

        assert response.status_code == 200
        assert "Project Alpha" in response.text
        assert "Building A.rvt" not in response.text  # No files shown

        # Verify list_files was NOT called
        mock_acc_client.list_files.assert_not_called()

    @patch("bimcalc.integrations.acc.get_acc_client")
    def test_acc_browser_handles_empty_projects(
        self, mock_get_client, client, mock_acc_client
    ):
        """Test browser handles case with no projects."""
        mock_acc_client.list_projects = AsyncMock(return_value=[])
        mock_get_client.return_value = mock_acc_client

        client.cookies.set("acc_token", "valid-token")

        response = client.get("/integrations/acc/browser")

        assert response.status_code == 200
        assert "Projects" in response.text

    @patch("bimcalc.integrations.acc.get_acc_client")
    def test_acc_browser_handles_api_error(
        self, mock_get_client, client, mock_acc_client
    ):
        """Test browser handles ACC API errors."""
        mock_acc_client.list_projects = AsyncMock(side_effect=Exception("API Error"))
        mock_get_client.return_value = mock_acc_client

        client.cookies.set("acc_token", "valid-token")

        with pytest.raises(Exception, match="API Error"):
            client.get("/integrations/acc/browser")


# Integration tests
def test_router_has_correct_routes():
    """Test that integrations router has all expected routes."""
    routes = [route.path for route in integrations.router.routes]

    assert "/api/integrations/acc/connect" in routes
    assert "/api/integrations/acc/callback" in routes
    assert "/integrations/acc/browser" in routes

    # Should have 3 routes total
    assert len(integrations.router.routes) == 3


def test_router_has_integrations_tag():
    """Test that router is tagged correctly."""
    assert "integrations" in integrations.router.tags
