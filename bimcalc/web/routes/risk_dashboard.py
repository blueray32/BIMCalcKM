"""Risk Dashboard routes for BIMCalc web UI.

Handles risk analysis and visualization.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse

from bimcalc.web.dependencies import get_templates, get_org_project

router = APIRouter(tags=["risk"])


@router.get("/risk-dashboard", response_class=HTMLResponse)
async def risk_dashboard_page(
    request: Request,
    org: str | None = None,
    project: str | None = None,
    templates=Depends(get_templates),
):
    """Render risk dashboard page."""
    org_id, project_id = get_org_project(request, org, project)

    return templates.TemplateResponse(
        "risk_dashboard.html",
        {"request": request, "org_id": org_id, "project_id": project_id},
    )
