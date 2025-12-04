"""Compliance routes for BIMCalc web UI.

Handles compliance checking workflow.
"""

from __future__ import annotations

from fastapi import APIRouter, UploadFile, File, Form, Query, Request, Depends
from fastapi.responses import HTMLResponse
from sqlalchemy import select

from bimcalc.db.connection import get_session
from bimcalc.db.models_intelligence import ComplianceRuleModel, ComplianceResultModel
from bimcalc.intelligence.compliance import (
    extract_rules_from_text,
    run_compliance_check,
)
from bimcalc.web.dependencies import get_templates

router = APIRouter(tags=["compliance"])


@router.get("/compliance", response_class=HTMLResponse)
async def compliance_page(
    request: Request,
    org: str | None = None,
    project: str | None = None,
    templates=Depends(get_templates),
):
    """Render compliance management page."""
    return templates.TemplateResponse(
        "compliance.html", {"request": request, "org_id": org, "project_id": project}
    )


@router.post("/api/compliance/upload")
async def upload_compliance_spec(
    file: UploadFile = File(...),
    org_id: str = Form(...),
    project_id: str = Form(...),
):
    """Upload compliance specification and extract rules."""
    content = (await file.read()).decode("utf-8")

    async with get_session() as session:
        extracted_rules = await extract_rules_from_text(content)

        saved_rules = []
        for rule_data in extracted_rules:
            rule = ComplianceRuleModel(
                org_id=org_id,
                project_id=project_id,
                name=rule_data["name"],
                description=rule_data["description"],
                rule_logic=rule_data["rule_logic"],
            )
            session.add(rule)
            saved_rules.append(rule)

        await session.commit()

        return {"success": True, "rule_count": len(saved_rules)}


@router.get("/api/compliance/rules")
async def get_compliance_rules(
    org: str = Query(...),
    project: str = Query(...),
):
    """Get extracted compliance rules."""
    async with get_session() as session:
        result = await session.execute(
            select(ComplianceRuleModel).where(
                ComplianceRuleModel.org_id == org,
                ComplianceRuleModel.project_id == project,
            )
        )
        rules = result.scalars().all()
        return {"rules": rules}


@router.post("/api/compliance/check")
async def run_compliance_check_route(
    org: str = Query(...),
    project: str = Query(...),
):
    """Run compliance check against rules."""
    async with get_session() as session:
        stats = await run_compliance_check(session, org, project)
        return {"success": True, "stats": stats}


@router.get("/api/compliance/results")
async def get_compliance_results(
    org: str = Query(...),
    project: str = Query(...),
):
    """Get compliance check results."""
    async with get_session() as session:
        result = await session.execute(
            select(ComplianceResultModel)
            .join(ComplianceRuleModel)
            .where(
                ComplianceRuleModel.org_id == org,
                ComplianceRuleModel.project_id == project,
            )
        )
        results = result.scalars().all()
        return {"results": results}
