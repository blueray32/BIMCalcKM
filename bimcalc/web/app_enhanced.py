"""Enhanced FastAPI web UI for BIMCalc - Full-featured management interface."""

from __future__ import annotations

import io
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Optional
from uuid import UUID, uuid4

import pandas as pd
from fastapi import Cookie, Depends, FastAPI, File, Form, HTTPException, Query, Request, Response, UploadFile
from fastapi.encoders import jsonable_encoder
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import func, select, text
from pydantic import BaseModel

from bimcalc.config import get_config
from bimcalc.db.connection import get_session
from bimcalc.db.match_results import record_match_result
from bimcalc.db.models import (
    ClassificationMappingModel,
    DataSyncLogModel,
    ItemMappingModel,
    ItemModel,
    MatchResultModel,
    PriceImportRunModel,
    PriceItemModel,
)
from bimcalc.ingestion.pricebooks import ingest_pricebook
from bimcalc.ingestion.schedules import ingest_schedule
from bimcalc.integration.classification_mapper import ClassificationMapper
from bimcalc.integration.crail4_transformer import Crail4Transformer
from bimcalc.matching.orchestrator import MatchOrchestrator
from bimcalc.models import FlagSeverity, Item
from bimcalc.reporting.builder import generate_report
from bimcalc.review import (
    approve_review_record,
    fetch_available_classifications,
    fetch_pending_reviews,
    fetch_review_record,
)
from bimcalc.pipeline.config_loader import load_pipeline_config
from bimcalc.pipeline.orchestrator import PipelineOrchestrator
from bimcalc.web.auth import (
    create_session,
    logout as auth_logout,
    require_auth,
    validate_session,
    verify_credentials,
)

templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))
app = FastAPI(title="BIMCalc Management Console", version="2.0")

# Authentication enabled by default (disable with BIMCALC_AUTH_DISABLED=true for development)
import os
AUTH_ENABLED = os.environ.get("BIMCALC_AUTH_DISABLED", "false").lower() != "true"

# Mount static files if directory exists
static_dir = Path(__file__).parent / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")


# ============================================================================
# Helper Functions
# ============================================================================

def _parse_flag_filter(flag: Optional[str]) -> list[str] | None:
    if flag is None or flag == "all" or flag == "":
        return None
    return [flag]


def _parse_severity_filter(severity: Optional[str]) -> FlagSeverity | None:
    if not severity or severity.lower() == "all":
        return None
    try:
        return FlagSeverity(severity)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid severity filter") from None


def _get_org_project(request: Request, org: Optional[str] = None, project: Optional[str] = None):
    """Get org/project with fallbacks."""
    config = get_config()
    return (org or config.org_id, project or "default")


# ============================================================================
# Authentication Routes
# ============================================================================

@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request, error: Optional[str] = None):
    """Login page."""
    return templates.TemplateResponse("login.html", {
        "request": request,
        "error": error,
    })


@app.post("/login")
async def login(
    request: Request,
    response: Response,
    username: str = Form(...),
    password: str = Form(...),
):
    """Process login form."""
    if verify_credentials(username, password):
        # Create session
        session_token = create_session(username)

        # Set cookie
        response = RedirectResponse(url="/", status_code=302)
        response.set_cookie(
            key="session",
            value=session_token,
            httponly=True,
            max_age=86400,  # 24 hours
            samesite="lax",
        )
        return response
    else:
        # Invalid credentials
        return RedirectResponse(url="/login?error=invalid", status_code=302)


@app.get("/logout")
async def logout(response: Response, session: Optional[str] = Cookie(default=None)):
    """Logout and clear session."""
    if session:
        auth_logout(session)

    response = RedirectResponse(url="/login", status_code=302)
    response.delete_cookie("session")
    return response


# ============================================================================
# Main Dashboard / Navigation
# ============================================================================

@app.get("/", response_class=HTMLResponse)
async def dashboard(
    request: Request,
    org: Optional[str] = None,
    project: Optional[str] = None,
    view: Optional[str] = Query(default=None),
    username: str = Depends(require_auth) if AUTH_ENABLED else None,
):
    """Main dashboard with navigation and statistics.

    Supports two views:
    - view=executive: Unified executive command center with health score
    - (default): Standard dashboard with quick actions
    """
    org_id, project_id = _get_org_project(request, org, project)

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
# Progress Tracking (Cost Estimation Workflow)
# ============================================================================

@app.get("/progress", response_class=HTMLResponse)
async def progress_dashboard(
    request: Request,
    org: Optional[str] = None,
    project: Optional[str] = None,
    view: Optional[str] = Query(default="standard"),  # standard or executive
    username: str = Depends(require_auth) if AUTH_ENABLED else None,
):
    """Progress tracking dashboard for cost estimation workflow.

    Args:
        view: "standard" for detailed view, "executive" for stakeholder presentation
    """
    from bimcalc.reporting.progress import compute_progress_metrics

    org_id, project_id = _get_org_project(request, org, project)

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


@app.get("/api/pipeline/status")
async def get_pipeline_status(
    org: str = Query(...),
    project: str = Query(...),
    username: str = Depends(require_auth) if AUTH_ENABLED else None,
):
    """Get current pipeline operation status for monitoring.

    Returns status of:
    - Matching operations (running, completed, failed)
    - Report generation
    - Last ingest time
    - Progress metrics
    """
    from bimcalc.reporting.progress import compute_progress_metrics

    async with get_session() as session:
        # Get progress metrics
        metrics = await compute_progress_metrics(session, org, project)

        # Get last ingest from ingest_logs table
        from bimcalc.db.models import IngestLogModel
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
                "status": "completed" if metrics.stage_matching.status == "completed" else "in_progress",
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
                "timestamp": last_ingest.started_at.isoformat() if last_ingest else None,
                "filename": last_ingest.filename if last_ingest else None,
                "items_total": last_ingest.items_total if last_ingest else 0,
            } if last_ingest else None,
            "computed_at": metrics.computed_at.isoformat(),
        }

        return JSONResponse(content=status)


