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
from fastapi.templating import Jinja2Templates

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
        # Templates are in bimcalc/web/templates/
        templates_dir = Path(__file__).parent / "templates"
        _templates = Jinja2Templates(directory=str(templates_dir))
    return _templates


# Future dependencies can be added here:
# - get_current_user() - Extract user from session
# - get_org_context() - Multi-tenancy organization context
# - get_cache() - Redis/in-memory cache
# - get_config() - Application configuration (already exists in bimcalc.config)
