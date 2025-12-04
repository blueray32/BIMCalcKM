"""Dashboard routes for BIMCalc web UI.

Extracted from app_enhanced.py as part of Phase 3.2 web refactor.
Handles main dashboard, progress tracking, and progress export.

Routes:
- GET  /                - Main dashboard with navigation and statistics
- GET  /progress        - Progress tracking dashboard
- GET  /progress/export - Export progress metrics to Excel
"""

from __future__ import annotations

import os
from datetime import datetime
from io import BytesIO

import pandas as pd
from fastapi import APIRouter, Depends, Query, Request, Response
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import func, select, text

from bimcalc.db.connection import get_session
from bimcalc.db.models import ItemMappingModel, ItemModel, PriceItemModel, ProjectModel
from bimcalc.web.auth import require_auth
from bimcalc.web.dependencies import get_org_project, get_templates

# Check if auth is enabled from environment
AUTH_ENABLED = os.getenv("BIMCALC_AUTH_ENABLED", "false").lower() == "true"

# Create router with dashboard tag
router = APIRouter(tags=["dashboard"])


# ============================================================================
# Dashboard Routes
# ============================================================================

@router.get("/", response_class=HTMLResponse)
async def dashboard(
    request: Request,
    org: str | None = None,
    project: str | None = None,
    view: str | None = Query(default=None),
    username: str = Depends(require_auth) if AUTH_ENABLED else None,
    templates = Depends(get_templates),
):
    """Main dashboard with navigation and statistics.

    Supports multiple views:
    - view=analytics: Analytics dashboard
    - view=reports: Report builder
    - view=executive: Unified executive command center with health score
    - (default): Standard dashboard with quick actions

    Extracted from: app_enhanced.py:202
    """
    # Auto-redirect: If no project specified, redirect to most recent project
    if project is None:
        async with get_session() as session:
            # Find most recent project
            stmt = select(ProjectModel).order_by(ProjectModel.created_at.desc()).limit(1)
            result = await session.execute(stmt)
            latest_project = result.scalar_one_or_none()
            
            if latest_project:
                # Redirect to same URL but with org/project params
                # Preserve view param if present
                url = f"/?org={latest_project.org_id}&project={latest_project.project_id}"
                if view:
                    url += f"&view={view}"
                return RedirectResponse(url=url)

    org_id, project_id = get_org_project(request, org, project)

    # Analytics view
    if view == "analytics":
        return templates.TemplateResponse(
            "dashboard_analytics.html",
            {
                "request": request,
                "org_id": org_id,
                "project_id": project_id,
            },
        )

    # Report Builder view
    if view == "reports":
        return templates.TemplateResponse(
            "report_builder.html",
            {
                "request": request,
                "org_id": org_id,
                "project_id": project_id,
            },
        )

    # Executive view: Show unified command center
    if view == "executive":
        from bimcalc.reporting.dashboard_metrics import compute_dashboard_metrics

        async with get_session() as session:
            metrics = await compute_dashboard_metrics(session, org_id, project_id)

        return templates.TemplateResponse(
            "dashboard_executive.html",
            {
                "request": request,
                "metrics": metrics,
                "org_id": org_id,
                "project_id": project_id,
            },
        )

    # Default view: Standard dashboard
    async with get_session() as session:
        # Get statistics
        items_result = await session.execute(
            select(func.count()).select_from(ItemModel).where(
                ItemModel.org_id == org_id,
                ItemModel.project_id == project_id,
            )
        )
        items_count = items_result.scalar_one()

        prices_result = await session.execute(
            select(func.count()).select_from(PriceItemModel).where(
                PriceItemModel.org_id == org_id,
                PriceItemModel.is_current == True
            )
        )
        prices_count = prices_result.scalar_one()

        mappings_result = await session.execute(
            select(func.count()).select_from(ItemMappingModel).where(
                ItemMappingModel.org_id == org_id,
                ItemMappingModel.end_ts.is_(None),
            )
        )
        mappings_count = mappings_result.scalar_one()

        # Count DISTINCT items with latest decision = manual-review
        review_query = text("""
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
        review_result = await session.execute(
            review_query, {"org_id": org_id, "project_id": project_id}
        )
        review_count = review_result.scalar_one()

    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "org_id": org_id,
            "project_id": project_id,
            "items_count": items_count,
            "prices_count": prices_count,
            "mappings_count": mappings_count,
            "review_count": review_count,
        },
    )


# ============================================================================
# Progress Tracking Routes
# ============================================================================

@router.get("/progress", response_class=HTMLResponse)
async def progress_dashboard(
    request: Request,
    org: str | None = None,
    project: str | None = None,
    view: str | None = Query(default="standard"),  # standard or executive
    username: str = Depends(require_auth) if AUTH_ENABLED else None,
    templates = Depends(get_templates),
):
    """Progress tracking dashboard for cost estimation workflow.

    Args:
        view: "standard" for detailed view, "executive" for stakeholder presentation

    Extracted from: app_enhanced.py:323
    """
    from bimcalc.reporting.progress import compute_progress_metrics

    org_id, project_id = get_org_project(request, org, project)

    async with get_session() as session:
        metrics = await compute_progress_metrics(session, org_id, project_id)

    # Choose template based on view mode
    template_name = "progress_executive.html" if view == "executive" else "progress.html"

    return templates.TemplateResponse(
        template_name,
        {
            "request": request,
            "org_id": org_id,
            "project_id": project_id,
            "metrics": metrics,
            "view_mode": view,
        },
    )


@router.get("/progress/export")
async def progress_export(
    request: Request,
    org: str | None = None,
    project: str | None = None,
):
    """Export progress metrics to Excel.

    Extracted from: app_enhanced.py:359
    """
    from bimcalc.reporting.progress import compute_progress_metrics

    org_id, project_id = get_org_project(request, org, project)

    async with get_session() as session:
        metrics = await compute_progress_metrics(session, org_id, project_id)

    # Create Excel file
    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        # Summary Sheet
        summary_data = [
            {"Metric": "Project", "Value": project_id},
            {"Metric": "Organization", "Value": org_id},
            {"Metric": "Generated At", "Value": datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")},
            {"Metric": "Overall Completion", "Value": f"{metrics.overall_completion:.1f}%"},
            {"Metric": "Total Items", "Value": metrics.total_items},
            {"Metric": "Matched Items", "Value": metrics.matched_items},
            {"Metric": "Pending Review", "Value": metrics.pending_review},
            {"Metric": "Critical Flags", "Value": metrics.flagged_critical},
        ]
        pd.DataFrame(summary_data).to_excel(writer, sheet_name="Summary", index=False)

        # Classification Breakdown
        if metrics.classification_coverage:
            class_data = [
                {
                    "Code": c.code,
                    "Total": c.total,
                    "Matched": c.matched,
                    "Coverage %": f"{c.percent:.1f}%"
                }
                for c in metrics.classification_coverage
            ]
            pd.DataFrame(class_data).to_excel(writer, sheet_name="Classifications", index=False)

    output.seek(0)
    filename = f"progress_{org_id}_{project_id}_{datetime.now().strftime('%Y%m%d')}.xlsx"

    headers = {
        "Content-Disposition": f"attachment; filename={filename}"
    }

    return Response(
        content=output.getvalue(),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers=headers
    )
