"""Compliance metrics for tracking QA/testing coverage across project items."""

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from bimcalc.db.models import DocumentLinkModel, DocumentModel, ItemModel
from bimcalc.utils.performance import log_slow_queries


@dataclass
class ComplianceMetrics:
    """Compliance metrics for project QA tracking."""

    # Overall stats
    total_items: int
    items_with_qa: int
    completion_percent: float
    
    # By classification
    coverage_by_classification: list[dict]
    
    # Deficiencies
    items_without_qa: list[dict]
    
    # Metadata
    computed_at: datetime


# Cache configuration
_CACHE_TTL_SECONDS = 300  # 5 minutes


def _get_cache_key(org_id: str, project_id: str) -> str:
    """Generate cache key for metrics."""
    return f"compliance:{org_id}:{project_id}"


async def _get_cached_metrics(org_id: str, project_id: str) -> ComplianceMetrics | None:
    """Get metrics from Redis cache if valid."""
    from bimcalc.utils.redis_cache import get_cached
    
    cache_key = _get_cache_key(org_id, project_id)
    return await get_cached(cache_key)


async def _cache_metrics(org_id: str, project_id: str, metrics: ComplianceMetrics) -> None:
    """Store metrics in Redis cache."""
    from bimcalc.utils.redis_cache import set_cached
    
    cache_key = _get_cache_key(org_id, project_id)
    await set_cached(cache_key, metrics, ttl_seconds=_CACHE_TTL_SECONDS)



@log_slow_queries(threshold_ms=1000)  # Log if takes > 1 second
async def compute_compliance_metrics(
    session: AsyncSession, org_id: str, project_id: str
) -> ComplianceMetrics:
    """Compute compliance metrics for QA coverage.
    
    Args:
        session: Database session
        org_id: Organization ID
        project_id: Project ID
        
    Returns:
        ComplianceMetrics with coverage statistics
    """
    # 1. Get all items
    items_query = select(ItemModel).where(
        ItemModel.org_id == org_id,
        ItemModel.project_id == project_id,
    )
    items_result = await session.execute(items_query)
    all_items = items_result.scalars().all()
    
    total_items = len(all_items)
    
    # 2. Get items with QA documents (tagged with #QA)
    items_with_qa_query = (
        select(ItemModel.id)
        .join(DocumentLinkModel, DocumentLinkModel.item_id == ItemModel.id)
        .join(DocumentModel, DocumentModel.id == DocumentLinkModel.document_id)
        .where(
            ItemModel.org_id == org_id,
            ItemModel.project_id == project_id,
        )
        .distinct()
    )
    
    items_with_qa_result = await session.execute(items_with_qa_query)
    items_with_qa_ids = {row[0] for row in items_with_qa_result.all()}
    
    items_with_qa_count = len(items_with_qa_ids)
    
    # 3. Calculate completion %
    completion_percent = (
        (items_with_qa_count / total_items * 100) if total_items > 0 else 0.0
    )
    
    # 4. Coverage by classification
    coverage_by_class = {}
    for item in all_items:
        class_code = item.classification_code or "Unknown"
        if class_code not in coverage_by_class:
            coverage_by_class[class_code] = {"total": 0, "with_qa": 0}
        
        coverage_by_class[class_code]["total"] += 1
        if item.id in items_with_qa_ids:
            coverage_by_class[class_code]["with_qa"] += 1
    
    coverage_by_classification = [
        {
            "classification": code,
            "total": stats["total"],
            "with_qa": stats["with_qa"],
            "percent": (stats["with_qa"] / stats["total"] * 100) if stats["total"] > 0 else 0.0,
        }
        for code, stats in coverage_by_class.items()
    ]
    
    # Sort by total count descending
    coverage_by_classification.sort(key=lambda x: x["total"], reverse=True)
    
    # 5. Items without QA (deficiencies)
    items_without_qa = [
        {
            "id": str(item.id),
            "family": item.family,
            "type_name": item.type_name,
            "classification_code": item.classification_code,
        }
        for item in all_items
        if item.id not in items_with_qa_ids
    ]
    
    return ComplianceMetrics(
        total_items=total_items,
        items_with_qa=items_with_qa_count,
        completion_percent=completion_percent,
        coverage_by_classification=coverage_by_classification,
        items_without_qa=items_without_qa,
        computed_at=datetime.utcnow(),
    )


async def compute_compliance_metrics_cached(
    session: AsyncSession, org_id: str, project_id: str
) -> ComplianceMetrics:
    """Compute compliance metrics with Redis caching.
    
    This is the preferred entry point for compliance metrics.
    Uses Redis cache with 5-minute TTL for distributed caching.
    
    Args:
        session: Database session
        org_id: Organization ID  
        project_id: Project ID
        
    Returns:
        ComplianceMetrics (cached or freshly computed)
    """
    # Check cache first
    cached = await _get_cached_metrics(org_id, project_id)
    if cached:
        return cached
    
    # Compute fresh
    metrics = await compute_compliance_metrics(session, org_id, project_id)
    
    # Cache for next time
    await _cache_metrics(org_id, project_id, metrics)
    
    return metrics
