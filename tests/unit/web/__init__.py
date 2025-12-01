"""Unit tests for BIMCalc web route modules.

This package contains unit tests for individual route modules.
Each route module should have a corresponding test file.

Structure:
    tests/unit/web/
    ├── test_routes_auth.py          # Auth routes
    ├── test_routes_dashboard.py     # Dashboard routes
    ├── test_routes_ingestion.py     # Ingestion routes
    ├── test_routes_matching.py      # Matching routes
    └── ... (one per route module)

Testing pattern:
    - Use FastAPI's TestClient for route testing
    - Mock database dependencies
    - Test auth requirements
    - Test request/response validation
    - Test error handling
"""
