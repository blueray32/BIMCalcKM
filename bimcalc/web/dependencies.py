"""Shared dependencies for BIMCalc web routes.

This module provides reusable dependencies for FastAPI route handlers.
Dependencies are injected using FastAPI's Depends() system.

Usage:
    from fastapi import Depends
    from bimcalc.web.dependencies import get_templates

    @router.get("/page")
    async def page(
        request: Request,
        templates = Depends(get_templates),
    ):
        return templates.TemplateResponse("page.html", {"request": request})
"""

from __future__ import annotations

from pathlib import Path
from fastapi import Request
from fastapi.templating import Jinja2Templates

from bimcalc.config import get_config

# Global singleton for templates
_templates: Jinja2Templates | None = None


def get_templates() -> Jinja2Templates:
    """Get Jinja2Templates instance for rendering HTML templates.

    This is a singleton - the templates directory is only initialized once.
    All route modules can depend on this function to get the templates instance.

    Returns:
        Jinja2Templates instance configured with BIMCalc templates directory.

    Example:
        @router.get("/dashboard")
        async def dashboard(
            request: Request,
            templates = Depends(get_templates),
        ):
            return templates.TemplateResponse(
                "dashboard.html",
                {"request": request, "data": ...}
            )
    """
    global _templates
    if _templates is None:
        # Templates are in bimcalc/web/templates/ and feature directories
        base_dir = Path(__file__).parent
        root_dir = base_dir.parent

        _templates = Jinja2Templates(
            directory=[
                str(base_dir / "templates"),
                str(root_dir / "ingestion" / "templates"),
                str(root_dir / "reporting" / "templates"),
            ]
        )
    return _templates


def get_org_project(
    request: Request, org: str | None = None, project: str | None = None
) -> tuple[str, str]:
    """Get organization and project IDs with fallbacks to config defaults.

    Extracted from app_enhanced.py:179 for use in dashboard and other routes.

    Args:
        request: FastAPI request object (for future session/cookie support)
        org: Organization ID from query parameter
        project: Project ID from query parameter

    Returns:
        Tuple of (org_id, project_id) with config defaults applied

    Example:
        @router.get("/dashboard")
        async def dashboard(
            request: Request,
            org: str | None = None,
            project: str | None = None,
        ):
            org_id, project_id = get_org_project(request, org, project)
            # Use org_id and project_id...
    """
    config = get_config()
    return (org or config.org_id, project or "default")


# Future dependencies can be added here:
# - get_current_user() - Extract user from session
# - get_org_context() - Multi-tenancy organization context (extended from get_org_project)
# - get_cache() - Redis/in-memory cache
# - get_config() - Application configuration (already exists in bimcalc.config)
