"""Prices management routes for BIMCalc web UI.

Extracted from app_enhanced.py as part of Phase 3.11 web refactor.
Handles price viewing, history, export, and detail pages.

Routes:
- GET /prices/history/{item_code} - View price history for specific item
- GET /prices-legacy              - List prices with filters and executive view
- GET /prices/export              - Export prices to Excel
- GET /prices/{price_id}          - View price details
"""

from __future__ import annotations

from datetime import datetime
from io import BytesIO
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, StreamingResponse
from openpyxl import Workbook
from openpyxl.styles import Alignment, Font
from sqlalchemy import func, select, text

from bimcalc.db.connection import get_session
from bimcalc.db.models import PriceItemModel
from bimcalc.web.dependencies import get_org_project, get_templates

# Create router with prices tag
router = APIRouter(tags=["prices"])


# ============================================================================
# Prices Routes
# ============================================================================


@router.get("/prices/history/{item_code}", response_class=HTMLResponse)
async def price_history(
    request: Request,
    item_code: str,
    region: str = Query(default="UK"),
    templates=Depends(get_templates),
):
    """View price history for a specific item.

    Shows all price records (current + historical) for an item code and region.

    Extracted from: app_enhanced.py:800
    """
    async with get_session() as session:
        # Get all price records (current + historical)
        stmt = (
            select(PriceItemModel)
            .where(
                PriceItemModel.item_code == item_code,
                PriceItemModel.region == region,
            )
            .order_by(PriceItemModel.valid_from.desc())
        )
        result = await session.execute(stmt)
        price_history_list = result.scalars().all()

        if not price_history_list:
            raise HTTPException(
                status_code=404,
                detail=f"No price history found for {item_code} in {region}",
            )

    return templates.TemplateResponse(
        "price_history.html",
        {
            "request": request,
            "item_code": item_code,
            "region": region,
            "price_history": price_history_list,
        },
    )