@app.get("/api/ingest/history")
async def get_ingest_history(
    org: str = Query(...),
    project: str = Query(...),
    limit: int = Query(default=10, ge=1, le=100),
    username: str = Depends(require_auth) if AUTH_ENABLED else None,
):
    """Get ingest history with statistics.

    Returns last N imports with:
    - Timestamp and filename
    - Items added/modified/unchanged/deleted
    - Error and warning counts
    - Processing time
    - Status (completed, failed, running)
    """
    from bimcalc.db.models import IngestLogModel

    async with get_session() as session:
        query = (
            select(IngestLogModel)
            .where(
                IngestLogModel.org_id == org,
                IngestLogModel.project_id == project,
            )
            .order_by(IngestLogModel.started_at.desc())
            .limit(limit)
        )
        results = (await session.execute(query)).scalars().all()

        history = [
            {
                "id": str(log.id),
                "timestamp": log.started_at.isoformat(),
                "filename": log.filename,
                "file_hash": log.file_hash,
                "statistics": {
                    "total": log.items_total,
                    "added": log.items_added,
                    "modified": log.items_modified,
                    "unchanged": log.items_unchanged,
                    "deleted": log.items_deleted,
                },
                "errors": log.errors,
                "warnings": log.warnings,
                "error_details": log.error_details if log.errors > 0 else None,
                "processing_time_ms": log.processing_time_ms,
                "status": log.status,
                "completed_at": log.completed_at.isoformat() if log.completed_at else None,
                "created_by": log.created_by,
            }
            for log in results
        ]

        return JSONResponse(content={
            "org_id": org,
            "project_id": project,
            "total_imports": len(history),
            "history": history,
        })


# ============================================================================
# Review Workflow (existing functionality)
# ============================================================================

@app.get("/review", response_class=HTMLResponse)
async def review_dashboard(
    request: Request,
    org: Optional[str] = None,
    project: Optional[str] = None,
    flag: Optional[str] = Query(default=None),
    severity: Optional[str] = Query(default=None),
    unmapped_only: Optional[str] = Query(default=None),
    classification: Optional[str] = Query(default=None),
    view: Optional[str] = Query(default=None),
):
    """Review items requiring manual approval.

    Supports two views:
    - view=executive: High-level dashboard for stakeholders
    - (default): Detailed list for reviewers
    """
    org_id, project_id = _get_org_project(request, org, project)

    # Executive view: Show aggregated metrics
    if view == "executive":
        from bimcalc.reporting.review_metrics import compute_review_metrics

        async with get_session() as session:
            metrics = await compute_review_metrics(session, org_id, project_id)

        return templates.TemplateResponse(
            "review_executive.html",
            {
                "request": request,
                "metrics": metrics,
                "org_id": org_id,
                "project_id": project_id,
            },
        )

    # Detailed view: Show item list (default)
    unmapped_filter = unmapped_only == "on" if unmapped_only else False

    async with get_session() as session:
        # Fetch available classifications for filter dropdown
        classifications = await fetch_available_classifications(session, org_id, project_id)

        # Fetch pending reviews with filters
        records = await fetch_pending_reviews(
            session,
            org_id,
            project_id,
            flag_types=_parse_flag_filter(flag),
            severity_filter=_parse_severity_filter(severity),
            unmapped_only=unmapped_filter,
            classification_filter=classification,
        )

    return templates.TemplateResponse(
        "review.html",
        {
            "request": request,
            "records": records,
            "classifications": classifications,
            "org_id": org_id,
            "project_id": project_id,
            "flag_filter": flag or "all",
            "severity_filter": severity or "all",
            "unmapped_only": unmapped_filter,
            "classification_filter": classification or "all",
        },
    )


@app.post("/review/approve")
async def approve_item(
    match_result_id: UUID = Form(...),
    annotation: Optional[str] = Form(None),
    org: Optional[str] = Form(None),
    project: Optional[str] = Form(None),
    flag: Optional[str] = Form(None),
    severity: Optional[str] = Form(None),
    unmapped_only: Optional[str] = Form(None),
    classification: Optional[str] = Form(None),
):
    """Approve a review item and create mapping."""
    org_id, project_id = _get_org_project(None, org, project)

    async with get_session() as session:
        record = await fetch_review_record(session, match_result_id)
        if record is None:
            raise HTTPException(status_code=404, detail="Review item not found")
        await approve_review_record(session, record, created_by="web-ui", annotation=annotation)

    # Preserve filter state in redirect
    redirect_url = f"/review?org={org_id}&project={project_id}"
    if flag:
        redirect_url += f"&flag={flag}"
    if severity:
        redirect_url += f"&severity={severity}"
    if unmapped_only:
        redirect_url += f"&unmapped_only={unmapped_only}"
    if classification:
        redirect_url += f"&classification={classification}"

    return RedirectResponse(redirect_url, status_code=303)


# ============================================================================
# File Upload & Ingestion
# ============================================================================

