"""Documents routes for BIMCalc web UI.

Handles document management and viewing.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse

from bimcalc.web.dependencies import get_templates, get_org_project

router = APIRouter(tags=["documents"])


@router.get("/documents", response_class=HTMLResponse)
async def documents_page(
    request: Request,
    org: str | None = None,
    project: str | None = None,
    templates=Depends(get_templates),
):
    """Render documents management page."""
    org_id, project_id = get_org_project(request, org, project)

    return templates.TemplateResponse(
        "documents.html",
        {"request": request, "org_id": org_id, "project_id": project_id},
    )
