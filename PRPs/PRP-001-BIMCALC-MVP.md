# PRP-001: BIMCalc MVP — Classification-First Cost Matching Engine with Mapping Memory

**Status**: Draft
**Created**: 2025-11-07
**Owner**: BIMCalc Team
**Type**: Product Requirements & Planning

---

## Goal

Deliver a production-ready **BIMCalc MVP**: an automated cost-matching engine that intelligently pairs BIM elements (from Revit schedules) with vendor pricing using:

1. **Classification-first blocking** via trust hierarchy (reduces candidate space by ≥20×)
2. **Canonical mapping memory** with SCD Type-2 history (enables instant auto-match on repeated items)
3. **Business risk flags** with UI enforcement (Critical-Veto vs Advisory)
4. **Immutable audit trail** (bit-for-bit reproducible reports using temporal as-of queries)
5. **Lightweight RAG/Graph QA agent** (query docs, price books, mappings using Pydantic AI)

---

## Why

### Current Pain Points
- **Manual matching is slow**: Cost engineers spend hours matching thousands of BIM items to vendor catalogs
- **Classification chaos**: Without structured classification, fuzzy matching runs against entire 5000+ item price books (O(N×M) explosion)
- **No learning curve**: Same items re-matched project after project
- **Hidden risks**: Unit mismatches, size conflicts, and stale prices slip through → costly overruns
- **No audit trail**: Can't reproduce "how did we price this 6 months ago?"

### Value Proposition
BIMCalc delivers:
- **20× faster candidate filtering** via classification blocking (benchmarked: p95 < 0.5s/item)
- **30-50% instant auto-match** on repeated items using canonical key memory
- **Zero critical errors** accepted (flags enforce unit/size/class safety)
- **Deterministic reports** (SCD2 temporal queries reproduce any historical run)
- **AI-assisted Q&A** (RAG + graph search for "why was this matched?" and "what changed?")

---

## Scope (MVP)

### In Scope

#### Core Matching Engine
- **Trust Hierarchy Classifier**: Assign `classification_code` via configurable YAML trust order:
  1. Omniclass/Uniformat override fields
  2. Curated manual classification lists
  3. Revit Category + System Type heuristics
  4. Fallback to "Unknown" (requires manual review)
- **Canonical Key Generator**: Normalize items to deterministic composite key:
  - `{classification_code, family_slug, type_slug, width, height, dn, angle, material, unit}`
  - Slug generation: lowercase, strip special chars, handle EU/US unit variants
- **Mapping Memory (SCD Type-2)**:
  - O(1) lookup: `canonical_key → active price_item_id`
  - Immutable history: `org_id, canonical_key, price_item_id, start_ts, end_ts, created_by, reason`
  - At-most-one active row per `(org_id, canonical_key)` via transactional writes
- **Class-Blocked Candidate Generator**: Pre-filter price items by `classification_code` (indexed)
- **Fuzzy Ranking**: RapidFuzz within class + numeric pre-filters (width/height/DN tolerance)
- **Business Risk Flags**:
  - **Critical-Veto** (block auto-accept): Unit Conflict, Size Mismatch, Angle Mismatch, Material Conflict, Class Mismatch
  - **Advisory** (warn but allow): Stale Price (>1 year), Currency/VAT inconsistency
- **Auto-Routing Logic**: Accept only if confidence=High AND zero flags
- **Report Generator**: Deterministic CSV/XLSX/PDF using SCD2 `as-of` join for `run_ts`

#### RAG/Graph Agent (Pydantic AI)
- **Vector Search** (`pgvector`): Semantic search over ingested docs (price books, ADRs, mappings)
- **Hybrid Search**: Combine vector + PostgreSQL full-text (TSVector) with tunable weights
- **Graph Search** (Graphiti/Neo4j): Entity relationships and temporal timelines
- **Agent Tools**:
  - `perform_comprehensive_search(query, use_vector=True, use_graph=True, limit=10)`
  - `get_document(document_id)`, `list_documents(filters)`
  - `get_entity_relationships(entity_name, depth=2)`
  - `get_entity_timeline(entity, start_date, end_date)`

#### CLI (Typer)
```bash
# Data ingestion
bimcalc ingest schedules <path>      # Load Revit CSV/XLSX
bimcalc ingest pricebook <path>      # Load vendor list (requires classification_code)

# Matching pipeline
bimcalc match run --project <id>     # Execute classification → fuzzy → flags → SCD2 write
bimcalc review ui                    # Launch web/TUI review interface with flag filters

# Reporting
bimcalc report build --project <id> [--as-of <ts>]  # Generate deterministic report

# Agent
bimcalc agent chat                   # Interactive RAG/Graph chat
bimcalc agent search "<query>"       # One-shot search
bimcalc agent doc <id>               # Fetch specific document

# Global flags
--model <name>                       # Override LLM model
--verbose                            # Debug logging
--dry-run                            # Preview without DB writes
--limit <n>                          # Process first N items (testing)
```