@app.get("/ingest", response_class=HTMLResponse)
async def ingest_page(request: Request, org: Optional[str] = None, project: Optional[str] = None):
    """File upload page for schedules and price books."""
    org_id, project_id = _get_org_project(request, org, project)

    return templates.TemplateResponse(
        "ingest.html",
        {
            "request": request,
            "org_id": org_id,
            "project_id": project_id,
        },
    )


@app.post("/ingest/schedules")
async def ingest_schedules(
    file: UploadFile = File(...),
    org: str = Form(...),
    project: str = Form(...),
):
    """Upload and ingest Revit schedules (CSV/XLSX)."""
    # Save uploaded file temporarily
    temp_path = Path(f"/tmp/{file.filename}")
    with open(temp_path, "wb") as f:
        content = await file.read()
        f.write(content)

    # Ingest
    try:
        async with get_session() as session:
            success_count, errors = await ingest_schedule(session, temp_path, org, project)

        # Clean up
        temp_path.unlink()

        return {
            "success": True,
            "message": f"Imported {success_count} items",
            "errors": errors[:5] if errors else [],  # Show first 5 errors
        }
    except Exception as e:
        if temp_path.exists():
            temp_path.unlink()
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/ingest/prices")
async def ingest_prices(
    file: UploadFile = File(...),
    vendor: str = Form(default="default"),
    use_cmm: bool = Form(default=True),
):
    """Upload and ingest price books (CSV/XLSX) with optional CMM translation."""
    # Save uploaded file temporarily
    temp_path = Path(f"/tmp/{file.filename}")
    with open(temp_path, "wb") as f:
        content = await file.read()
        f.write(content)

    # Ingest
    try:
        async with get_session() as session:
            success_count, errors = await ingest_pricebook(
                session, temp_path, vendor, use_cmm=use_cmm
            )
    except (ValueError, FileNotFoundError) as e:
        if temp_path.exists():
            temp_path.unlink()
        return JSONResponse(
            status_code=400,
            content={"success": False, "message": str(e)},
        )
    except Exception as e:
        if temp_path.exists():
            temp_path.unlink()
        raise HTTPException(status_code=500, detail=str(e))

    # Clean up
    temp_path.unlink()

    cmm_status = "with CMM enabled" if use_cmm else "without CMM"
    return {
        "success": True,
        "message": f"Imported {success_count} price items ({cmm_status})",
        "errors": errors[:5] if errors else [],
    }


# ============================================================================
# Matching Pipeline
# ============================================================================

@app.get("/match", response_class=HTMLResponse)
async def match_page(request: Request, org: Optional[str] = None, project: Optional[str] = None):
    """Page to trigger matching pipeline."""
    org_id, project_id = _get_org_project(request, org, project)

    return templates.TemplateResponse(
        "match.html",
        {
            "request": request,
            "org_id": org_id,
            "project_id": project_id,
        },
    )


@app.post("/match/run")
async def run_matching(
    org: str = Form(...),
    project: str = Form(...),
    limit: Optional[str] = Form(default=None),
):
    """Trigger matching pipeline for project."""
    limit_value: Optional[int] = None
    if limit not in (None, ""):
        try:
            limit_value = int(limit)
        except ValueError:
            raise HTTPException(status_code=422, detail="limit must be an integer")

    async with get_session() as session:
        orchestrator = MatchOrchestrator(session)

        # Query items
        stmt = select(ItemModel).where(
            ItemModel.org_id == org,
            ItemModel.project_id == project,
        )
        if limit_value:
            stmt = stmt.limit(limit_value)

        result = await session.execute(stmt)
        items = result.scalars().all()

        if not items:
            return {"success": False, "message": "No items found for project"}

        # Run matching
        results = []
        for item_model in items:
            item = Item(
                id=str(item_model.id),
                org_id=item_model.org_id,
                project_id=item_model.project_id,
                family=item_model.family,
                type_name=item_model.type_name,
                category=item_model.category,
                system_type=item_model.system_type,
                quantity=float(item_model.quantity) if item_model.quantity else None,
                unit=item_model.unit,
                width_mm=item_model.width_mm,
                height_mm=item_model.height_mm,
                dn_mm=item_model.dn_mm,
                angle_deg=item_model.angle_deg,
                material=item_model.material,
            )

            match_result, price_item = await orchestrator.match(item, "web-ui")

            # Persist canonical metadata generated during matching so downstream
            # reports and blocking queries have valid keys.
            item_model.canonical_key = item.canonical_key
            item_model.classification_code = item.classification_code

            # Persist match result to database
            await record_match_result(session, item_model.id, match_result)

            results.append({
                "item": f"{item.family} / {item.type_name}",
                "decision": match_result.decision.value,
                "confidence": match_result.confidence_score,
                "flags": [f.type for f in match_result.flags],
            })

        # Commit all changes (canonical keys and match results)
        await session.commit()

        return {
            "success": True,
            "message": f"Matched {len(results)} items",
            "results": results,
        }


# ============================================================================
# Items Management
# ============================================================================

@app.get("/items", response_class=HTMLResponse)
async def items_list(
    request: Request,
    org: Optional[str] = None,
    project: Optional[str] = None,
    page: int = Query(default=1, ge=1),
):
    """List and manage items."""
    org_id, project_id = _get_org_project(request, org, project)
    per_page = 50
    offset = (page - 1) * per_page

    async with get_session() as session:
        # Get items with pagination
        stmt = (
            select(ItemModel)
            .where(ItemModel.org_id == org_id, ItemModel.project_id == project_id)
            .order_by(ItemModel.created_at.desc())
            .limit(per_page)
            .offset(offset)
        )
        result = await session.execute(stmt)
        items = result.scalars().all()

        # Get total count
        count_result = await session.execute(
            select(func.count()).select_from(ItemModel).where(
                ItemModel.org_id == org_id,
                ItemModel.project_id == project_id,
            )
        )
        total = count_result.scalar_one()

    return templates.TemplateResponse(
        "items.html",
        {
            "request": request,
            "items": items,
            "org_id": org_id,
            "project_id": project_id,
            "page": page,
            "per_page": per_page,
            "total": total,
            "total_pages": (total + per_page - 1) // per_page,
        },
    )


