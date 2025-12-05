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
from bimcalc.web.routes import (
    analytics,
    audit,
    auth,
    classifications,
    compliance,
    price_scout,
    price_sources,
    dashboard,
    documents,
    integrations,
    items,
    mappings,
    matching,
    pipeline,
    prices,
    projects,
    review,
    revisions,
    risk_dashboard,
    scenarios,
    users,
    webhooks,
    search,
    revit,
    health,
)

__all__ = [
    "auth",  # Phase 3.1 - Authentication routes
    "dashboard",  # Phase 3.2 - Dashboard and progress routes
    "matching",  # Phase 3.4 - Matching pipeline routes
    "review",  # Phase 3.5 - Review workflow routes
    "items",  # Phase 3.6 - Items management routes
    "mappings",  # Phase 3.7 - Mappings management routes
    "audit",  # Phase 3.9 - Audit trail routes
    "pipeline",  # Phase 3.10 - Pipeline management routes
    "prices",  # Phase 3.11 - Prices management routes
    "scenarios",  # Phase 3.12 - Scenario planning routes
    "price_scout",  # Phase 3.13 - Price Scout integration routes
    "price_sources",  # Phase 3.13.1 - Price Sources management (Phase 2)
    "revisions",  # Phase 3.14 - Revisions tracking routes
    "integrations",  # Phase 3.15 - External integrations (ACC) routes
    "compliance",  # Phase 3.16 - Compliance routes
    "documents",  # Phase 3.17 - Documents routes
    "classifications",  # Phase 3.18 - Classifications routes
    "analytics",  # Phase 3.19 - Analytics routes
    "risk_dashboard",  # Phase 3.20 - Risk Dashboard routes
    "users",
    "webhooks",
    "search",  # Phase 3.21 - User management routes
    "revit",
    "health",
]