#### Database Schema
**PostgreSQL (with pgvector extension)**
```sql
-- Core tables
CREATE TABLE items (
  id UUID PRIMARY KEY,
  org_id TEXT NOT NULL,
  project_id TEXT NOT NULL,
  classification_code INT,           -- From trust hierarchy
  canonical_key TEXT NOT NULL,       -- Deterministic composite key
  category TEXT,
  family TEXT,
  type_name TEXT,
  quantity REAL,
  unit TEXT,
  width_mm REAL,
  height_mm REAL,
  dn_mm REAL,
  angle_deg REAL,
  material TEXT,
  source_file TEXT,
  created_at TIMESTAMP DEFAULT NOW()
);
CREATE INDEX idx_items_canonical ON items(canonical_key);
CREATE INDEX idx_items_class ON items(classification_code);

CREATE TABLE price_items (
  id UUID PRIMARY KEY,
  classification_code INT NOT NULL,  -- Required for blocking
  vendor_id TEXT,
  sku TEXT,
  description TEXT,
  unit TEXT,
  unit_price NUMERIC(12,2),
  currency TEXT DEFAULT 'EUR',
  vat_rate NUMERIC(5,2),
  last_updated DATE,
  attributes JSONB                   -- width, height, material, etc.
);
CREATE INDEX idx_price_class ON price_items(classification_code);

-- SCD Type-2 mapping memory
CREATE TABLE item_mapping (
  id UUID PRIMARY KEY,
  org_id TEXT NOT NULL,
  canonical_key TEXT NOT NULL,
  price_item_id UUID REFERENCES price_items(id),
  start_ts TIMESTAMP NOT NULL DEFAULT NOW(),
  end_ts TIMESTAMP,                  -- NULL = active
  created_by TEXT,
  reason TEXT,
  UNIQUE(org_id, canonical_key, start_ts),
  CHECK (end_ts IS NULL OR end_ts > start_ts)
);
CREATE UNIQUE INDEX idx_mapping_active
  ON item_mapping(org_id, canonical_key)
  WHERE end_ts IS NULL;              -- At most one active row

-- Flags & audit
CREATE TABLE match_flags (
  id UUID PRIMARY KEY,
  item_id UUID REFERENCES items(id),
  flag_type TEXT NOT NULL,           -- 'UnitConflict', 'SizeMismatch', etc.
  severity TEXT CHECK (severity IN ('Critical-Veto', 'Advisory')),
  message TEXT,
  created_at TIMESTAMP DEFAULT NOW()
);

-- RAG documents (pgvector)
CREATE TABLE documents (
  id UUID PRIMARY KEY,
  title TEXT,
  content TEXT,
  embedding VECTOR(1536),           -- OpenAI text-embedding-3-large
  metadata JSONB,
  created_at TIMESTAMP DEFAULT NOW()
);
CREATE INDEX idx_documents_embedding ON documents USING ivfflat (embedding vector_cosine_ops);
```

**Neo4j/Graphiti (optional, for graph relationships)**
```cypher
// Entities: PriceItem, Vendor, Material, Classification
// Relationships: REPLACES, EQUIVALENT_TO, MANUFACTURED_BY, BELONGS_TO_CLASS
```

### Out of Scope (Post-MVP)
- Multi-currency conversion logic (MVP: warn if non-EUR, manual review)
- Real-time Revit plugin integration (MVP: CSV export workflow)
- Advanced BI dashboards (MVP: static reports)
- Machine learning confidence models (MVP: rule-based flags)
- Batch approval API (MVP: one-by-one review)
- Mobile review UI (MVP: desktop web/TUI)

---

## Data Model

### Trust Hierarchy Configuration (`config/classification_hierarchy.yaml`)
```yaml
# Ordered from highest to lowest trust
trust_levels:
  - name: ExplicitOverride
    priority: 100
    fields: [omniclass_code, uniformat_code]

  - name: CuratedList
    priority: 90
    source: config/curated_classifications.csv
    match_on: [family, type_name]

  - name: RevitCategorySystem
    priority: 70
    rules:
      - category: "Mechanical Equipment"
        system_type: "HVAC"
        classification_code: 2301  # HVAC equipment
      - category: "Pipes"
        system_type: "Domestic Hot Water"
        classification_code: 2211

  - name: FallbackHeuristics
    priority: 50
    rules:
      - family_contains: ["duct", "diffuser"]
        classification_code: 2302
      - family_contains: ["valve", "fitting"]
        classification_code: 2215

  - name: Unknown
    priority: 0
    classification_code: 9999
    requires_manual_review: true
```

### Canonical Key Normalization Rules
```python
# Pseudocode for canonical_key generation
def canonical_key(item: Item) -> str:
    parts = [
        str(item.classification_code),
        slug(item.family),              # lowercase, strip "-_/", normalize spaces
        slug(item.type_name),
        normalize_unit(item.unit),      # "m" / "ea" / "m2" / "m3"
        round_mm(item.width_mm, 5),     # Round to nearest 5mm (tolerance)
        round_mm(item.height_mm, 5),
        round_mm(item.dn_mm, 5),        # Pipe diameter
        round_deg(item.angle_deg, 5),   # Elbow angle
        slug(item.material)             # "steel" / "copper" / "pvc"
    ]
    # Omit None values
    key = "/".join(str(p) for p in parts if p is not None)
    return sha256(key).hexdigest()[:16]  # 16-char deterministic hash
```

