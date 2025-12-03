"""Projects management routes for BIMCalc web UI.

Handles project creation and management.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Form, Request
from fastapi.responses import HTMLResponse
from sqlalchemy import select

from bimcalc.db.connection import get_session
from bimcalc.db.models import ProjectModel
from bimcalc.web.auth import require_auth
from bimcalc.web.dependencies import get_templates

router = APIRouter(tags=["projects"])

@router.get("/projects", response_class=HTMLResponse)
async def projects_page(
    request: Request,
    templates = Depends(get_templates),
):
    """Render projects management page."""
    return templates.TemplateResponse(
        "projects.html",
        {"request": request}
    )

from typing import Optional
from datetime import datetime
from pydantic import BaseModel, field_validator

class ProjectCreate(BaseModel):
    org_id: str
    project_id: str
    display_name: str
    region: str = "EU"
    description: Optional[str] = None
    start_date: Optional[datetime] = None
    target_completion: Optional[datetime] = None

    @field_validator('start_date', 'target_completion', mode='before')
    @classmethod
    def empty_string_to_none(cls, v):
        if v == "":
            return None
        return v

@router.post("/api/projects")
async def create_project(project_data: ProjectCreate):
    """Create a new project."""
    async with get_session() as session:
        # Check if exists
        existing = await session.execute(
            select(ProjectModel).where(
                ProjectModel.org_id == project_data.org_id,
                ProjectModel.project_id == project_data.project_id
            )
        )
        if existing.scalar_one_or_none():
            # Idempotent success
            pass
        else:
            project = ProjectModel(
                org_id=project_data.org_id,
                project_id=project_data.project_id,
                display_name=project_data.display_name,
                region=project_data.region,
                description=project_data.description,
                start_date=project_data.start_date,
                target_completion=project_data.target_completion,
                created_by="web-ui"
            )
            session.add(project)
            await session.commit()
            
    return {
        "success": True, 
        "org_id": project_data.org_id, 
        "project_id": project_data.project_id
    }

@router.get("/api/projects/all")
async def list_projects():
    """List all projects with summary stats."""
    async with get_session() as session:
        # Fetch projects
        result = await session.execute(
            select(ProjectModel).order_by(ProjectModel.created_at.desc())
        )
        projects = result.scalars().all()
        
        # TODO: Add item counts (requires join or separate query)
        # For now, return 0 items to unblock UI
        
        return {
            "projects": [
                {
                    "id": str(p.id),
                    "org_id": p.org_id,
                    "project_id": p.project_id,
                    "display_name": p.display_name,
                    "description": p.description,
                    "status": p.status,
                    "region": p.region,
                    "start_date": p.start_date.isoformat() if p.start_date else None,
                    "target_completion": p.target_completion.isoformat() if p.target_completion else None,
                    "created_at": p.created_at.isoformat(),
                    "item_count": 0, # Placeholder
                    "settings": p.settings
                }
                for p in projects
            ]

        }

@router.get("/api/projects/{project_id}")
async def get_project(project_id: str):
    """Get a single project by ID."""
    try:
        p_uuid = UUID(project_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid project ID format")

    async with get_session() as session:
        result = await session.execute(
            select(ProjectModel).where(ProjectModel.id == p_uuid)
        )
        project = result.scalar_one_or_none()
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")
            
        return {
            "id": str(project.id),
            "org_id": project.org_id,
            "project_id": project.project_id,
            "display_name": project.display_name,
            "description": project.description,
            "status": project.status,
            "region": project.region,
            "start_date": project.start_date,
            "target_completion": project.target_completion,
            "created_at": project.created_at,
            "settings": project.settings
        }

from uuid import UUID

@router.get("/api/projects/{project_id}/settings")
async def get_project_settings(project_id: str):
    """Get project settings."""
    try:
        p_uuid = UUID(project_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid project ID format")

    async with get_session() as session:
        result = await session.execute(
            select(ProjectModel).where(ProjectModel.id == p_uuid)
        )
        project = result.scalar_one_or_none()
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")
            
        return project.settings

@router.patch("/api/projects/{project_id}/settings")
async def update_project_settings(project_id: str, settings: dict):
    """Update project settings."""
    try:
        p_uuid = UUID(project_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid project ID format")

    async with get_session() as session:
        result = await session.execute(
            select(ProjectModel).where(ProjectModel.id == p_uuid)
        )
        project = result.scalar_one_or_none()
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")
            
        # Merge settings
        current_settings = dict(project.settings)
        current_settings.update(settings)
        project.settings = current_settings
        
        await session.commit()
        
    return {"success": True, "settings": project.settings}

# Labor Rates
from bimcalc.db.models import LaborRateOverride

@router.get("/api/projects/{project_id}/labor-rates")
async def get_labor_rates(project_id: str):
    """Get labor rate overrides."""
    try:
        p_uuid = UUID(project_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid project ID format")

    async with get_session() as session:
        result = await session.execute(
            select(LaborRateOverride).where(LaborRateOverride.project_id == p_uuid)
        )
        rates = result.scalars().all()
        
        return {
            "overrides": [
                {
                    "id": str(r.id),
                    "category": r.category,
                    "rate": float(r.rate)
                }
                for r in rates
            ]
        }

@router.post("/api/projects/{project_id}/labor-rates")
async def create_labor_rate(project_id: str, data: dict):
    """Create or update labor rate override."""
    try:
        p_uuid = UUID(project_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid project ID format")

    category = data.get("category")
    rate = data.get("rate")
    
    if not category or rate is None:
        raise HTTPException(status_code=400, detail="Category and rate required")
        
    async with get_session() as session:
        # Check if exists
        result = await session.execute(
            select(LaborRateOverride).where(
                LaborRateOverride.project_id == p_uuid,
                LaborRateOverride.category == category
            )
        )
        existing = result.scalar_one_or_none()
        
        if existing:
            existing.rate = rate
        else:
            override = LaborRateOverride(
                project_id=p_uuid,
                category=category,
                rate=rate
            )
            session.add(override)
            
        await session.commit()
        
    return {"success": True}

@router.delete("/api/projects/{project_id}/labor-rates/{rate_id}")
async def delete_labor_rate(project_id: str, rate_id: str):
    """Delete labor rate override."""
    try:
        p_uuid = UUID(project_id)
        r_uuid = UUID(rate_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid ID format")

    async with get_session() as session:
        result = await session.execute(
            select(LaborRateOverride).where(
                LaborRateOverride.id == r_uuid,
                LaborRateOverride.project_id == p_uuid
            )
        )
        rate = result.scalar_one_or_none()
        if not rate:
            raise HTTPException(status_code=404, detail="Rate not found")
            
        await session.delete(rate)
        await session.commit()
        
    return {"success": True}

@router.delete("/api/projects/{project_id}")
async def delete_project(project_id: str):
    """Delete a project."""
    try:
        p_uuid = UUID(project_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid project ID format")

    async with get_session() as session:
        result = await session.execute(
            select(ProjectModel).where(ProjectModel.id == p_uuid)
        )
        project = result.scalar_one_or_none()
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")
            
        await session.delete(project)
        await session.commit()
        
    return {"success": True}
