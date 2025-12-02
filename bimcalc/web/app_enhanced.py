"""Enhanced FastAPI web UI for BIMCalc - Full-featured management interface."""

from __future__ import annotations

import io
import os
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from uuid import UUID, uuid4
from typing import Dict, Optional, List, Any, Literal

import pandas as pd
from fastapi import (
    Cookie,
    Depends,
    FastAPI,
    File,
    Form,
    HTTPException,
    Query,
    Request,
    Response,
    UploadFile,
    Body,
)
from fastapi.encoders import jsonable_encoder
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from sqlalchemy import func, select, text

from bimcalc.config import get_config
from bimcalc.db.connection import get_session, get_db
from bimcalc.db.match_results import record_match_result
from bimcalc.db.models import (
    ClassificationMappingModel,
    DataSyncLogModel,
    ItemMappingModel,
    ItemModel,
    MatchResultModel,
    PriceImportRunModel,
    PriceItemModel,
    DocumentModel,
    DocumentLinkModel,
)
from bimcalc.db.models_intelligence import ComplianceRuleModel, ComplianceResultModel
from bimcalc.intelligence.compliance import extract_rules_from_text, run_compliance_check
from bimcalc.ingestion.pricebooks import ingest_pricebook
from bimcalc.ingestion.schedules import ingest_schedule
from bimcalc.intelligence.notifications import get_email_notifier, get_slack_notifier
from bimcalc.integration.classification_mapper import ClassificationMapper
from bimcalc.integration.crail4_transformer import Crail4Transformer
from bimcalc.matching.orchestrator import MatchOrchestrator
from bimcalc.models import FlagSeverity, Item
from bimcalc.pipeline.config_loader import load_pipeline_config
from bimcalc.pipeline.orchestrator import PipelineOrchestrator
# Removed: from bimcalc.reporting.builder import generate_report (function doesn't exist)
from bimcalc.review import (
    approve_review_record,
    fetch_available_classifications,
    fetch_pending_reviews,
    fetch_review_record,
)
from bimcalc.web.auth import (
    create_session,
    require_auth,
    verify_credentials,
)
from bimcalc.web.auth import (
    logout as auth_logout,
)
from bimcalc.intelligence.routes import router as intelligence_router
from bimcalc.web.routes import auth       # Phase 3.1 - Auth router
from bimcalc.web.routes import dashboard  # Phase 3.2 - Dashboard router
from bimcalc.web.routes import ingestion  # Phase 3.3 - Ingestion router
from bimcalc.web.routes import matching   # Phase 3.4 - Matching router
from bimcalc.web.routes import review     # Phase 3.5 - Review router
from bimcalc.web.routes import items      # Phase 3.6 - Items router

from starlette.middleware.base import BaseHTTPMiddleware
import structlog
from prometheus_fastapi_instrumentator import Instrumentator

from bimcalc.core.logging import configure_logging

# Initialize structured logging
configure_logging()
logger = structlog.get_logger()

templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))

app = FastAPI(
    title="BIMCalc Management Console",
    description="Web interface for managing BIMCalc pricing data",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# Include routers
# Phase 3.1 - Auth router (replaces inline auth routes at lines 149, 183, 192, 219)
app.include_router(auth.router)

# Phase 3.2 - Dashboard router (replaces inline dashboard/progress routes at lines 202, 323, 359)
app.include_router(dashboard.router)

# Phase 3.3 - Ingestion router (replaces inline ingestion routes at lines 515, 848, 863, 918)
app.include_router(ingestion.router)

# Phase 3.4 - Matching router (replaces inline matching routes at lines 863, 878)
app.include_router(matching.router)

# Phase 3.5 - Review router (replaces inline review routes at lines 418, 488, 567)
app.include_router(review.router)

# Phase 3.6 - Items router (replaces inline items routes at lines 732, 822, 930, 973)
app.include_router(items.router)

# Intelligence Features
config = get_config()
if config.enable_rag or config.enable_risk_scoring:
    app.include_router(intelligence_router)

# Prometheus Metrics
Instrumentator().instrument(app).expose(app)

# Request Logging Middleware
class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        structlog.contextvars.clear_contextvars()
        
        request_id = request.headers.get("X-Request-ID", str(uuid4()))
        structlog.contextvars.bind_contextvars(request_id=request_id)
        
        logger.info("request_started", 
            method=request.method, 
            path=request.url.path,
            client_ip=request.client.host
        )
        
        try:
            response = await call_next(request)
            
            logger.info("request_completed",
                status_code=response.status_code,
            )
            return response
            
        except Exception as exc:
            logger.error("request_failed", error=str(exc))
            raise

@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """Handle HTTP exceptions, specifically for redirects."""
    if exc.status_code in [301, 302, 303, 307, 308] and exc.headers and "Location" in exc.headers:
        return RedirectResponse(url=exc.headers["Location"], status_code=exc.status_code)
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail},
    )

app.add_middleware(RequestLoggingMiddleware)
# Authentication enabled by default (disable with BIMCALC_AUTH_DISABLED=true for development)
AUTH_ENABLED = os.environ.get("BIMCALC_AUTH_DISABLED", "false").lower() != "true"

# Mount static files if directory exists
static_dir = Path(__file__).parent / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

# Removed: favicon route - now in auth router (Phase 3.1)
# @app.get("/favicon.ico", include_in_schema=False)
# async def favicon():
#     return Response(status_code=204)


# ============================================================================
# Helper Functions
# ============================================================================

def _parse_flag_filter(flag: str | None) -> list[str] | None:
    if flag is None or flag == "all" or flag == "":
        return None
    return [flag]


def _parse_severity_filter(severity: str | None) -> FlagSeverity | None:
    if not severity or severity.lower() == "all":
        return None
    try:
        return FlagSeverity(severity)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid severity filter") from None


def _get_org_project(request: Request, org: str | None = None, project: str | None = None):
    """Get org/project with fallbacks."""
    config = get_config()
    return (org or config.org_id, project or "default")


# ============================================================================
# Authentication Routes - MOVED TO auth ROUTER (Phase 3.1)
# ============================================================================
# The following routes have been extracted to bimcalc/web/routes/auth.py:
#   - GET  /login       (was line 183)
#   - POST /login       (was line 192)
#   - GET  /logout      (was line 219)
#   - GET  /favicon.ico (was line 149)
#
# Router included above: app.include_router(auth.router)
# ============================================================================


# ============================================================================
# Dashboard Routes - MOVED TO dashboard ROUTER (Phase 3.2)
# ============================================================================
# The following routes have been extracted to bimcalc/web/routes/dashboard.py:
#   - GET  /                (was line 202) - Main dashboard
#   - GET  /progress        (was line 323) - Progress tracking
#   - GET  /progress/export (was line 359) - Progress export
#
# Router included above: app.include_router(dashboard.router)
# ============================================================================


# ============================================================================
# Main Dashboard / Navigation - REMOVED (moved to dashboard router)
# ============================================================================
# The following routes were here (now in dashboard.py):
#   @app.get("/") - Main dashboard
#   @app.get("/progress") - Progress tracking
#   @app.get("/progress/export") - Progress export


# ============================================================================
# API Routes (Pipeline Status)
# ============================================================================

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

@app.get("/api/revisions")
async def get_revisions(
    org: str = Query(...),
    project: str = Query(...),
    item_id: UUID | None = Query(None),
    limit: int = Query(default=50, ge=1, le=100),
    username: str = Depends(require_auth) if AUTH_ENABLED else None,
):
    """Get revision history for items."""
    from bimcalc.db.models import ItemRevisionModel, ItemModel

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

# ============================================================================
# Review Routes - REMOVED (moved to review router)
# ============================================================================
# The following routes were here (now in review.py):
#   @app.get("/review")         - was line 422
#   @app.post("/review/approve") - was line 492
#   @app.post("/review/reject")  - was line 571


# ============================================================================
# Ingestion Routes - MOVED TO ingestion ROUTER (Phase 3.3)
# ============================================================================
# The following routes have been extracted to bimcalc/web/routes/ingestion.py:
#   - GET  /ingest/history  (was line 519) - Ingest history dashboard
#   - GET  /ingest          (was line 848) - File upload page
#   - POST /ingest/schedules (was line 863) - Upload schedules
#   - POST /ingest/prices   (was line 918) - Upload prices
#
# Router included above: app.include_router(ingestion.router)
# ============================================================================


# ============================================================================
# Ingestion Routes - REMOVED (moved to ingestion router)
# ============================================================================
# The following routes were here (now in ingestion.py):
#   @app.get("/ingest/history")  - was line 519
#   @app.get("/ingest")          - was line 848
#   @app.post("/ingest/schedules") - was line 863
#   @app.post("/ingest/prices")  - was line 918


@app.get("/revisions", response_class=HTMLResponse)
async def revisions_page(
    request: Request,
    org: str | None = None,
    project: str | None = None,
):
    """Revision history dashboard."""
    org_id, project_id = _get_org_project(request, org, project)
    return templates.TemplateResponse(
        "revisions.html",
        {
            "request": request,
            "org_id": org_id,
            "project_id": project_id,
        },
    )

# ============================================================================
# File Upload & Ingestion
# ============================================================================

# Old review/reject route removed - see review router comment above

class BulkUpdateRequest(BaseModel):
    match_result_ids: List[UUID]
    action: Literal["approve", "reject"]
    annotation: Optional[str] = None
    org_id: str
    project_id: str

@app.post("/api/matches/bulk-update")
async def bulk_update_matches(
    request: BulkUpdateRequest,
    username: str = Depends(require_auth) if AUTH_ENABLED else None,
):
    """Bulk approve or reject matches."""
    async with get_session() as session:
        # Verify all match results exist and belong to org/project
        stmt = select(MatchResultModel).join(ItemModel).where(
            MatchResultModel.id.in_(request.match_result_ids),
            ItemModel.org_id == request.org_id,
            ItemModel.project_id == request.project_id
        )
        results = (await session.execute(stmt)).scalars().all()
        
        if len(results) != len(request.match_result_ids):
            found_ids = {r.id for r in results}
            missing = set(request.match_result_ids) - found_ids
            raise HTTPException(
                status_code=400, 
                detail=f"Some match results not found or access denied: {missing}"
            )

        processed_count = 0
        for match_result in results:
            if request.action == "approve":
                # Re-use existing approval logic
                # We need to fetch the full record structure expected by approve_review_record
                # For now, we'll implement a simplified version or fetch the record
                record = await fetch_review_record(session, match_result.id)
                if record:
                    await approve_review_record(
                        session, 
                        record, 
                        created_by=username or "web-ui", 
                        annotation=request.annotation
                    )
                    processed_count += 1
            
            elif request.action == "reject":
                match_result.decision = "rejected"
                match_result.reason = request.annotation or "Bulk rejection via web UI"
                match_result.created_by = username or "web-ui" # Update audit field
                # Note: 'reviewed_at' isn't on MatchResultModel based on previous view, 
                # but 'timestamp' is creation time. We might need a separate audit log or update existing fields.
                # For now, we update the decision.
                processed_count += 1
        
        await session.commit()
        
        return {"processed": processed_count, "action": request.action}

        return {"processed": processed_count, "action": request.action}


# ============================================================================
# Integrations (Autodesk Construction Cloud)
# ============================================================================

@app.get("/api/integrations/acc/connect")
async def acc_connect():
    """Initiate ACC OAuth flow."""
    from bimcalc.integrations.acc import get_acc_client
    client = get_acc_client()
    return RedirectResponse(client.get_auth_url())

@app.get("/api/integrations/acc/callback")
async def acc_callback(code: str, request: Request):
    """Handle ACC OAuth callback."""
    from bimcalc.integrations.acc import get_acc_client
    client = get_acc_client()
    tokens = await client.exchange_code(code)
    
    # Store token in session or cookie (simplified for MVP)
    response = RedirectResponse("/integrations/acc/browser")
    response.set_cookie("acc_token", tokens["access_token"], max_age=3600, httponly=True)
    return response

