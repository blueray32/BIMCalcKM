"""Audit trail routes for BIMCalc web UI.

Extracted from app_enhanced.py as part of Phase 3.9 web refactor.
Handles audit trail viewing with optional executive dashboard.

Routes:
- GET /audit - View audit trail with optional executive view
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import HTMLResponse
from sqlalchemy import func, select

from bimcalc.db.connection import get_session
from bimcalc.db.models import ItemModel, MatchResultModel
from bimcalc.web.dependencies import get_org_project, get_templates

# Create router with audit tag
router = APIRouter(tags=["audit"])


# ============================================================================
# Audit Trail Routes
# ============================================================================

@router.get("/audit", response_class=HTMLResponse)
async def audit_trail(
    request: Request,
    org: str | None = None,
    project: str | None = None,
    page: int = Query(default=1, ge=1),
    view: str | None = Query(default=None),
    templates=Depends(get_templates),
):
    """View audit trail of all decisions.

    Supports two views:
    - view=executive: Compliance and governance metrics dashboard
    - (default): Detailed audit trail with pagination

    Extracted from: app_enhanced.py:776
    """
    org_id, project_id = get_org_project(request, org, project)

    # Executive view: Show compliance metrics dashboard
    if view == "executive":
        from bimcalc.reporting.audit_metrics import compute_audit_metrics

        async with get_session() as session:
            metrics = await compute_audit_metrics(session, org_id, project_id)

        return templates.TemplateResponse(
            "audit_executive.html",
            {
                "request": request,
                "metrics": metrics,
                "org_id": org_id,
                "project_id": project_id,
            },
        )

    # Default view: Detailed audit trail
    per_page = 50
    offset = (page - 1) * per_page

    async with get_session() as session:
        # Get match results with item info
        stmt = (
            select(MatchResultModel, ItemModel)
            .join(ItemModel, ItemModel.id == MatchResultModel.item_id)
            .where(
                ItemModel.org_id == org_id,
                ItemModel.project_id == project_id,
            )
            .order_by(MatchResultModel.timestamp.desc())
            .limit(per_page)
            .offset(offset)
        )
        result = await session.execute(stmt)
        audit_records = result.all()

        # Get total count
        count_result = await session.execute(
            select(func.count())
            .select_from(MatchResultModel)
            .join(ItemModel, ItemModel.id == MatchResultModel.item_id)
            .where(
                ItemModel.org_id == org_id,
                ItemModel.project_id == project_id,
            )
        )
        total = count_result.scalar_one()

    return templates.TemplateResponse(
        "audit.html",
        {
            "request": request,
            "audit_records": audit_records,
            "org_id": org_id,
            "project_id": project_id,
            "page": page,
            "per_page": per_page,
            "total": total,
            "total_pages": (total + per_page - 1) // per_page,
        },
    )
