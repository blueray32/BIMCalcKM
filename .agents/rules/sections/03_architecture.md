# Architecture

## System Architecture

### Module Structure

```
bimcalc/
├── classification/    # Trust hierarchy, classification engine
├── canonical/         # Normalization, canonical key generation
├── mapping/          # SCD2 mapping memory, dictionary
├── flags/            # Risk flag engine (Critical-Veto, Advisory)
├── matching/         # Matching pipeline, candidate generation
├── ingestion/        # Data import from schedules, pricebooks
├── pipeline/         # Orchestration, workflow management
├── reporting/        # As-of reporting, export
├── intelligence/     # Compliance, recommendations, insights
├── review/           # UI for manual review
├── web/              # Web application (app_enhanced.py)
├── db/               # Database models, connections
├── config/           # Configuration management
└── cli.py            # Command-line interface
```

### Data Flow

1. **Ingestion** → Raw data from schedules/pricebooks
2. **Classification** → Assign trust level via hierarchy
3. **Canonicalization** → Generate normalized keys
4. **Matching** → Find candidates, rank, flag risks
5. **Review** → Human validation (if needed)
6. **Mapping Memory** → Store decisions as SCD2
7. **Reporting** → As-of queries for historical accuracy

### Key Architectural Patterns

#### 1. Classification-First Blocking
- Use classification to reduce candidate space
- Trust hierarchy determines source precedence
- Unknown classification triggers manual review

#### 2. SCD Type-2 Temporal Tracking
- Every mapping has `effective_date` and `end_date`
- Only one active row per canonical key
- Historical queries use as-of joins

#### 3. Layered Risk Management
- **Critical-Veto**: Blocks automation, requires human decision
- **Advisory**: Warns but allows proceed
- UI enforces flag semantics

#### 4. Separation of Concerns
- **Domain logic**: Classification, matching, flags
- **Data access**: Repositories, ORM models
- **Presentation**: Web UI, CLI, reports
- **Integration**: External API clients

### Database Schema Principles

- **Normalized** where it aids integrity
- **Denormalized** where performance demands (with justification)
- **Indexed** for query patterns, not speculatively
- **Constrained** with foreign keys and check constraints
- **Versioned** via Alembic migrations

### API Design

- **RESTful** where CRUD applies
- **Command-oriented** for workflows (match, ingest, review)
- **Consistent error responses** (structured JSON)
- **Pagination** for lists
- **Filtering** via query parameters

---

**Note**: Reference ADRs in `docs/ADRs/` for specific architectural decisions.
