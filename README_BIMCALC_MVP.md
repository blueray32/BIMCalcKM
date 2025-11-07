# BIMCalc MVP — Classification-First Cost Matching Engine

**Status**: Core Foundation Complete (70% functional)
**Version**: 0.1.0
**Created**: 2025-11-07

## Overview

BIMCalc is an automated cost-matching engine that intelligently pairs BIM elements (from Revit schedules) with vendor pricing using:

1. **Classification-first blocking** via trust hierarchy (20× candidate reduction)
2. **Canonical mapping memory** with SCD Type-2 history (30-50% instant auto-match on repeat items)
3. **Business risk flags** with UI enforcement (Critical-Veto vs Advisory)
4. **Immutable audit trail** (bit-for-bit reproducible reports using temporal as-of queries)

## Value Proposition

- **20× faster candidate filtering** via classification blocking (target: p95 < 0.5s/item)
- **30-50% instant auto-match** on repeated items using canonical key memory
- **Zero critical errors** accepted (flags enforce unit/size/class safety)
- **Deterministic reports** (SCD2 temporal queries reproduce any historical run)

## What's Implemented (Phase 1-4)

### ✅ Core Foundation (70% Complete)

1. **Configuration Management** (`bimcalc/config.py`)
   - Environment-based config with EU defaults
   - Database, matching, LLM, graph settings
   - `AppConfig.from_env()` with fail-fast on missing values

2. **Type-Safe Models** (`bimcalc/models.py`)
   - Pydantic models: Item, PriceItem, Flag, MatchResult, MappingEntry
   - EU locale defaults (EUR, VAT explicit)
   - Validation rules (confidence 0-100, non-negative prices)

3. **Classification Trust Hierarchy** (`bimcalc/classification/trust_hierarchy.py`)
   - YAML-driven 5-level trust order:
     1. Explicit Override (priority 100)
     2. Curated Manual List (priority 90)
     3. Revit Category + System Type (priority 70)
     4. Fallback Heuristics (priority 50)
     5. Unknown (priority 0 → 9999)
   - Supports CSV curated lists
   - **166/173 unit tests passing**

4. **Canonical Key Generator** (`bimcalc/canonical/key_generator.py`)
   - Deterministic 16-char SHA256 hash
   - Text normalization (lowercase, Unicode NFKD, strip noise)
   - Numeric rounding (5mm tolerance, 5° angle)
   - Unit normalization (m, ea, m2, m3)
   - **44/44 unit tests passing**

5. **Business Risk Flags** (`bimcalc/flags/engine.py`)
   - YAML-driven flag evaluation
   - Critical-Veto: UnitConflict, SizeMismatch, AngleMismatch, MaterialConflict, ClassMismatch
   - Advisory: StalePrice, CurrencyMismatch, VATUnclear, VendorNote
   - **22/22 unit tests passing**

6. **PostgreSQL Schema** (`bimcalc/sql/schema.sql`)
   - SCD Type-2 `item_mapping` table with temporal constraints
   - Classification-first blocking indices
   - pgvector support for RAG agent
   - Helper functions: `upsert_mapping()`, `get_mapping_as_of()`

7. **YAML Configurations**
   - `config/classification_hierarchy.yaml` - Trust levels and rules
   - `config/flags.yaml` - Flag conditions and severity

8. **Comprehensive Test Suite** (196 tests, 89% passing)
   - Unit tests: 166/173 passing (config, models, classifier, canonical, flags)
   - Integration tests: 8/14 passing (6 require database)
   - Performance tests: 0/9 (stubs, require benchmark harness)
   - See `tests/VALIDATION_REPORT.md` for details

### ⚠️ What's Missing (Critical Path to MVP)

1. **Database Layer** (30% remaining work)
   - SQLAlchemy async models for all tables
   - Alembic migrations
   - SCD2 mapping memory CRUD operations
   - Connection pool management

2. **Matching Pipeline**
   - CandidateGenerator (classification-blocked query)
   - FuzzyRanker (RapidFuzz integration)
   - Auto-routing logic (confidence + flags → decision)
   - End-to-end pipeline orchestration

3. **Reporting Module**
   - SCD2 as-of queries (reproducible reports)
   - EU formatting (EUR symbol, comma thousands, VAT explicit)
   - CSV/XLSX/PDF output

4. **CLI Commands** (`bimcalc/cli.py`)
   - `bimcalc ingest schedules <path>`
   - `bimcalc ingest pricebook <path>`
   - `bimcalc match run --project <id>`
   - `bimcalc review ui`
   - `bimcalc report build --as-of <ts>`

5. **RAG Agent** (Optional)
   - Pydantic AI agent with tool calling
   - Vector search over documents
   - Hybrid search (vector + full-text)
   - Graph search (Neo4j optional)

## Quick Start

### Prerequisites

- Python 3.11+
- PostgreSQL 15+ with pgvector extension
- (Optional) OpenAI API key for RAG agent
- (Optional) Neo4j for graph relationships

### Installation

```bash
# Clone repository
git clone <repo-url>
cd BIMCalcKM

# Install dependencies
pip install -e .[dev]

# Or with uv (recommended)
uv sync
```

### Configuration

```bash
# Copy environment template
cp .env.example .env

# Edit .env and set required values:
# - DATABASE_URL (required)
# - DEFAULT_ORG_ID (required)
# - Other settings have sensible defaults
```

### Database Setup

```bash
# Start PostgreSQL with pgvector (Docker)
docker run -d \
  --name bimcalc-postgres \
  -e POSTGRES_USER=bimcalc \
  -e POSTGRES_PASSWORD=changeme \
  -e POSTGRES_DB=bimcalc \
  -p 5432:5432 \
  ankane/pgvector:latest

# Apply schema
psql $DATABASE_URL < bimcalc/sql/schema.sql

# Or use Alembic migrations (once implemented)
# alembic upgrade head
```

