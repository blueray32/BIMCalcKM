"""Matching routes for BIMCalc web UI.

Extracted from app_enhanced.py as part of Phase 3.4 web refactor.
Handles matching pipeline operations - triggering matches between items and price books.

Routes:
- GET  /match      - Matching pipeline page
- POST /match/run  - Trigger matching pipeline for project
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse
from sqlalchemy import select

from bimcalc.db.connection import get_session
from bimcalc.db.match_results import record_match_result
from bimcalc.db.models import ItemModel
from bimcalc.matching.orchestrator import MatchOrchestrator
from bimcalc.models import Item
from bimcalc.web.dependencies import get_org_project, get_templates
from bimcalc.matching.smart_matcher import get_smart_suggestions

# Create router with matching tag
router = APIRouter(tags=["matching"])


# ============================================================================
# Matching Pipeline Routes
# ============================================================================


@router.get("/match", response_class=HTMLResponse)
async def match_page(
    request: Request,
    org: str | None = None,
    project: str | None = None,
    templates=Depends(get_templates),
):
    """Page to trigger matching pipeline.

    Provides UI for running matching operations on project items.

    Extracted from: app_enhanced.py:863
    """
    org_id, project_id = get_org_project(request, org, project)

    return templates.TemplateResponse(
        "match.html",
        {
            "request": request,
            "org_id": org_id,
            "project_id": project_id,
        },
    )


@router.post("/match/run")
async def run_matching(
    org: str = Form(...),
    project: str = Form(...),
    limit: str | None = Form(default=None),
):
    """Trigger matching pipeline for project.

    Runs the matching orchestrator on items in the specified project,
    persisting match results and canonical metadata to the database.

    Args:
        org: Organization ID
        project: Project ID
        limit: Optional limit on number of items to match

    Returns:
        JSON response with success status, message, and match results

    Extracted from: app_enhanced.py:878
    """
    limit_value: int | None = None
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

            results.append(
                {
                    "item": f"{item.family} / {item.type_name}",
                    "decision": match_result.decision.value,
                    "confidence": match_result.confidence_score,
                    "flags": [f.type for f in match_result.flags],
                }
            )

        # Commit all changes (canonical keys and match results)
        await session.commit()

        return {
            "success": True,
            "message": f"Matched {len(results)} items",
            "results": results,
        }


@router.get("/api/match/{item_id}/suggestions", response_class=HTMLResponse)
async def match_suggestions(
    request: Request,
    item_id: str,
    templates=Depends(get_templates)
):
    """Get AI-powered matching suggestions for an item."""
    from uuid import UUID
    try:
        uuid_obj = UUID(item_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid item ID")

    suggestions = await get_smart_suggestions(uuid_obj)
    
    return templates.TemplateResponse(
        "partials/suggestions.html",
        {"request": request, "suggestions": suggestions, "item_id": item_id}
    )
