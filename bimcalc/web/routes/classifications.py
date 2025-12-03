"""Classifications routes for BIMCalc web UI.

Handles classification systems and mapping.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse

from bimcalc.web.dependencies import get_templates, get_org_project

router = APIRouter(tags=["classifications"])

@router.get("/classifications", response_class=HTMLResponse)
async def classifications_page(
    request: Request,
    org: str | None = None,
    project: str | None = None,
    templates = Depends(get_templates),
):
    """Render classifications management page."""
    org_id, project_id = get_org_project(request, org, project)
    
    return templates.TemplateResponse(
        "classifications.html",
        {
            "request": request,
            "org_id": org_id,
            "project_id": project_id
        }
    )
