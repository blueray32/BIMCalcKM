# Smart Price Scout - Phase 2 Progress

**Started:** 2025-12-04
**Phase:** Multi-Source & Caching
**Status:** 🚧 IN PROGRESS

---

## Summary

Phase 2 of the Smart Price Scout enhancement focuses on multi-source intelligence with parallel fetching, intelligent aggregation, deduplication, and price comparison across multiple supplier sources.

### What Has Been Built (So Far)

#### 1. Database Schema for Multi-Source Support
- ✅ `price_sources` table with full metadata
- ✅ Tracks source URL, domain, enabled status
- ✅ Operational metadata: last_sync_at, last_sync_status, items_count, errors
- ✅ Per-source rate limiting configuration
- ✅ Cache TTL configuration per source
- ✅ Audit trail: created_at, updated_at, created_by
- ✅ Tags and notes for organization

**Files:**
- `bimcalc/db/models.py` - `PriceSourceModel` (lines 214-265, 53 lines)
- `bimcalc/db/migrations/versions/910b9e6e339a_add_price_sources_table.py` (61 lines)

**Database:**
- Table created with all indexes and constraints
- Unique constraint on org_id + domain
- Indexes for enabled sources and sync tracking

#### 2. Multi-Source Orchestrator
- ✅ Parallel fetching from 3-5 enabled sources simultaneously
- ✅ Per-source error handling (partial failure tolerance)
- ✅ Product aggregation across all sources
- ✅ Intelligent deduplication by vendor_code
- ✅ Price variance detection and comparison
- ✅ Source metadata tracking on each product
- ✅ Comprehensive statistics and error reporting

**Files:**
- `bimcalc/intelligence/multi_source_orchestrator.py` (394 lines)

**Key Classes:**
- `MultiSourceOrchestrator` - Main orchestration engine
- `MultiSourceResult` - Result container with stats

**Features:**
- Fetches from all enabled sources in parallel using `asyncio.gather`
- Applies per-source rate limiting
- Handles compliance errors gracefully
- Deduplicates by keeping lowest price
- Tracks duplicate sources and price variance
- Updates source sync metadata automatically

#### 3. Product Deduplication Logic
- ✅ Groups products by vendor_code
- ✅ Keeps product with lowest unit_price when duplicates found
- ✅ Stores all source variants in `_duplicate_sources` metadata
- ✅ Calculates price variance statistics (min, max, mean, variance_pct)
- ✅ Handles missing prices gracefully

**Algorithm:**
```python
For each vendor_code:
  - If single source: keep as-is
  - If multiple sources:
    - Sort by price (handle None values)
    - Keep cheapest valid price
    - Store all source variants in metadata
    - Calculate price variance: (max-min)/mean * 100
```

#### 4. Enhanced Integration Layer
- ✅ Updated `price_scout_sync.py` to use MultiSourceOrchestrator
- ✅ Parallel fetching replaces single-source approach
- ✅ Multi-source statistics in sync result
- ✅ Backward-compatible API signature

**Files:**
- `bimcalc/integration/price_scout_sync.py` - Enhanced with multi-source (140 lines)

**Changes:**
- Uses `MultiSourceOrchestrator` instead of `SmartPriceScout` directly
- Fetches from all org sources in parallel
- Logs multi-source statistics
- Returns aggregated unique products

#### 5. Price Sources Management UI
- ✅ List view of all configured sources
- ✅ Add new source form with validation
- ✅ Edit existing source
- ✅ Enable/disable sources with toggle
- ✅ Delete sources with confirmation
- ✅ View sync history and status
- ✅ Visual indicators for enabled/disabled and sync success/failure

**Files:**
- `bimcalc/web/routes/price_sources.py` (224 lines)
- `bimcalc/web/templates/price_sources.html` (142 lines)
- `bimcalc/web/templates/price_source_form.html` (134 lines)

**Routes:**
- `GET /price-sources` - List all sources
- `GET /price-sources/new` - New source form
- `POST /price-sources` - Create new source
- `GET /price-sources/{id}/edit` - Edit source form
- `POST /price-sources/{id}` - Update source
- `POST /price-sources/{id}/toggle` - Enable/disable
- `POST /price-sources/{id}/delete` - Delete source

