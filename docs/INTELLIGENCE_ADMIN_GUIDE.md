# BIMCalc Intelligence Features - Admin Guide

**Version:** 1.0  
**Last Updated:** November 2025  
**Audience:** System Administrators, DevOps

---

## 🎯 Overview

This guide covers configuration, troubleshooting, and optimization of BIMCalc's Intelligence features for administrators.

---

## 📋 Prerequisites

### Required Services
- ✅ PostgreSQL with `pgvector` extension
- ✅ Redis server (for caching)
- ✅ OpenAI API account

### Environment Variables
```bash
# Required
OPENAI_API_KEY=sk-...           # OpenAI API key
REDIS_URL=redis://redis:6379    # Redis connection

# Optional
POSTGRES_URL=postgresql://...    # Database (auto-configured in Docker)
```

### Python Dependencies
```toml
# In pyproject.toml
dependencies = [
    "openai>=1.12",      # LLM integration
    "pgvector>=0.2.4",   # Vector embeddings
    "redis>=5.0",        # Caching
    ...
]
```

---

## 🏗️ Architecture

### Component Overview

```
┌─────────────────────────────────────────┐
│           FastAPI Application           │
├─────────────────────────────────────────┤
│  • Analytics Dashboard                  │
│  • Risk Dashboard                       │
│  • Checklist Generation                 │
│  • Document Recommendations             │
└──────────┬──────────────────────────────┘
           │
    ┌──────┴──────┬──────────┬──────────┐
    ▼             ▼          ▼          ▼
┌────────┐  ┌──────────┐  ┌─────┐  ┌──────────┐
│Postgres│  │  Redis   │  │ AI  │  │ pgvector │
│   DB   │  │  Cache   │  │ LLM │  │ Vectors  │
└────────┘  └──────────┘  └─────┘  └──────────┘
```

### Data Flow

**1. Analytics:**
```
Request → Cache Check → DB Query → Cache Store → Response
          (10min TTL)
```

**2. Risk Scoring:**
```
Item → Calculate Risk → Cache Result → Return Score
       (4 factors)      (1hr TTL)
```

**3. Checklist Generation:**
```
Item → Find Docs → Call LLM → Parse → Store DB → Return
       (RAG)       (GPT-4o)           (JSONB)
```

**4. Recommendations:**
```
Item → Generate → Vector Search → Cache → Return
       Embedding  (pgvector)       (24hr)
```

---

## ⚙️ Configuration

### 1. OpenAI API Setup

**Get API Key:**
1. Visit https://platform.openai.com
2. Create account / sign in
3. Navigate to API keys
4. Create new key
5. Set in environment: `OPENAI_API_KEY=sk-...`

**Model Configuration:**
- **Embeddings:** `text-embedding-3-large` (1536 dimensions)
- **Checklists:** `gpt-4o-mini` (cost-optimized)

**Cost Management:**
```python
# In checklist_generator.py
model="gpt-4o-mini",      # $0.15/1M tokens
temperature=0.3,           # Consistent output
response_format={"type": "json_object"}  # Structured
```

### 2. Redis Configuration

**Docker Compose:**
```yaml
redis:
  image: redis:7-alpine
  ports:
    - "6379:6379"
  volumes:
    - redis_data:/data
```

**Cache Strategy:**
```python
# Cache TTLs
ANALYTICS_TTL = 600      # 10 minutes
RISK_TTL = 3600          # 1 hour
EMBEDDING_TTL = 86400    # 24 hours
```

**Monitor Cache:**
```bash
# Connect to Redis
docker compose exec redis redis-cli

# Check cache keys
KEYS analytics:*
KEYS risk:*
KEYS item_embedding:*

# View cache stats
INFO stats
```

### 3. PostgreSQL + pgvector

**Install Extension:**
```sql
CREATE EXTENSION IF NOT EXISTS vector;
```

**Verify:**
```sql
SELECT * FROM pg_extension WHERE extname = 'vector';
```

**Vector Index:**
```sql
-- Created automatically by Alembic migration
CREATE INDEX ON documents USING ivfflat (embedding vector_cosine_ops);
```

### 4. Database Migrations

**Apply migrations:**
```bash
# Inside app container
alembic upgrade head
```

**Check current version:**
```bash
alembic current
```

**Rollback if needed:**
```bash
alembic downgrade -1
```

---

## 📊 Monitoring

### Key Metrics to Track

**1. API Performance**
```
Average Response Times:
- Analytics: <2s (with cache), <5s (without)
- Risk Scoring: <200ms (with cache), <500ms (without)
- Recommendations: <50ms (with cache), <500ms (without)
- Checklist Generation: ~10s (no cache, LLM call)
```

**2. Cache Hit Rates**
```bash
# Check Redis stats
docker compose exec redis redis-cli INFO stats | grep hit_rate

Target: >80% hit rate
```

