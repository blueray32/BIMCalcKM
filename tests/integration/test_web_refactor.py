"""Integration tests for web refactor - ensure backward compatibility.

These tests verify that the refactored route modules work identically
to the original monolithic app_enhanced.py implementation.

Test strategy:
1. Test critical workflows end-to-end
2. Verify all routes are accessible
3. Check authentication still works
4. Ensure templates render correctly
"""

import pytest
from fastapi.testclient import TestClient


# Placeholder - will be implemented as routers are created
@pytest.mark.skip(reason="Router migration in progress")
class TestWebRefactorCompatibility:
    """Test that refactored routes maintain backward compatibility."""

    def test_all_routes_accessible(self, client: TestClient):
        """Smoke test: all routes should be accessible (not 404)."""
        routes_to_test = [
            "/",
            "/login",
            "/ingest",
            "/match",
            "/review",
            "/items",
            "/mappings",
            "/reports",
            "/pipeline",
        ]

        for route in routes_to_test:
            response = client.get(route, follow_redirects=False)
            # Should redirect to login (302) or show page (200), not 404
            assert response.status_code in [200, 302], (
                f"Route {route} returned {response.status_code}"
            )

    def test_auth_flow_works(self, client: TestClient):
        """Test login/logout flow still works."""
        # Login
        response = client.post(
            "/login", data={"username": "test_user", "password": "test_password"}
        )
        assert response.status_code in [200, 302]

        # Logout
        response = client.get("/logout")
        assert response.status_code == 302  # Redirect to login

    def test_api_endpoints_return_json(self, client: TestClient):
        """Test that API endpoints still return JSON."""
        api_routes = [
            "/api/pipeline/status",
            "/api/ingest/history",
            "/api/revisions",
        ]

        for route in api_routes:
            response = client.get(route)
            # May require auth (401) or return data (200)
            if response.status_code == 200:
                assert response.headers["content-type"].startswith("application/json")


# Fixture for test client (will be properly configured later)
@pytest.fixture
def client():
    """Create FastAPI test client."""
    from bimcalc.web.app_enhanced import app

    return TestClient(app)
