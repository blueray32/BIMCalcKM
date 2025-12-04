# ULTRATHINK: Smart Price Scout Architecture Review

**Date:** 2025-12-04
**Type:** HIGH VALUE - Cross-Cutting Feature Review
**Scope:** Comprehensive review of Smart Price Scout implementation and optimal architecture design

---

## Executive Summary

Smart Price Scout is an AI-powered price intelligence system that extracts product pricing data from supplier websites using LLM analysis and browser automation. This ULTRATHINK document analyzes the current implementation, compares it against industry best practices, and proposes an optimal architecture for maximum effectiveness and compliance.

**Key Findings:**
- ✅ **Strong Foundation**: Uses GPT-4 + Playwright for intelligent extraction
- ⚠️ **Limited Data Sources**: Currently single-URL focused, lacks multi-source orchestration
- ⚠️ **No Caching/Deduplication**: Repeated scans waste LLM tokens and time
- ⚠️ **Legal/Ethical Gaps**: No robots.txt compliance, rate limiting, or ToS awareness
- ⚠️ **Missing Competitive Intelligence**: No price comparison, trend analysis, or alerting

**Recommended Priority:** Enhance existing foundation with multi-source support, caching, compliance, and intelligence layer.

---

## 1. Current Implementation Analysis

### 1.1 Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                     Smart Price Scout System                    │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐     │
│  │  Web UI      │───→│  API Routes  │───→│  Worker      │     │
│  │ price_scout  │    │ /price-scout │    │ Background   │     │
│  │  .html       │    │              │    │ Jobs (ARQ)   │     │
│  └──────────────┘    └──────────────┘    └──────────────┘     │
│                            │                      │             │
│                            ↓                      ↓             │
│  ┌────────────────────────────────────────────────────────┐    │
│  │         SmartPriceScout Core Engine                    │    │
│  │  ┌──────────────┐    ┌──────────────┐                 │    │
│  │  │  Playwright  │───→│  GPT-4       │                 │    │
│  │  │  Browser     │    │  Analyzer    │                 │    │
│  │  │  Automation  │    │  (OpenAI)    │                 │    │
│  │  └──────────────┘    └──────────────┘                 │    │
│  └────────────────────────────────────────────────────────┘    │
│                            │                                    │
│                            ↓                                    │
│  ┌────────────────────────────────────────────────────────┐    │
│  │         PriceScoutTransformer                          │    │
│  │  - Classification mapping                              │    │
│  │  - Canonical key generation                            │    │
│  │  - Unit standardization                                │    │
│  └────────────────────────────────────────────────────────┘    │
│                            │                                    │
│                            ↓                                    │
│  ┌────────────────────────────────────────────────────────┐    │
│  │         PostgreSQL Database                            │    │
│  │  - price_items (SCD Type-2)                            │    │
│  │  - price_import_runs (audit log)                       │    │
│  │  - classification_mappings                             │    │
│  └────────────────────────────────────────────────────────┘    │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### 1.2 Key Components

#### **1.2.1 Intelligence Layer** (`bimcalc/intelligence/price_scout.py`)
- **Purpose**: Core extraction engine
- **Implementation**:
  - Playwright for headless browsing (connects to remote CDP or local instance)
  - GPT-4 for intelligent content analysis
  - Structured JSON output via `response_format`
  - Token optimization (50K char limit, removes clutter)
- **Strengths**:
  - Model-agnostic (configurable via `llm.llm_model`)
  - Handles both product detail pages and product lists
  - Clean separation of fetch vs. analyze
- **Weaknesses**:
  - No caching of page content or LLM results
  - No error recovery (retry logic)
  - No robots.txt compliance
  - No rate limiting

#### **1.2.2 Integration Layer** (`bimcalc/integration/`)
- **price_scout_sync.py**: ETL orchestration
  - Fetches from configured `PRICE_SCOUT_SOURCE_URL`
  - Single-source only (no multi-supplier support)
  - Fixed 7-day delta for incremental sync
- **price_scout_transformer.py**: Data transformation
  - Classification mapping (source → target scheme)
  - Canonical key generation for matching
  - Unit standardization (m², ea, etc.)
  - Rejection tracking (missing fields, unmapped classifications)

#### **1.2.3 Web UI** (`bimcalc/web/routes/price_scout.py`, `templates/price_scout.html`)
- **Features**:
  - ⚡ Quick Scout: Ad-hoc URL extraction (HTMX-powered)
  - 🔄 Scheduled Sync: Background job trigger
  - 📊 Statistics dashboard
  - 🗺️ Classification mapping management
  - 📜 Sync history viewer
- **Strengths**:
  - Modern, intuitive UI
  - Real-time job status polling
  - Both single-product and list view support
- **Gaps**:
  - No bulk URL import
  - No price comparison view
  - No alert configuration

#### **1.2.4 Database Schema**
- **price_items**: SCD Type-2 for price history
  - Composite key: `org_id + item_code + region`
  - Temporal tracking: `effective_date`, `end_date`
  - Includes `canonical_key` for BIMCalc matching integration
- **price_import_runs**: Audit log for sync jobs
  - Tracks fetched/loaded/rejected counts
  - Stores error messages and metadata

