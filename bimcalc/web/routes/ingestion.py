"""Ingestion routes for BIMCalc web UI.

Extracted from app_enhanced.py as part of Phase 3.3 web refactor.
Handles file upload and ingestion for schedules and price books.

Routes:
- GET  /ingest/history     - Ingest history dashboard
- GET  /ingest             - File upload page
- POST /ingest/schedules   - Upload and ingest Revit schedules (CSV/XLSX)
- POST /ingest/prices      - Upload and ingest price books (CSV/XLSX)
"""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse

from bimcalc.db.connection import get_session
from bimcalc.ingestion.pricebooks import ingest_pricebook
from bimcalc.ingestion.schedules import ingest_schedule
from bimcalc.intelligence.notifications import get_email_notifier, get_slack_notifier
from bimcalc.web.dependencies import get_org_project, get_templates

# Create router with ingestion tag
router = APIRouter(tags=["ingestion"])


# ============================================================================
# Ingestion Dashboard Routes
# ============================================================================

@router.get("/ingest/history", response_class=HTMLResponse)
async def ingest_history_page(
    request: Request,
    org: str | None = None,
    project: str | None = None,
    templates = Depends(get_templates),
):
    """Ingest history dashboard.

    Shows history of schedule and pricebook ingestions.

    Extracted from: app_enhanced.py:515
    """
    org_id, project_id = get_org_project(request, org, project)
    return templates.TemplateResponse(
        "ingest_history.html",
        {
            "request": request,
            "org_id": org_id,
            "project_id": project_id,
        },
    )


@router.get("/ingest", response_class=HTMLResponse)
async def ingest_page(
    request: Request,
    org: str | None = None,
    project: str | None = None,
    templates = Depends(get_templates),
):
    """File upload page for schedules and price books.

    Main ingestion UI with file upload forms.

    Extracted from: app_enhanced.py:848
    """
    org_id, project_id = get_org_project(request, org, project)

    return templates.TemplateResponse(
        "ingest.html",
        {
            "request": request,
            "org_id": org_id,
            "project_id": project_id,
        },
    )


# ============================================================================
# File Upload & Ingestion Routes
# ============================================================================

@router.post("/ingest/schedules")
async def ingest_schedules(
    file: UploadFile = File(...),
    org: str = Form(...),
    project: str = Form(...),
):
    """Upload and ingest Revit schedules (CSV/XLSX).

    Processes uploaded schedule file and imports items into database.
    Sends alerts on failure via email and Slack.

    Extracted from: app_enhanced.py:863
    """
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

        # Send alerts
        error_msg = str(e)
        email_notifier = get_email_notifier()
        slack_notifier = get_slack_notifier()

        # Background tasks for alerts to not block response too long (or use BackgroundTasks)
        # For now, await them as they are async and shouldn't take too long
        try:
            await email_notifier.send_ingestion_failure_alert(
                recipients=["admin@bimcalc.com"],  # TODO: Configure recipients
                filename=file.filename,
                error_message=error_msg,
                org_id=org
            )
            await slack_notifier.post_ingestion_failure_alert(
                filename=file.filename,
                error_message=error_msg,
                org_id=org
            )
        except Exception as alert_err:
            print(f"Failed to send alerts: {alert_err}")

        raise HTTPException(status_code=500, detail=error_msg)


@router.post("/ingest/prices")
async def ingest_prices(
    file: UploadFile = File(...),
    vendor: str = Form(default="default"),
    use_cmm: bool = Form(default=True),
):
    """Upload and ingest price books (CSV/XLSX) with optional CMM translation.

    Processes uploaded pricebook file and imports price items into database.
    Supports CMM (Classification Mapping Memory) for automatic classification.
    Sends alerts on failure via email and Slack.

    Args:
        file: Uploaded CSV/XLSX file
        vendor: Vendor/supplier identifier
        use_cmm: Whether to use CMM for classification mapping

    Extracted from: app_enhanced.py:918
    """
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

        # Send alerts
        error_msg = str(e)
        email_notifier = get_email_notifier()
        slack_notifier = get_slack_notifier()

        try:
            await email_notifier.send_ingestion_failure_alert(
                recipients=["admin@bimcalc.com"],
                filename=file.filename,
                error_message=error_msg,
                org_id=f"Vendor: {vendor}"
            )
            await slack_notifier.post_ingestion_failure_alert(
                filename=file.filename,
                error_message=error_msg,
                org_id=f"Vendor: {vendor}"
            )
        except Exception as alert_err:
            print(f"Failed to send alerts: {alert_err}")

        raise HTTPException(status_code=500, detail=error_msg)

    # Clean up
    temp_path.unlink()

    cmm_status = "with CMM enabled" if use_cmm else "without CMM"
    return {
        "success": True,
        "message": f"Imported {success_count} price items ({cmm_status})",
        "errors": errors[:5] if errors else [],
    }