@app.get("/integrations/acc/browser", response_class=HTMLResponse)
async def acc_browser(request: Request):
    """Browser for ACC files."""
    token = request.cookies.get("acc_token")
    if not token:
        return RedirectResponse("/api/integrations/acc/connect")
        
    from bimcalc.integrations.acc import get_acc_client
    client = get_acc_client()
    projects = await client.list_projects(token)
    
    # Simple HTML for file browsing
    project_list = "".join([f"<li><a href='?project_id={p['id']}'>{p['name']}</a></li>" for p in projects])
    
    files_html = ""
    project_id = request.query_params.get("project_id")
    if project_id:
        files = await client.list_files(token, project_id)
        files_html = "<h3>Files</h3><ul>" + "".join([
            f"<li>{f.name} (v{f.version}) - <button onclick='importFile(\"{f.id}\")'>Import</button></li>" 
            for f in files
        ]) + "</ul>"
        
    return f"""
    <html>
        <head><title>ACC Browser</title></head>
        <body>
            <h1>Autodesk Construction Cloud</h1>
            <h2>Projects</h2>
            <ul>{project_list}</ul>
            {files_html}
            <script>
                function importFile(fileId) {{
                    alert('Importing file ' + fileId);
                    // Call ingest API here
                }}
            </script>
        </body>
    </html>
    """

# ============================================================================
# Scenario Planning
# ============================================================================

@app.get("/api/scenarios/export")
async def export_scenarios(
    org: str = Query(...),
    project: str = Query(...),
    vendors: List[str] = Query(default=None),
):
    """Export scenario comparison to Excel."""
    from bimcalc.reporting.scenario import compute_vendor_scenario, get_available_vendors
    from bimcalc.reporting.export import export_scenario_to_excel
    
    async with get_session() as session:
        # Reuse logic from compare endpoint
        available_vendors = await get_available_vendors(session, org)
        
        selected_vendors = vendors if vendors else available_vendors[:3]
        
        comparisons = []
        for vendor in selected_vendors:
            result = await compute_vendor_scenario(session, org, project, vendor)
            comparisons.append(result)
            
        data = {
            "org_id": org,
            "project_id": project,
            "comparisons": [c.to_dict() for c in comparisons] # Assuming dataclass has to_dict or we convert
        }
        
        # Convert dataclasses to dict if needed
        # compute_vendor_scenario returns VendorScenario dataclass
        # We need to ensure it's serializable or access fields directly
        # The export function expects dicts.
        # Let's update the data construction to be explicit
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
# ============================================================================

@app.get("/scenarios", response_class=HTMLResponse)
async def scenario_page(
    request: Request, 
    org: str | None = None, 
    project: str | None = None
):
    """Scenario planning dashboard."""
    org_id, project_id = _get_org_project(request, org, project)
    
    return templates.TemplateResponse(
        "scenario.html",
        {
            "request": request,
            "org_id": org_id,
            "project_id": project_id,
        },
    )

@app.get("/api/scenarios/compare")
async def compare_scenarios(
    org: str = Query(...),
    project: str = Query(...),
    vendors: List[str] = Query(default=[]),
    username: str = Depends(require_auth) if AUTH_ENABLED else None,
):
    """Compare costs across multiple vendors."""
    from bimcalc.reporting.scenario import get_available_vendors, compute_vendor_scenario
    
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

# Old ingestion routes removed - now in ingestion router module (see lines 531-538)

# ============================================================================
# Matching Routes - REMOVED (moved to matching router)
# ============================================================================
# The following routes were here (now in matching.py):
#   @app.get("/match")      - was line 867
#   @app.post("/match/run") - was line 882


# ============================================================================
# Items Management
# ============================================================================
# REFACTORED: Items routes moved to bimcalc.web.routes.items (Phase 3.6)
# - GET    /items           -> items.items_list()      (was line 732-819)
# - GET    /items/export    -> items.items_export()    (was line 822-926)
# - GET    /items/{item_id} -> items.item_detail()     (was line 930-970)
# - DELETE /items/{item_id} -> items.delete_item()     (was line 973-986)


# ============================================================================
# Mappings Management
# ============================================================================

@app.get("/mappings", response_class=HTMLResponse)
async def mappings_list(
    request: Request,
    org: str | None = None,
    project: str | None = None,
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
    org: str | None = None,
    project: str | None = None,
    view: str | None = Query(default=None),
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
async def generate_report(
    request: Request,
    org: str | None = None,
    project: str | None = None,
    format: str = Query("xlsx", regex="^(xlsx|pdf|csv)$"),
    as_of: str | None = Query(None),
):
    """Generate and download financial reports."""
    from bimcalc.reporting.financial_metrics import compute_financial_metrics
    from bimcalc.reporting.export_utils import export_reports_to_excel, export_reports_to_pdf
    
    org_id, project_id = _get_org_project(request, org, project)

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

@app.get("/reports/generate")
async def generate_report_endpoint(
    org: str = Query(...),
    project: str = Query(...),
    as_of: str | None = Query(default=None),
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
    org: str | None = None,
    project: str | None = None,
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
    org: str | None = None,
    project: str | None = None,
    page: int = Query(default=1, ge=1),
    view: str | None = Query(default=None),
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
    org: str | None = None,
    project: str | None = None,
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


@app.get("/prices-legacy", response_class=HTMLResponse)
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
):
    """List all price items with search, filters, and optional history or executive view."""
    org_id, project_id = _get_org_project(request, org, project)

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
        count_stmt = select(func.count()).select_from(PriceItemModel).where(
            PriceItemModel.org_id == org_id
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
            count_stmt = count_stmt.where(PriceItemModel.classification_code == classification)
        if region:
            count_stmt = count_stmt.where(PriceItemModel.region == region)

        count_result = await session.execute(count_stmt)
        total = count_result.scalar_one()
        total_pages = (total + per_page - 1) // per_page

        # Apply pagination and ordering
        stmt = stmt.order_by(
            PriceItemModel.item_code,
            PriceItemModel.valid_from.desc(),
        ).limit(per_page).offset(offset)

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
        },
    )

@app.get("/prices/export")
async def prices_export(
    org: str | None = None,
    project: str | None = None,
    search: str | None = Query(default=None),
    vendor: str | None = Query(default=None),
    classification: str | None = Query(default=None),
    region: str | None = Query(default=None),
    current_only: bool = Query(default=True),
):
    """Export prices to Excel file."""
    org_id, project_id = _get_org_project(None, org, project)

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
    from io import BytesIO
    from openpyxl import Workbook
    from openpyxl.styles import Font, Alignment

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
                price.last_updated.strftime("%Y-%m-%d %H:%M") if price.last_updated else "",
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
    filename = f"prices_{org_id}{filters_str}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    return StreamingResponse(
        output,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )





@app.get("/prices/{price_id}", response_class=HTMLResponse)
async def price_detail(
    price_id: UUID,
    request: Request,
    org: str | None = None,
    project: str | None = None,
):
    """View price details including SCD Type-2 history."""
    org_id, project_id = _get_org_project(request, org, project)

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
        price_history = history_result.scalars().all()

    return templates.TemplateResponse(
        "price_detail.html",
        {
            "request": request,
            "price": price,
            "price_history": price_history,
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
            mapper = ClassificationMapper(session, request.org_id, request.items[0].get("project_id") if request.items else None)
            transformer = Crail4Transformer(mapper, request.target_scheme)

            valid_items, rejection_stats = await transformer.transform_batch(request.items)

            loaded_count = 0
            for item_data in valid_items:
                try:
                    classification_code = str(item_data["classification_code"])
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
    org: str | None = None,
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
                WHERE org_id = :org_id AND (source = 'crail4' OR source = 'crail4_api')
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
            from bimcalc.db.models import PriceImportRunModel
            import_runs_stmt = (
                select(PriceImportRunModel)
                .where(
                    PriceImportRunModel.org_id == org_id,
                    (PriceImportRunModel.source == "crail4") | (PriceImportRunModel.source == "crail4_api")
                )
                .order_by(PriceImportRunModel.started_at.desc())
                .limit(20)
            )
            import_runs_result = await session.execute(import_runs_stmt)
            import_runs = import_runs_result.scalars().all()
        except Exception as e:
            print(f"Error fetching import runs: {e}")
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
    classifications: str | None = Form(default=None),
    full_sync: bool = Form(default=False),
    region: str | None = Form(default=None),
    current_user: str = Depends(require_auth),
):
    """Trigger manual Crail4 sync."""
    org_id = get_config().org_id

    try:
        from bimcalc.core.queue import get_queue

        # Enqueue the job
        redis = await get_queue()
        job = await redis.enqueue_job(
            "run_crail4_sync",
            org_id=org_id,
            full_sync=full_sync
        )
        print(f"Enqueued Crail4 sync job: {job.job_id} for org {org_id}")

        # Return HTML fragment for HTMX
        return HTMLResponse(f"""
            <div class="message message-info" hx-get="/crail4-config/status/{job.job_id}" hx-trigger="load delay:2s" hx-swap="outerHTML">
                <strong>🚀 Sync Started!</strong><br>
                Job ID: {job.job_id}<br>
                <small>Checking status...</small>
            </div>
        """)

    except Exception as e:
        return HTMLResponse(f"""
            <div class="message message-error">
                <strong>❌ Error:</strong> {str(e)}
            </div>
        """)


@app.get("/crail4-config/status/{job_id}")
async def get_sync_status(job_id: str, current_user: str = Depends(require_auth)):
    """Poll for sync job status."""
    try:
        from arq.jobs import Job

        from bimcalc.core.queue import get_queue

        redis = await get_queue()
        job = Job(job_id, redis)
        status = await job.status()
        
        if status == "complete":
            result = await job.result()
            # Format result for display
            items_loaded = result.get("items_loaded", 0)
            items_fetched = result.get("items_fetched", 0)
            
            return HTMLResponse(f"""
                <div class="message message-success">
                    <strong>✅ Sync Complete!</strong><br>
                    Loaded {items_loaded} of {items_fetched} items.
                    <br>
                    <a href="/crail4-config" class="btn btn-primary mt-2" style="font-size: 0.8rem;">Refresh Page</a>
                </div>
            """)
            
        elif status == "in_progress":
             return HTMLResponse(f"""
                <div class="message message-info" hx-get="/crail4-config/status/{job_id}" hx-trigger="load delay:2s" hx-swap="outerHTML">
                    <strong>🔄 Syncing...</strong><br>
                    Job is running in background.
                    <div style="margin-top: 0.5rem; background: rgba(255,255,255,0.5); height: 4px; border-radius: 2px; overflow: hidden;">
                        <div style="background: #2b6cb0; height: 100%; width: 50%; animation: progress 2s infinite;"></div>
                    </div>
                    <style>@keyframes progress {{ 0% {{ transform: translateX(-100%); }} 100% {{ transform: translateX(100%); }} }}</style>
                </div>
            """)
            
        elif status == "failed":
             return HTMLResponse("""
                <div class="message message-error">
                    <strong>❌ Job Failed</strong><br>
                    The background job encountered an error.
                </div>
            """)
            
        else: # queued or not_found
             return HTMLResponse(f"""
                <div class="message message-info" hx-get="/crail4-config/status/{job_id}" hx-trigger="load delay:2s" hx-swap="outerHTML">
                    <strong>⏳ Queued...</strong><br>
                    Waiting for worker...
                </div>
            """)

    except Exception as e:
        return HTMLResponse(f"""
            <div class="message message-error">
                <strong>Error checking status:</strong> {str(e)}
            </div>
        """)
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
    sheet_name: str | None = Form(default=None),
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
    org: str | None = None,
    project: str | None = None,
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
    org: str | None = None,
    project: str | None = None,
    request: Request = None,
):
    """Export progress executive metrics to Excel."""
    from bimcalc.reporting.export_utils import export_progress_to_excel
    from bimcalc.reporting.progress import compute_progress_metrics

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
    org: str | None = None,
    project: str | None = None,
    request: Request = None,
):
    """Export review queue executive metrics to Excel."""
    from bimcalc.reporting.export_utils import export_review_to_excel
    from bimcalc.reporting.review_metrics import compute_review_metrics

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
    org: str | None = None,
    project: str | None = None,
    request: Request = None,
):
    """Export financial reports executive metrics to Excel."""
    from bimcalc.reporting.export_utils import export_reports_to_excel
    from bimcalc.reporting.financial_metrics import compute_financial_metrics

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
    org: str | None = None,
    project: str | None = None,
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
    org: str | None = None,
    request: Request = None,
):
    """Export price data quality metrics to Excel."""
    from bimcalc.reporting.export_utils import export_prices_to_excel
    from bimcalc.reporting.price_metrics import compute_price_metrics

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