**UI Features:**
- Responsive table with source details
- Status badges (Enabled/Disabled, Success/Failed)
- Last sync timestamp and item count
- Inline actions (Edit, Toggle, Delete)
- Form validation (URL format, duplicate domain)
- Helpful info boxes about compliance and multi-source benefits

#### 6. App Integration
- ✅ Router registered in `app_enhanced.py`
- ✅ Module imported in `routes/__init__.py`
- ✅ Templates created and accessible

---

## Key Metrics

### Code Added (Phase 2)
- **Production Code:** ~850 lines
  - Multi-source orchestrator: 394 lines
  - Price sources routes: 224 lines
  - Price sources model: 53 lines
  - Updated sync integration: ~40 lines (changes)
  - Migration: 61 lines

- **Templates:** ~280 lines
  - price_sources.html: 142 lines
  - price_source_form.html: 134 lines

- **Total:** ~1,130 lines

### Test Coverage
- ⏳ **Unit tests:** Not yet written
- ⏳ **Integration tests:** Not yet written
- **Target:** >80% coverage

---

## Phase 2 Features Comparison

### Before Phase 2
- ❌ Single source only
- ❌ No parallel fetching
- ❌ No deduplication
- ❌ No price comparison
- ❌ No source management UI
- ❌ Manual source configuration via env vars

### After Phase 2 (Current)
- ✅ Multiple sources per organization
- ✅ Parallel fetching from all enabled sources
- ✅ Intelligent deduplication by vendor_code
- ✅ Price variance detection and tracking
- ✅ Web UI for managing sources
- ✅ Per-source rate limiting and config
- ✅ Source sync history and error tracking
- ⏳ Redis caching (pending)
- ⏳ Bulk URL import (pending)

---

## Completed Tasks

- [x] Design database schema for price_sources table
- [x] Create Alembic migration for price_sources table
- [x] Create MultiSourceOrchestrator for parallel fetching
- [x] Add deduplication logic for products
- [x] Update price_scout_sync to use multi-source
- [x] Create UI for managing price sources

---

## Pending Tasks

- [ ] Implement Redis cache layer for Price Scout
- [ ] Add bulk URL import feature (CSV upload)
- [ ] Write unit tests for MultiSourceOrchestrator
- [ ] Write integration tests for multi-source workflow
- [ ] Update documentation with Phase 2 features
- [ ] Performance benchmarking (3-5 sources parallel)

---

## Testing Phase 2

### Manual Testing

```bash
# 1. Start the app
uvicorn bimcalc.web.app_enhanced:app --reload

# 2. Navigate to Price Sources UI
open http://localhost:8000/price-sources

# 3. Add test sources
# - Add 2-3 supplier URLs
# - Enable them
# - Set different rate limits

# 4. Run sync
python -c "
import asyncio
from bimcalc.integration.price_scout_sync import sync_price_scout_prices

result = asyncio.run(sync_price_scout_prices(org_id='acme-construction'))
print(f\"Multi-source stats: {result['multi_source_stats']}\")
"

# 5. Check results
# - View source list to see sync status
# - Check last_sync_at, items_count
# - Verify duplicates were removed
```

### Quick Smoke Test

```python
import asyncio
from bimcalc.intelligence.multi_source_orchestrator import MultiSourceOrchestrator

async def test():
    async with MultiSourceOrchestrator(org_id="acme-construction") as orchestrator:
        result = await orchestrator.fetch_all()

        print(f"Sources attempted: {result.stats['sources_attempted']}")
        print(f"Sources succeeded: {result.stats['sources_succeeded']}")
        print(f"Total products: {result.stats['total_products']}")
        print(f"Unique products: {result.stats['unique_products']}")
        print(f"Duplicates removed: {result.stats['duplicates_removed']}")

        if result.errors:
            print(f"Errors: {result.errors}")

asyncio.run(test())
```

---

## Next Steps

### Immediate (Complete Phase 2)
1. **Testing** - Write comprehensive unit and integration tests
2. **Redis Caching** - Add 24-hour cache with automatic invalidation
3. **Bulk Import** - CSV upload for adding multiple sources at once
4. **Documentation** - Update user guide with Phase 2 features

### Future Enhancements (Phase 3+)
1. **Price Intelligence Dashboard**
   - Competitive price comparison charts
   - Price trend analysis over time
   - Best deal recommendations