### Business Risk Flags Logic
```yaml
flags:
  UnitConflict:
    severity: Critical-Veto
    condition: item.unit != price.unit
    message: "Item unit '{item.unit}' does not match price unit '{price.unit}'"

  SizeMismatch:
    severity: Critical-Veto
    condition: |
      (item.width_mm and price.width_mm and abs(item.width_mm - price.width_mm) > 10) OR
      (item.height_mm and price.height_mm and abs(item.height_mm - price.height_mm) > 10)
    message: "Item dimensions differ by >10mm"

  AngleMismatch:
    severity: Critical-Veto
    condition: abs(item.angle_deg - price.angle_deg) > 5
    message: "Angle differs by >5°"

  MaterialConflict:
    severity: Critical-Veto
    condition: item.material and price.material and item.material != price.material
    message: "Material mismatch: {item.material} vs {price.material}"

  ClassMismatch:
    severity: Critical-Veto
    condition: item.classification_code != price.classification_code
    message: "Classification codes differ"

  StalePrice:
    severity: Advisory
    condition: price.last_updated < today() - 365 days
    message: "Price is over 1 year old"

  CurrencyMismatch:
    severity: Advisory
    condition: price.currency != 'EUR'
    message: "Non-EUR pricing requires manual conversion"
```

---

## Architecture

### Module Boundaries
```
bimcalc/
├── classification/
│   ├── trust_hierarchy.py       # YAML-driven classifier
│   └── backfill.py              # Bulk re-classify items
├── canonical/
│   ├── normalizer.py            # Slug, unit conversion, rounding
│   └── key_generator.py         # canonical_key(item) -> str
├── mapping/
│   ├── memory.py                # SCD2 CRUD (lookup, write, as-of query)
│   └── dictionary.py            # In-memory cache for hot keys
├── matching/
│   ├── candidate_generator.py  # Class-blocked filter
│   ├── fuzzy_ranker.py          # RapidFuzz + numeric pre-filter
│   └── auto_router.py           # confidence + flags → accept/review
├── flags/
│   ├── engine.py                # YAML-driven flag evaluation
│   └── models.py                # Flag, FlagResult Pydantic models
├── ingestion/
│   ├── schedules.py             # Parse Revit CSV/XLSX
│   └── pricebook.py             # Validate vendor data
├── reporting/
│   ├── builder.py               # SCD2 as-of join logic
│   └── formatters.py            # CSV/XLSX/PDF output (EU locale)
├── agent/                       # Pydantic AI RAG/Graph QA
│   ├── rag_pipeline/            # Copied from examples/rag_pipeline
│   │   ├── sql/schema.sql       # pgvector + hybrid search functions
│   │   ├── ingest.py
│   │   └── search.py
│   ├── tools.py                 # Agent tool definitions
│   ├── prompts.py               # System prompts
│   └── main.py                  # Pydantic Agent CLI
├── cli.py                       # Typer CLI entrypoint
└── config/                      # YAML configs
```

### Dependencies
```toml
# pyproject.toml additions
dependencies = [
    "pydantic>=2.8",
    "pydantic-ai>=0.0.15",       # Pydantic AI framework
    "pandas>=2.2",
    "typer>=0.12",
    "rapidfuzz>=3.9",
    "rich>=13.7",
    "PyYAML>=6.0",
    "asyncpg>=0.29",             # PostgreSQL async driver
    "pgvector>=0.3.0",           # pgvector extension support
    "neo4j>=5.20",               # Optional: Neo4j for graph
    "openai>=1.40",              # Embeddings + LLM
    "httpx>=0.27",               # Async HTTP for APIs
]
```

### Environment Configuration (`.env.example`)
```bash
# Database
DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/bimcalc
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=changeme

# Embeddings & LLM
OPENAI_API_KEY=sk-...
EMBEDDINGS_MODEL=text-embedding-3-large
LLM_MODEL=gpt-4-1106-preview

# Archon MCP (optional for RAG research)
ARCHON_SERVER=http://localhost:7007

# BIMCalc Settings
EU_LOCALE=1                      # EUR currency, metric, VAT explicit
DEFAULT_ORG_ID=acme-construction
LOG_LEVEL=INFO

# Matching Thresholds
FUZZY_MIN_SCORE=70               # RapidFuzz cutoff
AUTO_ACCEPT_MIN_CONFIDENCE=85    # High confidence threshold
SIZE_TOLERANCE_MM=10             # Dimension matching tolerance
ANGLE_TOLERANCE_DEG=5
```

---

## Acceptance Criteria