# ============================================================================
# Documents & Project Intelligence
# ============================================================================

@app.get("/documents", response_class=HTMLResponse)
async def documents_page(
    request: Request,
    org: str | None = None,
    project: str | None = None,
    q: str | None = Query(default=None),
    tag: str | None = Query(default=None),
):
    """Project Intelligence / Documents Search Page."""
    org_id, project_id = _get_org_project(request, org, project)

    return templates.TemplateResponse(
        "documents.html",
        {
            "request": request,
            "org_id": org_id,
            "project_id": project_id,
            "query": q,
            "tag": tag,
        },
    )


@app.get("/api/documents/search")
async def search_documents(
    q: str | None = Query(default=None),
    tag: str | None = Query(default=None),
    org: str = Query(...),
    project: str = Query(...),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
):
    """Search documents with pagination.
    
    Args:
        q: Search query
        tag: Filter by tag
        org: Organization ID
        project: Project ID
        page: Page number (1-indexed)
        page_size: Items per page (max 100)
    """
    async with get_session() as session:
        # Base query
        stmt = select(DocumentModel).where(
            DocumentModel.org_id == org,
            DocumentModel.project_id == project,
        )

        # Apply filters
        if tag:
            # Filter for documents with this tag
            stmt = stmt.where(DocumentModel.tags.contains([tag]))

        if q:
            # Simple text search on title and content
            stmt = stmt.where(
                (DocumentModel.title.ilike(f"%{q}%")) |
                (DocumentModel.content.ilike(f"%{q}%"))
            )

        # Get total count (before pagination)
        count_stmt = select(func.count()).select_from(stmt.subquery())
        total_result = await session.execute(count_stmt)
        total_count = total_result.scalar()

        # Apply pagination
        offset = (page - 1) * page_size
        stmt = stmt.offset(offset).limit(page_size).order_by(DocumentModel.created_at.desc())

        result = await session.execute(stmt)
        docs = result.scalars().all()

        # Calculate pagination metadata
        total_pages = (total_count + page_size - 1) // page_size  # Ceiling division

        return {
            "results": [
                {
                    "id": str(d.id),
                    "title": d.title,
                    "document_type": d.document_type,
                    "tags": d.tags or [],
                    "source_file": d.source_file,
                    "created_at": d.created_at.isoformat(),
                }
                for d in docs
            ],
            "pagination": {
                "page": page,
                "page_size": page_size,
                "total_count": total_count,
                "total_pages": total_pages,
                "has_next": page < total_pages,
                "has_prev": page > 1,
            }
        }


@app.get("/api/items/{item_id}/recommendations")
async def get_item_recommendations(item_id: UUID, request: Request):
    """Get AI-recommended documents for an item."""
    from bimcalc.intelligence.recommendations import get_document_recommendations
    
    async with get_session() as session:
        # Get item
        item = await session.get(ItemModel, item_id)
        if not item:
            raise HTTPException(status_code=404, detail="Item not found")
        
        # Get recommendations
        recommendations = await get_document_recommendations(session, item, limit=5)
        
        # Return HTML template
        return templates.TemplateResponse(
            "partials/recommendations.html",
            {"request": request, "recommendations": recommendations}
        )


@app.get("/api/items/{item_id}/documents")
async def get_item_documents(item_id: UUID):
    """Get documents linked to a specific item."""
    async with get_session() as session:
        stmt = (
            select(DocumentModel, DocumentLinkModel)
            .join(DocumentLinkModel)
            .where(DocumentLinkModel.item_id == item_id)
        )
        result = await session.execute(stmt)
        
        links = []
        for doc, link in result:
            links.append({
                "id": str(doc.id),
                "title": doc.title,
                "type": doc.doc_type,
                "tags": doc.tags,
                "link_type": link.link_type,
                "confidence": link.confidence,
                "url": f"/documents?q={doc.title}" # Placeholder link
            })
            
        return links


# ============================================================================
# Compliance & QA Tracking
# ============================================================================

@app.get("/compliance", response_class=HTMLResponse)
async def compliance_dashboard(
    request: Request,
    org: str | None = None,
    project: str | None = None,
):
    """Compliance & QA tracking dashboard."""
    org_id, project_id = _get_org_project(request, org, project)

    return templates.TemplateResponse(
        "compliance.html",
        {
            "request": request,
            "org_id": org_id,
            "project_id": project_id,
        },
    )


@app.get("/api/compliance/metrics")
async def get_compliance_metrics(
    org: str = Query(...),
    project: str = Query(...),
):
    """Get compliance metrics for project."""
    from bimcalc.reporting.compliance_metrics import compute_compliance_metrics_cached

    async with get_session() as session:
        metrics = await compute_compliance_metrics_cached(session, org, project)

        return {
            "total_items": metrics.total_items,
            "items_with_qa": metrics.items_with_qa,
            "completion_percent": metrics.completion_percent,
            "coverage_by_classification": metrics.coverage_by_classification,
            "items_without_qa": metrics.items_without_qa,
            "computed_at": metrics.computed_at.isoformat(),
        }


# ============================================================================
# Vendor Intelligence & Prices Dashboard
# ============================================================================

@app.get("/prices", response_class=HTMLResponse)
async def prices_dashboard(
    request: Request,
    org: str | None = None,
    project: str | None = None,
):
    """Render the Prices & Vendor Intelligence dashboard."""
    org_id, project_id = _get_org_project(request, org, project)
    
    async with get_session() as session:
        # Fetch recent price items
        from bimcalc.db.models import PriceItemModel
        stmt = (
            select(PriceItemModel)
            .where(PriceItemModel.org_id == org_id, PriceItemModel.is_current == True)
            .order_by(PriceItemModel.last_updated.desc())
            .limit(50)
        )
        result = await session.execute(stmt)
        price_items = result.scalars().all()

    return templates.TemplateResponse(
        "prices.html",
        {
            "request": request,
            "org_id": org_id,
            "project_id": project_id,
            "price_items": price_items,
        },
    )


@app.post("/api/intelligence/analyze-quote")
async def analyze_quote(
    file: UploadFile = File(...),
    current_user: str = Depends(require_auth) if AUTH_ENABLED else "user",
):
    """Analyze an uploaded quote/invoice PDF."""
    if not file.filename.lower().endswith('.pdf'):
        raise HTTPException(status_code=400, detail="Only PDF files are supported")

    try:
        content = await file.read()
        
        from bimcalc.intelligence.vendors import VendorAnalyzer
        analyzer = VendorAnalyzer()
        result = await analyzer.extract_quote_data(content, file.filename)
        
        return result
    except Exception as e:
        logger.error(f"Analysis failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/intelligence/analyze-url")
async def analyze_url(
    payload: dict,
    current_user: str = Depends(require_auth) if AUTH_ENABLED else "user",
):
    """Analyze a PDF from a URL."""
    url = payload.get("url")
    if not url:
        raise HTTPException(status_code=400, detail="URL is required")

    try:
        from bimcalc.intelligence.vendors import VendorAnalyzer
        analyzer = VendorAnalyzer()
        result = await analyzer.fetch_and_analyze_url(url)
        
        return result
    except Exception as e:
        logger.error(f"URL analysis failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/prices/save-extracted")
async def save_extracted_prices(
    request: Request,
    payload: dict,
    current_user: str = Depends(require_auth) if AUTH_ENABLED else "user",
):
    """Save extracted price items to the database."""
    org_id = payload.get("org_id", "default")
    items = payload.get("items", [])
    
    if not items:
        return {"status": "no_items", "count": 0}

    async with get_session() as session:
        from bimcalc.db.models import PriceItemModel
        
        saved_count = 0
        for item in items:
            # Create new price item
            new_item = PriceItemModel(
                org_id=org_id,
                item_code=item.get("vendor_code") or f"UNKNOWN-{uuid4().hex[:8]}",
                region="EU", # Default for now
                classification_code=0, # Default/Unknown
                vendor_code=item.get("vendor_code"),
                sku=item.get("vendor_code") or "UNKNOWN",
                description=item.get("description"),
                unit=item.get("unit") or "ea",
                unit_price=Decimal(str(item.get("unit_price", 0))),
                currency=item.get("currency", "EUR"),
                source_name="AI_EXTRACTION",
                source_currency=item.get("currency", "EUR"),
                is_current=True
            )
            session.add(new_item)
            saved_count += 1
        
        await session.commit()
    
    return {"status": "success", "count": saved_count}


# ================================================================================
# Projects
# ================================================================================

@app.get("/projects", response_class=HTMLResponse)
async def projects_page(
    request: Request,
    org: str | None = None,
):
    """Projects management page."""
    org_id = org or request.cookies.get("org_id", "default")
    
    return templates.TemplateResponse(
        "projects.html",
        {
            "request": request,
            "org_id": org_id,
        }
    )


# ================================================================================
# Analytics Dashboard
# ============================================================================

@app.get("/analytics", response_class=HTMLResponse)
async def analytics_dashboard(
    request: Request,
    org: str | None = None,
    project: str | None = None,
):
    """Advanced analytics dashboard with charts."""
    org_id, project_id = _get_org_project(request, org, project)

    return templates.TemplateResponse(
        "analytics.html",
        {
            "request": request,
            "org_id": org_id,
            "project_id": project_id,
        },
    )


@app.get("/risk-dashboard", response_class=HTMLResponse)
async def risk_dashboard_page(
    request: Request,
    org: str | None = None,
    project: str | None = None,
):
    """Risk dashboard showing high-risk items."""
    org_id, project_id = _get_org_project(request, org, project)

    return templates.TemplateResponse(
        "risk_dashboard.html",
        {
            "request": request,
            "org_id": org_id,
            "project_id": project_id,
        },
    )


@app.get("/api/analytics/classification-breakdown")
async def get_classification_breakdown_api(
    org: str = Query(...),
    project: str = Query(...),
):
    """Get classification breakdown data."""
    from bimcalc.reporting.analytics import get_classification_breakdown
    
    async with get_session() as session:
        data = await get_classification_breakdown(session, org, project)
        return data


@app.get("/api/analytics/compliance-timeline")
async def get_compliance_timeline_api(
    org: str = Query(...),
    project: str = Query(...),
):
    """Get compliance timeline data."""
    from bimcalc.reporting.analytics import get_compliance_timeline
    
    async with get_session() as session:
        data = await get_compliance_timeline(session, org, project)
        return data


@app.get("/api/analytics/cost-distribution")
async def get_cost_distribution_api(
    org: str = Query(...),
    project: str = Query(...),
):
    """Get cost distribution data."""
    from bimcalc.reporting.analytics import get_cost_by_classification
    
    async with get_session() as session:
        data = await get_cost_by_classification(session, org, project)
        return data


@app.get("/api/analytics/document-coverage")
async def get_document_coverage_api(
    org: str = Query(...),
    project: str = Query(...),
):
    """Get document coverage matrix data."""
    from bimcalc.reporting.analytics import get_document_coverage_matrix
    
    async with get_session() as session:
        data = await get_document_coverage_matrix(session, org, project)
        return data


# ============================================================================
# Risk Scoring
# ============================================================================

