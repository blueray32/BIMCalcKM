"""Advanced analytics for project intelligence."""

import logging
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from bimcalc.db.models import DocumentLinkModel, DocumentModel, ItemModel, MatchResultModel
from bimcalc.utils.redis_cache import get_cached, set_cached

logger = logging.getLogger(__name__)

# Cache TTL for analytics (10 minutes)
ANALYTICS_CACHE_TTL = 600


async def get_classification_breakdown(
    session: AsyncSession, org_id: str, project_id: str
) -> dict[str, int]:
    """Get item count by classification code.
    
    Args:
        session: Database session
        org_id: Organization ID
        project_id: Project ID
        
    Returns:
        Dict mapping classification code to item count
    """
    cache_key = f"analytics:classification:{org_id}:{project_id}"
    cached = await get_cached(cache_key)
    if cached:
        return cached
    
    # Query: group by classification, count items
    query = (
        select(
            ItemModel.classification_code,
            func.count(ItemModel.id).label("count")
        )
        .where(
            ItemModel.org_id == org_id,
            ItemModel.project_id == project_id,
            ItemModel.classification_code.isnot(None)
        )
        .group_by(ItemModel.classification_code)
        .order_by(func.count(ItemModel.id).desc())
    )
    
    result = await session.execute(query)
    data = {str(row.classification_code): row.count for row in result}
    
    # Cache result
    await set_cached(cache_key, data, ttl_seconds=ANALYTICS_CACHE_TTL)
    
    return data


async def get_compliance_timeline(
    session: AsyncSession, org_id: str, project_id: str
) -> dict[str, float]:
    """Get QA completion percentage over time (weekly).
    
    Args:
        session: Database session
        org_id: Organization ID
        project_id: Project ID
        
    Returns:
        Dict mapping week start date (ISO format) to completion percentage
    """
    cache_key = f"analytics:compliance_timeline:{org_id}:{project_id}"
    cached = await get_cached(cache_key)
    if cached:
        return cached
    
    # Get total items
    total_items_query = select(func.count(ItemModel.id)).where(
        ItemModel.org_id == org_id,
        ItemModel.project_id == project_id
    )
    total_result = await session.execute(total_items_query)
    total_items = total_result.scalar() or 1  # Avoid division by zero
    
    # Get document links grouped by week
    # Use DATE_TRUNC in PostgreSQL to group by week
    timeline_query = text("""
        SELECT 
            DATE_TRUNC('week', dl.created_at) as week_start,
            COUNT(DISTINCT dl.item_id) as items_with_docs
        FROM document_links dl
        JOIN items i ON i.id = dl.item_id
        WHERE i.org_id = :org_id 
          AND i.project_id = :project_id
        GROUP BY DATE_TRUNC('week', dl.created_at)
        ORDER BY week_start
    """)
    
    result = await session.execute(
        timeline_query,
        {"org_id": org_id, "project_id": project_id}
    )
    
    # Calculate cumulative percentage
    timeline = {}
    cumulative_items = set()
    
    for row in result:
        week_str = row.week_start.date().isoformat()
        # This is simplified - in production, track cumulative unique items
        completion_pct = (row.items_with_docs / total_items) * 100
        timeline[week_str] = round(completion_pct, 2)
    
    # If no data, return empty
    if not timeline:
        # Add current week with 0%
        current_week = (datetime.utcnow() - timedelta(days=datetime.utcnow().weekday())).date()
        timeline[current_week.isoformat()] = 0.0
    
    # Cache result
    await set_cached(cache_key, timeline, ttl_seconds=ANALYTICS_CACHE_TTL)
    
    return timeline


async def get_cost_by_classification(
    session: AsyncSession, org_id: str, project_id: str
) -> dict[str, float]:
    """Get total cost by classification code.
    
    Args:
        session: Database session
        org_id: Organization ID
        project_id: Project ID
        
    Returns:
        Dict mapping classification code to total cost
    """
    cache_key = f"analytics:cost_distribution:{org_id}:{project_id}"
    cached = await get_cached(cache_key)
    if cached:
        return cached
    
    # Query: join items with matches, sum prices by classification
    query = (
        select(
            ItemModel.classification_code,
            func.sum(MatchResultModel.price).label("total_cost")
        )
        .join(MatchResultModel, MatchResultModel.item_id == ItemModel.id)
        .where(
            ItemModel.org_id == org_id,
            ItemModel.project_id == project_id,
            ItemModel.classification_code.isnot(None),
            MatchResultModel.status == "approved"  # Only approved matches
        )
        .group_by(ItemModel.classification_code)
        .order_by(func.sum(MatchResultModel.price).desc())
    )
    
    result = await session.execute(query)
    data = {
        str(row.classification_code): float(row.total_cost or 0)
        for row in result
    }
    
    # Cache result
    await set_cached(cache_key, data, ttl_seconds=ANALYTICS_CACHE_TTL)
    
    return data


async def get_document_coverage_matrix(
    session: AsyncSession, org_id: str, project_id: str
) -> dict[str, Any]:
    """Get document coverage matrix (doc types × classifications).
    
    Args:
        session: Database session
        org_id: Organization ID
        project_id: Project ID
        
    Returns:
        Dict with matrix data structure
    """
    cache_key = f"analytics:doc_coverage:{org_id}:{project_id}"
    cached = await get_cached(cache_key)
    if cached:
        return cached
    
    # Query: pivot document types vs classification codes
    query = text("""
        SELECT 
            i.classification_code,
            d.document_type,
            COUNT(DISTINCT dl.document_id) as doc_count
        FROM items i
        LEFT JOIN document_links dl ON dl.item_id = i.id
        LEFT JOIN documents d ON d.id = dl.document_id
        WHERE i.org_id = :org_id 
          AND i.project_id = :project_id
          AND i.classification_code IS NOT NULL
        GROUP BY i.classification_code, d.document_type
        ORDER BY i.classification_code, d.document_type
    """)
    
    result = await session.execute(
        query,
        {"org_id": org_id, "project_id": project_id}
    )
    
    # Build matrix structure
    matrix = {}
    classifications = set()
    doc_types = set()
    
    for row in result:
        if row.document_type:  # Skip null doc types
            class_code = str(row.classification_code)
            doc_type = row.document_type
            
            classifications.add(class_code)
            doc_types.add(doc_type)
            
            if class_code not in matrix:
                matrix[class_code] = {}
            matrix[class_code][doc_type] = row.doc_count
    
    data = {
        "matrix": matrix,
        "classifications": sorted(classifications),
        "doc_types": sorted(doc_types)
    }
    
    # Cache result
    await set_cached(cache_key, data, ttl_seconds=ANALYTICS_CACHE_TTL)
    
    return data
