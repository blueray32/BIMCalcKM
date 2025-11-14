"""Enhanced FastAPI web UI for BIMCalc - Full-featured management interface."""

from __future__ import annotations

import io
from datetime import datetime
from pathlib import Path
from typing import Optional
from uuid import UUID

import pandas as pd
from fastapi import Cookie, Depends, FastAPI, File, Form, HTTPException, Query, Request, Response, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import func, select

from bimcalc.config import get_config
from bimcalc.db.connection import get_session
from bimcalc.db.match_results import record_match_result
from bimcalc.db.models import ItemMappingModel, ItemModel, MatchResultModel, PriceItemModel
from bimcalc.ingestion.pricebooks import ingest_pricebook
from bimcalc.ingestion.schedules import ingest_schedule
from bimcalc.matching.orchestrator import MatchOrchestrator
from bimcalc.models import FlagSeverity, Item
from bimcalc.reporting.builder import generate_report
from bimcalc.review import approve_review_record, fetch_pending_reviews, fetch_review_record
from bimcalc.db.models import DataSyncLogModel
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
    username: str = Depends(require_auth) if AUTH_ENABLED else None,
):
    """Main dashboard with navigation and statistics."""
    org_id, project_id = _get_org_project(request, org, project)

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

        review_result = await session.execute(
            select(func.count())
            .select_from(MatchResultModel)
            .join(ItemModel, ItemModel.id == MatchResultModel.item_id)
            .where(
                ItemModel.org_id == org_id,
                ItemModel.project_id == project_id,
                MatchResultModel.decision == "manual-review",
            )
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
):
    """Review items requiring manual approval."""
    org_id, project_id = _get_org_project(request, org, project)

    # Convert checkbox value to boolean
    unmapped_filter = unmapped_only == "on" if unmapped_only else False

    async with get_session() as session:
        records = await fetch_pending_reviews(
            session,
            org_id,
            project_id,
            flag_types=_parse_flag_filter(flag),
            severity_filter=_parse_severity_filter(severity),
            unmapped_only=unmapped_filter,
        )

    return templates.TemplateResponse(
        "review.html",
        {
            "request": request,
            "records": records,
            "org_id": org_id,
            "project_id": project_id,
            "flag_filter": flag or "all",
            "severity_filter": severity or "all",
            "unmapped_only": unmapped_filter,
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
    page: int = Query(default=1, ge=1),
):
    """List and manage active mappings."""
    config = get_config()
    org_id = org or config.org_id
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
async def reports_page(request: Request, org: Optional[str] = None, project: Optional[str] = None):
    """Reports generation page."""
    org_id, project_id = _get_org_project(request, org, project)

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
):
    """View audit trail of all decisions."""
    org_id, project_id = _get_org_project(request, org, project)
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
async def pipeline_dashboard(request: Request, page: int = Query(default=1, ge=1)):
    """Pipeline status and management dashboard."""
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
    current_only: bool = Query(default=True),
    page: int = Query(default=1, ge=1),
):
    """List all price items with optional history."""
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
        },
    )