@app.get("/api/items/{item_id}/risk")
async def get_item_risk_score(item_id: UUID):
    """Get risk score for a specific item."""
    from bimcalc.intelligence.risk_scoring import get_risk_score_cached
    from bimcalc.db.models import DocumentLinkModel
    from sqlalchemy import select
    
    async with get_session() as session:
        # Get item
        item = await session.get(ItemModel, item_id)
        if not item:
            raise HTTPException(status_code=404, detail="Item not found")
        
        # Get linked documents
        doc_query = (
            select(DocumentModel)
            .join(DocumentLinkModel)
            .where(DocumentLinkModel.item_id == item_id)
        )
        doc_result = await session.execute(doc_query)
        documents = list(doc_result.scalars())
        
        # Get match result (if any)
        match_query = select(MatchResultModel).where(
            MatchResultModel.item_id == item_id,
            MatchResultModel.decision == "auto-accepted"
        ).limit(1)
        match_result = await session.execute(match_query)
        match = match_result.scalar_one_or_none()
        
        # Calculate risk
        risk = await get_risk_score_cached(item, documents, match)
        
        return {
            "item_id": risk.item_id,
            "score": risk.score,
            "level": risk.level,
            "factors": risk.factors,
            "recommendations": risk.recommendations
        }


@app.get("/api/items/high-risk")
async def get_high_risk_items(
    org: str = Query(...),
    project: str = Query(...),
    threshold: int = Query(default=61, ge=0, le=100),
    limit: int = Query(default=50, ge=1, le=200)
):
    """Get high-risk items above threshold."""
    from bimcalc.intelligence.risk_scoring import ComplianceRiskScorer
    from bimcalc.db.models import DocumentLinkModel
    from sqlalchemy import select
    
    async with get_session() as session:
        # Get all items for project
        items_query = select(ItemModel).where(
            ItemModel.org_id == org,
            ItemModel.project_id == project
        ).limit(limit)
        items_result = await session.execute(items_query)
        items = list(items_result.scalars())
        
        scorer = ComplianceRiskScorer()
        high_risk_items = []
        
        for item in items:
            # Get documents for this item
            doc_query = (
                select(DocumentModel)
                .join(DocumentLinkModel)
                .where(DocumentLinkModel.item_id == item.id)
            )
            doc_result = await session.execute(doc_query)
            documents = list(doc_result.scalars())
            
            # Get match
            match_query = select(MatchResultModel).where(
                MatchResultModel.item_id == item.id,
                MatchResultModel.decision == "auto-accepted"
            ).limit(1)
            match_result = await session.execute(match_query)
            match = match_result.scalar_one_or_none()
            
            # Calculate risk
            risk = await scorer.calculate_risk(item, documents, match)
            
            if risk.score >= threshold:
                high_risk_items.append({
                    "item_id": str(item.id),
                    "family": item.family,
                    "type_name": item.type_name,
                    "classification_code": item.classification_code,
                    "risk_score": risk.score,
                    "risk_level": risk.level,
                    "recommendations": risk.recommendations
                })
        
        # Sort by risk score (highest first)
        high_risk_items.sort(key=lambda x: x["risk_score"], reverse=True)
        
        return {
            "threshold": threshold,
            "count": len(high_risk_items),
            "items": high_risk_items
        }


# ============================================================================
# QA Checklist Generation
# ============================================================================

@app.post("/api/items/{item_id}/generate-checklist")
async def generate_qa_checklist(item_id: UUID):
    """Generate QA checklist for item using AI."""
    from bimcalc.intelligence.checklist_generator import QAChecklistGenerator, calculate_completion_percent
    from bimcalc.intelligence.recommendations import get_document_recommendations
    from bimcalc.db.models import QAChecklistModel
    from sqlalchemy import select
    
    async with get_session() as session:
        # Get item
        item = await session.get(ItemModel, item_id)
        if not item:
            raise HTTPException(status_code=404, detail="Item not found")
        
        # Check if checklist already exists
        existing_query = select(QAChecklistModel).where(QAChecklistModel.item_id == item_id)
        existing_result = await session.execute(existing_query)
        existing_checklist = existing_result.scalar_one_or_none()
        
        if existing_checklist:
            return {
                "message": "Checklist already exists. Use PATCH to update or DELETE first.",
                "checklist_id": str(existing_checklist.id),
                "regenerate_url": f"/api/items/{item_id}/checklist"
            }
        
        # Get relevant quality documents (using recommendations engine!)
        recommendations = await get_document_recommendations(
            session, item, limit=5, min_score=0.3
        )
        
        if not recommendations:
            raise HTTPException(
                status_code=400,
                detail="No relevant quality documents found. Link documents first."
            )
        
        # Get full document objects
        doc_ids = [rec["id"] for rec in recommendations]
        docs_query = select(DocumentModel).where(DocumentModel.id.in_(doc_ids))
        docs_result = await session.execute(docs_query)
        quality_docs = list(docs_result.scalars())
        
        # Generate checklist using LLM
        generator = QAChecklistGenerator()
        checklist_data = await generator.generate_checklist(item, quality_docs)
        
        if not checklist_data.get("items"):
            raise HTTPException(
                status_code=500,
                detail="Failed to generate checklist. Please try again."
            )
        
        # Save to database
        checklist = QAChecklistModel(
            item_id=item_id,
            org_id=item.org_id,
            project_id=item.project_id,
            checklist_items={"items": checklist_data["items"]},
            source_documents={"docs": checklist_data["source_docs"]},
            auto_generated=True,
            completion_percent=0.0,
            created_by="system"
        )
        
        session.add(checklist)
        await session.commit()
        await session.refresh(checklist)
        
        return {
            "checklist_id": str(checklist.id),
            "item_id": str(item_id),
            "items": checklist_data["items"],
            "source_docs": checklist_data["source_docs"],
            "completion_percent": 0.0
        }


@app.get("/api/items/{item_id}/checklist")
async def get_qa_checklist(item_id: UUID):
    """Get existing QA checklist for item."""
    from bimcalc.db.models import QAChecklistModel
    from sqlalchemy import select
    
    async with get_session() as session:
        query = select(QAChecklistModel).where(QAChecklistModel.item_id == item_id)
        result = await session.execute(query)
        checklist = result.scalar_one_or_none()
        
        if not checklist:
            raise HTTPException(status_code=404, detail="No checklist found for this item")
        
        return {
            "checklist_id": str(checklist.id),
            "item_id": str(item_id),
            "items": checklist.checklist_items.get("items", []),
            "source_docs": checklist.source_documents.get("docs", []),
            "completion_percent": checklist.completion_percent,
            "generated_at": checklist.generated_at.isoformat(),
            "completed_at": checklist.completed_at.isoformat() if checklist.completed_at else None
        }


@app.patch("/api/items/{item_id}/checklist")
async def update_qa_checklist(item_id: UUID, updates: dict):
    """Update checklist item completion status."""
    from bimcalc.intelligence.checklist_generator import calculate_completion_percent
    from bimcalc.db.models import QAChecklistModel
    from sqlalchemy import select
    from datetime import datetime
    
    async with get_session() as session:
        query = select(QAChecklistModel).where(QAChecklistModel.item_id == item_id)
        result = await session.execute(query)
        checklist = result.scalar_one_or_none()
        
        if not checklist:
            raise HTTPException(status_code=404, detail="No checklist found for this item")
        
        # Update checklist items
        items = checklist.checklist_items.get("items", [])
        
        # Apply updates (expects {"item_id": <id>, "completed": true/false, "notes": "..."})
        updated_items = []
        for item in items:
            if str(item.get("id")) == str(updates.get("item_id")):
                item["completed"] = updates.get("completed", item.get("completed", False))
                item["notes"] = updates.get("notes", item.get("notes", ""))
            updated_items.append(item)
        
        # Recalculate completion percentage
        completion_percent = calculate_completion_percent(updated_items)
        
        # Update database
        checklist.checklist_items = {"items": updated_items}
        checklist.completion_percent = completion_percent
        
        # Mark as completed if 100%
        if completion_percent == 100.0 and not checklist.completed_at:
            checklist.completed_at = datetime.utcnow()
        elif completion_percent < 100.0:
            checklist.completed_at = None
        
        await session.commit()
        await session.refresh(checklist)
        
        return {
            "checklist_id": str(checklist.id),
            "items": updated_items,
            "completion_percent": completion_percent,
            "completed_at": checklist.completed_at.isoformat() if checklist.completed_at else None
        }


# ============================================================================
# Export APIs
# ============================================================================

@app.get("/api/items/{item_id}/checklist/export/pdf")
async def export_checklist_pdf(item_id: UUID):
    """Export checklist as PDF."""
    from bimcalc.intelligence.exports import ChecklistPDFExporter
    from bimcalc.db.models import QAChecklistModel
    from sqlalchemy import select
    from fastapi.responses import Response
    
    async with get_session() as session:
        # Get checklist
        query = select(QAChecklistModel).where(QAChecklistModel.item_id == item_id)
        result = await session.execute(query)
        checklist = result.scalar_one_or_none()
        
        if not checklist:
            raise HTTPException(status_code=404, detail="No checklist found")
        
        # Get item
        item = await session.get(ItemModel, item_id)
        if not item:
            raise HTTPException(status_code=404, detail="Item not found")
        
        # Generate PDF
        exporter = ChecklistPDFExporter()
        pdf_bytes = exporter.export(checklist, item)
        
        # Return as downloadable file
        filename = f"checklist_{item.family}_{item.type_name}.pdf".replace(" ", "_")
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )


@app.get("/api/analytics/export/excel")
async def export_analytics_excel(org: str = Query(...), project: str = Query(...)):
    """Export all analytics as Excel workbook."""
    from bimcalc.intelligence.exports import AnalyticsExcelExporter
    from bimcalc.reporting.analytics import (
        get_classification_breakdown,
        get_compliance_timeline,
        get_cost_distribution,
        get_document_coverage_matrix
    )
    from fastapi.responses import Response
    
    async with get_session() as session:
        # Gather all analytics data
        analytics_data = {
            "classification_breakdown": await get_classification_breakdown(session, org, project),
            "compliance_timeline": await get_compliance_timeline(session, org, project),
            "cost_distribution": await get_cost_distribution(session, org, project),
            "document_coverage": await get_document_coverage_matrix(session, org, project)
        }
        
        # Generate Excel
        exporter = AnalyticsExcelExporter()
        excel_bytes = exporter.export(analytics_data)
        
        # Return as downloadable file
        filename = f"analytics_{project}.xlsx"
        return Response(
            content=excel_bytes,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )


@app.get("/api/items/risk/export/csv")
async def export_risk_csv(
    org: str = Query(...),
    project: str = Query(...),
    threshold: int = Query(0, ge=0, le=100)
):
    """Export risk assessment as CSV."""
    from bimcalc.intelligence.exports import RiskCSVExporter
    from bimcalc.intelligence.risk_scoring import get_risk_score_cached
    from fastapi.responses import Response
    from sqlalchemy import select
    
    async with get_session() as session:
        # Get all items for project
        query = select(ItemModel).where(
            ItemModel.org_id == org,
            ItemModel.project_id == project
        )
        result = await session.execute(query)
        items = list(result.scalars())
        
        # Calculate risk for each item
        risk_items = []
        for item in items:
            risk = await get_risk_score_cached(session, str(item.id))
            
            if risk.score >= threshold:
                risk_items.append({
                    "item_id": str(item.id),
                    "family": item.family,
                    "type_name": item.type_name,
                    "classification_code": item.classification_code,
                    "risk_score": risk.score,
                    "risk_level": risk.level,
                    "recommendations": risk.recommendations
                })
        
        # Generate CSV
        exporter = RiskCSVExporter()
        csv_string = exporter.export(risk_items)
        
        # Return as downloadable file
        filename = f"risk_report_{project}.csv"
        return Response(
            content=csv_string,
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )


# ============================================================================
# Bulk Operations APIs
# ============================================================================

@app.post("/api/checklists/generate-batch")
async def generate_batch_checklists(request: Request, item_ids: list[str]):
    """Queue batch checklist generation job.
    
    Args:
        item_ids: List of item IDs to generate checklists for
        
    Returns:
        Job ID for tracking progress
    """
    from arq import create_pool
    from arq.connections import RedisSettings
    import os
    
    # Get org/project from first item
    async with get_session() as session:
        first_item = await session.get(ItemModel, UUID(item_ids[0]))
        if not first_item:
            raise HTTPException(status_code=404, detail="First item not found")
        
        org_id = first_item.org_id
        project_id = first_item.project_id
    
    # Queue ARQ job
    redis_settings = RedisSettings.from_dsn(
        os.environ.get("REDIS_URL", "redis://redis:6379")
    )
    redis = await create_pool(redis_settings)
    
    job = await redis.enqueue_job(
        "batch_generate_checklists_job",
        org_id,
        project_id,
        item_ids
    )
    
    return {
        "job_id": job.job_id,
        "status": "queued",
        "total_items": len(item_ids)
    }


