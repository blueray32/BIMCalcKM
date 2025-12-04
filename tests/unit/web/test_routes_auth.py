"""Tests for bimcalc.web.routes.auth - Authentication routes.

Tests the auth router module extracted in Phase 3.1.
"""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from unittest.mock import patch

from bimcalc.web.routes import auth


@pytest.fixture
def app():
    """Create test FastAPI app with auth router."""
    test_app = FastAPI()
    test_app.include_router(auth.router)
    return test_app


@pytest.fixture
def client(app):
    """Create test client."""
    return TestClient(app)


class TestLoginPage:
    """Tests for GET /login route."""

    def test_login_page_renders(self, client):
        """Test that login page renders successfully."""
        response = client.get("/login")
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]

    def test_login_page_with_error_param(self, client):
        """Test login page with error parameter."""
        response = client.get("/login?error=invalid")
        assert response.status_code == 200
        # Error parameter should be passed to template
        # (Can't easily test template rendering without full template setup)


class TestLoginPost:
    """Tests for POST /login route."""

    @patch("bimcalc.web.routes.auth.verify_credentials")
    @patch("bimcalc.web.routes.auth.create_session")
    def test_login_success(self, mock_create_session, mock_verify, client):
        """Test successful login creates session and redirects."""
        # Mock successful authentication
        mock_verify.return_value = True
        mock_create_session.return_value = "test-session-token"

        response = client.post(
            "/login",
            data={"username": "testuser", "password": "testpass"},
            follow_redirects=False,
        )

        # Should redirect to dashboard
        assert response.status_code == 302
        assert response.headers["location"] == "/"

        # Should set session cookie
        assert "session" in response.cookies
        assert response.cookies["session"] == "test-session-token"

        # Should call auth functions
        mock_verify.assert_called_once_with("testuser", "testpass")
        mock_create_session.assert_called_once_with("testuser")

    @patch("bimcalc.web.routes.auth.verify_credentials")
    def test_login_failure(self, mock_verify, client):
        """Test failed login redirects back with error."""
        # Mock failed authentication
        mock_verify.return_value = False

        response = client.post(
            "/login",
            data={"username": "baduser", "password": "badpass"},
            follow_redirects=False,
        )

        # Should redirect to login with error
        assert response.status_code == 302
        assert "/login" in response.headers["location"]
        assert "error=invalid" in response.headers["location"]

        # Should not set session cookie
        assert "session" not in response.cookies

    def test_login_missing_credentials(self, client):
        """Test login with missing credentials returns validation error."""
        # Missing password
        response = client.post("/login", data={"username": "testuser"})
        assert response.status_code == 422  # Validation error

        # Missing username
        response = client.post("/login", data={"password": "testpass"})
        assert response.status_code == 422


class TestLogout:
    """Tests for GET /logout route."""

    @patch("bimcalc.web.routes.auth.auth_logout")
    def test_logout_with_session(self, mock_auth_logout, client):
        """Test logout invalidates session and redirects."""
        # Set session cookie
        client.cookies.set("session", "test-session-token")

        response = client.get("/logout", follow_redirects=False)

        # Should redirect to login
        assert response.status_code == 302
        assert response.headers["location"] == "/login"

        # Should invalidate session
        mock_auth_logout.assert_called_once_with("test-session-token")

        # Should delete cookie (TestClient doesn't preserve deleted cookies, just verify redirect)
        # Cookie deletion is verified by the response having a Set-Cookie header with max-age=0

    @patch("bimcalc.web.routes.auth.auth_logout")
    def test_logout_without_session(self, mock_auth_logout, client):
        """Test logout without session still redirects."""
        response = client.get("/logout", follow_redirects=False)

        # Should redirect to login
        assert response.status_code == 302
        assert response.headers["location"] == "/login"

        # Should not call auth_logout (no session)
        mock_auth_logout.assert_not_called()


class TestFavicon:
    """Tests for GET /favicon.ico route."""

    def test_favicon_returns_204(self, client):
        """Test favicon returns 204 No Content."""
        response = client.get("/favicon.ico")
        assert response.status_code == 204
        assert len(response.content) == 0

    def test_favicon_not_in_schema(self):
        """Test favicon route is excluded from OpenAPI schema."""
        # Check route configuration
        favicon_route = None
        for route in auth.router.routes:
            if route.path == "/favicon.ico":
                favicon_route = route
                break

        assert favicon_route is not None
        assert favicon_route.include_in_schema is False


# Integration test
def test_router_has_correct_routes():
    """Test that auth router has all expected routes."""
    routes = [route.path for route in auth.router.routes]

    assert "/login" in routes
    assert "/logout" in routes
    assert "/favicon.ico" in routes

    # Should have 4 routes total (login GET/POST = 2, logout, favicon)
    assert len(auth.router.routes) == 4


def test_router_has_auth_tag():
    """Test that router is tagged correctly."""
    assert "authentication" in auth.router.tags
