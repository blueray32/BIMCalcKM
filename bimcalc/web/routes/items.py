"""Items management routes for BIMCalc web UI.

Extracted from app_enhanced.py as part of Phase 3.6 web refactor.
Handles item listing, detail viewing, export, and deletion.

Routes:
- GET    /items           - List and filter items with pagination
- GET    /items/export    - Export filtered items to Excel
- GET    /items/{item_id} - View item details
- DELETE /items/{item_id} - Delete an item
"""

from __future__ import annotations

from datetime import datetime
from io import BytesIO
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, StreamingResponse
from openpyxl import Workbook
from openpyxl.styles import Alignment, Font
from sqlalchemy import func, select

from bimcalc.db.connection import get_session
from bimcalc.db.models import ItemModel
from bimcalc.web.dependencies import get_org_project, get_templates

# Create router with items tag
router = APIRouter(tags=["items"])


# ============================================================================
# Items Management Routes
# ============================================================================

@router.get("/items", response_class=HTMLResponse)
async def items_list(
    request: Request,
    org: str | None = None,
    project: str | None = None,
    page: int = Query(default=1, ge=1),
    search: str | None = Query(default=None),
    category: str | None = Query(default=None),
    templates=Depends(get_templates),
):
    """List and manage items with search and filter.

    Supports pagination, search across family/type/category, and category filtering.

    Extracted from: app_enhanced.py:732
    """
    org_id, project_id = get_org_project(request, org, project)
    per_page = 50
    offset = (page - 1) * per_page

    async with get_session() as session:
        # Build query with filters
        stmt = select(ItemModel).where(
            ItemModel.org_id == org_id,
            ItemModel.project_id == project_id,
        )

        # Apply search filter (family, type, category)
        if search:
            search_term = f"%{search}%"
            stmt = stmt.where(
                (ItemModel.family.ilike(search_term))
                | (ItemModel.type_name.ilike(search_term))
                | (ItemModel.category.ilike(search_term))
            )

        # Apply category filter
        if category:
            stmt = stmt.where(ItemModel.category == category)

        # Get total count with filters
        count_stmt = select(func.count()).select_from(ItemModel).where(
            ItemModel.org_id == org_id,
            ItemModel.project_id == project_id,
        )
        if search:
            search_term = f"%{search}%"
            count_stmt = count_stmt.where(
                (ItemModel.family.ilike(search_term))
                | (ItemModel.type_name.ilike(search_term))
                | (ItemModel.category.ilike(search_term))
            )
        if category:
            count_stmt = count_stmt.where(ItemModel.category == category)

        count_result = await session.execute(count_stmt)
        total_items = count_result.scalar_one()
        total_pages = (total_items + per_page - 1) // per_page

        # Apply pagination and ordering
        stmt = stmt.order_by(ItemModel.created_at.desc()).limit(per_page).offset(offset)
        result = await session.execute(stmt)
        items = result.scalars().all()

        # Get distinct categories for filter dropdown
        categories_stmt = (
            select(ItemModel.category)
            .where(
                ItemModel.org_id == org_id,
                ItemModel.project_id == project_id,
                ItemModel.category.isnot(None),
            )
            .distinct()
            .order_by(ItemModel.category)
        )
        categories_result = await session.execute(categories_stmt)
        categories = [c for c in categories_result.scalars().all() if c]

    return templates.TemplateResponse(
        "items.html",
        {
            "request": request,
            "items": items,
            "org_id": org_id,
            "project_id": project_id,
            "page": page,
            "total_pages": total_pages,
            "total": total_items,
            "per_page": per_page,
            "search": search or "",
            "category": category or "",
            "categories": categories,
        },
    )


@router.get("/items/export")
async def items_export(
    org: str | None = None,
    project: str | None = None,
    search: str | None = Query(default=None),
    category: str | None = Query(default=None),
):
    """Export items to Excel file.

    Exports filtered items with same filters as list view.

    Extracted from: app_enhanced.py:822
    """
    org_id, project_id = get_org_project(None, org, project)

    async with get_session() as session:
        # Build query with same filters as list view
        stmt = select(ItemModel).where(
            ItemModel.org_id == org_id,
            ItemModel.project_id == project_id,
        )

        if search:
            search_term = f"%{search}%"
            stmt = stmt.where(
                (ItemModel.family.ilike(search_term))
                | (ItemModel.type_name.ilike(search_term))
                | (ItemModel.category.ilike(search_term))
            )

        if category:
            stmt = stmt.where(ItemModel.category == category)

        stmt = stmt.order_by(ItemModel.created_at.desc())
        result = await session.execute(stmt)
        items = result.scalars().all()

    # Create Excel file
    wb = Workbook()
    ws = wb.active
    ws.title = "Items"

    # Header row
    headers = [
        "Family",
        "Type",
        "Category",
        "Classification",
        "Canonical Key",
        "Quantity",
        "Unit",
        "Width (mm)",
        "Height (mm)",
        "DN (mm)",
        "Angle (°)",
        "Material",
        "Created At",
    ]
    ws.append(headers)

    # Style header
    for cell in ws[1]:
        cell.font = Font(bold=True)
        cell.alignment = Alignment(horizontal="center")

    # Data rows
    for item in items:
        ws.append(
            [
                item.family,
                item.type_name,
                item.category or "",
                item.classification_code or "",
                item.canonical_key or "",
                float(item.quantity) if item.quantity else "",
                item.unit or "",
                item.width_mm or "",
                item.height_mm or "",
                item.dn_mm or "",
                item.angle_deg or "",
                item.material or "",
                item.created_at.strftime("%Y-%m-%d %H:%M") if item.created_at else "",
            ]
        )

    # Auto-size columns
    for column in ws.columns:
        max_length = 0
        column_letter = column[0].column_letter
        for cell in column:
            if cell.value:
                max_length = max(max_length, len(str(cell.value)))
        ws.column_dimensions[column_letter].width = min(max_length + 2, 50)

    # Save to BytesIO
    output = BytesIO()
    wb.save(output)
    output.seek(0)

    # Return as downloadable file
    filename = f"items_{org_id}_{project_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    return StreamingResponse(
        output,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@router.get("/items/{item_id}", response_class=HTMLResponse)
async def item_detail(
    item_id: UUID,
    request: Request,
    org: str | None = None,
    project: str | None = None,
    templates=Depends(get_templates),
):
    """View item details.

    Shows detailed information for a single item.

    Extracted from: app_enhanced.py:930
    """
    org_id, project_id = get_org_project(request, org, project)

    async with get_session() as session:
        result = await session.execute(
            select(ItemModel).where(
                ItemModel.id == item_id,
                ItemModel.org_id == org_id,
                ItemModel.project_id == project_id,
            )
        )
        item = result.scalar_one_or_none()

        if not item:
            return templates.TemplateResponse(
                "error.html",
                {
                    "request": request,
                    "message": "Item not found",
                    "org_id": org_id,
                    "project_id": project_id,
                },
                status_code=404,
            )

    return templates.TemplateResponse(
        "item_detail.html",
        {
            "request": request,
            "item": item,
            "org_id": org_id,
            "project_id": project_id,
        },
    )


@router.delete("/items/{item_id}")
async def delete_item(item_id: UUID):
    """Delete an item.

    Permanently removes an item from the database.

    Extracted from: app_enhanced.py:973
    """
    async with get_session() as session:
        result = await session.execute(select(ItemModel).where(ItemModel.id == item_id))
        item = result.scalar_one_or_none()

        if not item:
            raise HTTPException(status_code=404, detail="Item not found")

        await session.delete(item)
        await session.commit()

    return {"success": True, "message": "Item deleted"}