### Performance
- [ ] **Blocking efficiency**: Classification blocking reduces candidates by ≥20× vs unfiltered fuzzy
- [ ] **Latency**: p95 < 0.5s per item on benchmark (N=500 items × M=5000 prices)
- [ ] **Auto-match rate**: ≥30% instant matches on second project with repeated items

### Safety
- [ ] **Zero critical errors**: 0 accepted matches with Critical-Veto flags active
- [ ] **Flag accuracy**: Unit/Size/Class mismatches detected at 100% precision (no false negatives)

### Auditability
- [ ] **Reproducibility**: Reports generated with `--as-of <timestamp>` are bit-for-bit identical for same timestamp
- [ ] **SCD2 integrity**: At most one active row per `(org_id, canonical_key)` enforced by unique constraint
- [ ] **Audit trail**: Every mapping change logs `created_by`, `reason`, `start_ts`

### Usability
- [ ] **Review UI**: Supports filtering by flag type (Unit Conflict, Size Mismatch, Stale Price, etc.)
- [ ] **Accept button disabled**: When Critical-Veto flags present, "Accept" is greyed out
- [ ] **Learning curve demo**: Two-pass test shows Project A approval → Project B instant auto-match (same canonical key)

### Agent Q&A
- [ ] **Documentation search**: `agent search "SCD2 mapping logic"` returns relevant ADR excerpts with citations
- [ ] **Relationship queries**: `agent search "what replaced this price item?"` uses graph search
- [ ] **Historical queries**: `agent search "why was this matched to SKU X in June?"` uses SCD2 temporal data

---

## Implementation Roadmap (4 Weeks)

### Week 1: Schema + Classification + Canonicalization
**Tasks**:
1. Add `classification_code`, `canonical_key` columns to `items` and `price_items` tables
2. Create `item_mapping` SCD2 table with indices (see schema above)
3. Implement `TrustHierarchyClassifier` (read YAML, apply rules in priority order)
4. Backfill `classification_code` for existing price book (CSV with manual classifications)
5. Implement `canonical_key` generation (slug, unit normalization, rounding, hashing)
6. Unit tests: classifier trust order, canonical key determinism, EU/US unit variants

**Deliverable**: All items and prices have valid `classification_code`; items generate stable `canonical_key`

---

### Week 2: Matching Pipeline + Flags + Mapping Memory
**Tasks**:
7. Implement `CandidateGenerator` (class-blocked query, indexed by `classification_code`)
8. Implement `FuzzyRanker` (RapidFuzz within class + numeric pre-filters for width/height/DN)
9. Implement `FlagsEngine` (YAML-driven evaluation, Critical-Veto vs Advisory)
10. Implement `MappingMemory` API:
    - `lookup(org_id, canonical_key) -> Optional[price_item_id]` (active row only)
    - `write(org_id, canonical_key, price_item_id, created_by, reason)` (close old, insert new)
    - `as_of_query(org_id, run_ts) -> List[Mapping]` (temporal join for reports)
11. Implement `AutoRouter` (accept if High confidence AND zero flags)
12. Integration test: Two-pass demo (Project A manual approve → Project B auto-match via canonical key)

**Deliverable**: End-to-end matching pipeline functional; two-pass demo proves learning

---

### Week 3: Agent + RAG/Graph + CLI
**Tasks**:
13. Copy `examples/rag_pipeline/` to `bimcalc/agent/rag_pipeline/` (preserve structure)
14. Review `rag_pipeline/sql/schema.sql` and apply to database (pgvector functions)
15. Ingest BIMCalc docs (ADRs, INITIAL.md, ROADMAP.md) into `documents` table with embeddings
16. Implement Pydantic AI agent tools:
    - `vector_search(query, limit=10)`
    - `hybrid_search(query, limit=10, text_weight=0.3)`
    - `graph_search(query)` (if Neo4j available)
    - `perform_comprehensive_search(query, use_vector=True, use_graph=True)`
    - `get_document(document_id)`, `list_documents(filters)`
17. Wire agent system prompt: "You are BIMCalc assistant. For costing questions, run matching pipeline. For docs/architecture questions, use hybrid_search. Cite sources."
18. Implement CLI subcommands (`bimcalc match`, `bimcalc agent`, `bimcalc report`)
19. Unit tests: Agent tool calls, prompt injection safety, citation formatting

**Deliverable**: CLI functional; agent answers "why was this matched?" using RAG + SCD2 data

---

### Week 4: Review UI + Reporting + Benchmarks + Docs
**Tasks**:
20. Implement review UI (web or TUI):
    - Table with columns: Item, Matched Price, Confidence, Flags, Actions
    - Filter chips: Unit Conflict, Size Mismatch, Angle, Material, Stale Price, Currency/VAT
    - "Accept" button disabled when Critical-Veto flags present
21. Implement `ReportBuilder`:
    - SCD2 as-of join: `SELECT ... FROM items JOIN item_mapping ON ... WHERE start_ts <= run_ts AND (end_ts IS NULL OR end_ts > run_ts)`
    - EU formatting: EUR symbol, comma thousands separator, period decimal, VAT explicit
    - Output formats: CSV, XLSX (openpyxl), PDF (reportlab)
