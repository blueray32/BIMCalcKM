from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bimcalc.db.connection import get_session
from bimcalc.db.models import ItemModel, DocumentModel, DocumentLinkModel, MatchResultModel
from bimcalc.intelligence.recommendations import get_document_recommendations
from bimcalc.intelligence.risk_scoring import get_risk_score_cached

router = APIRouter(prefix="/api/intelligence", tags=["intelligence"])

@router.get("/recommendations/{item_id}")
async def get_recommendations(item_id: str):
    """Get document recommendations for an item."""
    async with get_session() as session:
        # Fetch item
        result = await session.execute(select(ItemModel).where(ItemModel.id == item_id))
        item = result.scalar_one_or_none()
        
        if not item:
            raise HTTPException(status_code=404, detail="Item not found")
            
        recommendations = await get_document_recommendations(session, item)
        return recommendations

@router.get("/risk/{item_id}")
async def get_risk_score(item_id: str):
    """Get risk score for an item."""
    async with get_session() as session:
        # Fetch item
        result = await session.execute(select(ItemModel).where(ItemModel.id == item_id))
        item = result.scalar_one_or_none()
        
        if not item:
            raise HTTPException(status_code=404, detail="Item not found")
            
        # Fetch linked documents
        doc_query = (
            select(DocumentModel)
            .join(DocumentLinkModel)
            .where(DocumentLinkModel.item_id == item_id)
        )
        documents = (await session.execute(doc_query)).scalars().all()
        
        # Fetch match result
        match_query = (
            select(MatchResultModel)
            .where(MatchResultModel.item_id == item_id)
            .order_by(MatchResultModel.timestamp.desc())
            .limit(1)
        )
        match = (await session.execute(match_query)).scalar_one_or_none()
        
        risk = await get_risk_score_cached(item, documents, match)
        return risk