@app.get("/api/jobs/{job_id}/status")
async def get_job_status(job_id: str):
    """Get status of background job.
    
    Args:
        job_id: ARQ job ID
        
    Returns:
        Job status and result if complete
    """
    from arq import create_pool
    from arq.connections import RedisSettings
    from arq.jobs import JobStatus
    import os
    
    redis_settings = RedisSettings.from_dsn(
        os.environ.get("REDIS_URL", "redis://redis:6379")
    )
    redis = await create_pool(redis_settings)
    
    job = await redis.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    status_map = {
        JobStatus.queued: "queued",
        JobStatus.in_progress: "running",
        JobStatus.complete: "complete",
        JobStatus.not_found: "not_found"
    }
    
    return {
        "job_id": job_id,
        "status": status_map.get(job.status, "unknown"),
        "result": job.result if job.status == JobStatus.complete else None
    }


@app.post("/api/items/risk/assess-all")
async def assess_all_risks(org: str = Query(...), project: str = Query(...)):
    """Bulk assess risk for all items in project.
    
    Args:
        org: Organization ID
        project: Project ID
        
    Returns:
        Risk assessment results
    """
    from bimcalc.intelligence.bulk_operations import bulk_assess_risks
    
    async with get_session() as session:
        results = await bulk_assess_risks(session, org, project)
        return results


@app.get("/api/checklists/export-all")
async def export_all_checklists(org: str = Query(...), project: str = Query(...)):
    """Export all checklists as ZIP file.
    
    Args:
        org: Organization ID
        project: Project ID
        
    Returns:
        ZIP file download
    """
    from bimcalc.intelligence.bulk_operations import export_all_checklists_zip
    from fastapi.responses import Response
    
    async with get_session() as session:
        zip_bytes = await export_all_checklists_zip(session, org, project)
        
        filename = f"checklists_{project}.zip"
        return Response(
            content=zip_bytes,
            media_type="application/zip",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )


# ============================================================================
# Project Management APIs
# ============================================================================

@app.get("/api/projects")
async def get_projects():
    """Get list of all available org/project combinations (includes projects with 0 items)."""
    from sqlalchemy import select, func, union_all
    from bimcalc.db.models import ProjectModel
    
    async with get_session() as session:
        # Get projects from items table
        items_query = select(
            ItemModel.org_id,
            ItemModel.project_id,
            func.count(ItemModel.id).label('item_count')
        ).group_by(
            ItemModel.org_id,
            ItemModel.project_id
        )
        
        items_result = await session.execute(items_query)
        item_projects = {
            (row.org_id, row.project_id): row.item_count
            for row in items_result
        }
        
        # Get all projects from projects table
        projects_query = select(ProjectModel).order_by(
            ProjectModel.org_id,
            ProjectModel.project_id
        )
        projects_result = await session.execute(projects_query)
        db_projects = list(projects_result.scalars())
        
        # Combine: all registered projects plus any projects that only exist in items
        all_projects = {}
        
        # Add projects from projects table
        for proj in db_projects:
            key = (proj.org_id, proj.project_id)
            all_projects[key] = {
                "org_id": proj.org_id,
                "project_id": proj.project_id,
                "item_count": item_projects.get(key, 0),
                "display_name": f"{proj.display_name} ({item_projects.get(key, 0)} items)"
            }
        
        # Add any projects from items that aren't registered
        for (org_id, project_id), count in item_projects.items():
            key = (org_id, project_id)
            if key not in all_projects:
                all_projects[key] = {
                    "org_id": org_id,
                    "project_id": project_id,
                    "item_count": count,
                    "display_name": f"{project_id} ({count} items)"
                }
        
        # Sort by org then project
        sorted_projects = sorted(
            all_projects.values(),
            key=lambda x: (x['org_id'], x['project_id'])
        )
        
        return {"projects": sorted_projects}


@app.post("/api/projects")
async def create_project(
    org_id: str,
    project_id: str,
    display_name: str,
    description: str = None,
    start_date: str = None,
    target_completion: str = None,
    region: str = "EU"
):
    """Create a new project."""
    from bimcalc.db.models import ProjectModel
    from sqlalchemy import select
    from datetime import datetime
    
    async with get_session() as session:
        # Check if project already exists
        query = select(ProjectModel).where(
            ProjectModel.org_id == org_id,
            ProjectModel.project_id == project_id
        )
        result = await session.execute(query)
        existing = result.scalar_one_or_none()
        
        if existing:
            raise HTTPException(status_code=400, detail="Project already exists")
        
        # Parse dates
        start = datetime.fromisoformat(start_date) if start_date else None
        target = datetime.fromisoformat(target_completion) if target_completion else None
        
        # Create project
        project = ProjectModel(
            org_id=org_id,
            project_id=project_id,
            display_name=display_name,
            description=description,
            start_date=start,
            target_completion=target,
            status="active",
            region=region
        )
        
        session.add(project)
        await session.commit()
        
        return {
            "success": True,
            "project": {
                "org_id": project.org_id,
                "project_id": project.project_id,
                "display_name": project.display_name
            }
        }


@app.get("/api/projects/all")
async def get_all_projects():
    """Get all projects with metadata."""
    from bimcalc.db.models import ProjectModel
    from sqlalchemy import select, func
    
    async with get_session() as session:
        query = select(ProjectModel).order_by(ProjectModel.org_id, ProjectModel.project_id)
        result = await session.execute(query)
        projects = list(result.scalars())
        
        # Get item counts
        item_counts_query = select(
            ItemModel.org_id,
            ItemModel.project_id,
            func.count(ItemModel.id).label('count')
        ).group_by(ItemModel.org_id, ItemModel.project_id)
        
        item_counts_result = await session.execute(item_counts_query)
        item_counts = {
            (row.org_id, row.project_id): row.count
            for row in item_counts_result
        }
        
        return {
            "projects": [
                {
                    "id": str(proj.id),
                    "org_id": proj.org_id,
                    "project_id": proj.project_id,
                    "display_name": proj.display_name,
                    "description": proj.description,
                    "status": proj.status,
                    "start_date": proj.start_date.isoformat() if proj.start_date else None,
                    "target_completion": proj.target_completion.isoformat() if proj.target_completion else None,
                    "item_count": item_counts.get((proj.org_id, proj.project_id), 0),
                    "settings": proj.settings,
                    "created_at": proj.created_at.isoformat()
                }
                for proj in projects
            ]
        }


@app.delete("/api/projects/{project_uuid}")
async def delete_project(project_uuid: UUID):
    """Delete a project (metadata only, items remain)."""
    from bimcalc.db.models import ProjectModel
    
    async with get_session() as session:
        project = await session.get(ProjectModel, project_uuid)
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")
        
        await session.delete(project)
        await session.commit()
        
        return {"success": True, "message": "Project deleted"}


@app.patch("/api/projects/{project_uuid}/settings")
async def update_project_settings(project_uuid: UUID, settings: dict = Body(...)):
    """Update project settings with comprehensive validation.
    
    Supported settings:
    - blended_labor_rate: float (>= 0)
    - default_markup_percentage: float (0-100)
    - auto_approval_threshold: int (0-100)
    - risk_thresholds: {high: int, medium: int} (0-100)
    - currency: str (EUR, USD, GBP)
    - vat_rate: float (0-1)
    - vat_included: bool
    """
    from bimcalc.db.models import ProjectModel
    
    # Define allowed settings and their validation rules
    allowed_keys = {
        'blended_labor_rate',
        'default_markup_percentage',
        'auto_approval_threshold',
        'risk_thresholds',
        'currency',
        'vat_rate',
        'vat_included'
    }
    
    # Validate only allowed keys are present
    invalid_keys = set(settings.keys()) - allowed_keys
    if invalid_keys:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid settings keys: {', '.join(invalid_keys)}"
        )
    
    # Type and range validation
    try:
        if 'blended_labor_rate' in settings:
            rate = float(settings['blended_labor_rate'])
            if rate < 0:
                raise ValueError("Labor rate must be >= 0")
            settings['blended_labor_rate'] = rate
        
        if 'default_markup_percentage' in settings:
            markup = float(settings['default_markup_percentage'])
            if not 0 <= markup <= 100:
                raise ValueError("Markup percentage must be between 0 and 100")
            settings['default_markup_percentage'] = markup
        
        if 'auto_approval_threshold' in settings:
            threshold = int(settings['auto_approval_threshold'])
            if not 0 <= threshold <= 100:
                raise ValueError("Auto-approval threshold must be between 0 and 100")
            settings['auto_approval_threshold'] = threshold
        
        if 'risk_thresholds' in settings:
            thresholds = settings['risk_thresholds']
            if not isinstance(thresholds, dict):
                raise ValueError("risk_thresholds must be an object")
            if 'high' in thresholds:
                thresholds['high'] = int(thresholds['high'])
                if not 0 <= thresholds['high'] <= 100:
                    raise ValueError("High risk threshold must be between 0 and 100")
            if 'medium' in thresholds:
                thresholds['medium'] = int(thresholds['medium'])
                if not 0 <= thresholds['medium'] <= 100:
                    raise ValueError("Medium risk threshold must be between 0 and 100")
            # Validate high >= medium
            if 'high' in thresholds and 'medium' in thresholds:
                if thresholds['high'] < thresholds['medium']:
                    raise ValueError("High risk threshold must be >= medium risk threshold")
        
        if 'currency' in settings:
            currency = str(settings['currency']).upper()
            if currency not in ['EUR', 'USD', 'GBP']:
                raise ValueError("Currency must be EUR, USD, or GBP")
            settings['currency'] = currency
        
        if 'vat_rate' in settings:
            vat = float(settings['vat_rate'])
            if not 0 <= vat <= 1:
                raise ValueError("VAT rate must be between 0 and 1")
            settings['vat_rate'] = vat
        
        if 'vat_included' in settings:
            if not isinstance(settings['vat_included'], bool):
                raise ValueError("vat_included must be a boolean")
    
    except (ValueError, TypeError) as e:
        raise HTTPException(status_code=400, detail=str(e))
    
    async with get_session() as session:
        project = await session.get(ProjectModel, project_uuid)
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")
        
        # Merge settings (preserve existing values)
        current_settings = dict(project.settings) if project.settings else {}
        current_settings.update(settings)
        project.settings = current_settings
        
        session.add(project)
        await session.commit()
        
        return {"success": True, "settings": project.settings}


@app.get("/api/projects/{project_uuid}/labor-rates")
async def get_labor_rates(project_uuid: UUID):
    """Get all labor rate overrides for a project."""
    from bimcalc.db.models import LaborRateOverride, ProjectModel
    from sqlalchemy import select
    
    async with get_session() as session:
        # Get base rate from project settings
        project = await session.get(ProjectModel, project_uuid)
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")
        
        base_rate = project.settings.get('blended_labor_rate', 50.0) if project.settings else 50.0
        
        # Get category overrides
        query = select(LaborRateOverride).where(LaborRateOverride.project_id == project_uuid)
        result = await session.execute(query)
        overrides = result.scalars().all()
        
        return {
            "base_rate": float(base_rate),
            "overrides": [
                {
                    "id": str(o.id),
                    "category": o.category,
                    "rate": float(o.rate)
                }
                for o in overrides
            ]
        }


