# BIMCalc Dependencies & Configuration

**Purpose**: Essential environment configuration for BIMCalc MVP (PRP-001)
**Created**: 2025-11-07
**Status**: Ready for Implementation

---

## 1. Environment Variables

### Database Configuration
```bash
# PostgreSQL with async support
DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/bimcalc

# Neo4j (optional, for graph relationships)
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=changeme
```

### Embeddings & LLM (Optional for RAG Agent)
```bash
# OpenAI API
OPENAI_API_KEY=sk-...
EMBEDDINGS_MODEL=text-embedding-3-large
LLM_MODEL=gpt-4-1106-preview

# Alternative: Azure OpenAI
AZURE_OPENAI_ENDPOINT=https://your-instance.openai.azure.com/
AZURE_OPENAI_API_KEY=...
AZURE_OPENAI_API_VERSION=2024-02-15-preview
```

### Archon Integration (Optional)
```bash
# For project/task tracking via MCP
ARCHON_SERVER=http://localhost:7007
ARCHON_TOKEN=...
```

### BIMCalc Settings
```bash
# Locale & Currency (EU defaults)
EU_LOCALE=1                      # EUR currency, metric units, VAT explicit
DEFAULT_CURRENCY=EUR
VAT_INCLUDED=true
VAT_RATE=0.23                    # 23% Irish/EU standard rate

# Multi-tenancy
DEFAULT_ORG_ID=acme-construction

# Logging
LOG_LEVEL=INFO                   # DEBUG, INFO, WARNING, ERROR
LOG_FORMAT=json                  # json or text
```

### Matching Thresholds
```bash
# Classification & Fuzzy Matching
FUZZY_MIN_SCORE=70               # RapidFuzz cutoff (0-100)
AUTO_ACCEPT_MIN_CONFIDENCE=85    # High confidence threshold

# Physical Tolerances
SIZE_TOLERANCE_MM=10             # Width/Height tolerance
ANGLE_TOLERANCE_DEG=5            # Elbow/fitting angle tolerance
DN_TOLERANCE_MM=5                # Pipe diameter tolerance

# Candidate Generation
MAX_CANDIDATES_PER_ITEM=50       # Limit fuzzy search results
CLASS_BLOCKING_ENABLED=true      # Classification-first filtering
```

### Performance Tuning
```bash
# Database Connection Pooling
DB_POOL_SIZE=10
DB_POOL_MAX_OVERFLOW=20
DB_POOL_TIMEOUT=30

# Vector Search
VECTOR_INDEX_TYPE=ivfflat        # ivfflat or hnsw
VECTOR_LISTS=100                 # ivfflat lists (tune for dataset size)

# Batch Processing
BATCH_SIZE=100                   # Items per batch in ingestion/matching
MAX_WORKERS=4                    # Parallel workers for batch ops
```

---

## 2. Python Dependencies