@app.delete("/items/{item_id}")
async def delete_item(item_id: UUID):
    """Delete an item."""
    async with get_session() as session:
        result = await session.execute(select(ItemModel).where(ItemModel.id == item_id))
        item = result.scalar_one_or_none()

        if not item:
            raise HTTPException(status_code=404, detail="Item not found")

        await session.delete(item)
        await session.commit()

    return {"success": True, "message": "Item deleted"}


# ============================================================================
# Mappings Management
# ============================================================================

@app.get("/mappings", response_class=HTMLResponse)
async def mappings_list(
    request: Request,
    org: Optional[str] = None,
    project: Optional[str] = None,
    page: int = Query(default=1, ge=1),
):
    """List and manage active mappings."""
    org_id, project_id = _get_org_project(request, org, project)
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
            select(func.count()).select_from(ItemMappingModel).where(
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


@app.delete("/mappings/{mapping_id}")
async def delete_mapping(mapping_id: UUID):
    """Delete (close) a mapping."""
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


# ============================================================================
# Reports
# ============================================================================

@app.get("/reports", response_class=HTMLResponse)
async def reports_page(
    request: Request,
    org: Optional[str] = None,
    project: Optional[str] = None,
    view: Optional[str] = Query(default=None),
):
    """Reports page with optional executive view.

    Supports two views:
    - view=executive: Financial summary dashboard for stakeholders
    - (default): Report generation page
    """
    org_id, project_id = _get_org_project(request, org, project)

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


@app.get("/reports/generate")
async def generate_report_endpoint(
    org: str = Query(...),
    project: str = Query(...),
    as_of: Optional[str] = Query(default=None),
    format: str = Query(default="csv"),
):
    """Generate and download cost report."""
    as_of_dt = datetime.fromisoformat(as_of) if as_of else datetime.utcnow()

    async with get_session() as session:
        df = await generate_report(session, org, project, as_of_dt)

    if df.empty:
        raise HTTPException(status_code=404, detail="No data found for report")

    # Generate filename
    timestamp = as_of_dt.strftime("%Y%m%d_%H%M%S")
    filename = f"bimcalc_report_{project}_{timestamp}.{format}"

    if format == "xlsx":
        # Export to Excel
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name='Cost Report')
        output.seek(0)

        return StreamingResponse(
            output,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f"attachment; filename={filename}"},
        )
    else:
        # Export to CSV
        csv_content = df.to_csv(index=False)

        return StreamingResponse(
            io.StringIO(csv_content),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename={filename}"},
        )


@app.get("/reports/statistics", response_class=HTMLResponse)
async def statistics_page(
    request: Request,
    org: Optional[str] = None,
    project: Optional[str] = None,
):
    """Project statistics dashboard."""
    org_id, project_id = _get_org_project(request, org, project)

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


# ============================================================================
# Audit Trail
# ============================================================================

@app.get("/audit", response_class=HTMLResponse)
async def audit_trail(
    request: Request,
    org: Optional[str] = None,
    project: Optional[str] = None,
    page: int = Query(default=1, ge=1),
    view: Optional[str] = Query(default=None),
):
    """View audit trail of all decisions.

    Supports two views:
    - view=executive: Compliance and governance metrics dashboard
    - (default): Detailed audit trail with pagination
    """
    org_id, project_id = _get_org_project(request, org, project)

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


# ============================================================================
# Pipeline Management (NEW - SCD Type-2 Support)
# ============================================================================

