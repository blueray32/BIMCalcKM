"""Smart document recommendations using vector similarity."""

import logging
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from bimcalc.db.models import ItemModel
from bimcalc.utils.redis_cache import get_cached, set_cached

logger = logging.getLogger(__name__)


async def _generate_item_embedding(item: ItemModel) -> list[float] | None:
    """Generate embedding for an item using OpenAI.

    Args:
        item: Item to generate embedding for

    Returns:
        Embedding vector or None if failed
    """
    try:
        import openai
        import os

        # Create text representation of item
        item_text = f"{item.family or ''} {item.type_name or ''} {item.classification_code or ''}".strip()

        if not item_text:
            logger.warning(f"Item {item.id} has no text to embed")
            return None

        # Call OpenAI
        client = openai.AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        response = await client.embeddings.create(
            model="text-embedding-3-small", input=item_text
        )

        return response.data[0].embedding

    except Exception as e:
        logger.error(f"Failed to generate embedding for item {item.id}: {e}")
        return None


async def get_item_embedding(item: ItemModel) -> list[float] | None:
    """Get embedding for item with caching.

    Args:
        item: Item to get embedding for

    Returns:
        Embedding vector or None if failed
    """
    # Check cache first
    cache_key = f"item_embedding:{item.id}"
    cached_embedding = await get_cached(cache_key)

    if cached_embedding:
        return cached_embedding

    # Generate new embedding
    embedding = await _generate_item_embedding(item)

    if embedding:
        # Cache for 24 hours (items don't change often)
        await set_cached(cache_key, embedding, ttl_seconds=86400)

    return embedding


async def get_document_recommendations(
    session: AsyncSession, item: ItemModel, limit: int = 5, min_score: float = 0.0
) -> list[dict[str, Any]]:
    """Get AI-recommended documents for an item using vector similarity.

    Args:
        session: Database session
        item: Item to get recommendations for
        limit: Maximum number of recommendations

    Returns:
        List of recommended documents with relevance scores
    """
    # Get item embedding
    embedding = await get_item_embedding(item)

    if not embedding:
        logger.warning(f"No embedding available for item {item.id}")
        return []

    # Convert embedding to PostgreSQL array format
    embedding_str = "[" + ",".join(str(x) for x in embedding) + "]"

    # Vector similarity search using pgvector
    # cosine distance: 1 - (a <=> b) gives similarity (higher = more similar)
    query = text("""
        SELECT 
            id,
            title,
            doc_type as document_type,
            tags,
            source_file,
            1 - (embedding <=> CAST(:embedding AS vector)) as similarity
        FROM documents
        WHERE embedding IS NOT NULL
          AND 1 - (embedding <=> CAST(:embedding AS vector)) >= :min_score
        ORDER BY embedding <=> CAST(:embedding AS vector)
        LIMIT :limit
    """)

    result = await session.execute(
        query,
        {
            "embedding": embedding_str,
            "org_id": item.org_id,
            "project_id": item.project_id,
            "limit": limit,
            "min_score": min_score,
        },
    )

    recommendations = []
    for row in result:
        recommendations.append(
            {
                "id": str(row.id),
                "title": row.title,
                "document_type": row.document_type,
                "tags": row.tags or [],
                "source_file": row.source_file,
                "relevance": round(row.similarity * 100, 1),  # Convert to percentage
                "score": row.similarity,  # Raw score for template logic
            }
        )

    return recommendations
