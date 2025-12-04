"""Price Sources management routes for Smart Price Scout Phase 2.

Provides UI for managing supplier price data sources:
- List all configured sources
- Add new sources
- Edit existing sources
- Enable/disable sources
- View sync history and status
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4
from urllib.parse import urlparse

from fastapi import APIRouter, Request, Form, HTTPException, Depends
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import select, update, delete
from sqlalchemy.ext.asyncio import AsyncSession

from bimcalc.db.connection import get_session
from bimcalc.db.models import PriceSourceModel
from bimcalc.web.dependencies import get_templates

router = APIRouter(prefix="/price-sources", tags=["price_sources"])


@router.get("", response_class=HTMLResponse)
async def list_price_sources(
    request: Request,
    templates=Depends(get_templates)
):
    """Display list of configured price sources."""
    async with get_session() as session:
        # For now, hardcode org_id (TODO: get from session/auth)
        org_id = "acme-construction"

        stmt = select(PriceSourceModel).where(
            PriceSourceModel.org_id == org_id
        ).order_by(PriceSourceModel.name)

        result = await session.execute(stmt)
        sources = result.scalars().all()

        return templates.TemplateResponse(
            "price_sources.html",
            {
                "request": request,
                "sources": sources,
                "org_id": org_id,
            }
        )


@router.get("/new", response_class=HTMLResponse)
async def new_price_source_form(
    request: Request,
    templates=Depends(get_templates)
):
    """Display form for adding new price source."""
    return templates.TemplateResponse(
        "price_source_form.html",
        {
            "request": request,
            "source": None,  # New source
            "action": "/price-sources",
            "method": "POST",
        }
    )


@router.post("", response_class=RedirectResponse)
async def create_price_source(
    request: Request,
    name: str = Form(...),
    url: str = Form(...),
    enabled: bool = Form(False),
    cache_ttl_seconds: int = Form(86400),
    rate_limit_seconds: float = Form(2.0),
    notes: str = Form(None),
):
    """Create a new price source."""
    async with get_session() as session:
        # For now, hardcode org_id (TODO: get from session/auth)
        org_id = "acme-construction"

        # Extract domain from URL
        parsed_url = urlparse(url)
        domain = parsed_url.netloc

        if not domain:
            raise HTTPException(status_code=400, detail="Invalid URL: missing domain")

        # Check for duplicate domain
        stmt = select(PriceSourceModel).where(
            PriceSourceModel.org_id == org_id,
            PriceSourceModel.domain == domain
        )
        result = await session.execute(stmt)
        existing = result.scalars().first()

        if existing:
            raise HTTPException(
                status_code=400,
                detail=f"Source with domain '{domain}' already exists"
            )

        # Create new source
        source = PriceSourceModel(
            id=uuid4(),
            org_id=org_id,
            name=name,
            url=url,
            domain=domain,
            enabled=enabled,
            cache_ttl_seconds=cache_ttl_seconds,
            rate_limit_seconds=rate_limit_seconds,
            notes=notes,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )

        session.add(source)
        await session.commit()

    return RedirectResponse(url="/price-sources", status_code=303)


@router.get("/{source_id}/edit", response_class=HTMLResponse)
async def edit_price_source_form(
    request: Request, 
    source_id: UUID,
    templates=Depends(get_templates)
):
    """Display form for editing existing price source."""
    async with get_session() as session:
        stmt = select(PriceSourceModel).where(PriceSourceModel.id == source_id)
        result = await session.execute(stmt)
        source = result.scalars().first()

        if not source:
            raise HTTPException(status_code=404, detail="Source not found")

        return templates.TemplateResponse(
            "price_source_form.html",
            {
                "request": request,
                "source": source,
                "action": f"/price-sources/{source_id}",
                "method": "POST",
            }
        )


@router.post("/{source_id}", response_class=RedirectResponse)
async def update_price_source(
    request: Request,
    source_id: UUID,
    name: str = Form(...),
    url: str = Form(...),
    enabled: bool = Form(False),
    cache_ttl_seconds: int = Form(86400),
    rate_limit_seconds: float = Form(2.0),
    notes: str = Form(None),
):
    """Update an existing price source."""
    async with get_session() as session:
        # Extract domain from URL
        parsed_url = urlparse(url)
        domain = parsed_url.netloc

        if not domain:
            raise HTTPException(status_code=400, detail="Invalid URL: missing domain")

        # Update source
        stmt = (
            update(PriceSourceModel)
            .where(PriceSourceModel.id == source_id)
            .values(
                name=name,
                url=url,
                domain=domain,
                enabled=enabled,
                cache_ttl_seconds=cache_ttl_seconds,
                rate_limit_seconds=rate_limit_seconds,
                notes=notes,
                updated_at=datetime.utcnow(),
            )
        )

        result = await session.execute(stmt)
        await session.commit()

        if result.rowcount == 0:
            raise HTTPException(status_code=404, detail="Source not found")

    return RedirectResponse(url="/price-sources", status_code=303)


@router.post("/{source_id}/toggle", response_class=RedirectResponse)
async def toggle_price_source(request: Request, source_id: UUID):
    """Toggle enabled/disabled status of a price source."""
    async with get_session() as session:
        # Get current status
        stmt = select(PriceSourceModel).where(PriceSourceModel.id == source_id)
        result = await session.execute(stmt)
        source = result.scalars().first()

        if not source:
            raise HTTPException(status_code=404, detail="Source not found")

        # Toggle enabled
        stmt = (
            update(PriceSourceModel)
            .where(PriceSourceModel.id == source_id)
            .values(enabled=not source.enabled, updated_at=datetime.utcnow())
        )

        await session.execute(stmt)
        await session.commit()

    return RedirectResponse(url="/price-sources", status_code=303)


@router.post("/{source_id}/delete", response_class=RedirectResponse)
async def delete_price_source(request: Request, source_id: UUID):
    """Delete a price source."""
    async with get_session() as session:
        stmt = delete(PriceSourceModel).where(PriceSourceModel.id == source_id)
        result = await session.execute(stmt)
        await session.commit()

        if result.rowcount == 0:
            raise HTTPException(status_code=404, detail="Source not found")

    return RedirectResponse(url="/price-sources", status_code=303)