2. **Advanced Deduplication**
   - Fuzzy matching on descriptions
   - Machine learning-based product matching
   - Confidence scores

3. **Source Health Monitoring**
   - Automated health checks
   - Email alerts on failures
   - Uptime statistics

4. **API Integration**
   - Direct API connections where available
   - Structured data imports (vs web scraping)
   - Faster, more reliable data

---

## Architecture

### Multi-Source Data Flow

```
┌─────────────────────────────────────────────────────────────┐
│ sync_price_scout_prices(org_id)                             │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ MultiSourceOrchestrator                                      │
│  ├─ get_enabled_sources(org_id) → [Source1, Source2, ...]  │
│  └─ fetch_all() → parallel fetch from all sources           │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ Parallel Fetch (asyncio.gather)                             │
│  ├─ fetch_from_source(Source1) → products1                  │
│  ├─ fetch_from_source(Source2) → products2                  │
│  └─ fetch_from_source(Source3) → products3                  │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ Each fetch:                                                  │
│  1. Apply source-specific rate limit                        │
│  2. Check compliance (robots.txt)                           │
│  3. SmartPriceScout.extract(url)                            │
│  4. Add source metadata to products                         │
│  5. Update source sync status in DB                         │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ Aggregation & Deduplication                                 │
│  ├─ Combine all products from all sources                   │
│  ├─ Group by vendor_code                                    │
│  ├─ For duplicates: keep lowest price                       │
│  ├─ Store all sources in _duplicate_sources                 │
│  └─ Calculate price variance                                │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ Return MultiSourceResult                                     │
│  ├─ products: unique deduplicated list                      │
│  ├─ stats: sources_succeeded, unique_products, etc.         │
│  ├─ source_results: per-source details                      │
│  └─ errors: list of failed sources with reasons             │
└─────────────────────────────────────────────────────────────┘
```

---

## Database Schema

### price_sources Table

```sql
CREATE TABLE price_sources (
    id              UUID PRIMARY KEY,
    org_id          TEXT NOT NULL,
    name            TEXT NOT NULL,              -- "TLC Direct", "Rexel UK"
    url             TEXT NOT NULL,              -- Full catalog URL
    domain          TEXT NOT NULL,              -- Extracted domain for rate limiting
    enabled         BOOLEAN NOT NULL DEFAULT TRUE,
    cache_ttl_seconds INTEGER NOT NULL DEFAULT 86400,  -- 24 hours
    rate_limit_seconds FLOAT NOT NULL DEFAULT 2.0,

    -- Operational metadata
    last_sync_at    DATETIME,
    last_sync_status TEXT,                      -- "success", "failed", "partial"
    last_sync_items_count INTEGER,
    last_sync_error TEXT,

    -- Audit
    created_at      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_by      TEXT,

    -- Additional
    notes           TEXT,
    tags            JSON,

    CONSTRAINT uq_price_source_domain UNIQUE (org_id, domain)
);

-- Indexes
CREATE INDEX idx_price_sources_enabled ON price_sources (org_id, enabled);
CREATE INDEX idx_price_sources_last_sync ON price_sources (org_id, last_sync_at);
CREATE INDEX ix_price_sources_domain ON price_sources (domain);
CREATE INDEX ix_price_sources_org_id ON price_sources (org_id);
```

---

## Success Criteria

### Phase 2 Goals (Completed)
- ✅ Multi-source support (3-5 suppliers per org)
- ✅ Parallel fetching with asyncio
- ✅ Intelligent deduplication by vendor_code
- ✅ Price comparison and variance tracking
- ✅ Web UI for source management
- ⏳ Redis caching (deferred)
- ✅ Per-source rate limiting and configuration

### Code Quality
- ✅ Follows BIMCalc style guide
- ✅ Type hints on all new functions
- ✅ Google-style docstrings
- ✅ Comprehensive error handling
- ✅ Structured logging throughout
- ⏳ Unit tests (>80% coverage) - pending
- ⏳ Integration tests - pending

---

## Acknowledgments

- Phase 1 (Compliance & Stability) provided the foundation
- ULTRATHINK process for architectural planning
- Industry best practices for multi-source data aggregation
- BIMCalc modular architecture patterns

**Phase 2: Core Features Complete!** 🎉
**Next: Testing, Caching, and Documentation** 🚀