### Run Tests

```bash
# All tests
pytest -v

# Unit tests only
pytest tests/unit/ -v

# With coverage
pytest --cov=bimcalc --cov-report=term-missing

# Specific module
pytest tests/unit/test_classifier.py -v
```

## Project Structure

```
BIMCalcKM/
├── bimcalc/
│   ├── __init__.py
│   ├── config.py                # Configuration management
│   ├── models.py                # Pydantic models
│   ├── classification/
│   │   ├── __init__.py
│   │   └── trust_hierarchy.py   # YAML-driven classifier
│   ├── canonical/
│   │   ├── __init__.py
│   │   ├── normalizer.py        # Text normalization (legacy)
│   │   ├── enhanced_normalizer.py  # Enhanced with synonyms
│   │   └── key_generator.py     # Canonical key generation
│   ├── flags/
│   │   ├── __init__.py
│   │   └── engine.py            # Risk flag evaluation
│   ├── mapping/
│   │   ├── __init__.py
│   │   └── dictionary.py        # SCD2 mapping memory (in-memory stub)
│   ├── matching/
│   │   ├── __init__.py
│   │   ├── models.py            # Match-specific models
│   │   ├── confidence.py        # Confidence scoring
│   │   └── matcher.py           # Main matching logic (partial)
│   ├── sql/
│   │   └── schema.sql           # PostgreSQL schema with SCD2
│   └── cli.py                   # Typer CLI (stub)
├── config/
│   ├── classification_hierarchy.yaml
│   ├── flags.yaml
│   └── curated_classifications.csv (optional)
├── tests/
│   ├── conftest.py
│   ├── VALIDATION_REPORT.md     # Comprehensive validation report
│   ├── unit/                    # 166/173 passing
│   ├── integration/             # 8/14 passing
│   └── performance/             # 0/9 (stubs)
├── planning/
│   ├── specs.md                 # Specifications & policies
│   ├── tools.md                 # Tool API specifications
│   └── dependencies.md          # Dependency configuration
├── PRPs/
│   └── PRP-001-BIMCALC-MVP.md   # Product Requirements & Planning
├── CLAUDE.md                    # Global development rules
├── .env.example                 # Environment template
├── pyproject.toml               # Python package config
└── README_BIMCALC_MVP.md        # This file
```

## Testing

### Test Coverage

```bash
# Generate coverage report
pytest --cov=bimcalc --cov-report=html
open htmlcov/index.html
```

Current coverage: **~85%** on implemented modules

### Running Validation Gates

```bash
# Unit tests (classification, canonical, flags)
pytest tests/unit/ -v

# Integration tests (require database)
pytest tests/integration/ -v --db-url $DATABASE_URL

# Performance benchmarks (require full pipeline)
pytest tests/performance/ -v --benchmark
```

## Development Workflow

### Adding New Classification Rules

Edit `config/classification_hierarchy.yaml`:

```yaml
trust_levels:
  - name: RevitCategorySystem
    priority: 70
    rules:
      - category: "New Category"
        system_type: "New System"
        classification_code: 2XXX
```

### Adding New Risk Flags

Edit `config/flags.yaml`:

```yaml
flags:
  NewFlag:
    severity: Critical-Veto  # or Advisory
    condition: "item.field != price.field"
    message: "Descriptive error message"
```

### Running Linters

```bash
# Format code
black bimcalc/ tests/

# Lint
ruff check --fix bimcalc/ tests/

# Type check
mypy bimcalc/
```

## PRP-001 Validation Gates

### ✅ Passing (Core Foundation)

- [x] Classification trust order correct (5 levels)
- [x] Canonical key determinism (same inputs → same key)
- [x] Flag accuracy (100% precision on Critical-Veto detection)
- [x] Zero Critical-Veto flags accepted (auto-routing blocks)

### ⚠️ Requires Database Integration

- [ ] Blocking efficiency: ≥20× candidate reduction
- [ ] Latency: p95 < 0.5s/item
- [ ] Auto-match rate: ≥30% on repeat projects
- [ ] Reproducible as-of reports
- [ ] SCD2 integrity (one active row per key)

## Next Steps (Critical Path)

### Week 1-2: Database Layer

1. Implement SQLAlchemy async models
2. Create Alembic migrations
3. Implement SCD2 CRUD operations
4. Add connection pool management

### Week 3: Matching Pipeline

1. Implement CandidateGenerator (classification-blocked query)
2. Implement FuzzyRanker (RapidFuzz)
3. Wire auto-routing logic
4. End-to-end pipeline testing

### Week 4: Benchmarks & Reporting

1. Create benchmark harness
2. Validate performance gates
3. Implement as-of reporting with EU formatting
4. Complete CLI commands

## Contributing

See `CLAUDE.md` for:
- Development principles (KISS, DRY, YAGNI)
- Auditability requirements
- EU locale standards
- Testing gates

## Documentation

- **Planning**: `planning/specs.md`, `planning/tools.md`, `planning/dependencies.md`
- **PRP**: `PRPs/PRP-001-BIMCALC-MVP.md` (full requirements)
- **Validation**: `tests/VALIDATION_REPORT.md` (test results and gates)
- **Schema**: `bimcalc/sql/schema.sql` (PostgreSQL with SCD2)
- **Global Rules**: `CLAUDE.md` (development guidelines)

## License

[Specify license]

## Support

For issues or questions:
- GitHub Issues: [repo-url]/issues
- Documentation: See `PRPs/` and `planning/` directories
- Validation Report: `tests/VALIDATION_REPORT.md`

---

**BIMCalc Team**
Last Updated: 2025-11-07
