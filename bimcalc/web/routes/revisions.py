"""Revisions tracking routes for BIMCalc web UI.

Extracted from app_enhanced.py as part of Phase 3.14 web refactor.
Handles revision history viewing for tracked changes to BIM items.

Routes:
- GET /revisions              - Revision history dashboard page
- GET /api/revisions          - Get revision history as JSON
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse
from sqlalchemy import select

from bimcalc.db.connection import get_session
from bimcalc.web.dependencies import get_org_project, get_templates

# Create router with revisions tag
router = APIRouter(tags=["revisions"])


# ============================================================================
# Revisions Routes
# ============================================================================

@router.get("/revisions", response_class=HTMLResponse)
async def revisions_page(
    request: Request,
    org: str | None = None,
    project: str | None = None,
    templates=Depends(get_templates),
):
    """Revision history dashboard.

    Shows chronological history of changes to BIM items including
    field modifications, additions, and deletions.

    Extracted from: app_enhanced.py:482
    """
    org_id, project_id = get_org_project(request, org, project)
    return templates.TemplateResponse(
        "revisions.html",
        {
            "request": request,
            "org_id": org_id,
            "project_id": project_id,
        },
    )


@router.get("/api/revisions")
async def get_revisions(
    org: str = Query(...),
    project: str = Query(...),
    item_id: UUID | None = Query(None),
    limit: int = Query(default=50, ge=1, le=100),
):
    """Get revision history for items.

    Returns chronological list of changes to items including:
    - Field name and old/new values
    - Change type (created, modified, deleted)
    - Timestamp and source filename

    Supports filtering by specific item_id.

    Extracted from: app_enhanced.py:400
    """
    from bimcalc.db.models import ItemModel, ItemRevisionModel

    async with get_session() as session:
        query = (
            select(ItemRevisionModel, ItemModel.family, ItemModel.type_name)
            .join(ItemModel, ItemRevisionModel.item_id == ItemModel.id)
            .where(
                ItemRevisionModel.org_id == org,
                ItemRevisionModel.project_id == project,
            )
            .order_by(ItemRevisionModel.ingest_timestamp.desc())
            .limit(limit)
        )

        if item_id:
            query = query.where(ItemRevisionModel.item_id == item_id)

        results = (await session.execute(query)).all()

        revisions = [
            {
                "id": str(row.ItemRevisionModel.id),
                "item_id": str(row.ItemRevisionModel.item_id),
                "item_name": f"{row.family} / {row.type_name}",
                "field_name": row.ItemRevisionModel.field_name,
                "old_value": row.ItemRevisionModel.old_value,
                "new_value": row.ItemRevisionModel.new_value,
                "change_type": row.ItemRevisionModel.change_type,
                "ingest_timestamp": row.ItemRevisionModel.ingest_timestamp.isoformat(),
                "source_filename": row.ItemRevisionModel.source_filename,
            }
            for row in results
        ]

        return JSONResponse(content={
            "org_id": org,
            "project_id": project,
            "count": len(revisions),
            "revisions": revisions,
        })