22. Benchmark harness:
    - Generate synthetic dataset (N=500 items × M=5000 prices)
    - Measure p50/p95 latency per item
    - Measure candidate reduction (class blocking vs unfiltered)
    - Track auto-match rate, flag distribution
23. Documentation:
    - README: Quickstart, architecture diagram, CLI examples
    - ROADMAP.md: Mirror canvas roadmap into repo
    - ADR-0001: Link to full ADR (or inline if short)
    - `.env.example`: Annotated environment variables
    - Makefile: `make install`, `make test`, `make benchmark`, `make ingest-docs`

**Deliverable**: MVP complete; documented; benchmarked; ready for pilot project

---

## PIV Loop (Plan → Implement → Validate)

### Plan (This PRP)
- Define goals, scope, data model, architecture, acceptance criteria
- Identify dependencies, risks, open questions
- Break down into weekly milestones with clear deliverables

### Implement (Weeks 1-4)
- Follow modular architecture: one feature per module
- TDD: Write tests first for classifier, canonicalizer, flags
- Incremental: Each week ends with a working vertical slice
- Code review: Enforce Ruff + Black + Mypy; no PRs without tests

### Validate (Continuous)
- **Unit tests**: Every public function (coverage ≥80%)
- **Integration tests**: Two-pass demo, as-of reporting, agent Q&A
- **Benchmark tests**: Performance regressions caught in CI
- **Pilot project**: Run against real Revit schedules + vendor price book (100-500 items)

### Iterate (Post-MVP)
- Collect feedback: Which flags are most useful? False positive rate?
- Tune thresholds: Fuzzy score cutoff, size tolerance, confidence bands
- Add features: Batch approval API, advanced BI, Revit plugin

---

## Success Metrics

### Quantitative
- **Time savings**: Cost engineers reduce matching time from 8 hours → 1 hour per project (87.5% reduction)
- **Auto-match rate**: ≥30% items auto-matched on repeat projects (no manual review)
- **Flag precision**: 100% Critical-Veto flags are genuine errors (zero false positives)
- **Report accuracy**: €/m calculations match manual audits to 2 decimal places

### Qualitative
- **Confidence**: Engineers trust auto-matches (no "black box" fear due to flags + audit trail)
- **Transparency**: Product owner can answer "why did this match?" using agent + SCD2 history
- **Maintainability**: New classification rules added via YAML (no code changes)

---

## Open Questions

### Classification
- **Q**: Should we support multiple classification schemes (Omniclass + Uniformat simultaneously)?
- **A** (MVP): Pick one primary (e.g., Uniformat); store secondary in `metadata` JSONB

- **Q**: How do we handle "Unknown" classification in review UI?
- **A**: Flag as high-priority review; crowdsource corrections to curated list

### Mapping Memory
- **Q**: Should global (org-wide) mappings be shared across projects, or project-scoped?
- **A** (MVP): Org-wide by default (`org_id` scope); future: add `project_id` override option

- **Q**: Who can write mappings? (Auth concern)
- **A** (MVP): No auth; log `created_by` for audit; post-MVP: RBAC (engineer vs admin)

### Flags
- **Q**: Should Advisory flags still require manual review, or allow auto-accept with warning?
- **A** (MVP): Allow auto-accept but log; post-MVP: make configurable per flag type

### Agent
- **Q**: Should agent have write access to approve matches, or read-only Q&A?
- **A** (MVP): Read-only; write operations via CLI/UI only (safety)

### Reporting
- **Q**: Should reports include rejected/pending items, or only approved?
- **A** (MVP): Include all with status column; filter option in CLI (`--status approved`)

---

## Dependencies & Risks

### Technical Dependencies
| Dependency | Version | Purpose | Risk | Mitigation |
|------------|---------|---------|------|------------|
| PostgreSQL | 15+ | Primary DB + pgvector | Low | Mature, cloud-hosted options (RDS, Supabase) |
| pgvector | 0.5+ | Vector search for RAG | Medium | Fallback to SQLite + in-memory FAISS if unavailable |
| Neo4j/Graphiti | 5.x | Graph relationships | High (optional) | Make graph features optional; vector-only mode works |
| Pydantic AI | 0.0.15+ | Agent framework | Medium (alpha) | Pin version; fallback to raw OpenAI SDK if API changes |
| OpenAI API | GPT-4 | Embeddings + LLM | Low | Use Azure OpenAI or local models (Ollama) as backup |

### Data Quality Risks
| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| Revit schedules missing critical fields (Category, Unit) | High | High | Validate on ingestion; reject incomplete rows; provide column mapping UI |
| Vendor price books lack classification codes | Medium | High | Backfill using classifier; require vendors to adopt standard (Uniformat) |
| Inconsistent material naming ("SS" vs "Stainless Steel") | High | Medium | Expand slug normalization rules; maintain synonym dictionary |
| Historical data has no `created_by` (audit trail gaps) | Medium | Low | Backfill with "system" user; enforce going forward |

