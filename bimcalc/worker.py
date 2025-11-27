import os
from typing import Any

from arq.connections import RedisSettings
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from bimcalc.integration.crail4_sync import sync_crail4_prices

# Database setup for worker
DATABASE_URL = os.environ.get("DATABASE_URL")
if not DATABASE_URL:
    raise ValueError("DATABASE_URL environment variable is not set")

engine = create_async_engine(DATABASE_URL, echo=False)
async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

async def startup(ctx: dict[str, Any]) -> None:
    """Initialize resources when worker starts."""
    ctx["session_maker"] = async_session
    print("Worker started. Database connection initialized.")

async def shutdown(ctx: dict[str, Any]) -> None:
    """Cleanup resources when worker stops."""
    await engine.dispose()
    print("Worker stopped. Database connection closed.")

async def run_crail4_sync(ctx: dict[str, Any], org_id: str, full_sync: bool = False) -> dict[str, Any]:
    """Wrapper for sync_crail4_prices to run as a background job."""
    print(f"Starting Crail4 sync job for org_id={org_id}, full_sync={full_sync}")
    
    # sync_crail4_prices manages its own session and HTTP client
    delta_days = None if full_sync else 7
    
    result = await sync_crail4_prices(
        org_id=org_id, 
        delta_days=delta_days,
        classification_filter=None,
        region=None
    )
        
    print(f"Crail4 sync job completed: {result}")
    return result


async def send_daily_digest(ctx: dict[str, Any], org_id: str, project_id: str, recipients: list[str]) -> dict[str, Any]:
    """Send daily QA digest email to recipients."""
    from bimcalc.intelligence.notifications import get_email_notifier
    from bimcalc.intelligence.risk_scoring import get_risk_score_cached
    from bimcalc.db.models import ItemModel, QAChecklistModel
    from sqlalchemy import select, func
    from datetime import datetime, timedelta
    
    print(f"Starting daily digest for {org_id}/{project_id}")
    
    session_maker = ctx["session_maker"]
    async with session_maker() as session:
        # Calculate yesterday's stats
        yesterday = datetime.utcnow() - timedelta(days=1)
        yesterday_start = yesterday.replace(hour=0, minute=0, second=0, microsecond=0)
        
        # Get all items
        items_query = select(ItemModel).where(
            ItemModel.org_id == org_id,
            ItemModel.project_id == project_id
        )
        result = await session.execute(items_query)
        items = list(result.scalars())
        
        # Calculate risk scores
        high_risk_items = []
        for item in items:
            risk = await get_risk_score_cached(session, str(item.id))
            if risk.score >= 61:
                high_risk_items.append({
                    "family": item.family,
                    "type_name": item.type_name,
                    "score": risk.score
                })
        
        # Count checklists
        checklists_query = select(func.count()).select_from(QAChecklistModel).where(
            QAChecklistModel.org_id == org_id,
            QAChecklistModel.project_id == project_id
        )
        total_checklists = await session.scalar(checklists_query)
        
        # Count completed yesterday
        completed_query = select(func.count()).select_from(QAChecklistModel).where(
            QAChecklistModel.org_id == org_id,
            QAChecklistModel.project_id == project_id,
            QAChecklistModel.completed_at >= yesterday_start,
            QAChecklistModel.completion_percent == 100.0
        )
        completed_yesterday = await session.scalar(completed_query)
        
        # Count generated yesterday
        generated_query = select(func.count()).select_from(QAChecklistModel).where(
            QAChecklistModel.org_id == org_id,
            QAChecklistModel.project_id == project_id,
            QAChecklistModel.generated_at >= yesterday_start
        )
        generated_yesterday = await session.scalar(generated_query)
        
        # Calculate compliance
        if total_checklists and total_checklists > 0:
            completed_query = select(func.count()).select_from(QAChecklistModel).where(
                QAChecklistModel.org_id == org_id,
                QAChecklistModel.project_id == project_id,
                QAChecklistModel.completion_percent == 100.0
            )
            completed_total = await session.scalar(completed_query)
            compliance_percent = (completed_total / total_checklists) * 100
        else:
            compliance_percent = 0.0
        
        # Build digest data
        digest_data = {
            "new_high_risk": 0,  # Would need to track changes
            "checklists_completed": completed_yesterday or 0,
            "checklists_generated": generated_yesterday or 0,
            "total_high_risk": len(high_risk_items),
            "compliance_percent": compliance_percent,
            "active_checklists": total_checklists or 0,
            "top_risks": sorted(high_risk_items, key=lambda x: x["score"], reverse=True)[:5]
        }
        
        # Send email
        notifier = get_email_notifier()
        await notifier.send_daily_digest(recipients, digest_data)
        
        print(f"Daily digest sent to {len(recipients)} recipients")
        return {"sent": True, "recipients": len(recipients), "stats": digest_data}


async def batch_generate_checklists_job(
    ctx: dict[str, Any], 
    org_id: str, 
    project_id: str,
    item_ids: list[str]
) -> dict[str, Any]:
    """ARQ worker task for batch checklist generation.
    
    Args:
        ctx: ARQ context
        org_id: Organization ID
        project_id: Project ID
        item_ids: List of item IDs to process
        
    Returns:
        Results dict with stats
    """
    from bimcalc.intelligence.bulk_operations import batch_generate_checklists
    
    print(f"Starting batch checklist generation: {len(item_ids)} items")
    
    session_maker = ctx["session_maker"]
    async with session_maker() as session:
        # Progress callback
        def report_progress(current, total):
            print(f"Progress: {current}/{total} ({current/total*100:.1f}%)")
        
        results = await batch_generate_checklists(
            session,
            item_ids,
            progress_callback=report_progress
        )
        
        print(f"Batch generation complete: {results}")
        return results


# Worker settings
class WorkerSettings:
    functions = [run_crail4_sync, send_daily_digest, batch_generate_checklists_job]
    on_startup = startup
    on_shutdown = shutdown
    redis_settings = RedisSettings.from_dsn(
        os.environ.get("REDIS_URL", "redis://redis:6379")
    )
    # Daily digest at 9 AM (uncomment when ready to use)
    # from arq.cron import cron
    # cron_jobs = [
    #     cron(send_daily_digest, hour=9, minute=0, 
    #          kwargs={"org_id": "demo-org", "project_id": "tritex24-229", 
    #                  "recipients": ["team@example.com"]})
    # ]