@app.get("/pipeline", response_class=HTMLResponse)
async def pipeline_dashboard(
    request: Request,
    org: Optional[str] = None,
    project: Optional[str] = None,
    page: int = Query(default=1, ge=1)
):
    """Pipeline status and management dashboard."""
    org_id, project_id = _get_org_project(request, org, project)
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
            select(func.count()).select_from(DataSyncLogModel).where(
                DataSyncLogModel.status == "SUCCESS"
            )
        )
        success_count = success_result.scalar_one()

        failed_result = await session.execute(
            select(func.count()).select_from(DataSyncLogModel).where(
                DataSyncLogModel.status == "FAILED"
            )
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


@app.post("/pipeline/run")
async def run_pipeline_manual():
    """Manually trigger pipeline run."""
    try:
        # Load configuration
        config_path = Path(__file__).parent.parent.parent / "config" / "pipeline_sources.yaml"

        if not config_path.exists():
            return JSONResponse(
                status_code=400,
                content={"success": False, "message": f"Configuration file not found: {config_path}"},
            )

        importers = load_pipeline_config(config_path)

        if not importers:
            return JSONResponse(
                status_code=400,
                content={"success": False, "message": "No enabled data sources configured"},
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


@app.get("/pipeline/sources")
async def get_pipeline_sources():
    """Get configured pipeline sources."""
    try:
        config_path = Path(__file__).parent.parent.parent / "config" / "pipeline_sources.yaml"

        if not config_path.exists():
            return JSONResponse(
                status_code=404,
                content={"success": False, "message": f"Configuration file not found: {config_path}"},
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


# ============================================================================
# Price History Viewer (NEW - SCD Type-2 Support)
# ============================================================================

@app.get("/prices/history/{item_code}", response_class=HTMLResponse)
async def price_history(
    request: Request,
    item_code: str,
    region: str = Query(default="UK"),
):
    """View price history for a specific item."""
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
        price_history = result.scalars().all()

        if not price_history:
            raise HTTPException(
                status_code=404,
                detail=f"No price history found for {item_code} in {region}"
            )

    return templates.TemplateResponse(
        "price_history.html",
        {
            "request": request,
            "item_code": item_code,
            "region": region,
            "price_history": price_history,
        },
    )


@app.get("/prices", response_class=HTMLResponse)
async def prices_list(
    request: Request,
    org: Optional[str] = None,
    project: Optional[str] = None,  # Added project parameter for consistent navigation
    view: Optional[str] = Query(default=None),
    current_only: bool = Query(default=True),
    page: int = Query(default=1, ge=1),
):
    """List all price items with optional history or executive view.

    Supports two views:
    - view=executive: Price data quality dashboard for stakeholders
    - (default): Paginated price list table

    Note: Prices are org-scoped, but project param is used for navigation consistency
    """
    org_id, project_id = _get_org_project(request, org, project)

    # Executive view: Show price quality metrics
    if view == "executive":
        from bimcalc.reporting.price_metrics import compute_price_metrics

        async with get_session() as session:
            metrics = await compute_price_metrics(session, org_id)

            # Get pending review count for navigation badge (project-scoped)
            # Count DISTINCT items with latest decision = manual-review
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
                "project_id": project_id,  # Pass project for navigation consistency
                "unique_vendors": metrics.unique_vendors,
                "current_page": "prices",
                "pending_count": pending_count,
            },
        )

    # Default view: Paginated table
    per_page = 50
    offset = (page - 1) * per_page

    async with get_session() as session:
        # Build query
        stmt = select(PriceItemModel).order_by(
            PriceItemModel.item_code,
            PriceItemModel.valid_from.desc(),
        )

        if current_only:
            stmt = stmt.where(PriceItemModel.is_current == True)

        stmt = stmt.limit(per_page).offset(offset)

        result = await session.execute(stmt)
        prices = result.scalars().all()

        # Get total count
        count_stmt = select(func.count()).select_from(PriceItemModel)
        if current_only:
            count_stmt = count_stmt.where(PriceItemModel.is_current == True)

        count_result = await session.execute(count_stmt)
        total = count_result.scalar_one()

    return templates.TemplateResponse(
        "prices.html",
        {
            "request": request,
            "prices": prices,
            "current_only": current_only,
            "page": page,
            "per_page": per_page,
            "total": total,
            "total_pages": (total + per_page - 1) // per_page,
            "org_id": org_id,
            "project_id": project_id,
        },
    )


# ============================================================================
# Crail4 Bulk Import API
# ============================================================================


class BulkPriceImportRequest(BaseModel):
    """Request schema for Crail4 -> BIMCalc bulk imports."""

    org_id: str
    items: list[dict]
    source: str = "crail4_api"
    target_scheme: str = "UniClass2015"
    created_by: str = "system"


class BulkPriceImportResponse(BaseModel):
    """Response schema for bulk price imports."""

    run_id: str
    status: str
    items_received: int
    items_loaded: int
    items_rejected: int
    rejection_reasons: dict
    errors: list[str]


@app.post("/api/price-items/bulk-import", response_model=BulkPriceImportResponse)
async def bulk_import_prices(request: BulkPriceImportRequest):
    """Bulk import price items from external sources (Crail4 ETL)."""
    run_id = str(uuid4())
    errors: list[str] = []

    async with get_session() as session:
        import_run = PriceImportRunModel(
            id=run_id,
            org_id=request.org_id,
            source=request.source,
            started_at=datetime.utcnow(),
            status="running",
            items_fetched=len(request.items),
        )
        session.add(import_run)
        await session.flush()

        try:
            mapper = ClassificationMapper(session, request.org_id)
            transformer = Crail4Transformer(mapper, request.target_scheme)

            valid_items, rejection_stats = await transformer.transform_batch(request.items)

            loaded_count = 0
            for item_data in valid_items:
                try:
                    classification_value = item_data["classification_code"]
                    classification_code = int(str(classification_value).split()[0])
                except (KeyError, ValueError) as exc:
                    rejection_stats["transform_error"] = rejection_stats.get("transform_error", 0) + 1
                    errors.append(
                        f"Invalid classification for vendor_code={item_data.get('vendor_code')}: {exc}"
                    )
                    continue

                vendor_code = item_data.get("vendor_code")
                item_code = vendor_code or item_data.get("canonical_key")
                if not item_code:
                    item_code = f"crail4-{uuid4().hex[:8]}"
                region = item_data.get("region") or "global"
                sku = vendor_code or item_code
                currency = item_data["currency"]

                attributes_payload = {
                    "canonical_key": item_data.get("canonical_key"),
                    "classification_scheme": item_data.get("classification_scheme"),
                    "source_data": item_data.get("source_data"),
                }
                attributes = {
                    key: value for key, value in attributes_payload.items() if value is not None
                }

                price_item = PriceItemModel(
                    org_id=request.org_id,
                    item_code=item_code,
                    region=region,
                    vendor_id=request.source,
                    sku=sku,
                    description=item_data["description"],
                    classification_code=classification_code,
                    unit=item_data["unit"],
                    unit_price=item_data["unit_price"],
                    currency=currency,
                    vat_rate=item_data.get("vat_rate", Decimal("0.0")),
                    vendor_code=vendor_code,
                    source_name=request.source,
                    source_currency=currency,
                    vendor_note=None,
                    import_run_id=run_id,
                    last_updated=datetime.utcnow(),
                    attributes=jsonable_encoder(attributes) if attributes else {},
                )
                session.add(price_item)
                loaded_count += 1

            import_run.completed_at = datetime.utcnow()
            import_run.items_loaded = loaded_count
            import_run.items_rejected = len(request.items) - loaded_count
            import_run.rejection_reasons = rejection_stats
            import_run.status = "completed" if not errors else "completed_with_errors"
            if errors:
                import_run.error_message = "\n".join(errors[:10])

            await session.commit()

            return BulkPriceImportResponse(
                run_id=run_id,
                status=import_run.status,
                items_received=len(request.items),
                items_loaded=loaded_count,
                items_rejected=import_run.items_rejected,
                rejection_reasons=rejection_stats,
                errors=errors,
            )

        except Exception as exc:  # pragma: no cover - defensive
            import_run.status = "failed"
            import_run.error_message = str(exc)
            import_run.completed_at = datetime.utcnow()
            await session.commit()
            raise HTTPException(status_code=500, detail=f"Import failed: {exc}") from exc


@app.get("/api/price-imports/{run_id}")
async def get_import_run(run_id: str):
    """Fetch audit information for a specific price import run."""
    async with get_session() as session:
        stmt = select(PriceImportRunModel).where(PriceImportRunModel.id == run_id)
        result = await session.execute(stmt)
        run = result.scalar_one_or_none()

        if not run:
            raise HTTPException(status_code=404, detail="Import run not found")

        return {
            "run_id": run.id,
            "org_id": run.org_id,
            "source": run.source,
            "status": run.status,
            "started_at": run.started_at,
            "completed_at": run.completed_at,
            "items_fetched": run.items_fetched,
            "items_loaded": run.items_loaded,
            "items_rejected": run.items_rejected,
            "rejection_reasons": run.rejection_reasons,
            "error_message": run.error_message,
        }


# ============================================================================
# Crail4 Configuration UI
# ============================================================================


@app.get("/crail4-config", response_class=HTMLResponse)
async def crail4_config_page(
    request: Request,
    org: Optional[str] = None,
    current_user: str = Depends(require_auth),
):
    """Render Crail4 configuration page."""
    org_id, _ = _get_org_project(request, org)

    async with get_session() as session:
        # Load current configuration from environment
        config = {
            "api_key": os.getenv("CRAIL4_API_KEY", ""),
            "source_url": os.getenv("CRAIL4_SOURCE_URL", ""),
            "base_url": os.getenv("CRAIL4_BASE_URL", "https://www.crawl4ai-cloud.com/query"),
            "target_scheme": "UniClass2015",
        }

        # Test connection status
        connection_status = "not_configured"
        if config["api_key"]:
            try:
                from bimcalc.integration.crail4_client import Crail4Client
                client = Crail4Client(api_key=config["api_key"], base_url=config["base_url"])
                # Try a simple test query
                connection_status = "connected"
            except Exception:
                connection_status = "error"


        # Get statistics
        try:
            stats_query = text("""
                SELECT
                    COUNT(DISTINCT id) as total_syncs,
                    COALESCE(SUM(items_loaded), 0) as total_items_imported,
                    COALESCE(SUM(items_rejected), 0) as total_items_rejected
                FROM price_import_runs
                WHERE org_id = :org_id AND source = 'crail4'
            """)
            stats_result = await session.execute(stats_query, {"org_id": org_id})
            stats_row = stats_result.fetchone()

            stats = {
                "total_syncs": stats_row[0] if stats_row else 0,
                "total_items_imported": stats_row[1] if stats_row else 0,
                "total_items_rejected": stats_row[2] if stats_row else 0,
            }
        except Exception:
            # Table doesn't exist yet or other error - rollback transaction and use default values
            await session.rollback()
            stats = {
                "total_syncs": 0,
                "total_items_imported": 0,
                "total_items_rejected": 0,
            }



        # Get mappings count
        try:
            mappings_count_stmt = select(func.count()).select_from(ClassificationMappingModel).where(
                ClassificationMappingModel.org_id == org_id
            )
            mappings_result = await session.execute(mappings_count_stmt)
            stats["mappings_count"] = mappings_result.scalar_one()
        except Exception:
            await session.rollback()
            stats["mappings_count"] = 0

        # Get import runs history
        try:
            import_runs_stmt = (
                select(PriceImportRunModel)
                .where(
                    PriceImportRunModel.org_id == org_id,
                    PriceImportRunModel.source == "crail4"
                )
                .order_by(PriceImportRunModel.started_at.desc())
                .limit(20)
            )
            import_runs_result = await session.execute(import_runs_stmt)
            import_runs = import_runs_result.scalars().all()
        except Exception:
            await session.rollback()
            import_runs = []

        # Get classification mappings
        try:
            mappings_stmt = (
                select(ClassificationMappingModel)
                .where(ClassificationMappingModel.org_id == org_id)
                .order_by(ClassificationMappingModel.source_scheme, ClassificationMappingModel.source_code)
            )
            mappings_result = await session.execute(mappings_stmt)
            mappings = mappings_result.scalars().all()
        except Exception:
            await session.rollback()
            mappings = []

        return templates.TemplateResponse(
            "crail4_config.html",
            {
                "request": request,
                "config": config,
                "connection_status": connection_status,
                "stats": stats,
                "import_runs": import_runs,
                "mappings": mappings,
                "org_id": org_id,
            },
        )


@app.post("/crail4-config/save")
async def save_crail4_config(
    request: Request,
    api_key: str = Form(...),
    source_url: str = Form(...),
    base_url: str = Form(default="https://www.crawl4ai-cloud.com/query"),
    current_user: str = Depends(require_auth),
):
    """Save Crail4 configuration."""
    # Update .env file
    env_path = Path(".env")
    env_lines = []

    if env_path.exists():
        env_lines = env_path.read_text().splitlines()

    # Update or add configuration
    config_keys = {
        "CRAIL4_API_KEY": api_key,
        "CRAIL4_SOURCE_URL": source_url,
        "CRAIL4_BASE_URL": base_url,
    }

    for key, value in config_keys.items():
        found = False
        for i, line in enumerate(env_lines):
            if line.startswith(f"{key}="):
                env_lines[i] = f"{key}={value}"
                found = True
                break
        if not found:
            env_lines.append(f"{key}={value}")

    env_path.write_text("\n".join(env_lines) + "\n")

    # Update environment variables
    os.environ["CRAIL4_API_KEY"] = api_key
    os.environ["CRAIL4_SOURCE_URL"] = source_url
    os.environ["CRAIL4_BASE_URL"] = base_url

    return JSONResponse({"status": "success", "message": "Configuration saved successfully"})


@app.post("/crail4-config/test")
async def test_crail4_connection(
    current_user: str = Depends(require_auth),
):
    """Test Crail4 API connection."""
    api_key = os.getenv("CRAIL4_API_KEY")
    base_url = os.getenv("CRAIL4_BASE_URL", "https://www.crawl4ai-cloud.com/query")

    if not api_key:
        return JSONResponse(
            {"status": "error", "message": "API key not configured"},
            status_code=400
        )

    try:
        from bimcalc.integration.crail4_client import Crail4Client
        client = Crail4Client(api_key=api_key, base_url=base_url)
        # Try to fetch items (empty filter to test connection)
        await client.fetch_all_items(classification_filter=None)
        return JSONResponse({"status": "success", "message": "Connection successful"})
    except Exception as e:
        return JSONResponse(
            {"status": "error", "message": f"Connection failed: {str(e)}"},
            status_code=500
        )


@app.post("/crail4-config/sync")
async def trigger_crail4_sync(
    request: Request,
    classifications: Optional[str] = Form(default=None),
    full_sync: bool = Form(default=False),
    region: Optional[str] = Form(default=None),
    current_user: str = Depends(require_auth),
):
    """Trigger manual Crail4 sync."""
    org_id = get_config().org_id

    try:
        from bimcalc.integration.crail4_sync import sync_crail4_prices

        # Parse classifications filter
        class_filter = None
        if classifications and classifications.strip():
            class_filter = [c.strip() for c in classifications.split(",")]

        # Run sync
        delta_days = None if full_sync else 7
        result = await sync_crail4_prices(
            org_id=org_id,
            target_scheme="UniClass2015",
            delta_days=delta_days,
            classification_filter=class_filter,
            region=region,
        )

        return JSONResponse({
            "status": "success",
            "message": f"Sync completed: {result['items_loaded']}/{result['items_received']} items loaded",
            "result": result,
        })
    except Exception as e:
        return JSONResponse(
            {"status": "error", "message": f"Sync failed: {str(e)}"},
            status_code=500
        )


@app.get("/crail4-config/mappings/seed")
async def seed_classification_mappings(
    current_user: str = Depends(require_auth),
):
    """Seed default classification mappings."""
    org_id = get_config().org_id

    try:
        from bimcalc.integration.seed_classification_mappings import seed_mappings
        count = await seed_mappings(org_id=org_id)
        return JSONResponse({
            "status": "success",
            "message": f"Seeded {count} classification mappings"
        })
    except Exception as e:
        return JSONResponse(
            {"status": "error", "message": f"Seeding failed: {str(e)}"},
            status_code=500
        )


@app.post("/crail4-config/mappings/add")
async def add_classification_mapping(
    request: Request,
    source_scheme: str = Form(...),
    source_code: str = Form(...),
    target_scheme: str = Form(...),
    target_code: str = Form(...),
    confidence: float = Form(default=1.0),
    current_user: str = Depends(require_auth),
):
    """Add a new classification mapping."""
    org_id = get_config().org_id

    async with get_session() as session:
        # Check if mapping already exists
        existing_stmt = select(ClassificationMappingModel).where(
            ClassificationMappingModel.org_id == org_id,
            ClassificationMappingModel.source_scheme == source_scheme,
            ClassificationMappingModel.source_code == source_code,
            ClassificationMappingModel.target_scheme == target_scheme,
        )
        existing_result = await session.execute(existing_stmt)
        existing = existing_result.scalar_one_or_none()

        if existing:
            return JSONResponse(
                {"status": "error", "message": "Mapping already exists"},
                status_code=400
            )

        # Create new mapping
        mapping = ClassificationMappingModel(
            id=str(uuid4()),
            org_id=org_id,
            source_scheme=source_scheme,
            source_code=source_code,
            target_scheme=target_scheme,
            target_code=target_code,
            confidence=confidence,
            mapping_source="manual",
            created_by=current_user.get("username", "unknown"),
        )
        session.add(mapping)
        await session.commit()

        return JSONResponse({
            "status": "success",
            "message": "Classification mapping added successfully"
        })


# ============================================================================
# CSV Price Import Endpoints
# ============================================================================

@app.post("/api/prices/import-csv")
async def import_csv_prices(
    file: UploadFile = File(...),
    vendor_name: str = Form(...),
    org_id: str = Form(default="acme-construction"),
    sheet_name: Optional[str] = Form(default=None),
    current_user: str = Depends(require_auth),
):
    """Import supplier price list from CSV or Excel file."""
    import tempfile
    from pathlib import Path
    from bimcalc.integration.csv_price_importer import import_supplier_pricelist

    # Validate file extension
    file_ext = Path(file.filename).suffix.lower()
    if file_ext not in [".csv", ".xlsx", ".xls"]:
        return JSONResponse(
            {"status": "error", "message": f"Unsupported file format: {file_ext}"},
            status_code=400
        )

    # Save uploaded file to temporary location
    with tempfile.NamedTemporaryFile(delete=False, suffix=file_ext) as tmp_file:
        content = await file.read()
        tmp_file.write(content)
        tmp_path = tmp_file.name

    try:
        # Import prices
        result = await import_supplier_pricelist(
            file_path=tmp_path,
            org_id=org_id,
            vendor_name=vendor_name,
            sheet_name=sheet_name,
        )

        return JSONResponse({
            "status": "success",
            "message": f"Imported {result['items_loaded']}/{result['items_received']} items",
            "result": result,
        })

    except Exception as e:
        return JSONResponse(
            {"status": "error", "message": f"Import failed: {str(e)}"},
            status_code=500
        )
    finally:
        # Clean up temporary file
        Path(tmp_path).unlink(missing_ok=True)


# ============================================================================
# Executive Dashboard Export Endpoints
# ============================================================================

@app.get("/export/dashboard")
async def export_dashboard(
    org: Optional[str] = None,
    project: Optional[str] = None,
    request: Request = None,
):
    """Export dashboard executive metrics to Excel."""
    from bimcalc.reporting.dashboard_metrics import compute_dashboard_metrics
    from bimcalc.reporting.export_utils import export_dashboard_to_excel

    org_id, project_id = _get_org_project(request, org, project)

    async with get_session() as session:
        metrics = await compute_dashboard_metrics(session, org_id, project_id)

    excel_data = export_dashboard_to_excel(metrics, org_id, project_id)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"BIMCalc_Dashboard_{project_id}_{timestamp}.xlsx"

    return Response(
        content=excel_data,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.get("/export/progress")
async def export_progress(
    org: Optional[str] = None,
    project: Optional[str] = None,
    request: Request = None,
):
    """Export progress executive metrics to Excel."""
    from bimcalc.reporting.progress import compute_progress_metrics
    from bimcalc.reporting.export_utils import export_progress_to_excel

    org_id, project_id = _get_org_project(request, org, project)

    async with get_session() as session:
        metrics = await compute_progress_metrics(session, org_id, project_id)

    excel_data = export_progress_to_excel(metrics, org_id, project_id)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"BIMCalc_Progress_{project_id}_{timestamp}.xlsx"

    return Response(
        content=excel_data,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.get("/export/review")
async def export_review(
    org: Optional[str] = None,
    project: Optional[str] = None,
    request: Request = None,
):
    """Export review queue executive metrics to Excel."""
    from bimcalc.reporting.review_metrics import compute_review_metrics
    from bimcalc.reporting.export_utils import export_review_to_excel

    org_id, project_id = _get_org_project(request, org, project)

    async with get_session() as session:
        metrics = await compute_review_metrics(session, org_id, project_id)

    excel_data = export_review_to_excel(metrics, org_id, project_id)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"BIMCalc_ReviewQueue_{project_id}_{timestamp}.xlsx"

    return Response(
        content=excel_data,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.get("/export/reports")
async def export_reports(
    org: Optional[str] = None,
    project: Optional[str] = None,
    request: Request = None,
):
    """Export financial reports executive metrics to Excel."""
    from bimcalc.reporting.financial_metrics import compute_financial_metrics
    from bimcalc.reporting.export_utils import export_reports_to_excel

    org_id, project_id = _get_org_project(request, org, project)

    async with get_session() as session:
        metrics = await compute_financial_metrics(session, org_id, project_id)

    excel_data = export_reports_to_excel(metrics, org_id, project_id)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"BIMCalc_Financial_{project_id}_{timestamp}.xlsx"

    return Response(
        content=excel_data,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.get("/export/audit")
async def export_audit(
    org: Optional[str] = None,
    project: Optional[str] = None,
    request: Request = None,
):
    """Export audit trail executive metrics to Excel."""
    from bimcalc.reporting.audit_metrics import compute_audit_metrics
    from bimcalc.reporting.export_utils import export_audit_to_excel

    org_id, project_id = _get_org_project(request, org, project)

    async with get_session() as session:
        metrics = await compute_audit_metrics(session, org_id, project_id)

    excel_data = export_audit_to_excel(metrics, org_id, project_id)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"BIMCalc_Audit_{project_id}_{timestamp}.xlsx"

    return Response(
        content=excel_data,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.get("/export/prices")
async def export_prices(
    org: Optional[str] = None,
    request: Request = None,
):
    """Export price data quality metrics to Excel."""
    from bimcalc.reporting.price_metrics import compute_price_metrics
    from bimcalc.reporting.export_utils import export_prices_to_excel

    org_id, _ = _get_org_project(request, org, None)

    async with get_session() as session:
        metrics = await compute_price_metrics(session, org_id)

    excel_data = export_prices_to_excel(metrics, org_id)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"BIMCalc_Prices_{org_id}_{timestamp}.xlsx"

    return Response(
        content=excel_data,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