### pyproject.toml
```toml
[project]
name = "bimcalc"
version = "0.1.0"
description = "Classification-first BIM cost matching engine with mapping memory"
requires-python = ">=3.11"

dependencies = [
    # Core Framework
    "pydantic>=2.8",
    "pydantic-ai>=0.0.15",        # Pydantic AI framework for RAG agent

    # Data Processing
    "pandas>=2.2",
    "openpyxl>=3.1",              # Excel read/write
    "PyYAML>=6.0",                # YAML config parsing

    # CLI & UI
    "typer>=0.12",                # CLI framework
    "rich>=13.7",                 # Terminal formatting
    "textual>=0.50",              # Optional: TUI for review interface

    # Matching & Search
    "rapidfuzz>=3.9",             # Fast fuzzy string matching

    # Database
    "asyncpg>=0.29",              # PostgreSQL async driver
    "sqlalchemy[asyncio]>=2.0",   # ORM with async support
    "alembic>=1.13",              # Database migrations
    "pgvector>=0.3.0",            # pgvector extension support

    # Graph Database (Optional)
    "neo4j>=5.20",                # Neo4j driver
    "graphiti-core>=0.3",         # Graphiti temporal graph (if using)

    # LLM & Embeddings
    "openai>=1.40",               # OpenAI API client
    "httpx>=0.27",                # Async HTTP client
    "tiktoken>=0.7",              # Token counting for OpenAI

    # Utilities
    "python-dotenv>=1.0",         # .env file loading
    "structlog>=24.1",            # Structured logging
    "tenacity>=8.2",              # Retry logic
]

[project.optional-dependencies]
dev = [
    # Testing
    "pytest>=8.0",
    "pytest-asyncio>=0.23",
    "pytest-cov>=4.1",
    "pytest-benchmark>=4.0",
    "faker>=24.0",                # Generate test data

    # Linting & Formatting
    "ruff>=0.3",
    "black>=24.0",
    "mypy>=1.9",

    # Type Stubs
    "pandas-stubs>=2.2",
    "types-PyYAML>=6.0",
    "types-openpyxl>=3.1",
]

[project.scripts]
bimcalc = "bimcalc.cli:app"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.ruff]
line-length = 100
target-version = "py311"

[tool.ruff.lint]
select = ["E", "F", "I", "N", "UP", "B", "C4", "SIM"]
ignore = ["E501"]  # Line length handled by black

[tool.black]
line-length = 100
target-version = ["py311"]

[tool.mypy]
python_version = "3.11"
warn_return_any = true
warn_unused_configs = true
disallow_untyped_defs = false  # Start permissive, tighten later

[[tool.mypy.overrides]]
module = ["rapidfuzz.*", "pgvector.*", "graphiti.*"]
ignore_missing_imports = true

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
addopts = "-v --cov=bimcalc --cov-report=term-missing"
```

---

## 3. Database Setup

### PostgreSQL 15+ with pgvector

#### Installation (macOS)
```bash
# Install PostgreSQL 15
brew install postgresql@15

# Install pgvector extension
brew install pgvector

# Start service
brew services start postgresql@15

# Create database
createdb bimcalc

# Enable pgvector extension
psql bimcalc -c "CREATE EXTENSION IF NOT EXISTS vector;"
```

#### Installation (Linux/Docker)
```bash
# Docker Compose (recommended for dev)
docker run -d \
  --name bimcalc-postgres \
  -e POSTGRES_USER=bimcalc \
  -e POSTGRES_PASSWORD=changeme \
  -e POSTGRES_DB=bimcalc \
  -p 5432:5432 \
  ankane/pgvector:latest

# Or via Docker Compose (see docker-compose.yml below)
docker compose up -d postgres
```

#### Schema Initialization
```bash
# Run migrations
alembic upgrade head

# Or apply schema.sql directly
psql bimcalc < bimcalc/sql/schema.sql
```

### Neo4j (Optional, for Graph Relationships)
```bash
# Docker
docker run -d \
  --name bimcalc-neo4j \
  -e NEO4J_AUTH=neo4j/changeme \
  -p 7474:7474 -p 7687:7687 \
  neo4j:5.20-community

# Access browser: http://localhost:7474
```

### Database Indices (Critical for Performance)

```sql
-- Classification blocking (most important!)
CREATE INDEX idx_items_class ON items(classification_code);
CREATE INDEX idx_price_class ON price_items(classification_code);

-- Canonical key lookup (O(1) mapping memory)
CREATE INDEX idx_items_canonical ON items(canonical_key);
CREATE UNIQUE INDEX idx_mapping_active
  ON item_mapping(org_id, canonical_key)
  WHERE end_ts IS NULL;  -- At most one active row

-- Vector search (pgvector)
CREATE INDEX idx_documents_embedding
  ON documents
  USING ivfflat (embedding vector_cosine_ops)
  WITH (lists = 100);  -- Tune for dataset size

-- Full-text search (hybrid)
CREATE INDEX idx_documents_fts
  ON documents
  USING gin(to_tsvector('english', content));

-- Temporal queries (as-of)
CREATE INDEX idx_mapping_temporal
  ON item_mapping(org_id, canonical_key, start_ts, end_ts);

-- Flags filtering
CREATE INDEX idx_flags_item ON match_flags(item_id);
CREATE INDEX idx_flags_severity ON match_flags(severity);
```

---

## 4. Configuration Dataclasses

