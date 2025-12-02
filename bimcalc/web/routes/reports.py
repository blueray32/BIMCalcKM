"""Reports routes for BIMCalc web UI.

Extracted from app_enhanced.py as part of Phase 3.8 web refactor.
Handles report generation, executive dashboard, and statistics.

Routes:
- GET /reports              - Reports page with optional executive view
- GET /reports/generate     - Generate and download financial reports
- GET /reports/statistics   - Project statistics dashboard

Note: There was a duplicate /reports/generate route in the original code (lines 802 and 837).
The second route (generate_report_endpoint) has been commented out as it conflicts with the first.
This appears to be a bug that needs resolution.
"""

from __future__ import annotations

import io
from datetime import datetime

import pandas as pd
from fastapi import APIRouter, HTTPException, Query, Request, Response
from fastapi.responses import HTMLResponse, StreamingResponse

from bimcalc.db.connection import get_session
from bimcalc.db.models import ItemModel, MatchResultModel
from bimcalc.reporting.builder import generate_report
from bimcalc.web.dependencies import get_org_project, get_templates
from sqlalchemy import func, select
from fastapi import Depends

# Create router with reports tag
router = APIRouter(tags=["reports"])


# ============================================================================
# Reports Routes
# ============================================================================

@router.get("/reports", response_class=HTMLResponse)
async def reports_page(
    request: Request,
    org: str | None = None,
    project: str | None = None,
    view: str | None = Query(default=None),
    templates=Depends(get_templates),
):
    """Reports page with optional executive view.

    Supports two views:
    - view=executive: Financial summary dashboard for stakeholders
    - (default): Report generation page

    Extracted from: app_enhanced.py:758
    """
    org_id, project_id = get_org_project(request, org, project)

    # Executive view: Show financial metrics dashboard
    if view == "executive":
        from bimcalc.reporting.financial_metrics import compute_financial_metrics

        async with get_session() as session:
            metrics = await compute_financial_metrics(session, org_id, project_id)

        return templates.TemplateResponse(
            "reports_executive.html",
            {
                "request": request,
                "metrics": metrics,
                "org_id": org_id,
                "project_id": project_id,
            },
        )

    # Default view: Report generation page
    return templates.TemplateResponse(
        "reports.html",
        {
            "request": request,
            "org_id": org_id,
            "project_id": project_id,
        },
    )


@router.get("/reports/generate")
async def generate_report_download(
    request: Request,
    org: str | None = None,
    project: str | None = None,
    format: str = Query("xlsx", pattern="^(xlsx|pdf|csv)$"),
    as_of: str | None = Query(None),
):
    """Generate and download financial reports.

    Extracted from: app_enhanced.py:802
    """
    from bimcalc.reporting.financial_metrics import compute_financial_metrics
    from bimcalc.reporting.export_utils import export_reports_to_excel, export_reports_to_pdf

    org_id, project_id = get_org_project(request, org, project)

    # TODO: Handle as_of timestamp for temporal reporting (SCD2)
    # For now, we use current state as per existing logic

    async with get_session() as session:
        metrics = await compute_financial_metrics(session, org_id, project_id)

    if format == "pdf":
        content = export_reports_to_pdf(metrics, org_id, project_id)
        media_type = "application/pdf"
        filename = f"financial_report_{org_id}_{project_id}_{datetime.now().strftime('%Y%m%d')}.pdf"
    else:
        content = export_reports_to_excel(metrics, org_id, project_id)
        media_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        filename = f"financial_report_{org_id}_{project_id}_{datetime.now().strftime('%Y%m%d')}.xlsx"

    headers = {
        "Content-Disposition": f"attachment; filename={filename}"
    }

    return Response(content=content, media_type=media_type, headers=headers)


# TODO: DUPLICATE ROUTE - This conflicts with the route above
# The original app_enhanced.py had two @app.get("/reports/generate") routes (lines 802 and 837)
# This is a bug - FastAPI will only register one of them
# Commenting out for now - needs investigation to determine correct behavior
#
# @router.get("/reports/generate")
# async def generate_report_endpoint(
#     org: str = Query(...),
#     project: str = Query(...),
#     as_of: str | None = Query(default=None),
#     format: str = Query(default="csv"),
# ):
#     """Generate and download cost report."""
#     as_of_dt = datetime.fromisoformat(as_of) if as_of else datetime.utcnow()
#
#     async with get_session() as session:
#         df = await generate_report(session, org, project, as_of_dt)
#
#     if df.empty:
#         raise HTTPException(status_code=404, detail="No data found for report")
#
#     # Generate filename
#     timestamp = as_of_dt.strftime("%Y%m%d_%H%M%S")
#     filename = f"bimcalc_report_{project}_{timestamp}.{format}"
#
#     if format == "xlsx":
#         # Export to Excel
#         output = io.BytesIO()
#         with pd.ExcelWriter(output, engine='openpyxl') as writer:
#             df.to_excel(writer, index=False, sheet_name='Cost Report')
#         output.seek(0)
#
#         return StreamingResponse(
#             output,
#             media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
#             headers={"Content-Disposition": f"attachment; filename={filename}"},
#         )
#     else:
#         # Export to CSV
#         csv_content = df.to_csv(index=False)
#
#         return StreamingResponse(
#             io.StringIO(csv_content),
#             media_type="text/csv",
#             headers={"Content-Disposition": f"attachment; filename={filename}"},
#         )


@router.get("/reports/statistics", response_class=HTMLResponse)
async def statistics_page(
    request: Request,
    org: str | None = None,
    project: str | None = None,
    templates=Depends(get_templates),
):
    """Project statistics dashboard.

    Extracted from: app_enhanced.py:880
    """
    org_id, project_id = get_org_project(request, org, project)

    async with get_session() as session:
        # Get match statistics
        match_stats_result = await session.execute(
            select(
                MatchResultModel.decision,
                func.count().label("count"),
                func.avg(MatchResultModel.confidence_score).label("avg_confidence"),
            )
            .join(ItemModel, ItemModel.id == MatchResultModel.item_id)
            .where(
                ItemModel.org_id == org_id,
                ItemModel.project_id == project_id,
            )
            .group_by(MatchResultModel.decision)
        )
        match_stats = match_stats_result.all()

        # Get cost summary from latest report
        df = await generate_report(session, org_id, project_id, datetime.utcnow())

        if not df.empty:
            total_items = len(df)
            matched_items = df["sku"].notna().sum()
            total_net = df["total_net"].sum()
            total_gross = df["total_gross"].sum()
        else:
            total_items = matched_items = total_net = total_gross = 0

    return templates.TemplateResponse(
        "statistics.html",
        {
            "request": request,
            "org_id": org_id,
            "project_id": project_id,
            "match_stats": match_stats,
            "total_items": total_items,
            "matched_items": matched_items,
            "total_net": total_net,
            "total_gross": total_gross,
        },
    )