### Organizational Risks
| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| Engineers don't trust auto-matches | Medium | High | Transparent flags + audit trail; pilot with champion team first |
| Vendors resist providing structured data | High | Medium | Demonstrate ROI (faster quotes); offer hybrid CSV → classification tool |
| Scope creep (add BI dashboards, mobile app) | High | Medium | Strict MVP scope; maintain post-MVP backlog; defer non-critical features |

---

## Testing Strategy

### Unit Tests (≥80% coverage)
```python
# tests/unit/test_classifier.py
def test_trust_hierarchy_omniclass_overrides_revit():
    item = Item(omniclass_code=2301, category="Mechanical", system_type="HVAC")
    assert classifier.classify(item) == 2301  # Omniclass wins

def test_trust_hierarchy_falls_back_to_heuristics():
    item = Item(family="Supply Air Diffuser")  # No explicit class
    assert classifier.classify(item) == 2302  # Heuristic: diffuser → 2302

# tests/unit/test_canonical.py
def test_canonical_key_deterministic():
    item = Item(family="Pipe Elbow", type_name="90° DN100 Steel")
    key1 = canonical_key(item)
    key2 = canonical_key(item)
    assert key1 == key2

def test_canonical_key_handles_eu_us_unit_variants():
    item_m = Item(width_mm=1000, unit="m")
    item_mm = Item(width_mm=1000, unit="mm")
    # Should normalize to same key (both → mm internally)
    assert canonical_key(item_m) == canonical_key(item_mm)

# tests/unit/test_flags.py
def test_unit_conflict_flag_raised():
    item = Item(unit="m")
    price = PriceItem(unit="ea")
    flags = engine.evaluate(item, price)
    assert any(f.type == "UnitConflict" and f.severity == "Critical-Veto" for f in flags)
```

### Integration Tests
```python
# tests/integration/test_two_pass_demo.py
async def test_two_pass_learning_curve():
    # Project A: Manual match and approve
    item_a = Item(canonical_key="abc123", family="Elbow 90° DN100")
    price = PriceItem(id="price-xyz", sku="ELB-100-90")
    await mapping_memory.write("org1", "abc123", "price-xyz", "engineer@example.com", "manual match")

    # Project B: Same item should auto-match via canonical key
    item_b = Item(canonical_key="abc123", family="Elbow 90° DN100")  # Identical key
    match = await matcher.match(item_b)
    assert match.source == "mapping_memory"  # Not fuzzy!
    assert match.price_item_id == "price-xyz"
    assert match.auto_accepted is True

# tests/integration/test_as_of_reporting.py
async def test_report_reproducibility():
    # Setup: Create mapping at t1, change at t2
    t1 = datetime(2025, 1, 1, 12, 0)
    await mapping_memory.write("org1", "key1", "price-old", "user", "initial", ts=t1)

    t2 = datetime(2025, 2, 1, 12, 0)
    await mapping_memory.write("org1", "key1", "price-new", "user", "updated", ts=t2)

    # Generate reports as-of t1 and t2
    report_t1_first = await reporter.build(as_of=t1)
    report_t2 = await reporter.build(as_of=t2)
    report_t1_second = await reporter.build(as_of=t1)  # Re-run historical report

    # Assert: t1 reports identical, t2 different
    assert report_t1_first == report_t1_second  # Bit-for-bit reproducible
    assert report_t1_first != report_t2         # Different price at t2
```

### Performance Benchmarks
```python
# tests/benchmark/test_matching_performance.py
import pytest

@pytest.mark.benchmark
def test_classification_blocking_performance(benchmark_data):
    items = benchmark_data.items  # N=500
    prices = benchmark_data.prices  # M=5000

    # Without blocking: O(N×M) fuzzy
    unblocked_candidates = [fuzzy_match(item, prices) for item in items]
    assert sum(len(c) for c in unblocked_candidates) > 500 * 5000 * 0.1  # >250k comparisons

    # With blocking: O(N×(M/20))
    blocked_candidates = [candidate_generator.generate(item) for item in items]
    assert sum(len(c) for c in blocked_candidates) < 500 * 300  # <150k comparisons (20× reduction)

    # Latency check
    timings = [time_match(item) for item in items]
    p95 = np.percentile(timings, 95)
    assert p95 < 0.5  # p95 < 500ms
```

---

## Documentation Checklist

- [ ] **README.md**: Quickstart, architecture diagram, CLI usage examples
- [ ] **ROADMAP.md**: Mirror canvas roadmap; update weekly with progress
- [ ] **ADR-0001**: Full ADR or link to canvas doc (classification, SCD2, flags)
- [ ] **docs/classification_guide.md**: How to add new classification rules to YAML
- [ ] **docs/canonical_key_spec.md**: Normalization rules, tolerance values, slug logic
- [ ] **docs/flags_reference.md**: All flag types, severity, conditions, examples
- [ ] **docs/scd2_explained.md**: SCD2 concepts, as-of queries, audit trail usage
- [ ] **docs/agent_usage.md**: Agent commands, example queries, RAG vs graph search
- [ ] **.env.example**: Annotated environment variables with defaults
- [ ] **Makefile**: Common commands (`make install`, `make test`, `make benchmark`, `make ingest-docs`)
- [ ] **CONTRIBUTING.md**: Code standards (Ruff, Black, Mypy), PR checklist, testing requirements