### 1.3 Data Flow

```
1. USER ACTION
   │
   ├─ Quick Scout: User pastes URL
   │   └→ POST /price-scout/scout
   │      └→ SmartPriceScout.extract(url)
   │         ├→ Playwright fetches page
   │         ├→ GPT-4 analyzes content
   │         └→ Returns structured JSON
   │            └→ Rendered inline (no DB save)
   │
   └─ Scheduled Sync: User triggers background job
       └→ POST /price-scout/sync
          └→ Enqueue job: run_price_scout_sync
             └→ sync_price_scout_prices(org_id, delta_days)
                ├→ SmartPriceScout.extract(source_url)
                ├→ PriceScoutTransformer.transform_batch()
                └→ Bulk import via API: /api/price-items/bulk-import
                   └→ Inserts into price_items (SCD Type-2)

2. BACKGROUND WORKER (ARQ)
   └→ Processes job queue
      └→ Executes run_price_scout_sync()
         └→ Returns result to job status
```

### 1.4 Integration with BIMCalc Core

**Tight Integration Points:**
1. **Classification System**: Uses `ClassificationMapper` for scheme translation
2. **Canonical Keys**: Generates keys via `parse_fitting_attributes()` for matching
3. **SCD Type-2**: Aligns with BIMCalc's temporal mapping memory pattern
4. **Multi-Tenancy**: Respects `org_id` scoping throughout

**Loose Integration Points:**
1. **Matching Pipeline**: Price data available but not actively used in matching confidence
2. **Risk Flags**: No price variance flags generated from scout data
3. **Reporting**: Price scout data not yet surfaced in executive reports

---

## 2. Industry Best Practices Research

### 2.1 Leading Price Intelligence Tools (2025)

From web research, top platforms include:

