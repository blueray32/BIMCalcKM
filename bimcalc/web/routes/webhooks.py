from fastapi import APIRouter, Depends, Form, Request, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import select
from uuid import UUID
import secrets

from bimcalc.db.connection import get_session
from bimcalc.db.models import WebhookModel
from bimcalc.web.auth import require_admin
from bimcalc.web.dependencies import get_templates
from bimcalc.core.webhook_dispatcher import trigger_webhook

router = APIRouter(prefix="/webhooks", tags=["webhooks"])

@router.get("/", response_class=HTMLResponse)
async def list_webhooks(
    request: Request,
    username: str = Depends(require_admin),
    templates=Depends(get_templates),
):
    async with get_session() as session:
        result = await session.execute(select(WebhookModel).order_by(WebhookModel.created_at.desc()))
        webhooks = result.scalars().all()
        
    return templates.TemplateResponse(
        "webhooks.html",
        {"request": request, "webhooks": webhooks, "username": username}
    )

@router.post("/new")
async def create_webhook(
    request: Request,
    url: str = Form(...),
    events: str = Form(...),  # Comma separated
    username: str = Depends(require_admin),
):
    event_list = [e.strip() for e in events.split(",") if e.strip()]
    secret = secrets.token_hex(24)
    
    async with get_session() as session:
        webhook = WebhookModel(
            url=url,
            secret=secret,
            events=event_list,
            is_active=True
        )
        session.add(webhook)
        await session.commit()
        
    return RedirectResponse(url="/webhooks", status_code=302)

@router.post("/{webhook_id}/delete")
async def delete_webhook(
    request: Request,
    webhook_id: str,
    username: str = Depends(require_admin),
):
    async with get_session() as session:
        webhook = await session.get(WebhookModel, UUID(webhook_id))
        if webhook:
            await session.delete(webhook)
            await session.commit()
            
    return RedirectResponse(url="/webhooks", status_code=302)

@router.post("/test")
async def test_webhook(
    request: Request,
    username: str = Depends(require_admin),
):
    await trigger_webhook("ping", {"message": "Test webhook from BIMCalc", "user": username})
    return RedirectResponse(url="/webhooks?msg=Test+event+triggered", status_code=302)