---

## Glossary

| Term | Definition |
|------|------------|
| **Classification Code** | Integer ID from standard taxonomy (e.g., Uniformat, Omniclass) grouping similar items |
| **Canonical Key** | Deterministic composite hash of normalized item attributes (class, family, size, unit, material) |
| **SCD Type-2** | Slowly Changing Dimension Type-2: Temporal database pattern tracking full history with `start_ts`/`end_ts` |
| **Trust Hierarchy** | Ordered list of classification sources (explicit override → curated list → heuristics → unknown) |
| **Critical-Veto Flag** | Business risk flag that **blocks** auto-accept (e.g., Unit Conflict, Size Mismatch) |
| **Advisory Flag** | Warning flag that allows auto-accept but logs concern (e.g., Stale Price, Currency) |
| **Mapping Memory** | SCD2 table storing `canonical_key → price_item_id` mappings with immutable history |
| **As-Of Query** | Temporal SQL query retrieving data valid at specific `run_ts` (enables reproducible reports) |
| **Blocking** | Pre-filtering candidates by classification to reduce search space (e.g., 20× reduction) |
| **RAG** | Retrieval-Augmented Generation: LLM + vector search over documents for Q&A |
| **Slug** | Normalized string (lowercase, stripped special chars) for deterministic comparison |

---

## Appendix A: Example Workflows

### Workflow 1: Initial Project Matching
```bash
# 1. Ingest Revit schedule
bimcalc ingest schedules revit_export_project_a.csv --project project-a

# 2. Ingest vendor price book (with classification codes)
bimcalc ingest pricebook vendor_catalog_2025.csv

# 3. Run matching pipeline
bimcalc match run --project project-a
# Output:
#   - 500 items classified (480 via Revit category, 15 via curated list, 5 unknown)
#   - 0 auto-matches (no mapping memory yet)
#   - 250 High confidence (no flags) → auto-accepted
#   - 200 Medium/High with Advisory flags → review queue
#   - 50 Low confidence or Critical-Veto flags → review queue

# 4. Review and approve matches
bimcalc review ui
# Engineer filters by "Unit Conflict", corrects 10 items, approves rest
# All approvals written to mapping memory (SCD2)

# 5. Generate report
bimcalc report build --project project-a --format xlsx
# Output: project_a_2025_11_07.xlsx (deterministic, reproducible)
```

### Workflow 2: Repeat Project (Learning Curve)
```bash
# Project B uses same families as Project A
bimcalc ingest schedules revit_export_project_b.csv --project project-b
bimcalc match run --project project-b

# Output:
#   - 500 items classified
#   - **150 auto-matches via mapping memory** (30% instant!)
#   - 200 High confidence (no flags) → auto-accepted
#   - 100 Medium/High with Advisory flags → review queue
#   - 50 Low confidence or Critical-Veto flags → review queue

# Total review queue: 150 items (down from 250 in Project A)
# Engineer time: 4 hours (down from 8 hours)
```

### Workflow 3: Historical Audit
```bash
# Q: "What price did we use for Elbow 90° DN100 in June 2024?"
bimcalc agent search "price for elbow 90 DN100 in June 2024"

# Agent workflow:
#   1. Searches mapping memory SCD2 table with as-of query (2024-06-01)
#   2. Finds canonical key → price_item_id mapping active at that date
#   3. Joins to price_items table for SKU and price
#   4. Returns: "SKU ELB-100-90, €45.50, matched by engineer@example.com on 2024-05-15"
```

### Workflow 4: Flag Investigation
```bash
# Q: "Why wasn't this auto-matched?"
bimcalc agent search "why was item X not auto-matched?"

# Agent workflow:
#   1. Searches match_flags table for item X
#   2. Finds Critical-Veto flag: "Unit Conflict: item unit 'm' != price unit 'ea'"
#   3. Returns: "Auto-accept blocked due to Critical-Veto flag. Review required."
```

---

## Appendix B: Example YAML Configs

### `config/classification_hierarchy.yaml`
```yaml
trust_levels:
  - name: ExplicitOverride
    priority: 100
    fields: [omniclass_code, uniformat_code]
    description: "User-provided classification codes override all heuristics"

  - name: CuratedList
    priority: 90
    source: config/curated_classifications.csv
    match_on: [family, type_name]
    description: "Manually curated mappings for common families"

  - name: RevitCategorySystem
    priority: 70
    rules:
      - category: "Mechanical Equipment"
        system_type: "HVAC"
        classification_code: 2301
      - category: "Mechanical Equipment"
        system_type: "Plumbing"
        classification_code: 2211
      - category: "Pipes"
        system_type: "Domestic Hot Water"
        classification_code: 2211
      - category: "Ducts"
        classification_code: 2302
      - category: "Pipe Fittings"
        classification_code: 2215

  - name: FallbackHeuristics
    priority: 50
    rules:
      - family_contains: ["duct", "diffuser", "grille"]
        classification_code: 2302
      - family_contains: ["valve", "fitting", "elbow", "tee"]
        classification_code: 2215
      - family_contains: ["pump", "fan", "boiler"]
        classification_code: 2301

  - name: Unknown
    priority: 0
    classification_code: 9999
    requires_manual_review: true
    description: "Fallback for unclassifiable items"
```

