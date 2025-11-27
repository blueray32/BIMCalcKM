# Performance Optimization Guide

## Overview

This guide covers performance improvements for BIMCalc's Project Intelligence features, focusing on caching and query optimization.

## 1. Query Caching Strategy

### Compliance Metrics Caching

Compliance metrics are expensive to compute (multiple joins, aggregations) but don't change frequently.

**Implementation:**
```python
# bimcalc/reporting/compliance_metrics.py

from functools import lru_cache
import hashlib
import json

# Simple in-memory cache (upgrade to Redis for production)
_metrics_cache = {}

async def compute_compliance_metrics_cached(
    session: AsyncSession, 
    org_id: str, 
    project_id: str,
    cache_ttl: int = 300  # 5 minutes
) -> ComplianceMetrics:
    """Cached version of compliance metrics computation."""
    cache_key = f"compliance:{org_id}:{project_id}"
    
    # Check cache
    if cache_key in _metrics_cache:
        cached_data, timestamp = _metrics_cache[cache_key]
        if (datetime.utcnow() - timestamp).total_seconds() < cache_ttl:
            return cached_data
    
    # Compute fresh
    metrics = await compute_compliance_metrics(session, org_id, project_id)
    
    # Store in cache
    _metrics_cache[cache_key] = (metrics, datetime.utcnow())
    
    return metrics
```

**Redis Implementation (Production):**
```python
import redis.asyncio as redis
import pickle

async def get_cached_metrics(
    redis_client: redis.Redis,
    cache_key: str
) -> ComplianceMetrics | None:
    cached = await redis_client.get(cache_key)
    if cached:
        return pickle.loads(cached)
    return None

async def set_cached_metrics(
    redis_client: redis.Redis,
    cache_key: str,
    metrics: ComplianceMetrics,
    ttl: int = 300
):
    await redis_client.setex(
        cache_key,
        ttl,
        pickle.dumps(metrics)
    )
```

### Document Search Caching

Cache frequent searches and tag filters:

```python
# LRU cache for search results
@lru_cache(maxsize=100)
def get_documents_by_tag_cached(tag: str, project_id: str):
    # Returns cached results for repeated tag selections
    pass
```

## 2. Database Query Optimization

### Index Coverage Analysis

```sql
-- Check index usage
SELECT 
    schemaname,
    tablename,
    indexname,
    idx_scan,
    idx_tup_read,
    idx_tup_fetch
FROM pg_stat_user_indexes
WHERE schemaname = 'public'
ORDER BY idx_scan DESC;
```

### Recommended Indexes

Already created by migrations, but verify:

```sql
-- Documents
CREATE INDEX CONCURRENTLY idx_documents_tags_gin 
ON documents USING gin(tags);

CREATE INDEX CONCURRENTLY idx_documents_project 
ON documents(org_id, project_id);

-- Document Links
CREATE INDEX CONCURRENTLY idx_document_links_item 
ON document_links(item_id);

-- Vector Search (for large datasets)
CREATE INDEX CONCURRENTLY idx_documents_vector 
ON documents USING ivfflat (embedding vector_cosine_ops)
WITH (lists = 100);
```

### Query Optimization Examples

**Before:**
```python
# N+1 query problem
for item in items:
    links = session.query(DocumentLink).filter_by(item_id=item.id).all()
```

**After:**
```python
# Eager loading
items = session.query(Item).options(
    selectinload(Item.document_links)
).all()
```

## 3. API Response Time Targets

| Endpoint | Target | Notes |
|----------|--------|-------|
| `/documents` | < 200ms | With caching |
| `/compliance` | < 500ms | Complex aggregations |
| `/classifications` | < 100ms | Simple CRUD |
| `/api/documents/search` | < 300ms | Vector search |

## 4. Monitoring

### Query Performance Logging

```python
import time
import logging

logger = logging.getLogger(__name__)

async def log_slow_queries(func):
    async def wrapper(*args, **kwargs):
        start = time.time()
        result = await func(*args, **kwargs)
        duration = (time.time() - start) * 1000
        
        if duration > 500:  # Log queries > 500ms
            logger.warning(f"Slow query: {func.__name__} took {duration:.2f}ms")
        
        return result
    return wrapper
```

### Metrics to Track

- Query execution time
- Cache hit/miss rates
- Number of items/documents per project
- API response times (p50, p95, p99)

## 5. Pagination

For large result sets, implement pagination:

```python
@app.get("/api/documents/search")
async def search_documents(
    q: str | None = None,
    page: int = 1,
    page_size: int = 20
):
    offset = (page - 1) * page_size
    
    stmt = (
        select(DocumentModel)
        .limit(page_size)
        .offset(offset)
    )
    
    # Return paginated results with metadata
    return {
        "results": docs,
        "page": page,
        "page_size": page_size,
        "total": total_count
    }
```

## 6. Background Processing

Move expensive operations to background tasks:

```python
# Use ARQ for async processing
async def recompute_compliance_metrics(
    ctx, org_id: str, project_id: str
):
    """Background task to refresh compliance cache."""
    async with get_session() as session:
        metrics = await compute_compliance_metrics(session, org_id, project_id)
        await cache_metrics(metrics, org_id, project_id)
```

## Implementation Checklist

- [ ] Add Redis for distributed caching
- [ ] Implement compliance metrics caching
- [ ] Add document search result caching
- [ ] Create slow query logging
- [ ] Set up monitoring dashboards
- [ ] Implement pagination for large result sets
- [ ] Move heavy computations to background tasks
- [ ] Add database query plan analysis
- [ ] Optimize vector search with ivfflat index

## Expected Improvements

- **Compliance Dashboard**: 2-3x faster on repeated visits
- **Document Search**: 50% reduction in query time for cached results
- **API Latency**: p95 under 500ms for all endpoints
- **Database Load**: 30-40% reduction in query volume