@app.post("/api/projects/{project_uuid}/labor-rates")
async def create_labor_rate_override(
    project_uuid: UUID,
    category: str = Body(...),
    rate: float = Body(...)
):
    """Create or update a labor rate override for a category."""
    from bimcalc.db.models import LaborRateOverride, ProjectModel
    from sqlalchemy import select
    
    # Validation
    if rate < 0:
        raise HTTPException(status_code=400, detail="Rate must be >= 0")
    if not category.strip():
        raise HTTPException(status_code=400, detail="Category cannot be empty")
    
    async with get_session() as session:
        # Verify project exists
        project = await session.get(ProjectModel, project_uuid)
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")
        
        # Check if override already exists
        query = select(LaborRateOverride).where(
            LaborRateOverride.project_id == project_uuid,
            LaborRateOverride.category == category
        )
        existing = (await session.execute(query)).scalar_one_or_none()
        
        if existing:
            # Update existing
            existing.rate = Decimal(str(rate))
            existing.updated_at = datetime.utcnow()
            override_id = existing.id
        else:
            # Create new
            override = LaborRateOverride(
                id=uuid4(),
                project_id=project_uuid,
                category=category,
                rate=Decimal(str(rate))
            )
            session.add(override)
            override_id = override.id
        
        await session.commit()
        return {"success": True, "id": str(override_id)}


@app.delete("/api/projects/{project_uuid}/labor-rates/{override_id}")
async def delete_labor_rate_override(project_uuid: UUID, override_id: UUID):
    """Delete a labor rate override."""
    from bimcalc.db.models import LaborRateOverride
    
    async with get_session() as session:
        override = await session.get(LaborRateOverride, override_id)
        if not override or override.project_id != project_uuid:
            raise HTTPException(status_code=404, detail="Override not found")
        
        await session.delete(override)
        await session.commit()
        return {"success": True}


@app.get("/api/projects/{project_uuid}/export/excel")
async def export_project_excel(project_uuid: UUID):
    """Export project cost breakdown to Excel format.
    
    Returns Excel workbook with:
    - Cost Summary sheet
    - Category Labor Rates sheet
    - Items List sheet
    """
    from bimcalc.reporting.excel_export import generate_cost_breakdown_excel
    from bimcalc.db.models import ProjectModel
    from fastapi.responses import StreamingResponse
    from datetime import datetime
    
    async with get_session() as session:
        # Get project for filename
        project = await session.get(ProjectModel, project_uuid)
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")
        
        # Generate Excel file
        excel_bytes = await generate_cost_breakdown_excel(
            session,
            project.org_id,
            project.project_id
        )
        
        # Generate filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{project.project_id}_costs_{timestamp}.xlsx"
        
        #Return as streaming response
        return StreamingResponse(
            excel_bytes,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"'
            }
        )


@app.get("/api/projects/{project_uuid}/export/csv/items")
async def export_items_csv_endpoint(
    project_uuid: UUID,
    category: Optional[str] = Query(None, description="Filter by category")
):
    """Export project items to CSV."""
    from bimcalc.reporting.csv_export import export_items_csv
    from bimcalc.db.models import ProjectModel
    from fastapi.responses import StreamingResponse
    from datetime import datetime
    
    async with get_session() as session:
        project = await session.get(ProjectModel, project_uuid)
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")
            
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{project.project_id}_items_{timestamp}.csv"
        
        return StreamingResponse(
            export_items_csv(session, project.org_id, project.project_id, category=category),
            media_type="text/csv",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'}
        )


@app.get("/api/projects/{project_uuid}/export/csv/prices")
async def export_prices_csv_endpoint(
    project_uuid: UUID,
    category: Optional[str] = Query(None, description="Filter by category"),
    vendor: Optional[str] = Query(None, description="Filter by vendor")
):
    """Export price book to CSV."""
    from bimcalc.reporting.csv_export import export_prices_csv
    from bimcalc.db.models import ProjectModel
    from fastapi.responses import StreamingResponse
    from datetime import datetime
    
    async with get_session() as session:
        project = await session.get(ProjectModel, project_uuid)
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")
            
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{project.org_id}_prices_{timestamp}.csv"
        
        return StreamingResponse(
            export_prices_csv(session, project.org_id, category=category, vendor=vendor),
            media_type="text/csv",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'}
        )


@app.get("/api/projects/{project_uuid}/export/csv/matches")
async def export_matches_csv_endpoint(
    project_uuid: UUID,
    min_confidence: Optional[float] = Query(None, description="Filter by minimum confidence score"),
    decision: Optional[str] = Query(None, description="Filter by decision status")
):
    """Export match results to CSV."""
    from bimcalc.reporting.csv_export import export_matches_csv
    from bimcalc.db.models import ProjectModel
    from fastapi.responses import StreamingResponse
    from datetime import datetime
    
    async with get_session() as session:
        project = await session.get(ProjectModel, project_uuid)
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")
            
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{project.project_id}_matches_{timestamp}.csv"
        
        return StreamingResponse(
            export_matches_csv(
                session, 
                project.org_id, 
                project.project_id,
                min_confidence=min_confidence,
                decision=decision
            ),
            media_type="text/csv",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'}
        )


@app.get("/api/projects/{project_uuid}/export/pdf")
async def export_project_pdf(project_uuid: UUID):
    """Export project report to PDF."""
    from bimcalc.reporting.pdf_export import generate_project_pdf_report
    from bimcalc.db.models import ProjectModel
    from fastapi.responses import StreamingResponse
    from datetime import datetime
    
    async with get_session() as session:
        project = await session.get(ProjectModel, project_uuid)
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")
            
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{project.project_id}_report_{timestamp}.pdf"
        
        pdf_buffer = await generate_project_pdf_report(session, project.org_id, project.project_id)
        
        return StreamingResponse(
            pdf_buffer,
            media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'}
        )


@app.get("/api/projects/{project_uuid}/intelligence/risk")
async def get_project_risk_analysis(project_uuid: UUID):
    """Get risk analysis for a project."""
    from bimcalc.intelligence.risk_engine import RiskEngine
    from bimcalc.db.models import ItemModel, MatchResultModel, PriceItemModel
    
    async with get_session() as session:
        # Fetch all items with their matches and price items
        # Note: This is a simplified fetch for the MVP. In production, use joined loads.
        items_query = select(ItemModel).where(
            ItemModel.project_id == str(project_uuid)  # Assuming project_id is stored as string in items
        )
        items = (await session.execute(items_query)).scalars().all()
        
        if not items:
            return {"summary": {"high": 0, "medium": 0, "low": 0}, "high_risk_items": []}
            
        engine = RiskEngine()
        risk_scores = []
        
        for item in items:
            # Fetch match result
            match_query = select(MatchResultModel).where(MatchResultModel.item_id == item.id)
            match_result = (await session.execute(match_query)).scalar_one_or_none()
            
            # Fetch price item if match exists
            price_item = None
            if match_result and match_result.price_item_id:
                price_item = await session.get(PriceItemModel, match_result.price_item_id)
                
            # Calculate risk
            score = engine.calculate_item_risk(item, match_result, price_item)
            risk_scores.append({
                "item_id": str(item.id),
                "family": item.family,
                "type": item.type_name,
                "score": score.total_risk_score,
                "factors": score.risk_factors
            })
            
        # Aggregate results
        high_risk = [s for s in risk_scores if s["score"] >= 80]
        medium_risk = [s for s in risk_scores if 50 <= s["score"] < 80]
        low_risk = [s for s in risk_scores if s["score"] < 50]
        
        return {
            "summary": {
                "high": len(high_risk),
                "medium": len(medium_risk),
                "low": len(low_risk),
                "avg_score": sum(s["score"] for s in risk_scores) / len(risk_scores) if risk_scores else 0
            },
            "high_risk_items": sorted(high_risk, key=lambda x: x["score"], reverse=True)[:10]  # Top 10
        }


@app.get("/api/projects/{project_uuid}/intelligence/recommendations")
async def get_project_recommendations(project_uuid: UUID):
    """Get actionable recommendations for a project."""
    from bimcalc.intelligence.recommendation_engine import RecommendationEngine
    from bimcalc.db.models import ItemModel, MatchResultModel, PriceItemModel
    
    async with get_session() as session:
        # Fetch items
        items_query = select(ItemModel).where(
            ItemModel.project_id == str(project_uuid)
        )
        items = (await session.execute(items_query)).scalars().all()
        
        if not items:
            return {"recommendations": []}
            
        # Fetch matches
        item_ids = [item.id for item in items]
        match_query = select(MatchResultModel).where(MatchResultModel.item_id.in_(item_ids))
        matches_list = (await session.execute(match_query)).scalars().all()
        matches_map = {m.item_id: m for m in matches_list}
        
        # Fetch price items
        price_item_ids = [m.price_item_id for m in matches_list if m.price_item_id]
        price_items_map = {}
        if price_item_ids:
            price_query = select(PriceItemModel).where(PriceItemModel.id.in_(price_item_ids))
            price_items_list = (await session.execute(price_query)).scalars().all()
            price_items_map = {p.id: p for p in price_items_list}
            
        # Generate recommendations
        engine = RecommendationEngine()
        recommendations = engine.generate_recommendations(items, matches_map, price_items_map)
        
        return {
            "recommendations": [
                {
                    "type": r.type,
                    "severity": r.severity,
                    "message": r.message,
                    "action_label": r.action_label,
                    "action_url": r.action_url,
                    "item_id": str(r.item_id),
                    "potential_saving": r.potential_saving
                }
                for r in recommendations
            ]
        }


@app.get("/api/projects/{project_uuid}/intelligence/compliance")
async def get_project_compliance(project_uuid: UUID):
    """Get compliance status for a project."""
    from bimcalc.intelligence.compliance_engine import ComplianceEngine
    from bimcalc.db.models import ItemModel, MatchResultModel, PriceItemModel, ProjectModel
    from bimcalc.db.models_intelligence import ComplianceRuleModel
    
    async with get_session() as session:
        # 1. Fetch Project to get Org ID
        project = await session.get(ProjectModel, project_uuid)
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")
            
        org_id = project.org_id
        
        # 2. Fetch Rules (Seed if empty)
        rules_query = select(ComplianceRuleModel).where(
            ComplianceRuleModel.org_id == org_id,
            ComplianceRuleModel.is_active == True
        )
        rules = (await session.execute(rules_query)).scalars().all()
        
        if not rules:
            # Seed default rules
            default_rules = [
                ComplianceRuleModel(
                    id=uuid4(), org_id=org_id, name="Classification Required", 
                    description="All items must have a classification code",
                    rule_type="classification_required", severity="high", is_active=True
                ),
                ComplianceRuleModel(
                    id=uuid4(), org_id=org_id, name="Approved Vendors Only", 
                    description="Items must be sourced from approved vendors",
                    rule_type="vendor_whitelist", severity="critical", is_active=True,
                    configuration={"vendors": ["Vendor A", "Vendor B", "Global Supplies Ltd"]}
                )
            ]
            session.add_all(default_rules)
            await session.commit()
            rules = default_rules
            
        # 3. Fetch Data
        items_query = select(ItemModel).where(ItemModel.project_id == str(project_uuid))
        items = (await session.execute(items_query)).scalars().all()
        
        if not items:
            return {"summary": {"passed": 0, "failed": 0, "score": 100}, "failures": []}
            
        item_ids = [item.id for item in items]
        match_query = select(MatchResultModel).where(MatchResultModel.item_id.in_(item_ids))
        matches_list = (await session.execute(match_query)).scalars().all()
        matches_map = {m.item_id: m for m in matches_list}
        
        price_item_ids = [m.price_item_id for m in matches_list if m.price_item_id]
        price_items_map = {}
        if price_item_ids:
            price_query = select(PriceItemModel).where(PriceItemModel.id.in_(price_item_ids))
            price_items_list = (await session.execute(price_query)).scalars().all()
            price_items_map = {p.id: p for p in price_items_list}
            
        # 4. Evaluate
        engine = ComplianceEngine()
        all_results = []
        
        for item in items:
            match = matches_map.get(item.id)
            price_item = None
            if match and match.price_item_id:
                price_item = price_items_map.get(match.price_item_id)
                
            results = engine.evaluate_item(item, price_item, rules)
            all_results.extend(results)
            
        # 5. Aggregate
        failures = [r for r in all_results if not r.passed]
        total_checks = len(all_results)
        passed_checks = total_checks - len(failures)
        score = (passed_checks / total_checks * 100) if total_checks > 0 else 100
        
        # Group failures by item for UI
        failures_by_item = {}
        for f in failures:
            if f.item_id not in failures_by_item:
                # Find item details (inefficient but fine for MVP)
                item = next(i for i in items if i.id == f.item_id)
                failures_by_item[f.item_id] = {
                    "item_id": str(item.id),
                    "family": item.family,
                    "type": item.type_name,
                    "issues": []
                }
            failures_by_item[f.item_id]["issues"].append(f.message)
            
        return {
            "summary": {
                "passed": passed_checks,
                "failed": len(failures),
                "total": total_checks,
                "score": score
            },
            "failures": list(failures_by_item.values())[:20] # Limit to 20 items
        }


