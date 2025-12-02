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
from bimcalc.web.routes import audit, auth, crail4, dashboard, ingestion, items, mappings, matching, pipeline, prices, reports, review, revisions, scenarios

__all__ = [
    "auth",       # Phase 3.1 - Authentication routes
    "dashboard",  # Phase 3.2 - Dashboard and progress routes
    "ingestion",  # Phase 3.3 - Ingestion routes
    "matching",   # Phase 3.4 - Matching pipeline routes
    "review",     # Phase 3.5 - Review workflow routes
    "items",      # Phase 3.6 - Items management routes
    "mappings",   # Phase 3.7 - Mappings management routes
    "reports",    # Phase 3.8 - Reports routes
    "audit",      # Phase 3.9 - Audit trail routes
    "pipeline",   # Phase 3.10 - Pipeline management routes
    "prices",     # Phase 3.11 - Prices management routes
    "scenarios",  # Phase 3.12 - Scenario planning routes
    "crail4",     # Phase 3.13 - Crail4 integration routes
    "revisions",  # Phase 3.14 - Revisions tracking routes
]
