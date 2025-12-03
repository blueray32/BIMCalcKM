"""Analytics routes for BIMCalc web UI.

Handles analytics dashboard and metrics.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse

from bimcalc.web.dependencies import get_templates, get_org_project

router = APIRouter(tags=["analytics"])

@router.get("/analytics", response_class=HTMLResponse)
async def analytics_page(
    request: Request,
    org: str | None = None,
    project: str | None = None,
    templates = Depends(get_templates),
):
    """Render analytics dashboard page."""
    org_id, project_id = get_org_project(request, org, project)
    
    return templates.TemplateResponse(
        "analytics.html",
        {
            "request": request,
            "org_id": org_id,
            "project_id": project_id
        }
    )
