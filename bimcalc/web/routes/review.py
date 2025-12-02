"""Review routes for BIMCalc web UI.

Extracted from app_enhanced.py as part of Phase 3.5 web refactor.
Handles review workflow - approving and rejecting match results.

Routes:
- GET  /review         - Review dashboard (detailed and executive views)
- POST /review/approve - Approve a review item and create mapping
- POST /review/reject  - Reject a suggested match
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Form, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import select

from bimcalc.db.connection import get_session
from bimcalc.db.models import MatchResultModel
from bimcalc.models import FlagSeverity
from bimcalc.review import (
    approve_review_record,
    fetch_available_classifications,
    fetch_pending_reviews,
    fetch_review_record,
)
from bimcalc.web.dependencies import get_org_project, get_templates

# Create router with review tag
router = APIRouter(tags=["review"])


# ============================================================================
# Helper Functions
# ============================================================================

def _parse_flag_filter(flag: str | None) -> list[str] | None:
    """Parse flag filter parameter.

    Extracted from: app_enhanced.py:176
    """
    if flag is None or flag == "all" or flag == "":
        return None
    return [flag]


def _parse_severity_filter(severity: str | None) -> FlagSeverity | None:
    """Parse severity filter parameter.

    Extracted from: app_enhanced.py:182
    """
    if not severity or severity.lower() == "all":
        return None
    try:
        return FlagSeverity(severity)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid severity filter") from None


# ============================================================================
# Review Workflow Routes
# ============================================================================

@router.get("/review", response_class=HTMLResponse)
async def review_dashboard(
    request: Request,
    org: str | None = None,
    project: str | None = None,
    flag: str | None = Query(default=None),
    severity: str | None = Query(default=None),
    unmapped_only: str | None = Query(default=None),
    classification: str | None = Query(default=None),
    view: str | None = Query(default=None),
    templates=Depends(get_templates),
):
    """Review items requiring manual approval.

    Supports two views:
    - view=executive: High-level dashboard for stakeholders
    - (default): Detailed list for reviewers

    Extracted from: app_enhanced.py:418
    """
    org_id, project_id = get_org_project(request, org, project)

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


@router.post("/review/approve")
async def approve_item(
    match_result_id: UUID = Form(...),
    annotation: str | None = Form(None),
    org: str | None = Form(None),
    project: str | None = Form(None),
    flag: str | None = Form(None),
    severity: str | None = Form(None),
    unmapped_only: str | None = Form(None),
    classification: str | None = Form(None),
):
    """Approve a review item and create mapping.

    Extracted from: app_enhanced.py:488
    """
    org_id, project_id = get_org_project(None, org, project)

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


@router.post("/review/reject")
async def reject_review(
    request: Request,
    match_result_id: str = Form(...),
    org: str = Form(...),
    project: str = Form(...),
    flag: str | None = Form(default=None),
    severity: str | None = Form(default=None),
    unmapped_only: str | None = Form(default=None),
    classification: str | None = Form(default=None),
):
    """Reject a suggested match.

    Extracted from: app_enhanced.py:567
    """
    org_id, project_id = get_org_project(request, org, project)

    async with get_session() as session:
        # Get match result
        result = await session.execute(
            select(MatchResultModel).where(MatchResultModel.id == match_result_id)
        )
        match_result = result.scalar_one_or_none()

        if not match_result:
            raise HTTPException(status_code=404, detail="Match result not found")

        # Update status to rejected
        match_result.decision = "rejected"
        match_result.decision_reason = "Manual rejection via web UI"
        match_result.reviewed_at = datetime.utcnow()
        match_result.reviewed_by = "web-ui"  # In real app, use user ID

        await session.commit()

    # Redirect back to dashboard with filters preserved
    params = {
        "org": org_id,
        "project": project_id,
        "flag": flag,
        "severity": severity,
        "unmapped_only": unmapped_only,
        "classification": classification,
    }
    # Remove None values
    query_string = "&".join(f"{k}={v}" for k, v in params.items() if v and v != "None")

    return RedirectResponse(
        url=f"/review?{query_string}",
        status_code=303
    )
