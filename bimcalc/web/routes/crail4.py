"""Crail4 integration routes for BIMCalc web UI.

Extracted from app_enhanced.py as part of Phase 3.13 web refactor.
Handles Crail4 AI-powered price data scraping configuration and synchronization.

Routes:
- GET  /crail4-config                - Configuration and management page
- POST /crail4-config/save           - Save API configuration
- POST /crail4-config/test           - Test API connection
- POST /crail4-config/sync           - Trigger manual sync job
- GET  /crail4-config/status/{job_id} - Poll sync job status
- POST /crail4-config/mappings/add   - Add classification mapping
"""

from __future__ import annotations

import os
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, JSONResponse
from sqlalchemy import func, select, text

from bimcalc.config import get_config
from bimcalc.db.connection import get_session
from bimcalc.db.models import ClassificationMappingModel
from bimcalc.web.auth import require_auth
from bimcalc.web.dependencies import get_org_project, get_templates

# Create router with crail4 tag
router = APIRouter(tags=["crail4"])


# ============================================================================
# Crail4 Integration Routes
# ============================================================================

@router.get("/crail4-config", response_class=HTMLResponse)
async def crail4_config_page(
    request: Request,
    org: str | None = None,
    current_user: str = Depends(require_auth),
    templates=Depends(get_templates),
):
    """Render Crail4 configuration page.

    Shows API configuration, connection status, sync statistics,
    import history, and classification mappings.

    Extracted from: app_enhanced.py:1383
    """
    org_id, _ = get_org_project(request, org)

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


@router.post("/crail4-config/save")
async def save_crail4_config(
    request: Request,
    api_key: str = Form(...),
    source_url: str = Form(...),
    base_url: str = Form(default="https://www.crawl4ai-cloud.com/query"),
    current_user: str = Depends(require_auth),
):
    """Save Crail4 configuration.

    Updates .env file and environment variables with API credentials.

    Extracted from: app_enhanced.py:1499
    """
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


@router.post("/crail4-config/test")
async def test_crail4_connection(
    current_user: str = Depends(require_auth),
):
    """Test Crail4 API connection.

    Attempts to connect to Crail4 API and fetch items to verify credentials.

    Extracted from: app_enhanced.py:1542
    """
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


@router.post("/crail4-config/sync")
async def trigger_crail4_sync(
    request: Request,
    classifications: str | None = Form(default=None),
    full_sync: bool = Form(default=False),
    region: str | None = Form(default=None),
    current_user: str = Depends(require_auth),
):
    """Trigger manual Crail4 sync.

    Enqueues a background job to fetch and import price data from Crail4.
    Returns HTMX fragment showing job status.

    Extracted from: app_enhanced.py:1569
    """
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


@router.get("/crail4-config/status/{job_id}")
async def get_sync_status(job_id: str, current_user: str = Depends(require_auth)):
    """Poll for sync job status.

    Returns HTMX fragment showing current job status with auto-refresh.
    Used for real-time progress updates during synchronization.

    Extracted from: app_enhanced.py:1609
    """
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

        else:  # queued or not_found
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


@router.post("/crail4-config/mappings/add")
async def add_classification_mapping(
    request: Request,
    source_scheme: str = Form(...),
    source_code: str = Form(...),
    target_scheme: str = Form(...),
    target_code: str = Form(...),
    confidence: float = Form(default=1.0),
    current_user: str = Depends(require_auth),
):
    """Add a new classification mapping.

    Creates a manual classification mapping for translating between
    classification schemes (e.g., vendor codes to UniClass).

    Extracted from: app_enhanced.py:1690
    """
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