@router.get("/prices", response_class=HTMLResponse)
async def prices_list(
    request: Request,
    org: str | None = None,
    project: str | None = None,
    view: str | None = Query(default=None),
    current_only: bool = Query(default=True),
    page: int = Query(default=1, ge=1),
    search: str | None = Query(default=None),
    vendor: str | None = Query(default=None),
    classification: str | None = Query(default=None),
    region: str | None = Query(default=None),
    templates=Depends(get_templates),
):
    """List all price items with search, filters, and optional history or executive view.

    Supports two views:
    - view=executive: Price quality metrics dashboard
    - (default): Paginated table with search and filters

    Extracted from: app_enhanced.py:837
    """
    org_id, project_id = get_org_project(request, org, project)

    # Executive view: Show price quality metrics
    if view == "executive":
        from bimcalc.reporting.price_metrics import compute_price_metrics

        async with get_session() as session:
            metrics = await compute_price_metrics(session, org_id)

            # Get pending review count for navigation badge
            pending_query = text("""
                WITH ranked_results AS (
                    SELECT
                        mr.item_id,
                        mr.decision,
                        ROW_NUMBER() OVER (PARTITION BY mr.item_id ORDER BY mr.timestamp DESC) as rn
                    FROM match_results mr
                    JOIN items i ON i.id = mr.item_id
                    WHERE i.org_id = :org_id
                      AND i.project_id = :project_id
                )
                SELECT COUNT(*)
                FROM ranked_results
                WHERE rn = 1 AND decision IN ('manual-review', 'pending-review')
            """)
            pending_result = await session.execute(
                pending_query, {"org_id": org_id, "project_id": project_id}
            )
            pending_count = pending_result.scalar_one()

        return templates.TemplateResponse(
            "prices_executive.html",
            {
                "request": request,
                "metrics": metrics,
                "org_id": org_id,
                "project_id": project_id,
                "unique_vendors": metrics.unique_vendors,
                "current_page": "prices",
                "pending_count": pending_count,
            },
        )

    # Default view: Paginated table with search and filters
    per_page = 50
    offset = (page - 1) * per_page

    async with get_session() as session:
        # Build query with filters
        stmt = select(PriceItemModel).where(PriceItemModel.org_id == org_id)

        if current_only:
            stmt = stmt.where(PriceItemModel.is_current == True)

        # Apply search filter (description, SKU, item_code)
        if search:
            search_term = f"%{search}%"
            stmt = stmt.where(
                (PriceItemModel.description.ilike(search_term))
                | (PriceItemModel.sku.ilike(search_term))
                | (PriceItemModel.item_code.ilike(search_term))
            )

        # Apply vendor filter
        if vendor:
            stmt = stmt.where(PriceItemModel.vendor_id == vendor)

        # Apply classification filter
        if classification:
            stmt = stmt.where(PriceItemModel.classification_code == classification)

        # Apply region filter
        if region:
            stmt = stmt.where(PriceItemModel.region == region)

        # Get total count with filters
        count_stmt = (
            select(func.count())
            .select_from(PriceItemModel)
            .where(PriceItemModel.org_id == org_id)
        )
        if current_only:
            count_stmt = count_stmt.where(PriceItemModel.is_current == True)
        if search:
            search_term = f"%{search}%"
            count_stmt = count_stmt.where(
                (PriceItemModel.description.ilike(search_term))
                | (PriceItemModel.sku.ilike(search_term))
                | (PriceItemModel.item_code.ilike(search_term))
            )
        if vendor:
            count_stmt = count_stmt.where(PriceItemModel.vendor_id == vendor)
        if classification:
            count_stmt = count_stmt.where(
                PriceItemModel.classification_code == classification
            )
        if region:
            count_stmt = count_stmt.where(PriceItemModel.region == region)

        count_result = await session.execute(count_stmt)
        total = count_result.scalar_one()
        total_pages = (total + per_page - 1) // per_page

        # Apply pagination and ordering
        stmt = (
            stmt.order_by(
                PriceItemModel.item_code,
                PriceItemModel.valid_from.desc(),
            )
            .limit(per_page)
            .offset(offset)
        )

        result = await session.execute(stmt)
        prices = result.scalars().all()

        # Get distinct vendors for filter dropdown
        vendors_stmt = (
            select(PriceItemModel.vendor_id)
            .where(
                PriceItemModel.org_id == org_id,
                PriceItemModel.vendor_id.isnot(None),
            )
            .distinct()
            .order_by(PriceItemModel.vendor_id)
        )
        vendors_result = await session.execute(vendors_stmt)
        vendors = [v for v in vendors_result.scalars().all() if v]

        # Get distinct classifications
        classifications_stmt = (
            select(PriceItemModel.classification_code)
            .where(
                PriceItemModel.org_id == org_id,
                PriceItemModel.classification_code.isnot(None),
            )
            .distinct()
            .order_by(PriceItemModel.classification_code)
        )
        classifications_result = await session.execute(classifications_stmt)
        classifications = [c for c in classifications_result.scalars().all() if c]

        # Get distinct regions
        regions_stmt = (
            select(PriceItemModel.region)
            .where(PriceItemModel.org_id == org_id)
            .distinct()
            .order_by(PriceItemModel.region)
        )
        regions_result = await session.execute(regions_stmt)
        regions = [r for r in regions_result.scalars().all() if r]

    return templates.TemplateResponse(
        "prices.html",
        {
            "request": request,
            "prices": prices,
            "current_only": current_only,
            "page": page,
            "per_page": per_page,
            "total": total,
            "total_pages": total_pages,
            "org_id": org_id,
            "project_id": project_id,
            "search": search or "",
            "vendor": vendor or "",
            "classification": classification or "",
            "region": region or "",
            "vendors": vendors,
            "classifications": classifications,
            "regions": regions,
            "request_url": str(request.url).replace(
                "/prices-legacy", "/prices"
            ),  # Ensure correct URL in template
        },
    )


from fastapi.responses import RedirectResponse


@router.get("/prices-legacy")
async def prices_legacy_redirect(request: Request):
    """Redirect legacy /prices-legacy URLs to /prices."""
    new_url = str(request.url).replace("/prices-legacy", "/prices")
    return RedirectResponse(url=new_url)


