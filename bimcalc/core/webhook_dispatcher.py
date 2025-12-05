import hmac
import hashlib
import json
import httpx
import os
from datetime import datetime
from sqlalchemy import select
from arq import create_pool
from arq.connections import RedisSettings
from bimcalc.db.connection import get_session
from bimcalc.db.models import WebhookModel

async def trigger_webhook(event_type: str, payload: dict):
    """Trigger webhooks for a given event.
    
    Args:
        event_type: Event name (e.g. "item.matched")
        payload: Data to send
    """
    
    # Find active webhooks
    async with get_session() as session:
        stmt = select(WebhookModel).where(WebhookModel.is_active == True)
        result = await session.execute(stmt)
        webhooks = result.scalars().all()
        
        matching_webhooks = [
            w for w in webhooks 
            if event_type in w.events or "*" in w.events
        ]
        
        if not matching_webhooks:
            return

        # Enqueue jobs
        redis_url = os.environ.get("REDIS_URL", "redis://localhost:6379")
        try:
            redis = await create_pool(RedisSettings.from_dsn(redis_url))
            
            for webhook in matching_webhooks:
                await redis.enqueue_job(
                    "send_webhook_request",
                    webhook_id=str(webhook.id),
                    event_type=event_type,
                    payload=payload,
                    timestamp=datetime.utcnow().isoformat()
                )
            
            await redis.close()
        except Exception as e:
            print(f"Failed to enqueue webhook jobs: {e}")

async def send_webhook_request(ctx, webhook_id: str, event_type: str, payload: dict, timestamp: str):
    """Worker job to send webhook request."""
    
    session_maker = ctx.get("session_maker")
    if not session_maker:
        # Fallback if not running in worker context
        from bimcalc.db.connection import get_session
        session_cm = get_session()
    else:
        session_cm = session_maker()

    async with session_cm as session:
        from uuid import UUID
        try:
            webhook = await session.get(WebhookModel, UUID(webhook_id))
        except Exception:
            return

        if not webhook or not webhook.is_active:
            return

        full_payload = {
            "event": event_type,
            "timestamp": timestamp,
            "data": payload
        }
        body = json.dumps(full_payload)
        
        signature = hmac.new(
            webhook.secret.encode(),
            body.encode(),
            hashlib.sha256
        ).hexdigest()
        
        headers = {
            "Content-Type": "application/json",
            "X-BIMCalc-Signature": signature,
            "X-BIMCalc-Event": event_type,
            "User-Agent": "BIMCalc-Webhook/1.0"
        }
        
        async with httpx.AsyncClient() as client:
            try:
                await client.post(webhook.url, content=body, headers=headers, timeout=10.0)
            except httpx.RequestError as e:
                print(f"Webhook delivery failed to {webhook.url}: {e}")