### Core Configuration Models
```python
# bimcalc/config.py

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Optional


@dataclass
class DBConfig:
    """Database connection configuration."""
    url: str
    pool_size: int = 10
    pool_max_overflow: int = 20
    pool_timeout: int = 30
    echo: bool = False  # SQL logging


@dataclass
class MatchingConfig:
    """Matching algorithm thresholds."""
    fuzzy_min_score: int = 70
    auto_accept_min_confidence: int = 85
    size_tolerance_mm: int = 10
    angle_tolerance_deg: int = 5
    dn_tolerance_mm: int = 5
    max_candidates_per_item: int = 50
    class_blocking_enabled: bool = True


@dataclass
class EUConfig:
    """European locale and currency defaults."""
    currency: str = "EUR"
    vat_included: bool = True
    vat_rate: Decimal = Decimal("0.23")
    decimal_separator: str = ","
    thousands_separator: str = "."
    date_format: str = "%d/%m/%Y"


@dataclass
class LLMConfig:
    """LLM and embeddings configuration."""
    provider: str = "openai"  # openai, azure, ollama
    api_key: Optional[str] = None
    embeddings_model: str = "text-embedding-3-large"
    llm_model: str = "gpt-4-1106-preview"
    temperature: float = 0.1
    max_tokens: int = 4000

    # Azure-specific
    azure_endpoint: Optional[str] = None
    azure_api_version: str = "2024-02-15-preview"


@dataclass
class VectorConfig:
    """Vector search configuration."""
    index_type: str = "ivfflat"  # ivfflat or hnsw
    lists: int = 100  # ivfflat parameter
    similarity_threshold: float = 0.7
    max_results: int = 10


@dataclass
class GraphConfig:
    """Graph database configuration (optional)."""
    enabled: bool = False
    uri: str = "bolt://localhost:7687"
    user: str = "neo4j"
    password: str = "changeme"
    database: str = "neo4j"


@dataclass
class AppConfig:
    """Root application configuration."""
    org_id: str
    log_level: str = "INFO"
    log_format: str = "json"  # json or text

    # Sub-configurations
    db: DBConfig
    matching: MatchingConfig = field(default_factory=MatchingConfig)
    eu: EUConfig = field(default_factory=EUConfig)
    llm: LLMConfig = field(default_factory=LLMConfig)
    vector: VectorConfig = field(default_factory=VectorConfig)
    graph: GraphConfig = field(default_factory=GraphConfig)

    @classmethod
    def from_env(cls) -> "AppConfig":
        """Load configuration from environment variables."""
        import os
        from dotenv import load_dotenv

        load_dotenv()

        return cls(
            org_id=os.getenv("DEFAULT_ORG_ID", "default"),
            log_level=os.getenv("LOG_LEVEL", "INFO"),
            log_format=os.getenv("LOG_FORMAT", "json"),
            db=DBConfig(
                url=os.environ["DATABASE_URL"],  # Required!
                pool_size=int(os.getenv("DB_POOL_SIZE", "10")),
                pool_max_overflow=int(os.getenv("DB_POOL_MAX_OVERFLOW", "20")),
                pool_timeout=int(os.getenv("DB_POOL_TIMEOUT", "30")),
            ),
            matching=MatchingConfig(
                fuzzy_min_score=int(os.getenv("FUZZY_MIN_SCORE", "70")),
                auto_accept_min_confidence=int(os.getenv("AUTO_ACCEPT_MIN_CONFIDENCE", "85")),
                size_tolerance_mm=int(os.getenv("SIZE_TOLERANCE_MM", "10")),
                angle_tolerance_deg=int(os.getenv("ANGLE_TOLERANCE_DEG", "5")),
                dn_tolerance_mm=int(os.getenv("DN_TOLERANCE_MM", "5")),
            ),
            llm=LLMConfig(
                api_key=os.getenv("OPENAI_API_KEY"),
                embeddings_model=os.getenv("EMBEDDINGS_MODEL", "text-embedding-3-large"),
                llm_model=os.getenv("LLM_MODEL", "gpt-4-1106-preview"),
            ),
            graph=GraphConfig(
                enabled=os.getenv("NEO4J_URI") is not None,
                uri=os.getenv("NEO4J_URI", "bolt://localhost:7687"),
                user=os.getenv("NEO4J_USER", "neo4j"),
                password=os.getenv("NEO4J_PASSWORD", "changeme"),
            ),
        )
```

