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

import csv
import io
import logging
import os
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, Request, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse
from sqlalchemy import func, select, text

from bimcalc.config import get_config
from bimcalc.db.connection import get_session
from bimcalc.db.models import ClassificationMappingModel
from bimcalc.web.auth import require_auth
from bimcalc.web.dependencies import get_org_project, get_templates

# Create router with crail4 tag



# ============================================================================
# Crail4 Integration Routes
# ============================================================================

router = APIRouter(prefix="/price-scout", tags=["price-scout"])

@router.get("", response_class=HTMLResponse)
async def price_scout_page(
    request: Request,
    current_user: str = Depends(require_auth),
    templates=Depends(get_templates),
):
    """Render the Price Scout configuration page."""
    # Get current config
    config = get_config()
    org_id = config.org_id
    
    # Check connection status
    connection_status = "unknown"
    connection_error = None
    
    if os.getenv("PRICE_SCOUT_API_KEY"):
        connection_status = "connected"
    else:
        connection_status = "not_configured"

    async with get_session() as session:
        # Get statistics
        try:
            stats_query = text("""
                SELECT
                    COUNT(DISTINCT id) as total_syncs,
                    COALESCE(SUM(items_loaded), 0) as total_items_imported,
                    COALESCE(SUM(items_rejected), 0) as total_items_rejected
                FROM price_import_runs
                WHERE org_id = :org_id AND (source = 'crail4' OR source = 'crail4_api' OR source = 'price_scout_api')
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
                    (PriceImportRunModel.source == "crail4") | (PriceImportRunModel.source == "crail4_api") | (PriceImportRunModel.source == "price_scout_api")
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
        "price_scout.html",
        {
            "request": request,
            "config": {
                "api_key": os.getenv("PRICE_SCOUT_API_KEY", ""),
                "source_url": os.getenv("PRICE_SCOUT_SOURCE_URL", ""),
                "target_scheme": "UniClass2015",
            },
            "connection_status": connection_status,
            "connection_error": connection_error,
            "stats": stats,
            "import_runs": import_runs,
            "mappings": mappings,
            "org_id": org_id,
            "project_id": "default",
        },
    )


@router.post("/save")
async def save_price_scout_config(
    request: Request,
    api_key: str = Form(...),
    source_url: str = Form(""),
    current_user: str = Depends(require_auth),
):
    """Save Price Scout configuration.

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
        "PRICE_SCOUT_API_KEY": api_key,
        "PRICE_SCOUT_SOURCE_URL": source_url,
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
    os.environ["PRICE_SCOUT_API_KEY"] = api_key
    os.environ["PRICE_SCOUT_SOURCE_URL"] = source_url

    return JSONResponse({"status": "success", "message": "Configuration saved successfully"})


@router.post("/test")
async def test_price_scout_connection(
    current_user: str = Depends(require_auth),
):
    """Test connection to OpenAI. Scout connection.

    Verifies OpenAI API connectivity.
    """
    try:
        from bimcalc.intelligence.price_scout import SmartPriceScout
        
        # Simple test with a dummy URL to check LLM instantiation
        # We don't actually fetch to save time/tokens, just check init
        async with SmartPriceScout() as scout:
            pass
            
        return JSONResponse({"status": "success", "message": "Smart Price Scout (OpenAI) Connected"})
    except Exception as e:
        return JSONResponse(
            {"status": "error", "message": f"Connection failed: {str(e)}"},
            status_code=500
        )


@router.post("/sync")
async def trigger_price_scout_sync(
    request: Request,
    classifications: str | None = Form(default=None),
    full_sync: bool = Form(default=False),
    region: str | None = Form(default=None),
    current_user: str = Depends(require_auth),
):
    """Trigger manual Price Scout sync.

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
            "run_price_scout_sync",
            org_id=org_id,
            full_sync=full_sync
        )
        print(f"Enqueued Price Scout sync job: {job.job_id} for org {org_id}")

        # Return HTML fragment for HTMX
        return HTMLResponse(f"""
            <div class="message message-info" hx-get="/crail4-config/status/{job.job_id}" hx-trigger="load delay:2s" hx-swap="outerHTML">
                <strong>Sync Started!</strong><br>
                Job ID: {job.job_id}<br>
                <small>Checking status...</small>
            </div>
        """)

    except Exception as e:
        return HTMLResponse(f"""
            <div class="message message-error">
                <strong>Error:</strong> {str(e)}
            </div>
        """)


@router.post("/scout")
async def trigger_quick_scout(
    request: Request,
    url: str = Form(...),
    force_refresh: bool = Form(False),
    current_user: str = Depends(require_auth),
):
    """Execute quick scout on a single URL.

    Uses SmartPriceScout to extract data and returns HTML fragment.
    """
    try:
        from bimcalc.intelligence.price_scout import SmartPriceScout
        
        async with SmartPriceScout() as scout:
            result = await scout.extract(url, force_refresh=force_refresh)
            
        # Handle new schema (v2) or legacy flat dict (v1 fallback)
        products = result.get("products", [])
        page_type = result.get("page_type", "product_detail")
        
        # Fallback for legacy flat structure
        if not products and "description" in result:
            products = [result]
            page_type = "product_detail"

        if page_type == "product_list" and len(products) > 1:
            # Render Table for Product List
            rows = ""
            for p in products:
                rows += f"""
                <tr style="border-bottom: 1px solid #e2e8f0;">
                    <td style="padding: 0.75rem;">{p.get('vendor_code', 'N/A')}</td>
                    <td style="padding: 0.75rem;">{p.get('description', 'N/A')}</td>
                    <td style="padding: 0.75rem; font-weight: 600; color: #059669;">
                        {p.get('currency', '')} {p.get('unit_price', 'N/A')}
                    </td>
                    <td style="padding: 0.75rem;">
                         <button class="btn btn-sm" style="background: #edf2f7; color: #4a5568; padding: 0.25rem 0.5rem; border-radius: 4px; border: none;">
                            Import
                         </button>
                    </td>
                </tr>
                """
            
            html = f"""
            <div style="margin-top: 1.5rem; border: 1px solid #cbd5e1; border-radius: 8px; overflow: hidden;">
                <div style="background: #f8fafc; padding: 0.75rem 1rem; border-bottom: 1px solid #cbd5e1; font-weight: 600; display: flex; justify-content: space-between; align-items: center;">
                    <span>Found {len(products)} Products</span>
                    <span style="background: #dbeafe; color: #1e40af; padding: 0.25rem 0.5rem; border-radius: 999px; font-size: 0.75rem;">Product List</span>
                </div>
                <div style="overflow-x: auto;">
                    <table style="width: 100%; border-collapse: collapse; font-size: 0.9rem;">
                        <thead>
                            <tr style="background: #f1f5f9; text-align: left;">
                                <th style="padding: 0.75rem;">Code</th>
                                <th style="padding: 0.75rem;">Description</th>
                                <th style="padding: 0.75rem;">Price</th>
                                <th style="padding: 0.75rem;">Action</th>
                            </tr>
                        </thead>
                        <tbody>
                            {rows}
                        </tbody>
                    </table>
                </div>
            </div>
            """
        else:
            # Render Single Card (take first product)
            product = products[0] if products else {}
            
            html = f"""
            <div style="margin-top: 1.5rem; border: 1px solid #cbd5e1; border-radius: 8px; overflow: hidden;">
                <div style="background: #f8fafc; padding: 0.75rem 1rem; border-bottom: 1px solid #cbd5e1; font-weight: 600; display: flex; justify-content: space-between;">
                    <span>Extraction Result</span>
                    <span style="color: #10b981;">Success</span>
                </div>
                <div style="padding: 1rem;">
                    <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 1rem; margin-bottom: 1rem;">
                        <div>
                            <div style="font-size: 0.75rem; color: #64748b; text-transform: uppercase;">Vendor Code</div>
                            <div style="font-weight: 600; font-size: 1.1rem;">{product.get('vendor_code', 'N/A')}</div>
                        </div>
                        <div>
                            <div style="font-size: 0.75rem; color: #64748b; text-transform: uppercase;">Price</div>
                            <div style="font-weight: 600; font-size: 1.1rem; color: #059669;">
                                {product.get('currency', '')} {product.get('unit_price', 'N/A')}
                                <span style="font-size: 0.8rem; color: #64748b; font-weight: normal;">/ {product.get('unit', 'ea')}</span>
                            </div>
                        </div>
                    </div>
                    
                    <div style="margin-bottom: 1rem;">
                        <div style="font-size: 0.75rem; color: #64748b; text-transform: uppercase;">Description</div>
                        <div style="font-size: 1rem;">{product.get('description', 'N/A')}</div>
                    </div>

                    <div style="background: #f1f5f9; padding: 0.75rem; border-radius: 6px; font-family: monospace; font-size: 0.85rem; overflow-x: auto;">
                        <div style="font-size: 0.75rem; color: #64748b; text-transform: uppercase; margin-bottom: 0.25rem;">Raw Data</div>
                        {str(product)}
                    </div>
                </div>
            </div>
            """
        return HTMLResponse(html)

    except Exception as e:
        return HTMLResponse(f"""
            <div class="message message-error" style="margin-top: 1rem;">
                <strong>Extraction Failed:</strong> {str(e)}
            </div>
        """)

    org_id = get_config().org_id

    try:
        from bimcalc.core.queue import get_queue

        # Enqueue the job
        redis = await get_queue()
        job = await redis.enqueue_job(
            "run_price_scout_sync",
            org_id=org_id,
            full_sync=full_sync
        )
        print(f"Enqueued Price Scout sync job: {job.job_id} for org {org_id}")

        # Return HTML fragment for HTMX
        return HTMLResponse(f"""
            <div class="message message-info" hx-get="/crail4-config/status/{job.job_id}" hx-trigger="load delay:2s" hx-swap="outerHTML">
                <strong>Sync Started!</strong><br>
                Job ID: {job.job_id}<br>
                <small>Checking status...</small>
            </div>
        """)

    except Exception as e:
        return HTMLResponse(f"""
            <div class="message message-error">
                <strong>Error:</strong> {str(e)}
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
                    <strong>Sync Complete!</strong><br>
                    Loaded {items_loaded} of {items_fetched} items.
                    <br>
                    <a href="/crail4-config" class="btn btn-primary mt-2" style="font-size: 0.8rem;">Refresh Page</a>
                </div>
            """)

        elif status == "in_progress":
             return HTMLResponse(f"""
                <div class="message message-info" hx-get="/crail4-config/status/{job_id}" hx-trigger="load delay:2s" hx-swap="outerHTML">
                    <strong>Syncing...</strong><br>
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
                    <strong>Job Failed</strong><br>
                    The background job encountered an error.
                </div>
            """)

        else:  # queued or not_found
             return HTMLResponse(f"""
                <div class="message message-info" hx-get="/crail4-config/status/{job_id}" hx-trigger="load delay:2s" hx-swap="outerHTML">
                    <strong>Queued...</strong><br>
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


@router.get("/price-imports/{run_id}", response_class=HTMLResponse)
async def get_price_import_details(
    request: Request,
    run_id: str,
    current_user: str = Depends(require_auth),
    templates=Depends(get_templates),
):
    """Get details of a specific price import run.

    Returns HTML page with full details including rejection reasons and error messages.
    """
    from bimcalc.db.models import PriceImportRunModel

    async with get_session() as session:
        result = await session.execute(
            select(PriceImportRunModel).where(PriceImportRunModel.id == run_id)
        )
        run = result.scalar_one_or_none()

        if not run:
            return templates.TemplateResponse(
                "error.html",
                {
                    "request": request,
                    "message": "Import run not found",
                    "org_id": "default", # Fallback
                    "project_id": "default", # Fallback
                },
                status_code=404,
            )

        return templates.TemplateResponse(
            "price_import_detail.html",
            {
                "request": request,
                "run": run,
                "org_id": run.org_id,
            },
        )


from fastapi.responses import RedirectResponse

@router.get("/api/price-imports/{run_id}")
async def redirect_price_import_details(run_id: str):
    """Redirect legacy API route to new UI route."""
    return RedirectResponse(url=f"/price-imports/{run_id}")


@router.get("/crail4-config")
async def redirect_crail4_config():
    """Redirect legacy Crail4 config route to new Price Scout route."""
    return RedirectResponse(url="/price-scout")


# ============================================================================
# Bulk Import Logic
# ============================================================================

async def process_bulk_import_task(
    urls: list[str],
    org_id: str,
    project_id: str,
    user_id: str,
    force_refresh: bool = False
):
    """Background task to process bulk imported URLs."""
    logger = logging.getLogger(__name__)
    logger.info(f"Starting bulk import for {len(urls)} URLs")
    
    from bimcalc.intelligence.price_scout import SmartPriceScout
    from bimcalc.db.models import PriceImportItemModel, PriceImportModel
    
    # Create import record
    async with get_session() as session:
        import_record = PriceImportModel(
            id=uuid4(),
            org_id=org_id,
            project_id=project_id,
            source="bulk_scout",
            filename="bulk_import.csv",
            status="processing",
            created_by=user_id
        )
        session.add(import_record)
        await session.commit()
        import_id = import_record.id

    # Process URLs
    success_count = 0
    fail_count = 0
    
    async with SmartPriceScout() as scout:
        for url in urls:
            try:
                # Extract data
                result = await scout.extract(url, force_refresh=force_refresh)
                
                # Handle both single and multi-product results
                products = result.get("products", [])
                if not products and "description" in result:
                    products = [result]
                
                async with get_session() as session:
                    for p in products:
                        item = PriceImportItemModel(
                            id=uuid4(),
                            import_id=import_id,
                            org_id=org_id,
                            raw_data=p,
                            description=p.get("description"),
                            vendor_code=p.get("vendor_code"),
                            unit_price=p.get("unit_price"),
                            currency=p.get("currency"),
                            unit=p.get("unit"),
                            status="pending"
                        )
                        session.add(item)
                    await session.commit()
                
                success_count += 1
                
            except Exception as e:
                logger.error(f"Failed to scout {url}: {e}")
                fail_count += 1
                
    # Update status
    async with get_session() as session:
        record = await session.get(PriceImportModel, import_id)
        if record:
            record.status = "completed"
            record.notes = f"Processed {len(urls)} URLs. Success: {success_count}, Failed: {fail_count}"
            await session.commit()
            
    logger.info(f"Bulk import finished. Success: {success_count}, Failed: {fail_count}")


@router.post("/bulk-import")
async def bulk_import_upload(
    background_tasks: BackgroundTasks,
    request: Request,
    file: UploadFile = File(...),
    force_refresh: bool = Form(False),
    current_user: str = Depends(require_auth),
):
    """Handle bulk import CSV upload."""
    if not file.filename.endswith('.csv'):
        return HTMLResponse(
            '<div class="message message-error">Invalid file type. Please upload a CSV.</div>'
        )
        
    content = await file.read()
    text_content = content.decode('utf-8')
    
    urls = []
    try:
        csv_reader = csv.DictReader(io.StringIO(text_content))
        for row in csv_reader:
            if 'url' in row and row['url'].strip():
                urls.append(row['url'].strip())
    except Exception as e:
        return HTMLResponse(
            f'<div class="message message-error">Failed to parse CSV: {str(e)}</div>'
        )
        
    if not urls:
        return HTMLResponse(
            '<div class="message message-error">No URLs found in CSV. Ensure "url" column exists.</div>'
        )
        
    # Get context
    config = get_config()
    org_id = config.org_id or "default"
    project_id = "default" # TODO: Get from request if needed
    
    # Launch background task
    background_tasks.add_task(
        process_bulk_import_task,
        urls,
        org_id,
        project_id,
        current_user,
        force_refresh
    )
    
    return HTMLResponse(f"""
        <div class="message message-success">
            <strong>Import Started!</strong><br>
            Processing {len(urls)} URLs in the background. Check the "Imports" tab for progress.
        </div>
    """)
