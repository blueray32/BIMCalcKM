"""BIMCalc Web Route Modules.

This package contains modular route definitions for the BIMCalc web UI.
Each module handles a specific functional area using FastAPI's APIRouter.

Architecture:
- Each route module exports a `router` object (APIRouter instance)
- Main app includes these routers in app_enhanced.py
- Shared dependencies provided by bimcalc.web.dependencies
- Shared models defined in bimcalc.web.models

Pattern (from intelligence/routes.py):
    from fastapi import APIRouter
    router = APIRouter(tags=["feature"])

    @router.get("/endpoint")
    async def handler(...):
        pass

Usage:
    from bimcalc.web.routes import auth
    app.include_router(auth.router)
"""

# Import routers as they are created
from bimcalc.web.routes import auth, dashboard, ingestion, items, mappings, matching, review

__all__ = [
    "auth",       # Phase 3.1 - Authentication routes
    "dashboard",  # Phase 3.2 - Dashboard and progress routes
    "ingestion",  # Phase 3.3 - Ingestion routes
    "matching",   # Phase 3.4 - Matching pipeline routes
    "review",     # Phase 3.5 - Review workflow routes
    "items",      # Phase 3.6 - Items management routes
    "mappings",   # Phase 3.7 - Mappings management routes
]