---

## 5. Docker Compose (Development)

### docker-compose.yml
```yaml
version: "3.9"

services:
  postgres:
    image: ankane/pgvector:latest
    container_name: bimcalc-postgres
    environment:
      POSTGRES_USER: bimcalc
      POSTGRES_PASSWORD: changeme
      POSTGRES_DB: bimcalc
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./bimcalc/sql/schema.sql:/docker-entrypoint-initdb.d/01-schema.sql
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U bimcalc"]
      interval: 10s
      timeout: 5s
      retries: 5

  neo4j:
    image: neo4j:5.20-community
    container_name: bimcalc-neo4j
    environment:
      NEO4J_AUTH: neo4j/changeme
    ports:
      - "7474:7474"  # Browser
      - "7687:7687"  # Bolt
    volumes:
      - neo4j_data:/data
    profiles:
      - graph  # Optional: docker compose --profile graph up

  archon:
    image: archon-mcp-server:latest
    container_name: bimcalc-archon
    ports:
      - "7007:7007"
    environment:
      DATABASE_URL: postgresql://archon:changeme@archon-db:5432/archon
    profiles:
      - archon  # Optional

volumes:
  postgres_data:
  neo4j_data:
```

### Usage
```bash
# Start PostgreSQL only (minimum viable)
docker compose up -d postgres

# Start with Neo4j (graph features)
docker compose --profile graph up -d

# Start everything (including Archon MCP)
docker compose --profile archon up -d

# Stop all
docker compose down

# Reset data (DESTRUCTIVE!)
docker compose down -v
```

---

## 6. Initialization Checklist

### Step 1: Environment Setup
- [ ] Copy `.env.example` to `.env` and fill required values
- [ ] Ensure `DATABASE_URL` is valid (test with `psql <url>`)
- [ ] Verify `OPENAI_API_KEY` if using RAG agent
- [ ] Set `DEFAULT_ORG_ID` to your organization

### Step 2: Database Initialization
- [ ] Start PostgreSQL (Docker or local)
- [ ] Enable pgvector extension: `CREATE EXTENSION vector;`
- [ ] Run migrations: `alembic upgrade head`
- [ ] Verify indices: `\di` in psql (should see class/canonical/vector indices)

### Step 3: Python Environment
- [ ] Install uv: `curl -LsSf https://astral.sh/uv/install.sh | sh`
- [ ] Sync dependencies: `uv sync` or `pip install -e .[dev]`
- [ ] Run tests: `pytest -v`
- [ ] Verify CLI: `bimcalc --help`

### Step 4: Configuration Files
- [ ] Review `config/classification_hierarchy.yaml`
- [ ] Review `config/flags.yaml`
- [ ] Add curated classifications: `config/curated_classifications.csv`

### Step 5: Initial Data Ingestion (Optional)
- [ ] Ingest sample price book: `bimcalc ingest pricebook samples/vendor.csv`
- [ ] Ingest docs for RAG: `bimcalc agent ingest-docs ai_docs/`
- [ ] Verify: `bimcalc agent search "test query"`

---

## 7. Dependency Justification

### Core Dependencies

| Package | Purpose | Why Essential |
|---------|---------|---------------|
| **pydantic>=2.8** | Data validation & settings | Type-safe models, validation, serialization |
| **pydantic-ai** | Agent framework | RAG/Graph QA agent, tool calling |
| **pandas>=2.2** | Data processing | Schedule/pricebook ingestion, transformations |
| **typer>=0.12** | CLI framework | User-friendly CLI with help docs |
| **rapidfuzz>=3.9** | Fuzzy matching | Fast string similarity (Levenshtein, Jaro-Winkler) |
| **asyncpg>=0.29** | PostgreSQL driver | High-performance async DB access |
| **pgvector>=0.3.0** | Vector search | Semantic search over documents |

### Optional Dependencies

| Package | Purpose | When to Skip |
|---------|---------|--------------|
| **neo4j>=5.20** | Graph relationships | Skip if no graph features needed |
| **textual>=0.50** | TUI review UI | Skip if web UI or CLI-only |
| **graphiti-core** | Temporal graph | Skip if Neo4j-only sufficient |

