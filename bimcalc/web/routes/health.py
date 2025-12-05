"""Health check API routes.

Provides endpoints for monitoring application health and connectivity.
"""

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from bimcalc.db.connection import get_db

router = APIRouter(prefix="/health", tags=["Health"])


@router.get("", status_code=status.HTTP_200_OK)
async def health_check(db: AsyncSession = Depends(get_db)):
    """Check application health.
    
    Verifies database connectivity.
    """
    try:
        # Check DB connection
        await db.execute(text("SELECT 1"))
        return {"status": "ok", "database": "connected"}
    except Exception as e:
        return {
            "status": "error",
            "database": "disconnected",
            "detail": str(e)
        }