**3. OpenAI API Usage**
```python
# Monitor in OpenAI dashboard
- Requests per day
- Token usage
- Cost per day

Expected: <$0.50 per 100-item project
```

**4. Database Performance**
```sql
-- Slow query log
SELECT query, calls, total_time, mean_time
FROM pg_stat_statements
WHERE query LIKE '%analytics%' OR query LIKE '%risk%'
ORDER BY mean_time DESC
LIMIT 10;
```

### Health Checks

**1. Application Health:**
```bash
curl http://localhost:8003/health
```

**2. Redis Health:**
```bash
docker compose exec redis redis-cli PING
# Should return: PONG
```

**3. Database Health:**
```bash
docker compose exec db pg_isready
# Should return: accepting connections
```

**4. Worker Health:**
```bash
docker compose logs worker --tail=50
# Should show: "Worker started successfully"
```

---

## 🔧 Troubleshooting

### Common Issues

#### 1. "No module named 'pgvector'"

**Symptom:** Worker container crashes on startup

**Solution:**
```bash
# Rebuild worker with dependencies
docker compose build worker
docker compose up -d worker
```

**Verify:** Check `pyproject.toml` has `pgvector>=0.2.4`

#### 2. Analytics Charts Not Loading

**Symptoms:**
- "Failed to load chart"
- Empty charts

**Check:**
```bash
# 1. Verify database has data
docker compose exec db psql -U bimcalc -c "SELECT COUNT(*) FROM items;"

# 2. Check Redis connection
docker compose exec redis redis-cli PING

# 3. View app logs
docker compose logs app | grep analytics
```

**Solution:**
- Populate database with items
- Restart Redis: `docker compose restart redis`
- Clear cache: `docker compose exec redis redis-cli FLUSHDB`

#### 3. Checklist Generation Fails

**Symptoms:**
- "Failed to generate checklist"
- Takes >30 seconds

**Check:**
```bash
# 1. Verify OpenAI API key
docker compose exec app env | grep OPENAI_API_KEY

# 2. Test OpenAI connection
docker compose exec app python3 -c "
import openai
client = openai.OpenAI()
print(client.models.list())
"

# 3. Check documents exist
docker compose exec db psql -U bimcalc -c "SELECT COUNT(*) FROM documents;"
```

**Solutions:**
- Set valid `OPENAI_API_KEY`
- Upload quality documents
- Check OpenAI API status: https://status.openai.com

#### 4. High OpenAI Costs

**Symptoms:**
- Unexpected API bills
- >$5 per project

**Check:**
```python
# Review usage in OpenAI dashboard
# Expected: ~$0.12 per 100-item project
```

**Solutions:**
```python
# 1. Verify caching is working
docker compose exec redis redis-cli KEYS item_embedding:*
# Should show cached embeddings

# 2. Increase cache TTL if needed
# In recommendations.py:
EMBEDDING_CACHE_TTL = 86400  # 24 hours (increase if needed)

# 3. Limit document context
# In checklist_generator.py:
excerpt = doc.content[:500]  # Limit to 500 tokens
```

#### 5. Risk Scores Always 0

**Symptoms:**
- All items show 0 risk
- No high-risk items

**Check:**
```bash
# Verify items have proper data
docker compose exec db psql -U bimcalc -c "
SELECT 
  COUNT(*) as total,
  COUNT(classification_code) as with_class,
  AVG(EXTRACT(EPOCH FROM (NOW() - created_at))/86400) as avg_age_days
FROM items;
"
```

**Solution:**
- Ensure items have classifications
- Link documents to items
- Run matching to get confidence scores

---

## 🚀 Performance Optimization

### 1. Cache Tuning

**Increase cache size:**
```yaml
# docker-compose.yml
redis:
  command: redis-server --maxmemory 512mb --maxmemory-policy allkeys-lru
```

**Monitor cache memory:**
```bash
docker compose exec redis redis-cli INFO memory
```

### 2. Database Indexing

**Verify indexes exist:**
```sql
-- Should exist from migrations
SELECT indexname FROM pg_indexes WHERE tablename IN ('items', 'documents', 'qa_checklists');
```

**Add custom indexes if needed:**
```sql
-- For frequent risk queries
CREATE INDEX CONCURRENTLY idx_items_age ON items(created_at DESC);

-- For analytics
CREATE INDEX CONCURRENTLY idx_items_classification ON items(classification_code) 
WHERE classification_code IS NOT NULL;
```

### 3. Embedding Optimization

**Batch generate embeddings:**
```python
# For bulk operations
from bimcalc.intelligence.recommendations import get_item_embedding

async def pregenerate_embeddings(item_ids: list):
    """Pre-cache embeddings for multiple items"""
    for item_id in item_ids:
        await get_item_embedding(item_id)  # Caches result
```

### 4. API Rate Limiting

**Prevent OpenAI rate limits:**
```python
# In checklist_generator.py
import asyncio
from functools import wraps

def rate_limit(calls_per_minute=20):
    """Decorator to rate limit OpenAI calls"""
    ...
```

