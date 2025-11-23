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

# Worker settings
class WorkerSettings:
    functions = [run_crail4_sync]
    on_startup = startup
    on_shutdown = shutdown
    redis_settings = RedisSettings.from_dsn(
        os.environ.get("REDIS_URL", "redis://redis:6379")
    )
    # Optional: Add cron jobs here
    # cron_jobs = [
    #     cron(run_crail4_sync, hour=0, minute=0, kwargs={"org_id": "default", "full_sync": True})
    # ]