# --- Rule Management Endpoints ---

class RuleUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None
    configuration: Optional[Dict] = None
    severity: Optional[str] = None

class RuleCreate(BaseModel):
    name: str
    description: str
    rule_type: str
    severity: str
    is_active: bool = True
    configuration: Dict = {}

@app.get("/api/projects/{project_uuid}/intelligence/rules")
async def get_project_rules(project_uuid: UUID):
    """Get all compliance rules for a project's organization."""
    from bimcalc.db.models import ProjectModel
    from bimcalc.db.models_intelligence import ComplianceRuleModel
    
    async with get_session() as session:
        project = await session.get(ProjectModel, project_uuid)
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")
            
        rules_query = select(ComplianceRuleModel).where(
            ComplianceRuleModel.org_id == project.org_id
        )
        rules = (await session.execute(rules_query)).scalars().all()
        
        return {
            "rules": [
                {
                    "id": str(r.id),
                    "name": r.name,
                    "description": r.description,
                    "rule_type": r.rule_type,
                    "severity": r.severity,
                    "is_active": r.is_active,
                    "configuration": r.configuration
                }
                for r in rules
            ]
        }

@app.post("/api/projects/{project_uuid}/intelligence/rules")
async def create_project_rule(project_uuid: UUID, rule: RuleCreate):
    """Create a new compliance rule."""
    from bimcalc.db.models import ProjectModel
    from bimcalc.db.models_intelligence import ComplianceRuleModel
    
    async with get_session() as session:
        project = await session.get(ProjectModel, project_uuid)
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")
            
        new_rule = ComplianceRuleModel(
            id=uuid4(),
            org_id=project.org_id,
            name=rule.name,
            description=rule.description,
            rule_type=rule.rule_type,
            severity=rule.severity,
            is_active=rule.is_active,
            configuration=rule.configuration
        )
        session.add(new_rule)
        await session.commit()
        
        return {"id": str(new_rule.id), "status": "created"}

@app.put("/api/projects/{project_uuid}/intelligence/rules/{rule_id}")
async def update_project_rule(project_uuid: UUID, rule_id: UUID, update: RuleUpdate):
    """Update an existing compliance rule."""
    from bimcalc.db.models_intelligence import ComplianceRuleModel
    
    async with get_session() as session:
        rule = await session.get(ComplianceRuleModel, rule_id)
        if not rule:
            raise HTTPException(status_code=404, detail="Rule not found")
            
        if update.name is not None: rule.name = update.name
        if update.description is not None: rule.description = update.description
        if update.is_active is not None: rule.is_active = update.is_active
        if update.configuration is not None: rule.configuration = update.configuration

        if update.severity is not None: rule.severity = update.severity
        
        await session.commit()
        return {"status": "updated"}

# ------------------------------------------------------------------------------
# Document Analysis Endpoints
# ------------------------------------------------------------------------------

from bimcalc.intelligence.document_processor import DocumentProcessor
from bimcalc.reporting.analytics import AnalyticsEngine
from bimcalc.db.models_documents import ProjectDocumentModel, ExtractedItemModel
from fastapi import UploadFile, BackgroundTasks, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from bimcalc.db.models import ProjectModel
# get_session is already imported from bimcalc.db.connection

@app.on_event("startup")
async def startup():
    try:
        from arq import create_pool
        from bimcalc.worker import WorkerSettings
        app.state.arq_pool = await create_pool(WorkerSettings.redis_settings)
    except ImportError:
        logger.warning("arq not installed, background tasks disabled")
    except Exception as e:
        logger.warning(f"Failed to initialize arq pool: {e}")

@app.on_event("shutdown")
async def shutdown():
    if hasattr(app.state, "arq_pool"):
        await app.state.arq_pool.close()

@app.post("/api/projects/{project_uuid}/documents/upload")
async def upload_document(
    project_uuid: UUID,
    file: UploadFile,
    db: AsyncSession = Depends(get_db),
    request: Request = None # Added request to access app state
):
    """Upload a document for analysis."""
    # Verify project exists
    result = await db.execute(select(ProjectModel).where(ProjectModel.id == project_uuid))
    project = result.scalars().first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    processor = DocumentProcessor(db)
    document = await processor.ingest_document(file, project.org_id, str(project_uuid))
    
    # Enqueue processing job
    if hasattr(request.app.state, "arq_pool"):
        await request.app.state.arq_pool.enqueue_job("process_document_job", str(document.id))
        document.status = "pending" # Ensure status is pending
    else:
        # Fallback for testing or if pool not init
        logger.warning("ARQ pool not initialized, falling back to sync processing")
        await processor.process_document(document.id) 
    
    return {"id": str(document.id), "filename": document.filename, "status": document.status}

@app.post("/api/projects/{project_uuid}/documents/{document_id}/process")
async def process_document_endpoint(
    project_uuid: UUID,
    document_id: UUID,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db)
):
    """Trigger processing for a document."""
    processor = DocumentProcessor(db)
    # Note: passing db session to background task is risky if session closes. 
    # Better to create new session in task. For now, we'll run it awaitable to ensure it finishes.
    # Or just run it synchronously for MVP.
    await processor.process_document(document_id)
    return {"status": "processing_started"}

@app.get("/api/projects/{project_uuid}/documents")
async def get_project_documents(
    project_uuid: UUID,
    db: AsyncSession = Depends(get_db)
):
    """List all documents for a project."""
    result = await db.execute(
        select(ProjectDocumentModel)
        .where(ProjectDocumentModel.project_id == str(project_uuid))
        .order_by(ProjectDocumentModel.uploaded_at.desc())
    )
    docs = result.scalars().all()
    return [
        {
            "id": str(d.id),
            "filename": d.filename,
            "status": d.status,
            "uploaded_at": d.uploaded_at,
            "file_size": d.file_size_bytes
        }
        for d in docs
    ]

class ConvertItemsRequest(BaseModel):
    item_ids: List[UUID] | Literal["all"]

@app.post("/api/projects/{project_uuid}/documents/{document_id}/convert")
async def convert_document_items(
    project_uuid: UUID,
    document_id: UUID,
    request: ConvertItemsRequest,
    db: AsyncSession = Depends(get_db)
):
    """Convert extracted items to project estimate items."""
    # Verify document exists and belongs to project
    result = await db.execute(
        select(ProjectDocumentModel)
        .where(
            ProjectDocumentModel.id == document_id,
            ProjectDocumentModel.project_id == str(project_uuid)
        )
    )
    document = result.scalars().first()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    # Fetch items to convert
    query = select(ExtractedItemModel).where(
        ExtractedItemModel.document_id == document_id,
        ExtractedItemModel.is_converted == False
    )
    
    if request.item_ids != "all":
        query = query.where(ExtractedItemModel.id.in_(request.item_ids))
        
    result = await db.execute(query)
    items_to_convert = result.scalars().all()
    
    if not items_to_convert:
        return {"converted_count": 0, "message": "No eligible items found to convert"}

    converted_count = 0
    for extracted in items_to_convert:
        # Create new ItemModel
        new_item = ItemModel(
            id=uuid4(),
            org_id=document.org_id,
            project_id=document.project_id,
            family="Document Import",
            type_name=extracted.description or "Unknown Item",
            category="Uncategorized",
            system_type="Document Import",
            quantity=extracted.quantity,
            unit=extracted.unit,
            attributes={
                "source_document_id": str(document_id),
                "source_extracted_item_id": str(extracted.id),
                "estimated_unit_price": float(extracted.unit_price) if extracted.unit_price else None,
                "original_text": extracted.raw_text
            }
        )
        db.add(new_item)
        
        # Update extracted item status
        extracted.is_converted = True
        extracted.converted_item_id = new_item.id
        
        converted_count += 1
    
    await db.commit()
    
    return {
        "converted_count": converted_count,
        "message": f"Successfully converted {converted_count} items to project estimate"
    }

@app.get("/api/projects/{project_uuid}/documents/{document_id}/results")
async def get_document_results(
    project_uuid: UUID,
    document_id: UUID,
    db: AsyncSession = Depends(get_db)
):
    """Get extracted items for a document."""
    result = await db.execute(
        select(ExtractedItemModel)
        .where(ExtractedItemModel.document_id == document_id)
        .order_by(ExtractedItemModel.page_number)
    )
    items = result.scalars().all()
    return [
        {
            "id": str(i.id),
            "description": i.description,
            "quantity": i.quantity,
            "unit": i.unit,
            "unit_price": i.unit_price,
            "total_price": i.total_price,
            "confidence": i.confidence_score,
            "page": i.page_number,
            "raw_text": i.raw_text
        }
        for i in items
    ]

@app.delete("/api/projects/{project_uuid}/intelligence/rules/{rule_id}")
async def delete_project_rule(project_uuid: UUID, rule_id: UUID):
    """Delete a compliance rule."""
    from bimcalc.db.models_intelligence import ComplianceRuleModel
    
    async with get_session() as session:
        rule = await session.get(ComplianceRuleModel, rule_id)
        if not rule:
            raise HTTPException(status_code=404, detail="Rule not found")
            
        await session.delete(rule)
        await session.commit()
        return {"status": "deleted"}




# ============================================================================
# Analytics & Reporting
# ============================================================================

@app.get("/api/projects/{project_uuid}/analytics/cost-trends")
async def get_cost_trends(
    project_uuid: UUID,
    db: AsyncSession = Depends(get_db)
):
    """Get historical cost trends."""
    try:
        engine = AnalyticsEngine(db)
        return await engine.get_cost_trends(project_uuid)
    except Exception as e:
        # Return empty data if analytics fails (e.g., project doesn't exist)
        return {"labels": [], "datasets": [{"label": "Cumulative Cost", "data": [], "borderColor": "#4F46E5", "backgroundColor": "rgba(79, 70, 229, 0.1)", "fill": True}]}

@app.get("/api/projects/{project_uuid}/analytics/category-distribution")
async def get_category_distribution(
    project_uuid: UUID,
    db: AsyncSession = Depends(get_db)
):
    """Get cost distribution by category."""
    try:
        engine = AnalyticsEngine(db)
        return await engine.get_category_distribution(project_uuid)
    except Exception as e:
        return {"labels": [], "datasets": [{"data": [], "backgroundColor": []}]}

@app.get("/api/projects/{project_uuid}/analytics/resource-utilization")
async def get_resource_utilization(
    project_uuid: UUID,
    db: AsyncSession = Depends(get_db)
):
    """Get resource utilization metrics."""
    try:
        engine = AnalyticsEngine(db)
        return await engine.get_resource_utilization(project_uuid)
    except Exception as e:
        return {"labels": [], "datasets": [{"label": "Item Count", "data": [], "backgroundColor": "#10B981"}]}


# ============================================================================
# Report Builder
# ============================================================================

class ReportTemplateCreate(BaseModel):
    name: str
    org_id: str
    project_id: str | None = None
    configuration: dict

@app.post("/api/reports/templates")
async def create_report_template(
    template: ReportTemplateCreate,
    db: AsyncSession = Depends(get_db)
):
    """Create a new report template."""
    from bimcalc.reporting.builder import ReportBuilder
    builder = ReportBuilder(db)
    return await builder.create_template(
        org_id=template.org_id,
        name=template.name,
        config=template.configuration,
        project_id=template.project_id
    )

@app.get("/api/reports/templates")
async def get_report_templates(
    org_id: str,
    project_id: str | None = None,
    db: AsyncSession = Depends(get_db)
):
    """Get available report templates."""
    from bimcalc.reporting.builder import ReportBuilder
    builder = ReportBuilder(db)
    return await builder.get_templates(org_id, project_id)


# ============================================================================
# Email Notifications
# ============================================================================