### `config/flags.yaml`
```yaml
flags:
  UnitConflict:
    severity: Critical-Veto
    condition: "item.unit != price.unit"
    message: "Item unit '{item.unit}' does not match price unit '{price.unit}'"

  SizeMismatch:
    severity: Critical-Veto
    condition: |
      (item.width_mm is not None and price.width_mm is not None and
       abs(item.width_mm - price.width_mm) > env.SIZE_TOLERANCE_MM) or
      (item.height_mm is not None and price.height_mm is not None and
       abs(item.height_mm - price.height_mm) > env.SIZE_TOLERANCE_MM)
    message: "Item dimensions differ by more than {env.SIZE_TOLERANCE_MM}mm"

  AngleMismatch:
    severity: Critical-Veto
    condition: |
      item.angle_deg is not None and price.angle_deg is not None and
      abs(item.angle_deg - price.angle_deg) > env.ANGLE_TOLERANCE_DEG
    message: "Angle differs by more than {env.ANGLE_TOLERANCE_DEG}°"

  MaterialConflict:
    severity: Critical-Veto
    condition: |
      item.material is not None and price.material is not None and
      slug(item.material) != slug(price.material)
    message: "Material mismatch: {item.material} vs {price.material}"

  ClassMismatch:
    severity: Critical-Veto
    condition: "item.classification_code != price.classification_code"
    message: "Classification codes differ: {item.classification_code} vs {price.classification_code}"

  StalePrice:
    severity: Advisory
    condition: "price.last_updated < (today() - timedelta(days=365))"
    message: "Price is over 1 year old (last updated: {price.last_updated})"

  CurrencyMismatch:
    severity: Advisory
    condition: "price.currency != 'EUR'"
    message: "Non-EUR pricing ({price.currency}) requires manual conversion"

  VATUnclear:
    severity: Advisory
    condition: "price.vat_rate is None"
    message: "VAT rate not specified in price data"
```

---

## Appendix C: SQL Query Examples

### SCD2 Mapping Memory: As-Of Query
```sql
-- Get mappings valid at 2024-06-01 12:00:00
SELECT
  m.canonical_key,
  m.price_item_id,
  p.sku,
  p.description,
  p.unit_price,
  m.created_by,
  m.reason
FROM item_mapping m
JOIN price_items p ON m.price_item_id = p.id
WHERE m.org_id = 'acme-construction'
  AND m.start_ts <= '2024-06-01 12:00:00'
  AND (m.end_ts IS NULL OR m.end_ts > '2024-06-01 12:00:00');
```

### Vector Search (from `rag_pipeline/sql/schema.sql`)
```sql
-- Semantic search using pgvector
SELECT
  id,
  title,
  content,
  1 - (embedding <=> query_embedding) AS similarity
FROM documents
WHERE 1 - (embedding <=> query_embedding) > 0.7  -- Similarity threshold
ORDER BY embedding <=> query_embedding
LIMIT 10;
```

### Hybrid Search (Vector + Full-Text)
```sql
-- Combined vector + TSVector search
WITH vector_results AS (
  SELECT id, 1 - (embedding <=> query_embedding) AS vector_score
  FROM documents
  ORDER BY embedding <=> query_embedding
  LIMIT 20
),
text_results AS (
  SELECT id, ts_rank(to_tsvector('english', content), query) AS text_score
  FROM documents
  WHERE to_tsvector('english', content) @@ query
  ORDER BY text_score DESC
  LIMIT 20
)
SELECT
  d.id,
  d.title,
  d.content,
  COALESCE(v.vector_score * 0.7, 0) + COALESCE(t.text_score * 0.3, 0) AS combined_score
FROM documents d
LEFT JOIN vector_results v ON d.id = v.id
LEFT JOIN text_results t ON d.id = t.id
WHERE v.id IS NOT NULL OR t.id IS NOT NULL
ORDER BY combined_score DESC
LIMIT 10;
```

---

## Sign-Off

**Ready for Implementation**: ☐ Yes
**Technical Review**: ☐ Approved (Architect)
**Product Review**: ☐ Approved (Product Owner)
**Security Review**: ☐ N/A (MVP, no auth)

**Next Steps**:
1. Create GitHub project board with Week 1-4 milestones
2. Set up CI pipeline (pytest, coverage, Ruff, Black, Mypy)
3. Provision dev environments (PostgreSQL + pgvector, optional Neo4j)
4. Kick off Week 1: Schema + Classification + Canonicalization