@router.get("/prices/export")
async def prices_export(
    org: str | None = None,
    project: str | None = None,
    search: str | None = Query(default=None),
    vendor: str | None = Query(default=None),
    classification: str | None = Query(default=None),
    region: str | None = Query(default=None),
    current_only: bool = Query(default=True),
):
    """Export prices to Excel file.

    Exports filtered prices with same filters as list view.

    Extracted from: app_enhanced.py:1017
    """
    org_id, project_id = get_org_project(None, org, project)

    async with get_session() as session:
        # Build query with same filters as list view
        stmt = select(PriceItemModel).where(PriceItemModel.org_id == org_id)

        if current_only:
            stmt = stmt.where(PriceItemModel.is_current == True)

        if search:
            search_term = f"%{search}%"
            stmt = stmt.where(
                (PriceItemModel.description.ilike(search_term))
                | (PriceItemModel.sku.ilike(search_term))
                | (PriceItemModel.item_code.ilike(search_term))
            )

        if vendor:
            stmt = stmt.where(PriceItemModel.vendor_id == vendor)

        if classification:
            stmt = stmt.where(PriceItemModel.classification_code == classification)

        if region:
            stmt = stmt.where(PriceItemModel.region == region)

        stmt = stmt.order_by(
            PriceItemModel.item_code,
            PriceItemModel.valid_from.desc(),
        )
        result = await session.execute(stmt)
        prices = result.scalars().all()

    # Create Excel file
    wb = Workbook()
    ws = wb.active
    ws.title = "Prices"

    # Header row
    headers = [
        "Vendor ID",
        "Item Code",
        "SKU",
        "Description",
        "Classification",
        "Unit",
        "Unit Price",
        "Currency",
        "VAT Rate",
        "Region",
        "Width (mm)",
        "Height (mm)",
        "DN (mm)",
        "Angle (°)",
        "Material",
        "Valid From",
        "Valid To",
        "Is Current",
        "Source",
        "Last Updated",
    ]
    ws.append(headers)

    # Style header
    for cell in ws[1]:
        cell.font = Font(bold=True)
        cell.alignment = Alignment(horizontal="center")

    # Data rows
    for price in prices:
        ws.append(
            [
                price.vendor_id or "",
                price.item_code,
                price.sku,
                price.description,
                price.classification_code,
                price.unit,
                float(price.unit_price),
                price.currency,
                float(price.vat_rate) if price.vat_rate else "",
                price.region,
                price.width_mm or "",
                price.height_mm or "",
                price.dn_mm or "",
                price.angle_deg or "",
                price.material or "",
                price.valid_from.strftime("%Y-%m-%d") if price.valid_from else "",
                price.valid_to.strftime("%Y-%m-%d") if price.valid_to else "",
                "Yes" if price.is_current else "No",
                price.source_name,
                price.last_updated.strftime("%Y-%m-%d %H:%M")
                if price.last_updated
                else "",
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
    filters_str = f"_{'current' if current_only else 'history'}"
    if search:
        filters_str += f"_search-{search[:10]}"
    if vendor:
        filters_str += f"_vendor-{vendor}"
    filename = (
        f"prices_{org_id}{filters_str}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    )
    return StreamingResponse(
        output,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@router.get("/prices/{price_id}", response_class=HTMLResponse)
async def price_detail(
    price_id: UUID,
    request: Request,
    org: str | None = None,
    project: str | None = None,
    templates=Depends(get_templates),
):
    """View price details including SCD Type-2 history.

    Shows detailed information for a single price and its historical versions.

    Extracted from: app_enhanced.py:1158
    """
    org_id, project_id = get_org_project(request, org, project)

    async with get_session() as session:
        # Get the specific price
        result = await session.execute(
            select(PriceItemModel).where(
                PriceItemModel.id == price_id,
                PriceItemModel.org_id == org_id,
            )
        )
        price = result.scalar_one_or_none()

        if not price:
            return templates.TemplateResponse(
                "error.html",
                {
                    "request": request,
                    "message": "Price not found",
                    "org_id": org_id,
                    "project_id": project_id,
                },
                status_code=404,
            )

        # Get price history (all versions of this item_code + region)
        history_result = await session.execute(
            select(PriceItemModel)
            .where(
                PriceItemModel.org_id == org_id,
                PriceItemModel.item_code == price.item_code,
                PriceItemModel.region == price.region,
            )
            .order_by(PriceItemModel.valid_from.desc())
        )
        price_history_list = history_result.scalars().all()

    return templates.TemplateResponse(
        "price_detail.html",
        {
            "request": request,
            "price": price,
            "price_history": price_history_list,
            "org_id": org_id,
            "project_id": project_id,
        },
    )