---

## 💰 Cost Optimization

### Understanding Costs

**Per 100-Item Project:**
- Embeddings: ~$0.02 (with 80% cache hit)
- Checklists: ~$0.10 (1 per item)
- **Total:** ~$0.12

### Cost Reduction Strategies

**1. Aggressive Caching**
```python
# Increase TTLs for stable data
EMBEDDING_CACHE_TTL = 604800  # 7 days for stable items
```

**2. Limit Context Size**
```python
# In checklist_generator.py
MAX_DOCUMENT_TOKENS = 2000  # Limit per document
```

**3. Batch Processing**
```python
# Generate checklists in bulk during off-hours
# Not real-time = cheaper rates potentially
```

**4. Model Selection**
```python
# Use cheapest appropriate model
model="gpt-4o-mini"  # $0.15/1M vs gpt-4 $5/1M
```

---

## 🔐 Security

### API Key Management

**Never commit keys:**
```bash
# .gitignore
.env
*.env
config/secrets.yml
```

**Rotate API keys:**
```bash
# Monthly rotation recommended
1. Create new OpenAI key
2. Update environment variable
3. Restart containers
4. Delete old key
```

### Database Security

**Backup schedule:**
```bash
# Daily backups
docker compose exec db pg_dump -U bimcalc > backup_$(date +%Y%m%d).sql
```

**Access control:**
```sql
-- Limit permissions
REVOKE ALL ON qa_checklists FROM public;
GRANT SELECT, INSERT, UPDATE ON qa_checklists TO app_user;
```

---

## 📈 Scaling Considerations

### Horizontal Scaling

**Multiple app instances:**
```yaml
# docker-compose.yml
app:
  deploy:
    replicas: 3
  environment:
    - REDIS_URL=redis://redis:6379  # Shared cache
```

### Vertical Scaling

**Increase resources:**
```yaml
app:
  deploy:
    resources:
      limits:
        cpus: '2'
        memory: 4G
```

### Database Scaling

**Connection pooling:**
```python
# In connection.py
engine = create_async_engine(
    DATABASE_URL,
    pool_size=20,          # Increase for more connections
    max_overflow=10,
    pool_pre_ping=True
)
```

---

## 📚 API Reference

### Analytics Endpoints

```
GET /api/analytics/classification-breakdown?org={org}&project={project}
→ Returns: {"labels": [...], "values": [...]}

GET /api/analytics/compliance-timeline?org={org}&project={project}
→ Returns: {"dates": [...], "percentages": [...]}

GET /api/analytics/cost-distribution?org={org}&project={project}
→ Returns: {"labels": [...], "values": [...]}

GET /api/analytics/document-coverage?org={org}&project={project}
→ Returns: {"matrix": [[...]], "row_labels": [...], "col_labels": [...]}
```

### Risk Scoring Endpoints

```
GET /api/items/{item_id}/risk
→ Returns: {
    "item_id": "...",
    "score": 75.0,
    "level": "High",
    "factors": {...},
    "recommendations": [...]
}

GET /api/items/high-risk?org={org}&project={project}&threshold={61}&limit={50}
→ Returns: {
    "threshold": 61,
    "count": 12,
    "items": [...]
}
```

### Checklist Endpoints

```
POST /api/items/{item_id}/generate-checklist
→ Returns: {
    "checklist_id": "...",
    "items": [...],
    "source_docs": [...],
    "completion_percent": 0.0
}

GET /api/items/{item_id}/checklist
→ Returns: {
    "checklist_id": "...",
    "items": [...],
    "completion_percent": 60.0,
    "completed_at": null
}

PATCH /api/items/{item_id}/checklist
→ Body: {"item_id": 1, "completed": true}
→ Returns: {
    "completion_percent": 80.0,
    "completed_at": null
}
```

### Recommendations Endpoint

```
GET /api/items/{item_id}/recommendations
→ Returns: HTML partial with top 5 documents
```

---

## 🎓 Best Practices

### For Administrators

✅ **Monitor costs daily** - Check OpenAI dashboard  
✅ **Backup database weekly** - Automated backups  
✅ **Rotate API keys monthly** - Security best practice  
✅ **Monitor cache hit rates** - Target >80%  
✅ **Review logs regularly** - Catch issues early  
✅ **Test disaster recovery** - Have rollback plan

### For Deployment

✅ **Use environment files** - Not hardcoded values  
✅ **Enable SSL/TLS** - For production  
✅ **Set up monitoring** - Prometheus + Grafana  
✅ **Configure alerts** - For failures/high costs  
✅ **Document changes** - Keep runbook updated

---

## 📞 Support

**Issues?**
- Check logs: `docker compose logs [service] --tail=100`
- Review this guide
- Contact development team

**Feature requests?**
- Document use case
- Estimate value/impact
- Submit to roadmap

---

**Version History:**
- v1.0 (Nov 2025) - Initial release with all 4 features
