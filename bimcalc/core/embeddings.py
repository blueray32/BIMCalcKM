import logging
import os
from typing import List

import openai
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bimcalc.db.connection import get_session
from bimcalc.db.models import ItemModel, PriceItemModel
from bimcalc.utils.redis_cache import get_cached, set_cached

logger = logging.getLogger(__name__)

async def generate_embedding(text: str) -> List[float] | None:
    """Generate embedding for text using OpenAI."""
    if not text or not text.strip():
        return None

    # Check cache
    cache_key = f"embedding:{hash(text)}"
    cached = await get_cached(cache_key)
    if cached:
        return cached

    try:
        client = openai.AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        response = await client.embeddings.create(
            model="text-embedding-3-small", input=text
        )
        embedding = response.data[0].embedding
        
        # Cache
        await set_cached(cache_key, embedding, ttl_seconds=86400 * 7) # 1 week
        return embedding
    except Exception as e:
        logger.error(f"Failed to generate embedding: {e}")
        return None

async def update_item_embedding(item_id: str):
    """Generate and save embedding for an item."""
    async with get_session() as session:
        from uuid import UUID
        item = await session.get(ItemModel, UUID(item_id))
        if not item:
            return

        # Create text representation
        # Include family, type, classification, and attributes
        text_parts = [
            item.family,
            item.type_name,
            item.classification_code or "",
            item.category or "",
            item.material or "",
        ]
        # Add attributes values
        if item.attributes:
            text_parts.extend([str(v) for v in item.attributes.values() if isinstance(v, (str, int, float))])
            
        text = " ".join([p for p in text_parts if p])
        
        embedding = await generate_embedding(text)
        if embedding:
            item.embedding = embedding
            await session.commit()

async def update_price_item_embedding(price_item_id: str):
    """Generate and save embedding for a price item."""
    async with get_session() as session:
        from uuid import UUID
        item = await session.get(PriceItemModel, UUID(price_item_id))
        if not item:
            return

        text_parts = [
            item.description,
            item.vendor_code or "",
            item.sku,
            item.classification_code,
            item.material or "",
        ]
        if item.attributes:
            text_parts.extend([str(v) for v in item.attributes.values() if isinstance(v, (str, int, float))])
            
        text = " ".join([p for p in text_parts if p])
        
        embedding = await generate_embedding(text)
        if embedding:
            item.embedding = embedding
            await session.commit()
