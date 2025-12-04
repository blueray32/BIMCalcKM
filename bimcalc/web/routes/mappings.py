"""Mappings management routes for BIMCalc web UI.

Extracted from app_enhanced.py as part of Phase 3.7 web refactor.
Handles mapping listing and deletion (closing).

Routes:
- GET    /mappings            - List active mappings with pagination
- DELETE /mappings/{mapping_id} - Delete (close) a mapping
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import HTMLResponse
from sqlalchemy import func, select

from bimcalc.db.connection import get_session
from bimcalc.db.models import ItemMappingModel, PriceItemModel
from bimcalc.web.dependencies import get_org_project, get_templates

# Create router with mappings tag
router = APIRouter(tags=["mappings"])


# ============================================================================
# Mappings Management Routes
# ============================================================================


@router.get("/mappings", response_class=HTMLResponse)
async def mappings_list(
    request: Request,
    org: str | None = None,
    project: str | None = None,
    page: int = Query(default=1, ge=1),
    templates=Depends(get_templates),
):
    """List and manage active mappings.

    Shows active mappings with pagination. Only displays current prices
    and mappings that have not been closed (end_ts is NULL).

    Extracted from: app_enhanced.py:746
    """
    org_id, project_id = get_org_project(request, org, project)
    per_page = 50
    offset = (page - 1) * per_page

    async with get_session() as session:
        # Get active mappings with pagination (only current prices)
        stmt = (
            select(ItemMappingModel, PriceItemModel)
            .join(PriceItemModel, PriceItemModel.id == ItemMappingModel.price_item_id)
            .where(
                ItemMappingModel.org_id == org_id,
                ItemMappingModel.end_ts.is_(None),
                PriceItemModel.is_current == True,
            )
            .order_by(ItemMappingModel.start_ts.desc())
            .limit(per_page)
            .offset(offset)
        )
        result = await session.execute(stmt)
        mappings = result.all()

        # Get total count
        count_result = await session.execute(
            select(func.count())
            .select_from(ItemMappingModel)
            .where(
                ItemMappingModel.org_id == org_id,
                ItemMappingModel.end_ts.is_(None),
            )
        )
        total = count_result.scalar_one()

    return templates.TemplateResponse(
        "mappings.html",
        {
            "request": request,
            "mappings": mappings,
            "org_id": org_id,
            "project_id": project_id,
            "page": page,
            "per_page": per_page,
            "total": total,
            "total_pages": (total + per_page - 1) // per_page,
        },
    )


@router.delete("/mappings/{mapping_id}")
async def delete_mapping(mapping_id: UUID):
    """Delete (close) a mapping.

    Uses SCD2 (Slowly Changing Dimension Type 2) pattern to close the mapping
    by setting end_ts instead of physically deleting the record.

    Extracted from: app_enhanced.py:799
    """
    async with get_session() as session:
        result = await session.execute(
            select(ItemMappingModel).where(ItemMappingModel.id == mapping_id)
        )
        mapping = result.scalar_one_or_none()

        if not mapping:
            raise HTTPException(status_code=404, detail="Mapping not found")

        # Close mapping (SCD2)
        mapping.end_ts = datetime.utcnow()
        await session.commit()

    return {"success": True, "message": "Mapping closed"}
