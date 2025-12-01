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
"""

__all__ = []  # Will be populated as routers are created
