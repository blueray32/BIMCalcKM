from typing import List, Dict, Any
from uuid import UUID
from sqlalchemy import text
from bimcalc.db.connection import get_session
from bimcalc.db.models import ItemModel
from bimcalc.core.embeddings import update_item_embedding

async def get_smart_suggestions(item_id: UUID, limit: int = 5) -> List[Dict[str, Any]]:
    """Get smart matching suggestions for an item using vector search."""
    async with get_session() as session:
        item = await session.get(ItemModel, item_id)
        if not item:
            return []
        
        if item.embedding is None:
             # Try to generate on the fly if missing
             # We need to close the session before calling update_item_embedding as it creates its own session
             pass 
        
    # Generate embedding if missing (outside session context)
    if item.embedding is None:
        await update_item_embedding(str(item_id))
        async with get_session() as session:
            item = await session.get(ItemModel, item_id)
            if not item or item.embedding is None:
                return []

async def find_matches_by_embedding(session, embedding: List[float], limit: int = 5) -> List[Dict[str, Any]]:
    """Find matching price items using an embedding vector."""
    embedding_str = "[" + ",".join(str(x) for x in embedding) + "]"
    
    query = text("""
        SELECT id, description, vendor_code, sku, unit_price, currency, classification_code,
               1 - (embedding <=> CAST(:embedding AS vector)) as similarity,
               vendor_id
        FROM price_items
        WHERE embedding IS NOT NULL AND is_current = true
        ORDER BY embedding <=> CAST(:embedding AS vector)
        LIMIT :limit
    """)
    
    result = await session.execute(query, {"embedding": embedding_str, "limit": limit})
    rows = result.fetchall()
    
    return [
        {
            "id": str(row.id),
            "description": row.description,
            "vendor_code": row.vendor_code,
            "sku": row.sku,
            "price": f"{row.unit_price} {row.currency}",
            "unit_price": row.unit_price,
            "currency": row.currency,
            "vendor_id": row.vendor_id,
            "classification": row.classification_code,
            "similarity": float(row.similarity)
        }
        for row in rows
    ]


async def get_smart_suggestions(item_id: UUID, limit: int = 5) -> List[Dict[str, Any]]:
    """Get smart matching suggestions for an item using vector search."""
    async with get_session() as session:
        item = await session.get(ItemModel, item_id)
        if not item:
            return []
        
        if item.embedding is None:
             # Try to generate on the fly if missing
             # We need to close the session before calling update_item_embedding as it creates its own session
             pass 
        
    # Generate embedding if missing (outside session context)
    if item.embedding is None:
        await update_item_embedding(str(item_id))
        async with get_session() as session:
            item = await session.get(ItemModel, item_id)
            if not item or item.embedding is None:
                return []

    async with get_session() as session:
        return await find_matches_by_embedding(session, item.embedding, limit)
