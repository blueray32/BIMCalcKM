"""Scenario planning routes for BIMCalc web UI.

Extracted from app_enhanced.py as part of Phase 3.12 web refactor.
Handles scenario comparison, vendor analysis, and exports.

Routes:
- GET  /scenarios              - Scenario planning dashboard page
- GET  /api/scenarios/compare  - Compare costs across multiple vendors
- GET  /api/scenarios/export   - Export scenario comparison to Excel
"""

from __future__ import annotations

from datetime import datetime
from typing import List

from fastapi import APIRouter, Depends, Query, Request, Response
from fastapi.responses import HTMLResponse

from bimcalc.db.connection import get_session
from bimcalc.web.dependencies import get_org_project, get_templates

# Create router with scenarios tag
router = APIRouter(tags=["scenarios"])


# ============================================================================
# Scenarios Routes
# ============================================================================

@router.get("/scenarios", response_class=HTMLResponse)
async def scenario_page(
    request: Request,
    org: str | None = None,
    project: str | None = None,
    templates=Depends(get_templates),
):
    """Scenario planning dashboard.

    Shows scenario comparison interface for analyzing vendor options.

    Extracted from: app_enhanced.py:691
    """
    org_id, project_id = get_org_project(request, org, project)

    return templates.TemplateResponse(
        "scenario.html",
        {
            "request": request,
            "org_id": org_id,
            "project_id": project_id,
        },
    )


@router.get("/api/scenarios/compare")
async def compare_scenarios(
    org: str = Query(...),
    project: str = Query(...),
    vendors: List[str] = Query(default=[]),
):
    """Compare costs across multiple vendors.

    If no vendors specified, returns top 3 available vendors.
    Computes cost, coverage, and match statistics for each vendor.

    Extracted from: app_enhanced.py:709
    """
    from bimcalc.reporting.scenario import compute_vendor_scenario, get_available_vendors

    async with get_session() as session:
        # If no vendors specified, fetch top 3 available
        target_vendors = vendors
        if not target_vendors:
            available = await get_available_vendors(session, org)
            target_vendors = available[:3]

        scenarios = []
        for vendor in target_vendors:
            scenario = await compute_vendor_scenario(session, org, project, vendor)
            scenarios.append({
                "vendor": scenario.vendor_name,
                "total_cost": scenario.total_cost,
                "coverage": scenario.coverage_percent,
                "matched": scenario.matched_items,
                "missing": scenario.missing_items
            })

        return {
            "scenarios": scenarios,
            "all_vendors": await get_available_vendors(session, org)
        }


@router.get("/api/scenarios/export")
async def export_scenarios(
    org: str = Query(...),
    project: str = Query(...),
    vendors: List[str] = Query(default=None),
):
    """Export scenario comparison to Excel.

    Generates Excel file with detailed vendor comparison including:
    - Total costs per vendor
    - Coverage percentages
    - Matched and missing items
    - Line item details

    Extracted from: app_enhanced.py:627
    """
    from bimcalc.reporting.export import export_scenario_to_excel
    from bimcalc.reporting.scenario import compute_vendor_scenario, get_available_vendors

    async with get_session() as session:
        # Reuse logic from compare endpoint
        available_vendors = await get_available_vendors(session, org)

        selected_vendors = vendors if vendors else available_vendors[:3]

        comparisons = []
        for vendor in selected_vendors:
            result = await compute_vendor_scenario(session, org, project, vendor)
            comparisons.append(result)

        # Convert dataclasses to dict for export
        dict_comparisons = []
        for c in comparisons:
            dict_comparisons.append({
                "vendor_name": c.vendor_name,
                "total_cost": c.total_cost,
                "coverage_percent": c.coverage_percent,
                "matched_items_count": c.matched_items_count,
                "missing_items_count": c.missing_items_count,
                "details": [
                    {
                        "item_family": m.item.family,
                        "item_type": m.item.type_name,
                        "quantity": float(m.item.quantity) if m.item.quantity else 0,
                        "unit": m.item.unit,
                        "unit_price": float(m.price.unit_price) if m.price else 0,
                        "line_total": float(m.line_total),
                        "status": "matched"
                    } for m in c.matched_items
                ]
            })

        excel_file = export_scenario_to_excel({"comparisons": dict_comparisons}, org, project)

        filename = f"scenario_comparison_{org}_{project}_{datetime.now().strftime('%Y%m%d')}.xlsx"

        return Response(
            content=excel_file.getvalue(),
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
