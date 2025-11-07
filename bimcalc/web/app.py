"""FastAPI web UI for BIMCalc review workflow."""

from __future__ import annotations

from pathlib import Path
from typing import Optional
from uuid import UUID

from fastapi import FastAPI, Form, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from bimcalc.config import get_config
from bimcalc.db.connection import get_session
from bimcalc.models import FlagSeverity
from bimcalc.review import approve_review_record, fetch_pending_reviews, fetch_review_record

templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))
app = FastAPI(title="BIMCalc Review UI")


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


@app.get("/", response_class=HTMLResponse)
async def review_dashboard(
    request: Request,
    org: Optional[str] = None,
    project: Optional[str] = None,
    flag: Optional[str] = Query(default=None),
    severity: Optional[str] = Query(default=None),
):
    config = get_config()
    org_id = org or config.org_id
    project_id = project or "default"

    async with get_session() as session:
        records = await fetch_pending_reviews(
            session,
            org_id,
            project_id,
            flag_types=_parse_flag_filter(flag),
            severity_filter=_parse_severity_filter(severity),
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
        },
    )


@app.post("/approve")
async def approve_item(
    match_result_id: UUID = Form(...),
    annotation: Optional[str] = Form(None),
    org: Optional[str] = Form(None),
    project: Optional[str] = Form(None),
):
    config = get_config()
    org_id = org or config.org_id
    project_id = project or "default"

    async with get_session() as session:
        record = await fetch_review_record(session, match_result_id)
        if record is None:
            raise HTTPException(status_code=404, detail="Review item not found")
        await approve_review_record(session, record, created_by="web-ui", annotation=annotation)

    redirect_url = f"/?org={org_id}&project={project_id}"
    return RedirectResponse(redirect_url, status_code=303)