class SendEmailRequest(BaseModel):
    recipient_emails: list[str]
    report_type: str = "weekly"

@app.post("/api/projects/{project_uuid}/email/send-report")
async def send_project_report(
    project_uuid: UUID,
    request: SendEmailRequest,
    background_tasks: BackgroundTasks,
    db_request: Request = None
):
    """Send a project report via email using background task."""
    # Enqueue email job
    if hasattr(db_request.app.state, "arq_pool"):
        await db_request.app.state.arq_pool.enqueue_job(
            "send_scheduled_report_job",
            str(project_uuid),
            request.recipient_emails,
            request.report_type
        )
        return {"status": "queued", "job": "send_scheduled_report_job"}
    else:
        return {"status": "error", "message": "ARQ not available"}


# ============================================================================
# Vendor & Price Intelligence
# ============================================================================

@app.get("/prices", response_class=HTMLResponse)
async def prices_page(request: Request, org: str = "default", project: str = "default"):
    """Vendor and price intelligence dashboard."""
    return app.templates.TemplateResponse(
        request, 
        "prices.html", 
        {"org_id": org, "project_id": project}
    )

@app.post("/api/vendors/extract")
async def extract_vendors(org: str = Query(...), project: str = Query(...)):
    """Extract vendor info and analyze prices using AI."""
    from bimcalc.intelligence.vendors import extract_vendor_info, classify_vendor
    from sqlalchemy import select
    
    async with get_session() as session:
        # Get items for project
        query = select(ItemModel).where(
            ItemModel.org_id == org,
            ItemModel.project_id == project
        ).limit(50)  # Limit for demo performance
        
        result = await session.execute(query)
        items = list(result.scalars())
        
        vendors = {}
        insights = []
        
        # Process items
        for item in items:
            # 1. Extract vendor from description/name
            description = f"{item.family} {item.type_name}"
            info = await extract_vendor_info(description)
            vendor_name = info.get("vendor_name") or "Unknown Vendor"
            
            if vendor_name not in vendors:
                vendors[vendor_name] = {
                    "items": [],
                    "total_value": 0,
                    "category": None
                }
            
            # Mock price for demo (since we don't have real price data yet)
            # In production this would come from the item.price field
            import random
            price = random.randint(100, 5000)
            variance = random.randint(-15, 25)
            
            vendors[vendor_name]["items"].append({
                "id": str(item.id),
                "family": item.family,
                "type_name": item.type_name,
                "price": price,
                "variance": variance
            })
            vendors[vendor_name]["total_value"] += price
            
        # 2. Classify vendors
        for name, data in vendors.items():
            if name != "Unknown Vendor":
                item_names = [i["type_name"] for i in data["items"]]
                classification = await classify_vendor(name, item_names)
                data["category"] = classification.get("category")
        
        # 3. Generate Insights
        high_variance_vendors = [
            name for name, data in vendors.items() 
            if any(i["variance"] > 20 for i in data["items"])
        ]
        
        if high_variance_vendors:
            insights.append({
                "title": "High Price Variance Detected",
                "description": f"Vendors {', '.join(high_variance_vendors[:3])} have items with >20% price variance above market average."
            })
            
        insights.append({
            "title": "Vendor Consolidation Opportunity",
            "description": f"You have {len(vendors)} active vendors. Consider consolidating electrical supplies to negotiate better rates."
        })
            
        return {
            "vendors": vendors,
            "insights": insights
        }


@app.post("/api/prices/fetch-live")
async def fetch_live_prices(org: str = Query(...), project: str = Query(...)):
    """Fetch live prices from external suppliers (Demo)."""
    from bimcalc.intelligence.suppliers import fetch_live_price_for_item
    from sqlalchemy import select
    
    async with get_session() as session:
        # Get items for project
        query = select(ItemModel).where(
            ItemModel.org_id == org,
            ItemModel.project_id == project
        ).limit(20)  # Limit for demo
        
        result = await session.execute(query)
        items = list(result.scalars())
        
        updated_items = []
        
        for item in items:
            # Fetch live price
            data = await fetch_live_price_for_item(item.family, item.type_name)
            
            # Update item (in a real app, we'd save this to the DB)
            # For this demo, we just return the data to the frontend
            updated_items.append({
                "id": str(item.id),
                "family": item.family,
                "type_name": item.type_name,
                "old_price": 0, # Placeholder
                "new_price": data["price"],
                "supplier": data["supplier"],
                "fetched_at": data["fetched_at"]
            })
            
        return {
            "success": True,
            "updated_count": len(updated_items),
            "items": updated_items
        }


# ============================================================================
# Classification Management
# ============================================================================

@app.get("/classifications", response_class=HTMLResponse)
async def classifications_page(
    request: Request,
    org: str | None = None,
    project: str | None = None,
):
    """Classification management page."""
    org_id, project_id = _get_org_project(request, org, project)

    return templates.TemplateResponse(
        "classifications.html",
        {
            "request": request,
            "org_id": org_id,
            "project_id": project_id,
        },
    )


@app.get("/api/classifications/mappings")
async def get_classification_mappings(
    org: str = Query(...),
    project: str = Query(...),
):
    """Get all classification mappings for a project."""
    from bimcalc.db.models import ProjectClassificationMappingModel
    
    async with get_session() as session:
        stmt = (
            select(ProjectClassificationMappingModel)
            .where(
                ProjectClassificationMappingModel.org_id == org,
                ProjectClassificationMappingModel.project_id == project,
            )
            .order_by(ProjectClassificationMappingModel.local_code)
        )
        result = await session.execute(stmt)
        mappings = result.scalars().all()

    return [
        {
            "id": str(m.id),
            "local_code": m.local_code,
            "standard_code": m.standard_code,
            "description": m.description,
            "created_by": m.created_by,
            "created_at": m.created_at.isoformat(),
        }
        for m in mappings
    ]


@app.post("/api/classifications/mappings")
async def create_classification_mapping(
    org: str = Form(...),
    project: str = Form(...),
    local_code: str = Form(...),
    standard_code: str = Form(...),
    description: str = Form(default=""),
):
    """Create a new classification mapping."""
    from bimcalc.db.models import ProjectClassificationMappingModel
    
    async with get_session() as session:
        # Check for duplicate
        existing = await session.execute(
            select(ProjectClassificationMappingModel).where(
                ProjectClassificationMappingModel.org_id == org,
                ProjectClassificationMappingModel.project_id == project,
                ProjectClassificationMappingModel.local_code == local_code,
            )
        )
        if existing.scalar_one_or_none():
            raise HTTPException(
                status_code=400,
                detail=f"Mapping for local code '{local_code}' already exists"
            )

        mapping = ProjectClassificationMappingModel(
            org_id=org,
            project_id=project,
            local_code=local_code,
            standard_code=standard_code,
            description=description,
            created_by="web-ui",
        )
        session.add(mapping)
        await session.commit()

    return {"success": True, "message": "Mapping created successfully"}


@app.delete("/api/classifications/mappings/{mapping_id}")
async def delete_classification_mapping(mapping_id: UUID):
    """Delete a classification mapping."""
    from bimcalc.db.models import ProjectClassificationMappingModel
    
    async with get_session() as session:
        stmt = select(ProjectClassificationMappingModel).where(
            ProjectClassificationMappingModel.id == mapping_id
        )
        result = await session.execute(stmt)
        mapping = result.scalar_one_or_none()

        if not mapping:
            raise HTTPException(status_code=404, detail="Mapping not found")

        await session.delete(mapping)
        await session.commit()

    return {"success": True, "message": "Mapping deleted successfully"}

# ============================================================================
# Compliance Checker Routes
# ============================================================================

@app.get("/compliance", response_class=HTMLResponse)
async def compliance_dashboard(
    request: Request,
    org: str | None = None,
    project: str | None = None,
):
    """Compliance Checker Dashboard."""
    org_id, project_id = _get_org_project(request, org, project)
    return templates.TemplateResponse(
        "compliance.html",
        {
            "request": request,
            "org_id": org_id,
            "project_id": project_id,
        },
    )

@app.post("/api/compliance/upload")
async def upload_compliance_spec(
    file: UploadFile = File(...),
    org_id: str = Form(...),
    project_id: str = Form(...),
):
    """Upload specification and extract rules."""
    content = await file.read()
    text_content = ""
    
    # Simple text extraction
    try:
        text_content = content.decode("utf-8")
    except UnicodeDecodeError:
        # TODO: Handle PDF/Docx
        return JSONResponse(
            status_code=400, 
            content={"detail": "Only text files supported for MVP."}
        )
        
    rules = await extract_rules_from_text(text_content)
    
    if not rules:
        return JSONResponse(content={"rule_count": 0, "message": "No rules found."})
        
    async with get_session() as session:
        # Save rules
        for r in rules:
            rule_model = ComplianceRuleModel(
                org_id=org_id,
                project_id=project_id,
                name=r["name"],
                description=r["description"],
                rule_logic=r["rule_logic"],
                created_by="web-upload"
            )
            session.add(rule_model)
        await session.commit()
        
    return {"rule_count": len(rules)}

@app.get("/api/compliance/rules")
async def get_compliance_rules(
    org: str = Query(...),
    project: str = Query(...),
):
    async with get_session() as session:
        stmt = select(ComplianceRuleModel).where(
            ComplianceRuleModel.org_id == org,
            ComplianceRuleModel.project_id == project
        )
        rules = (await session.execute(stmt)).scalars().all()
        return {"rules": rules}

@app.post("/api/compliance/check")
async def trigger_compliance_check(
    org: str = Query(...),
    project: str = Query(...),
):
    async with get_session() as session:
        stats = await run_compliance_check(session, org, project)
        return {"stats": stats}

@app.get("/api/compliance/results")
async def get_compliance_results(
    org: str = Query(...),
    project: str = Query(...),
):
    async with get_session() as session:
        # Join with Item and Rule to get names
        stmt = (
            select(ComplianceResultModel, ItemModel.type_name, ComplianceRuleModel.name)
            .join(ItemModel, ComplianceResultModel.item_id == ItemModel.id)
            .join(ComplianceRuleModel, ComplianceResultModel.rule_id == ComplianceRuleModel.id)
            .where(
                ItemModel.org_id == org,
                ItemModel.project_id == project
            )
            .order_by(ComplianceResultModel.status)
        )
        results = (await session.execute(stmt)).all()
        
        data = []
        for res, item_name, rule_name in results:
            data.append({
                "id": str(res.id),
                "status": res.status,
                "message": res.message,
                "item_name": item_name,
                "rule_name": rule_name,
                "checked_at": res.checked_at.isoformat()
            })
            
        return {"results": data}

# ============================================================================
# Advanced Analytics Routes
# ============================================================================

@app.get("/analytics/advanced", response_class=HTMLResponse)
async def analytics_advanced_dashboard(
    request: Request,
    org: str | None = None,
    project: str | None = None,
):
    """Advanced Analytics Dashboard."""
    org_id, project_id = _get_org_project(request, org, project)
    return templates.TemplateResponse(
        "analytics_advanced.html",
        {
            "request": request,
            "org_id": org_id,
            "project_id": project_id,
        },
    )

@app.get("/api/analytics/history/{item_code}")
async def get_item_history_api(
    item_code: str,
    org: str = Query(...),
):
    from bimcalc.reporting.analytics import AnalyticsEngine
    async with get_session() as session:
        engine = AnalyticsEngine(session)
        return await engine.get_item_price_history(item_code, org)

@app.post("/api/analytics/vendor-comparison")
async def get_vendor_comparison_api(
    item_codes: List[str] = Body(...),
    org: str = Query(...),
):
    from bimcalc.reporting.analytics import AnalyticsEngine
    async with get_session() as session:
        engine = AnalyticsEngine(session)
        return await engine.compare_vendors(item_codes, org)

@app.get("/api/analytics/forecast")
async def get_forecast_api(
    project: str = Query(...),
    days: int = Query(90),
):
    from bimcalc.reporting.analytics import AnalyticsEngine
    async with get_session() as session:
        engine = AnalyticsEngine(session)
        return await engine.forecast_cost_trends(project, days)
