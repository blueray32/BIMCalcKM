"""Pipeline management routes for BIMCalc web UI.

Extracted from app_enhanced.py as part of Phase 3.10 web refactor.
Handles pipeline dashboard, manual execution, and source configuration.

Routes:
- GET  /pipeline         - Pipeline status and management dashboard
- POST /pipeline/run     - Manually trigger pipeline run
- GET  /pipeline/sources - Get configured pipeline sources
"""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse
from sqlalchemy import func, select

from bimcalc.db.connection import get_session
from bimcalc.db.models import DataSyncLogModel, IngestLogModel
from bimcalc.pipeline.config_loader import load_pipeline_config
from bimcalc.pipeline.orchestrator import PipelineOrchestrator
from bimcalc.reporting.progress import compute_progress_metrics
from bimcalc.web.dependencies import get_org_project, get_templates

# Create router with pipeline tag
router = APIRouter(tags=["pipeline"])


# ============================================================================
# Pipeline Management Routes
# ============================================================================


@router.get("/pipeline", response_class=HTMLResponse)
async def pipeline_dashboard(
    request: Request,
    org: str | None = None,
    project: str | None = None,
    page: int = Query(default=1, ge=1),
    templates=Depends(get_templates),
):
    """Pipeline status and management dashboard.

    Shows pipeline run history with pagination and summary statistics.

    Extracted from: app_enhanced.py:787
    """
    org_id, project_id = get_org_project(request, org, project)
    per_page = 20
    offset = (page - 1) * per_page

    async with get_session() as session:
        # Get pipeline run history
        stmt = (
            select(DataSyncLogModel)
            .order_by(DataSyncLogModel.run_timestamp.desc())
            .limit(per_page)
            .offset(offset)
        )
        result = await session.execute(stmt)
        pipeline_runs = result.scalars().all()

        # Get total count
        count_result = await session.execute(
            select(func.count()).select_from(DataSyncLogModel)
        )
        total = count_result.scalar_one()

        # Get summary statistics
        success_result = await session.execute(
            select(func.count())
            .select_from(DataSyncLogModel)
            .where(DataSyncLogModel.status == "SUCCESS")
        )
        success_count = success_result.scalar_one()

        failed_result = await session.execute(
            select(func.count())
            .select_from(DataSyncLogModel)
            .where(DataSyncLogModel.status == "FAILED")
        )
        failed_count = failed_result.scalar_one()

        # Get last run timestamp
        last_run_result = await session.execute(
            select(DataSyncLogModel.run_timestamp)
            .order_by(DataSyncLogModel.run_timestamp.desc())
            .limit(1)
        )
        last_run = last_run_result.scalar_one_or_none()

    return templates.TemplateResponse(
        "pipeline.html",
        {
            "request": request,
            "pipeline_runs": pipeline_runs,
            "org_id": org_id,
            "project_id": project_id,
            "page": page,
            "per_page": per_page,
            "total": total,
            "total_pages": (total + per_page - 1) // per_page,
            "success_count": success_count,
            "failed_count": failed_count,
            "last_run": last_run,
        },
    )


@router.post("/pipeline/run")
async def run_pipeline_manual():
    """Manually trigger pipeline run.

    Loads pipeline configuration and executes all enabled data sources.

    Extracted from: app_enhanced.py:857
    """
    try:
        # Load configuration
        config_path = (
            Path(__file__).parent.parent.parent / "config" / "pipeline_sources.yaml"
        )

        if not config_path.exists():
            return JSONResponse(
                status_code=400,
                content={
                    "success": False,
                    "message": f"Configuration file not found: {config_path}",
                },
            )

        importers = load_pipeline_config(config_path)

        if not importers:
            return JSONResponse(
                status_code=400,
                content={
                    "success": False,
                    "message": "No enabled data sources configured",
                },
            )

        # Run pipeline
        orchestrator = PipelineOrchestrator(importers)
        summary = await orchestrator.run()

        return {
            "success": summary["overall_success"],
            "message": f"Pipeline completed: {summary['successful_sources']}/{summary['total_sources']} sources successful",
            "details": summary,
        }

    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"success": False, "message": str(e)},
        )


@router.get("/pipeline/sources")
async def get_pipeline_sources():
    """Get configured pipeline sources.

    Returns list of configured data sources with their configuration.

    Extracted from: app_enhanced.py:895
    """
    try:
        config_path = (
            Path(__file__).parent.parent.parent / "config" / "pipeline_sources.yaml"
        )

        if not config_path.exists():
            return JSONResponse(
                status_code=404,
                content={
                    "success": False,
                    "message": f"Configuration file not found: {config_path}",
                },
            )

        importers = load_pipeline_config(config_path)
        sources = [
            {
                "name": imp.source_name,
                "type": imp.__class__.__name__,
                "config": imp.config,
            }
            for imp in importers
        ]
        return {"success": True, "sources": sources}
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"success": False, "message": str(e)},
        )


@router.get("/api/pipeline/status")
async def get_pipeline_status(
    org: str = Query(...),
    project: str = Query(...),
):
    """Get current pipeline operation status for monitoring.

    Returns status of:
    - Matching operations (running, completed, failed)
    - Report generation
    - Last ingest time
    - Progress metrics

    Extracted from: app_enhanced.py:279
    """

    async with get_session() as session:
        # Get progress metrics
        metrics = await compute_progress_metrics(session, org, project)

        # Get last ingest from ingest_logs table
        last_ingest_query = (
            select(IngestLogModel)
            .where(
                IngestLogModel.org_id == org,
                IngestLogModel.project_id == project,
                IngestLogModel.status == "completed",
            )
            .order_by(IngestLogModel.started_at.desc())
            .limit(1)
        )
        last_ingest = (await session.execute(last_ingest_query)).scalar_one_or_none()

        # Build status response
        status = {
            "project": {
                "org_id": org,
                "project_id": project,
            },
            "pipeline": {
                "overall_status": metrics.overall_status,
                "overall_completion": float(metrics.overall_completion),
            },
            "matching": {
                "status": "completed"
                if metrics.stage_matching.status == "completed"
                else "in_progress",
                "progress": f"{metrics.matched_items}/{metrics.total_items} items",
                "completion_percent": float(metrics.stage_matching.completion_percent),
                "auto_approved": metrics.auto_approved,
                "pending_review": metrics.pending_review,
            },
            "review": {
                "status": metrics.stage_review.status,
                "completion_percent": float(metrics.stage_review.completion_percent),
                "critical_flags": metrics.flagged_critical,
                "advisory_flags": metrics.flagged_advisory,
            },
            "last_ingest": {
                "timestamp": last_ingest.started_at.isoformat()
                if last_ingest
                else None,
                "filename": last_ingest.filename if last_ingest else None,
                "items_total": last_ingest.items_total if last_ingest else 0,
            }
            if last_ingest
            else None,
            "computed_at": metrics.computed_at.isoformat(),
        }

        return JSONResponse(content=status)