1. **Bright Insights** ([Bright Data](https://brightdata.com/blog/web-data/best-price-intelligence-tools))
   - 150M+ IPs across 195 countries
   - Real-time monitoring with AI-driven alerts
   - Customizable dashboards
   - **Key Takeaway**: Scale and global reach matter

2. **Prisync** ([Competitor Price Tracking](https://prisync.com/))
   - Focus on 3-5 direct competitors (not everyone)
   - Automated repricing based on rules
   - **Key Takeaway**: Strategic competitor selection

3. **Competera / Omnia Retail**
   - Enterprise optimization with margin floors
   - Seasonality and stock level integration
   - **Key Takeaway**: Context-aware pricing

### 2.2 Best Practice Patterns

#### **2.2.1 Product Matching Strategy**
> "Match apples to apples: exact SKU/size/region; document equivalence rules."

**Application to BIMCalc**: Already implemented via canonical keys, but need better cross-supplier normalization.

#### **2.2.2 Monitoring Cadence**
> "Segment by category: real-time for high-velocity, weekly for long-tail."

**Application to BIMCalc**:
- Construction materials are relatively stable (weekly checks sufficient)
- But project-critical items (e.g., specified fixtures) may need daily monitoring

#### **2.2.3 Response Strategy**
> "Create SOP with thresholds, margin floors, approvers, and SLA."

**Application to BIMCalc**:
- Generate Advisory flags when competitor price is 10%+ lower
- Generate Critical-Veto flags when price variance >20% (trust issue)

#### **2.2.4 Alert Features**
> "Real-time alerts when competitors change prices."

**Application to BIMCalc**: Currently missing - need notification system.

### 2.3 Construction-Specific Insights

#### **2.3.1 API Solutions for Construction**

- **1build** ([Construction Cost API](https://www.1build.com/))
  - Tracks 68M live materials/labor/equipment costs
  - County-level granularity (US)
  - Modern API for integration
  - **Relevance**: Could supplement web scraping for US projects

- **ENR Cost Data** ([Construction Cost Dashboard](https://www.enr.com/Cost-Data-Dashboard))
  - 20 major US cities, 60+ material types
  - API for instant updates
  - **Relevance**: Macro-level price trends

- **Handoff** ([YC Company](https://www.ycombinator.com/companies/handoff))
  - Integrates directly with Home Depot, Lowe's catalogs
  - Real-time pricing and inventory
  - **Relevance**: For North American suppliers

#### **2.3.2 Key Insight**
Construction materials have:
- **High fragmentation**: 1000s of SKUs across many suppliers
- **Regional variation**: Prices vary by geography (shipping, local demand)
- **Volume discounts**: Trade accounts get different pricing
- **Seasonal fluctuations**: Copper, steel, lumber prices volatile

**Implication**: Price Scout needs multi-region support and volume-tier awareness.

---

## 3. Legal and Ethical Compliance

### 3.1 Legal Status of Price Scraping

From research ([ProWebScraper](https://prowebscraper.com/blog/is-price-scraping-legal/), [PromptCloud](https://www.promptcloud.com/blog/ensuring-ethical-price-scraping-best-practices-and-guidelines/)):

**✅ LEGAL when:**
- Data is publicly available (no login required)
- Complies with website Terms of Service
- Respects robots.txt directives
- Doesn't cause server overload
- No personal data collection (GDPR)

**❌ ILLEGAL when:**
- Bypasses security (passwords, CAPTCHAs)
- Violates ToS with anti-scraping clauses
- Causes denial of service (excessive requests)
- Extracts confidential data
- Ignores cease-and-desist notices

### 3.2 Current Compliance Gaps

| Requirement | Current Status | Risk Level | Fix Needed |
|-------------|---------------|------------|------------|
| **Robots.txt** | ❌ Not checked | HIGH | Add pre-flight check |
| **Rate Limiting** | ❌ None | HIGH | Implement delays |
| **User-Agent** | ✅ Set (realistic) | LOW | OK |
| **ToS Awareness** | ❌ No validation | MEDIUM | User acceptance |
| **GDPR** | ✅ No personal data | LOW | OK |
| **Server Load** | ⚠️ Single request/page | MEDIUM | Monitor |
| **Auth Bypass** | ✅ Public pages only | LOW | OK |

### 3.3 Recommendations

#### **Immediate (P0):**
1. **Add robots.txt parser**
   ```python
   import urllib.robotparser

   async def is_url_allowed(url: str, user_agent: str) -> bool:
       """Check if URL is allowed per robots.txt"""
       rp = urllib.robotparser.RobotFileParser()
       rp.set_url(urllib.parse.urljoin(url, "/robots.txt"))
       rp.read()
       return rp.can_fetch(user_agent, url)
   ```

2. **Implement rate limiting**
   - Minimum 2-second delay between requests to same domain
   - Configurable per-supplier rules

#### **Short-term (P1):**
3. **Add ToS acceptance**
   - User must acknowledge they have permission to scrape supplier site
   - Log acceptance in audit trail

4. **Retry with exponential backoff**
   - Handle 429 (Too Many Requests) gracefully
   - Respect Retry-After headers

#### **Long-term (P2):**
5. **Supplier whitelist/blacklist**
   - Maintain list of known-compliant suppliers
   - Warn on unknown domains

---

## 4. Gap Analysis

### 4.1 Feature Gaps

| Feature | Current | Industry Standard | Priority |
|---------|---------|------------------|----------|
| **Multi-Source** | Single URL | 3-5 competitors | HIGH |
| **Caching** | None | 24hr cache | HIGH |
| **Price Alerts** | None | Real-time notifications | MEDIUM |
| **Trend Analysis** | None | Historical charts | MEDIUM |
| **Bulk Import** | None | CSV/list support | MEDIUM |
| **Competitor View** | None | Side-by-side comparison | HIGH |
| **API Mode** | None | RESTful API | LOW |
| **Proxy Rotation** | None | Residential proxies | LOW |

### 4.2 Technical Debt

1. **No Caching**: Every scan hits supplier site + uses LLM tokens
   - **Cost**: Wastes ~$0.01-0.05 per GPT-4 call
   - **Fix**: Redis cache with TTL

2. **Single Source**: Can't compare multiple suppliers
   - **Impact**: Limited competitive intelligence
   - **Fix**: Multi-source orchestration

3. **No Deduplication**: Same URL can be scanned multiple times
   - **Impact**: Duplicate price_items records
   - **Fix**: Check existing records before insert

4. **Error Handling**: Basic try/catch, no retry logic
   - **Impact**: Transient failures fail permanently
   - **Fix**: Tenacity library for retries

5. **No Validation**: Doesn't verify price reasonableness
   - **Impact**: Could import obviously wrong prices (e.g., $0.01)
   - **Fix**: Add validation rules (min/max price, outlier detection)

### 4.3 Integration Gaps

1. **Matching Pipeline**: Price scout data not used in confidence scoring
   - **Fix**: Add price variance as a ranking signal

2. **Risk Flags**: No flags generated from price data
   - **Fix**: Generate "price_outlier" flags when variance >20%

3. **Reporting**: Scout data invisible in executive reports
   - **Fix**: Add "Price Intelligence" section to executive dashboard

---

## 5. Optimal Architecture Proposal

### 5.1 High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                    SMART PRICE SCOUT V2.0                           │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │                    WEB UI LAYER                              │  │
│  │  ┌────────────┐  ┌────────────┐  ┌────────────┐             │  │
│  │  │Quick Scout │  │Multi-Source│  │ Alerts &   │             │  │
│  │  │(Ad-hoc)    │  │ Sync       │  │ Dashboard  │             │  │
│  │  └────────────┘  └────────────┘  └────────────┘             │  │
│  └──────────────────────────────────────────────────────────────┘  │
│                              │                                      │
│                              ↓                                      │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │                    API ROUTES LAYER                          │  │
│  │  /price-scout/scout (single URL)                             │  │
│  │  /price-scout/sync (multi-source batch)                      │  │
│  │  /price-scout/compare (competitor view)                      │  │
│  │  /price-scout/alerts/config                                  │  │
│  └──────────────────────────────────────────────────────────────┘  │
│                              │                                      │
│                              ↓                                      │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │              ORCHESTRATION LAYER (NEW)                       │  │
│  │  ┌────────────────────────────────────────────────────────┐  │  │
│  │  │  MultiSourceOrchestrator                               │  │  │
│  │  │  - Parallel fetching from N suppliers                  │  │  │
│  │  │  - Rate limiting per domain                            │  │  │
│  │  │  - Retry with exponential backoff                      │  │  │
│  │  │  - Compliance checks (robots.txt)                      │  │  │
│  │  └────────────────────────────────────────────────────────┘  │  │
│  └──────────────────────────────────────────────────────────────┘  │
│                              │                                      │
│                              ↓                                      │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │              EXTRACTION LAYER (Enhanced)                     │  │
│  │  ┌────────────────┐    ┌────────────────┐                   │  │
│  │  │ SmartScout     │    │ Cache Layer    │                   │  │
│  │  │ - Playwright   │───→│ - Redis        │                   │  │
│  │  │ - GPT-4        │    │ - 24hr TTL     │                   │  │
│  │  │ - Validators   │    │ - Token saving │                   │  │
│  │  └────────────────┘    └────────────────┘                   │  │
│  └──────────────────────────────────────────────────────────────┘  │
│                              │                                      │
│                              ↓                                      │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │           INTELLIGENCE LAYER (NEW)                           │  │
│  │  ┌────────────────────────────────────────────────────────┐  │  │
│  │  │  PriceIntelligenceEngine                               │  │  │
│  │  │  - Competitor comparison                               │  │  │
│  │  │  - Trend detection                                     │  │  │
│  │  │  - Anomaly alerts (price spikes)                       │  │  │
│  │  │  - Recommendation generation                           │  │  │
│  │  └────────────────────────────────────────────────────────┘  │  │
│  └──────────────────────────────────────────────────────────────┘  │
│                              │                                      │
│                              ↓                                      │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │              TRANSFORMATION LAYER (Existing)                 │  │
│  │  - Classification mapping                                    │  │
│  │  - Canonical key generation                                  │  │
│  │  - Unit standardization                                      │  │
│  └──────────────────────────────────────────────────────────────┘  │
│                              │                                      │
│                              ↓                                      │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │              STORAGE LAYER (PostgreSQL + Redis)              │  │
│  │  - price_items (SCD Type-2)                                  │  │
│  │  - price_sources (supplier configs)                          │  │
│  │  - price_alerts (alert rules)                                │  │
│  │  - price_comparison_cache (Redis)                            │  │
│  └──────────────────────────────────────────────────────────────┘  │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

### 5.2 New Components

#### **5.2.1 MultiSourceOrchestrator**

```python
class MultiSourceOrchestrator:
    """Orchestrates parallel price extraction from multiple suppliers."""

    def __init__(self, sources: list[PriceSource], cache: RedisCache):
        self.sources = sources
        self.cache = cache
        self.rate_limiters = {s.domain: RateLimiter(s.delay) for s in sources}

    async def fetch_all(
        self,
        classification_filter: list[str] | None = None
    ) -> list[PriceItem]:
        """Fetch from all sources in parallel with compliance."""

        tasks = []
        for source in self.sources:
            # Check compliance
            if not await self._is_compliant(source):
                logger.warning(f"Skipping {source.name}: non-compliant")
                continue

            # Check cache first
            cached = await self.cache.get(source.cache_key())
            if cached:
                logger.info(f"Using cached data for {source.name}")
                tasks.append(asyncio.create_task(asyncio.sleep(0)))
                continue

            # Rate limit
            await self.rate_limiters[source.domain].acquire()

            # Fetch
            tasks.append(self._fetch_source(source, classification_filter))

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Flatten and deduplicate
        all_items = []
        for result in results:
            if isinstance(result, Exception):
                logger.error(f"Source fetch failed: {result}")
                continue
            all_items.extend(result)

        return self._deduplicate(all_items)

    async def _is_compliant(self, source: PriceSource) -> bool:
        """Check robots.txt and rate limits."""
        # Check robots.txt
        allowed = await is_robots_allowed(source.url)
        if not allowed:
            return False

        # Check if we've been rate-limited recently
        if await self.cache.get(f"rate_limit:{source.domain}"):
            return False

        return True

    async def _fetch_source(
        self,
        source: PriceSource,
        classification_filter: list[str] | None
    ) -> list[PriceItem]:
        """Fetch from single source with retry."""

        for attempt in range(3):
            try:
                async with SmartPriceScout() as scout:
                    result = await scout.extract(source.url)

                # Cache result
                await self.cache.set(
                    source.cache_key(),
                    result,
                    ttl=source.cache_ttl
                )

                return result.get("products", [])

            except Exception as e:
                if attempt < 2:
                    wait = 2 ** attempt  # Exponential backoff
                    logger.warning(f"Retry {attempt+1}/3 after {wait}s: {e}")
                    await asyncio.sleep(wait)
                else:
                    logger.error(f"Failed after 3 attempts: {e}")
                    raise
```

#### **5.2.2 PriceIntelligenceEngine**

```python
class PriceIntelligenceEngine:
    """Analyzes price data to generate insights and alerts."""

    async def analyze_item(
        self,
        canonical_key: str,
        session: AsyncSession
    ) -> PriceAnalysis:
        """Analyze price for a single item across all sources."""

        # Get all active prices for this item
        stmt = select(PriceItemModel).where(
            PriceItemModel.canonical_key == canonical_key,
            PriceItemModel.end_date.is_(None)  # Active only
        )
        result = await session.execute(stmt)
        prices = list(result.scalars())

        if not prices:
            return PriceAnalysis(canonical_key=canonical_key, status="no_data")

        # Calculate statistics
        price_values = [p.unit_price for p in prices]
        mean_price = Decimal(sum(price_values)) / len(price_values)
        min_price = min(price_values)
        max_price = max(price_values)
        variance_pct = ((max_price - min_price) / mean_price) * 100

        # Generate insights
        insights = []

        # Insight 1: Best deal
        best_supplier = min(prices, key=lambda p: p.unit_price)
        insights.append(Insight(
            type="best_deal",
            message=f"Lowest price: {best_supplier.vendor_code} at {best_supplier.unit_price} {best_supplier.currency}",
            data={"supplier": best_supplier.vendor_code, "price": best_supplier.unit_price}
        ))

        # Insight 2: High variance warning
        if variance_pct > 20:
            insights.append(Insight(
                type="price_outlier",
                severity="critical",
                message=f"Price variance {variance_pct:.1f}% exceeds 20% threshold",
                data={"min": min_price, "max": max_price, "variance_pct": variance_pct}
            ))

        # Insight 3: Trend detection (requires historical data)
        trend = await self._detect_trend(canonical_key, session)
        if trend:
            insights.append(Insight(
                type="price_trend",
                message=f"Price {trend.direction} by {trend.change_pct:.1f}% over {trend.period}",
                data={"direction": trend.direction, "change_pct": trend.change_pct}
            ))

        return PriceAnalysis(
            canonical_key=canonical_key,
            status="analyzed",
            mean_price=mean_price,
            min_price=min_price,
            max_price=max_price,
            variance_pct=variance_pct,
            supplier_count=len(prices),
            insights=insights
        )

    async def check_alerts(
        self,
        org_id: str,
        session: AsyncSession
    ) -> list[PriceAlert]:
        """Check all configured alerts and return triggered ones."""

        # Get alert configurations
        stmt = select(PriceAlertModel).where(
            PriceAlertModel.org_id == org_id,
            PriceAlertModel.enabled == True
        )
        result = await session.execute(stmt)
        alert_configs = list(result.scalars())

        triggered_alerts = []

        for config in alert_configs:
            # Evaluate alert condition
            triggered = await self._evaluate_alert(config, session)
            if triggered:
                triggered_alerts.append(triggered)

        return triggered_alerts
```

#### **5.2.3 Cache Layer (Redis)**

```python
class PriceScoutCache:
    """Redis-backed cache for price scout data."""

    def __init__(self, redis_client):
        self.redis = redis_client

    async def get_extraction(self, url: str) -> dict | None:
        """Get cached extraction result."""
        key = f"price_scout:extraction:{self._hash_url(url)}"
        data = await self.redis.get(key)
        return json.loads(data) if data else None

    async def set_extraction(self, url: str, data: dict, ttl: int = 86400):
        """Cache extraction result for 24 hours."""
        key = f"price_scout:extraction:{self._hash_url(url)}"
        await self.redis.setex(key, ttl, json.dumps(data))

    async def get_comparison(self, canonical_key: str) -> dict | None:
        """Get cached price comparison."""
        key = f"price_scout:comparison:{canonical_key}"
        data = await self.redis.get(key)
        return json.loads(data) if data else None

    async def set_comparison(self, canonical_key: str, data: dict, ttl: int = 3600):
        """Cache comparison for 1 hour."""
        key = f"price_scout:comparison:{canonical_key}"
        await self.redis.setex(key, ttl, json.dumps(data))

    def _hash_url(self, url: str) -> str:
        """Create cache key from URL."""
        import hashlib
        return hashlib.sha256(url.encode()).hexdigest()[:16]
```

### 5.3 Database Schema Enhancements

```sql
-- New table: price_sources
CREATE TABLE price_sources (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id TEXT NOT NULL,
    name TEXT NOT NULL,  -- "TLC Direct", "Rexel UK", etc.
    url TEXT NOT NULL,   -- Base catalog URL
    domain TEXT NOT NULL,  -- For rate limiting
    enabled BOOLEAN DEFAULT true,
    cache_ttl INTEGER DEFAULT 86400,  -- 24 hours
    rate_limit_delay INTEGER DEFAULT 2,  -- Seconds between requests
    last_sync_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(org_id, domain)
);

-- New table: price_alerts
CREATE TABLE price_alerts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id TEXT NOT NULL,
    name TEXT NOT NULL,
    alert_type TEXT NOT NULL,  -- 'price_drop', 'price_spike', 'new_low', 'variance'
    canonical_key TEXT,  -- Specific item, or NULL for all
    threshold_pct NUMERIC,
    enabled BOOLEAN DEFAULT true,
    notification_channels TEXT[],  -- ['email', 'slack', 'ui']
    created_at TIMESTAMP DEFAULT NOW()
);

-- New table: price_alert_history
CREATE TABLE price_alert_history (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    alert_id UUID REFERENCES price_alerts(id),
    triggered_at TIMESTAMP DEFAULT NOW(),
    canonical_key TEXT,
    message TEXT,
    data JSONB
);

-- Add index for price comparison queries
CREATE INDEX idx_price_items_canonical_active
ON price_items(canonical_key, end_date)
WHERE end_date IS NULL;
```

### 5.4 Configuration Changes

```python
# bimcalc/config.py additions

class PriceScoutConfig(BaseModel):
    """Price Scout configuration."""

    # LLM Settings
    llm_model: str = "gpt-4-1106-preview"
    llm_temperature: float = 0.1

    # Browser Settings
    browser_cdp_url: str | None = None
    browser_timeout_ms: int = 60000

    # Caching
    cache_enabled: bool = True
    cache_ttl_seconds: int = 86400  # 24 hours

    # Compliance
    respect_robots_txt: bool = True
    default_rate_limit_seconds: int = 2
    user_agent: str = "BIMCalc PriceScout/1.0 (Contact: support@bimcalc.com)"

    # Multi-Source
    max_parallel_sources: int = 5
    retry_attempts: int = 3
    retry_backoff_base: int = 2

    # Validation
    min_price_threshold: Decimal = Decimal("0.01")
    max_price_threshold: Decimal = Decimal("100000.00")

    # Intelligence
    price_variance_warning_pct: float = 10.0
    price_variance_critical_pct: float = 20.0
```

---

## 6. Implementation Roadmap

### Phase 1: Compliance & Stability (P0) - 1 week
**Goal**: Make current implementation legally compliant and production-ready

1. ✅ Add robots.txt checking
2. ✅ Implement rate limiting per domain
3. ✅ Add retry logic with exponential backoff
4. ✅ Improve error handling and logging
5. ✅ Add price validation (min/max thresholds)
6. ✅ Unit tests for extraction + transformation

**Deliverables:**
- `bimcalc/intelligence/compliance.py` (robots.txt parser)
- `bimcalc/intelligence/rate_limiter.py`
- Enhanced `SmartPriceScout` with retry logic
- Test coverage >80%

**Risk**: LOW - These are additive improvements

---

### Phase 2: Multi-Source & Caching (P1) - 2 weeks
**Goal**: Enable competitive price intelligence across multiple suppliers

1. ✅ Create `price_sources` database table
2. ✅ Implement `MultiSourceOrchestrator`
3. ✅ Add Redis caching layer
4. ✅ UI for managing price sources
5. ✅ Update sync job to fetch from all enabled sources
6. ✅ Add deduplication logic

**Deliverables:**
- `bimcalc/intelligence/orchestrator.py`
- `bimcalc/intelligence/cache.py`
- Migration: `alembic/versions/xxx_add_price_sources.py`
- UI: `/price-scout/sources` management page
- Bulk import UI: paste list of URLs

**Risk**: MEDIUM - Requires new database schema and UI

---

### Phase 3: Intelligence Layer (P1) - 2 weeks
**Goal**: Surface actionable insights from price data

1. ✅ Create `PriceIntelligenceEngine`
2. ✅ Implement competitor comparison view
3. ✅ Add trend detection (requires historical queries)
4. ✅ Create alert system (database tables)
5. ✅ UI for alert configuration
6. ✅ Notification delivery (email/Slack)

**Deliverables:**
- `bimcalc/intelligence/price_intelligence.py`
- Migration: `alembic/versions/xxx_add_price_alerts.py`
- UI: `/price-scout/compare` (competitor view)
- UI: `/price-scout/alerts` (alert management)
- Integration with `bimcalc/intelligence/notifications.py`

**Risk**: MEDIUM - New complex logic

---

### Phase 4: Integration with Core (P2) - 1 week
**Goal**: Use price intelligence in matching and risk scoring

1. ✅ Add price variance to matching confidence scoring
2. ✅ Generate risk flags from price analysis
3. ✅ Surface price intelligence in executive reports
4. ✅ Add price comparison to review UI

**Deliverables:**
- Enhanced `bimcalc/matching/ranker.py` (price signal)
- Enhanced `bimcalc/flags/engine.py` (price flags)
- Updated `bimcalc/reporting/executive.py`
- UI: Price comparison widget in `/review`

**Risk**: LOW - Additive features

---

### Phase 5: API & Advanced Features (P3) - 1 week
**Goal**: Enable programmatic access and advanced use cases

1. ✅ RESTful API endpoints
2. ✅ Webhook support for alerts
3. ✅ Bulk CSV import of URLs
4. ✅ Export price comparison reports
5. ✅ Proxy rotation support (optional)

**Deliverables:**
- `bimcalc/web/routes/price_scout_api.py`
- OpenAPI documentation
- CSV import UI
- Export to Excel/PDF

**Risk**: LOW - Optional enhancements

---

## 7. Alternatives Considered

### Alternative 1: Use Existing Price Intelligence SaaS

**Option**: Integrate with Prisync, Competera, or Bright Insights

**Pros:**
- ✅ Proven at scale
- ✅ No maintenance burden
- ✅ Advanced features out-of-box

**Cons:**
- ❌ Monthly cost ($500-5000/mo)
- ❌ Construction-specific suppliers may not be covered
- ❌ Less control over data
- ❌ Integration complexity

**Decision**: ❌ **Rejected** - BIMCalc's niche (construction materials) requires custom extraction logic. Generic SaaS won't handle classification mapping, canonical keys, or BIMCalc's unique workflow.

---

### Alternative 2: Use 1build API Instead of Web Scraping

**Option**: Replace web scraping with 1build's 68M material database API

**Pros:**
- ✅ Legal and compliant
- ✅ Comprehensive US coverage
- ✅ Real-time pricing
- ✅ No scraping infrastructure

**Cons:**
- ❌ US-only (BIMCalc targets EU/UK)
- ❌ Subscription cost
- ❌ Limited to their catalog (may not include all suppliers)
- ❌ No control over data freshness

**Decision**: ⚠️ **Hybrid Approach** - Use 1build API as a supplementary data source for US projects, but keep web scraping for EU suppliers.

---

### Alternative 3: Simpler Manual CSV Import Only

**Option**: Remove web scraping entirely, rely on manual price list uploads

**Pros:**
- ✅ Simple to implement
- ✅ No legal concerns
- ✅ No LLM costs

**Cons:**
- ❌ Manual labor intensive
- ❌ Data staleness (users must remember to update)
- ❌ No competitive intelligence

**Decision**: ❌ **Rejected** - The AI-powered extraction is a key differentiator and time-saver. Manual CSV is already available as a fallback (existing Ingest page).

---

## 8. Risks and Mitigation

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| **Supplier blocks scraping** | MEDIUM | HIGH | Implement robots.txt compliance, rate limiting, use realistic user-agent. Maintain fallback to manual CSV. |
| **LLM extraction errors** | MEDIUM | MEDIUM | Add validation layer, human review for low-confidence extractions. Cache results to avoid repeated LLM calls. |
| **Cost explosion (LLM tokens)** | LOW | MEDIUM | Cache aggressively (24hr TTL). Limit content to 50K chars. Use cheaper models for simple pages. |
| **Legal action from supplier** | LOW | HIGH | Add ToS acceptance flow. Maintain whitelist of known-compliant suppliers. Respond immediately to cease-and-desist. |
| **Data quality issues** | MEDIUM | MEDIUM | Implement price validation rules. Flag outliers for review. Track rejection stats. |
| **Browser automation failure** | LOW | LOW | Use remote CDP service (resilient). Fallback to local Playwright. Retry logic. |

---

## 9. Success Metrics

### Phase 1 (Compliance):
- ✅ 100% of URLs checked against robots.txt
- ✅ Rate limiting enforced (measured via logs)
- ✅ Retry success rate >90%
- ✅ Zero legal complaints

### Phase 2 (Multi-Source):
- ✅ Average 3-5 suppliers configured per org
- ✅ Cache hit rate >50%
- ✅ Sync time <5 minutes for 5 sources
- ✅ Deduplication rate >80%

### Phase 3 (Intelligence):
- ✅ >50% of items have multi-supplier comparison
- ✅ Price variance insights generated for >80% of items
- ✅ Alerts triggered for price drops >10%
- ✅ User feedback: "helpful" rating >80%

### Phase 4 (Integration):
- ✅ Price variance flags in >20% of matches
- ✅ Price intelligence in 100% of executive reports
- ✅ Matching confidence improved (measured via A/B test)

---

## 10. Conclusion & Recommendation

### Summary

Smart Price Scout has a **solid foundation** with GPT-4 + Playwright, but currently operates as a **single-source extraction tool** rather than a comprehensive **price intelligence platform**.

**Key Strengths:**
- ✅ AI-powered extraction handles diverse page layouts
- ✅ Integrated with BIMCalc's classification and canonical key systems
- ✅ SCD Type-2 for price history
- ✅ Modern, intuitive UI

**Critical Gaps:**
- ❌ Legal/ethical compliance (robots.txt, rate limiting)
- ❌ Multi-source comparison
- ❌ Price intelligence and alerts
- ❌ Caching (wasting LLM tokens)

### Recommended Path Forward

**Adopt the 5-Phase Roadmap:**
1. **Phase 1 (1 week)**: Fix compliance gaps immediately
2. **Phase 2 (2 weeks)**: Add multi-source + caching for competitive intel
3. **Phase 3 (2 weeks)**: Build intelligence layer for insights
4. **Phase 4 (1 week)**: Integrate with matching and risk scoring
5. **Phase 5 (1 week)**: Polish with API and advanced features

**Total Effort**: ~7 weeks of focused development

**Expected Outcome**: Transform Price Scout from a "web scraper" into a **strategic price intelligence platform** that:
- ✅ Complies with legal and ethical standards
- ✅ Provides competitive insights across 3-5 suppliers
- ✅ Proactively alerts on price changes
- ✅ Improves matching confidence via price signals
- ✅ Saves time and money through caching

### Next Steps

1. **User Feedback**: Present this ULTRATHINK to stakeholders and get buy-in
2. **Prioritization**: Confirm phase priorities based on business needs
3. **Spike**: 1-day technical spike on Redis caching integration
4. **Start Phase 1**: Begin with compliance improvements (low-risk, high-value)

---

## Appendix: Code Examples

### A. Robots.txt Checker

```python
# bimcalc/intelligence/compliance.py

import urllib.parse
import urllib.robotparser
from functools import lru_cache

import httpx

logger = logging.getLogger(__name__)


@lru_cache(maxsize=100)
async def is_robots_allowed(url: str, user_agent: str = "BIMCalc PriceScout/1.0") -> bool:
    """Check if URL is allowed per robots.txt.

    Args:
        url: The URL to check
        user_agent: User agent string

    Returns:
        True if allowed, False if disallowed
    """
    try:
        # Parse URL to get base
        parsed = urllib.parse.urlparse(url)
        robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"

        # Fetch robots.txt
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(robots_url, follow_redirects=True)

        if response.status_code == 404:
            # No robots.txt = allowed
            logger.debug(f"No robots.txt at {robots_url}, allowing")
            return True

        if response.status_code != 200:
            # Error fetching = allowed (fail open)
            logger.warning(f"Error fetching robots.txt: {response.status_code}, allowing")
            return True

        # Parse robots.txt
        rp = urllib.robotparser.RobotFileParser()
        rp.parse(response.text.splitlines())

        # Check if URL is allowed
        allowed = rp.can_fetch(user_agent, url)

        if not allowed:
            logger.warning(f"Robots.txt disallows {url}")

        return allowed

    except Exception as e:
        logger.error(f"Error checking robots.txt for {url}: {e}")
        # Fail open (allow on error)
        return True
```

### B. Rate Limiter

```python
# bimcalc/intelligence/rate_limiter.py

import asyncio
import time
from collections import defaultdict

class RateLimiter:
    """Simple token bucket rate limiter per domain."""

    def __init__(self, delay_seconds: float = 2.0):
        self.delay = delay_seconds
        self.last_request = defaultdict(float)
        self.lock = asyncio.Lock()

    async def acquire(self, domain: str):
        """Wait until rate limit allows next request."""
        async with self.lock:
            now = time.time()
            last = self.last_request[domain]
            elapsed = now - last

            if elapsed < self.delay:
                wait = self.delay - elapsed
                logger.debug(f"Rate limiting {domain}: waiting {wait:.2f}s")
                await asyncio.sleep(wait)

            self.last_request[domain] = time.time()
```

### C. Enhanced SmartPriceScout with Retry

```python
# bimcalc/intelligence/price_scout.py (enhanced)

from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

class SmartPriceScout:
    """AI Agent that browses supplier websites and extracts price data."""

    def __init__(self):
        self.config = get_config()
        self.api_key = os.getenv("PRICE_SCOUT_API_KEY") or self.config.llm.api_key

        if not self.api_key:
            raise ValueError("OPENAI_API_KEY is required for Smart Price Scout")

        self.client = AsyncOpenAI(api_key=self.api_key)
        self.model = self.config.price_scout.llm_model
        self.cache = PriceScoutCache() if self.config.price_scout.cache_enabled else None

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((httpx.RequestError, asyncio.TimeoutError))
    )
    async def extract(self, url: str) -> dict[str, Any]:
        """Extract product details from a URL using LLM with retry."""
        logger.info(f"Scouting price from: {url}")

        # Check cache first
        if self.cache:
            cached = await self.cache.get_extraction(url)
            if cached:
                logger.info(f"Using cached extraction for {url}")
                return cached

        # Check robots.txt compliance
        if self.config.price_scout.respect_robots_txt:
            if not await is_robots_allowed(url, self.config.price_scout.user_agent):
                raise ValueError(f"URL {url} disallowed by robots.txt")

        # Fetch and analyze
        content = await self._fetch_page_content(url)
        extracted_data = await self._analyze_content(content, url)

        # Validate result
        self._validate_extraction(extracted_data)

        # Cache result
        if self.cache:
            await self.cache.set_extraction(url, extracted_data)

        return extracted_data

    def _validate_extraction(self, data: dict):
        """Validate extracted data meets quality standards."""
        products = data.get("products", [])

        for product in products:
            price = product.get("unit_price")
            if price is not None:
                price_decimal = Decimal(str(price))

                # Check min threshold
                if price_decimal < self.config.price_scout.min_price_threshold:
                    logger.warning(f"Suspicious low price: {price}")

                # Check max threshold
                if price_decimal > self.config.price_scout.max_price_threshold:
                    logger.warning(f"Suspicious high price: {price}")
```

---

## References

1. [Best Price Intelligence Tools 2025](https://brightdata.com/blog/web-data/best-price-intelligence-tools)
2. [What Is Price Intelligence? Definition and Best Practices](https://www.shopify.com/blog/price-intelligence)
3. [1build Construction Cost API](https://www.1build.com/)
4. [Is Web Scraping Legal in 2025?](https://www.browserless.io/blog/is-web-scraping-legal)
5. [Ethical Price Scraping: Best Practices](https://www.promptcloud.com/blog/ensuring-ethical-price-scraping-best-practices-and-guidelines/)
6. [Understanding The Legality: Is Price Scraping Legal?](https://prowebscraper.com/blog/is-price-scraping-legal/)

---

**Document Status:** DRAFT for Review
**Author:** Claude Code (ULTRATHINK Process)
**Review Requested From:** User/Stakeholders