---

## 8. Troubleshooting

### Database Connection Issues
```bash
# Test connection
psql $DATABASE_URL -c "SELECT version();"

# Check pgvector installed
psql $DATABASE_URL -c "SELECT * FROM pg_extension WHERE extname='vector';"

# Manually enable
psql $DATABASE_URL -c "CREATE EXTENSION IF NOT EXISTS vector;"
```

### Missing Environment Variables
```python
# Validation on startup (fail fast)
from bimcalc.config import AppConfig

try:
    config = AppConfig.from_env()
except KeyError as e:
    print(f"ERROR: Missing required environment variable: {e}")
    print("Copy .env.example to .env and set all values.")
    exit(1)
```

### Embedding API Failures
```bash
# Test OpenAI connection
python -c "
from openai import OpenAI
client = OpenAI()
response = client.embeddings.create(
    model='text-embedding-3-large',
    input='test'
)
print(f'Embedding dim: {len(response.data[0].embedding)}')
"
```

### Performance Issues
```sql
-- Check if indices exist
SELECT schemaname, tablename, indexname
FROM pg_indexes
WHERE tablename IN ('items', 'price_items', 'item_mapping', 'documents');

-- Rebuild vector index if slow
DROP INDEX idx_documents_embedding;
CREATE INDEX idx_documents_embedding
  ON documents
  USING ivfflat (embedding vector_cosine_ops)
  WITH (lists = 200);  -- Increase lists for larger datasets

-- Vacuum and analyze
VACUUM ANALYZE items;
VACUUM ANALYZE price_items;
VACUUM ANALYZE documents;
```

---

## 9. Security Notes

### Secrets Management
- **Never commit** `.env` files to git (use `.env.example` as template)
- Use **environment variables** for all secrets (no hardcoded keys)
- Rotate `OPENAI_API_KEY` regularly
- Use **read-only** database credentials where possible

### Database Security
```sql
-- Create limited-privilege user for application
CREATE USER bimcalc_app WITH PASSWORD 'strong-password';
GRANT CONNECT ON DATABASE bimcalc TO bimcalc_app;
GRANT USAGE ON SCHEMA public TO bimcalc_app;
GRANT SELECT, INSERT, UPDATE ON ALL TABLES IN SCHEMA public TO bimcalc_app;
GRANT USAGE ON ALL SEQUENCES IN SCHEMA public TO bimcalc_app;

-- Prevent DELETE and DROP (audit trail immutability)
REVOKE DELETE ON item_mapping FROM bimcalc_app;
```

### LLM Prompt Injection Protection
```python
# Sanitize user queries before RAG agent
import re

def sanitize_query(query: str) -> str:
    """Remove potential prompt injection patterns."""
    # Strip control characters
    query = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', query)
    # Limit length
    return query[:500]
```

---

## 10. Next Steps

### Immediate (Week 1)
1. Set up dev environment (Docker + PostgreSQL + pgvector)
2. Initialize database schema and indices
3. Install Python dependencies and verify CLI
4. Create `.env` with local configuration

### Week 2
5. Ingest sample price book with classification codes
6. Test classification hierarchy and canonical key generation
7. Validate SCD2 mapping memory writes

### Week 3
8. Ingest documentation for RAG agent
9. Test agent search and hybrid queries
10. Benchmark vector search performance

### Week 4
11. Load test with 500 items × 5000 prices
12. Measure p95 latency and candidate reduction
13. Document performance tuning results

---

## Summary

**Essential for MVP**:
- PostgreSQL 15+ with pgvector extension
- Python 3.11+ with Pydantic, Typer, RapidFuzz, asyncpg
- Environment variables: `DATABASE_URL`, `DEFAULT_ORG_ID`
- Configuration files: `classification_hierarchy.yaml`, `flags.yaml`

**Optional but Recommended**:
- OpenAI API key for RAG agent features
- Neo4j for graph relationship queries
- Docker Compose for consistent dev environment

**Philosophy**: Start minimal, add complexity only when justified by value. Core matching engine works with PostgreSQL alone; RAG/Graph are additive enhancements.

---

**Document Version**: 1.0
**Last Updated**: 2025-11-07
**Maintainer**: BIMCalc Team
