# BIMCalc

**Production-ready BIM cost matching engine** with enterprise-grade features for automated Revit → price catalog matching.

## 🎯 Key Features

### Core Capabilities
- **Classification-first blocking** - 6-50× candidate reduction for fast, accurate matching
- **Canonical mapping memory** - Project-agnostic keys with SCD Type-2 history
- **Enhanced confidence scoring** - Multi-dimensional analysis (text, attributes, size, material)
- **Business risk flags** - Critical-veto and advisory flags with UI enforcement
- **Escape-hatch matching** - Intelligent fallback when no in-class candidates exist
- **Multi-tenant architecture** - Organization-scoped mappings with audit trail

### User Experience
- **Interactive web UI** (port 8001) - Color-coded confidence, severity badges, real-time filtering
- **Textual console UI** - Terminal-based review for CLI workflows
- **One-click actions** - Accept, reject, remap with instant feedback
- **Smart filtering** - View by confidence, risk level, or matching status
- **Price history** - Track price changes over time across sources

### Enterprise Features
- **PostgreSQL + pgvector** - Production-grade database with vector similarity search
- **Multi-source ingestion** - CSV, XLSX, JSON, APIs (extensible pipeline architecture)
- **Automated data pipelines** - Scheduled price updates with validation
- **Backup & recovery** - Automated database backups with compression
- **Health monitoring** - Automated health checks with alerting
- **Performance tested** - <1ms p95 latency on 10K+ price catalogs

## 🚀 Quickstart

### Local Development (SQLite)
```bash
# Setup environment
python -m venv .venv
source .venv/bin/activate
pip install -e .[dev]

# Verify installation
pytest -q
bimcalc --help

# Run browser-based review UI
bimcalc web serve --host 0.0.0.0 --port 8001
# Visit http://localhost:8001
```

### Production Deployment (PostgreSQL + Docker)

```bash
# 1. Build and start services
docker compose build
docker compose up -d db

# 2. Initialize database schema
docker compose run --rm app bimcalc init

# 3. Ingest price catalogs
docker compose run --rm app bimcalc ingest-prices \
  pricebooks/vendor_a.xlsx \
  pricebooks/vendor_b.csv \
  --org acme-corp

# 4. Ingest Revit schedules
docker compose run --rm app bimcalc ingest-schedules \
  examples/schedules/project_a.csv \
  --project project-a \
  --org acme-corp

# 5. Run matching pipeline
docker compose run --rm app bimcalc match \
  --project project-a \
  --org acme-corp

# 6. Launch web UI for review
docker compose up app
# Visit http://localhost:8001

# 7. Generate cost report
docker compose run --rm app bimcalc report \
  --project project-a \
  --org acme-corp \
  --output reports/project_a_$(date +%Y%m%d).csv
```

## 📊 Web UI Features

### Review Dashboard
- **Color-coded confidence**
  - 🟢 Green: High confidence (≥0.85) - Auto-approve candidates
  - 🟡 Yellow: Medium confidence (0.70-0.84) - Requires review
  - 🔴 Red: Low confidence (<0.70) - Careful review needed

- **Risk flag indicators**
  - 🔴 **Critical**: Blocks acceptance (unit/size/material conflicts)
  - 🟡 **Advisory**: Requires acknowledgment (stale price, vendor notes)

- **Smart filters**
  - Filter by confidence level (high/medium/low)
  - Filter by risk level (critical/advisory/none)
  - Filter by status (pending/approved/rejected)
  - Search by item name, classification, or price description

- **Interactive actions**
  - ✅ Accept - Approve match and create mapping
  - ❌ Reject - Decline match with reason
  - 🔄 Remap - Choose different price from candidates
  - 📝 Annotate - Add notes for audit trail

### Price Management
- **Price history view** - Track price changes over time
- **Multi-source tracking** - See which vendor/source provides each price
- **Currency & VAT handling** - Explicit EUR defaults with configurable VAT
- **Regional pricing** - Support for DE, ES, FR, IE, UK, and more

## 🏗️ Architecture

### Path C: Enhanced Review Workflow
```
Revit Items → Classification → Canonicalization → Candidate Generation
     ↓              ↓                 ↓                    ↓
  [Elements]   [OmniClass]      [Canonical Key]     [In-Class Search]
     ↓              ↓                 ↓                    ↓
  Matching ← Risk Flags ← Confidence Scoring ← Attribute Analysis
     ↓              ↓                 ↓                    ↓
  [Auto?]      [Critical?]         [≥0.85?]           [Size/Material]
     ↓              ↓                 ↓                    ↓
  Result ← Manual Review ← Web UI ← Mapping Memory (SCD2)
```

### Data Pipeline Architecture
```
Sources → Validation → Normalization → Database → Review UI → Reports
   ↓          ↓             ↓             ↓          ↓          ↓
[APIs]    [Schema]      [Canonical]   [Postgres]  [Web]    [CSV/PDF]
[CSV]     [Types]       [Parse]       [SCD2]      [TUI]    [Excel]
[XLSX]    [Ranges]      [Embed]       [Audit]     [API]    [JSON]
```

## 🧪 Testing & Performance

### Unit Tests
```bash
# Run all tests
pytest -v

# Run with coverage
pytest --cov=bimcalc --cov-report=html

# Run specific test suites
pytest tests/unit/test_review.py
pytest tests/integration/test_escape_hatch.py
```

### Performance Benchmarks
```bash
# Generate test data (10K prices)
python tests/performance/generate_test_data.py

# Run benchmarks
python tests/performance/benchmark.py

# Results: <1ms p95 latency for candidate generation
# See PERFORMANCE_TEST_RESULTS.md for details
```

### Validation Tests
```bash
# Test multi-tenant isolation
pytest tests/integration/test_multi_tenant.py

# Test SCD2 constraints
pytest tests/integration/test_scd2_constraints.py

# Test escape-hatch behavior
pytest tests/integration/test_escape_hatch.py
```

## 📦 Data Pipeline Features

### Multi-Source Ingestion
```bash
# Ingest from multiple formats
bimcalc ingest-prices \
  pricebooks/vendor_a.xlsx \
  pricebooks/vendor_b.csv \
  pricebooks/api_dump.json \
  --org acme-corp

# Ingest with validation
bimcalc ingest-prices source.csv --validate --strict
```

### Automated Pipelines
```bash
# Setup automated price updates
./scripts/setup_automation.sh

# Configure data sources
cp config/pipeline_sources_template.yaml config/pipeline_sources.yaml
vim config/pipeline_sources.yaml

# Validate configuration
python scripts/validate_config.py
```

### Pipeline Monitoring
```bash
# View pipeline status
./scripts/monitoring_dashboard.sh

# Check health
./scripts/health_check.sh

# View logs
tail -f logs/pipeline.log
```

## 🔒 Backup & Recovery

### Automated Backups
```bash
# Setup backup schedule (daily + weekly)
./scripts/setup_backup_schedule.sh

# Manual backup
./scripts/backup_postgres.sh

# Restore from backup
./scripts/restore_postgres.sh backups/backup_20250114_120000.sql.gz
```

### Backup Configuration
- Daily backups: 7-day retention
- Weekly backups: 4-week retention
- Compressed with gzip
- Stored in `./backups/` directory

## 📈 Monitoring & Alerts

### Health Monitoring
```bash
# Setup monitoring
./scripts/setup_automation.sh

# Check system health
./scripts/health_check.sh

# Monitor and alert
./scripts/monitor_and_alert.sh
```

### Monitoring Checks
- ✅ Database connectivity
- ✅ Disk space (alert at 90%)
- ✅ Service responsiveness
- ✅ Pipeline execution status
- ✅ Error rate thresholds

## 🌍 Environment Configuration

### Required Variables
```bash
# Database (SQLite for dev, PostgreSQL for prod)
export DATABASE_URL="sqlite:///./bimcalc.db"
# or
export DATABASE_URL="postgresql+psycopg://user:pass@localhost:5432/bimcalc"

# Organization (multi-tenant)
export DEFAULT_ORG_ID="acme-corp"

# Currency & VAT (EU defaults)
export CURRENCY="EUR"
export VAT_INCLUDED="false"
export VAT_RATE="0.23"

# Logging
export LOG_LEVEL="INFO"
```

### Optional Variables
```bash
# External integrations
export ARCHON_SERVER="https://archon.example.com"
export ARCHON_TOKEN="your-token-here"

# Embeddings (if using external provider)
export EMBEDDINGS_PROVIDER="openai"
export OPENAI_API_KEY="sk-..."

# Alert configuration
export ALERT_EMAIL="ops@example.com"
export ALERT_WEBHOOK="https://hooks.slack.com/..."
```

## 📚 Documentation

### Core Documentation
- **[CLAUDE.md](CLAUDE.md)** - Global rules and invariants
- **[PERFORMANCE_TEST_RESULTS.md](PERFORMANCE_TEST_RESULTS.md)** - Benchmark results
- **[STAGING_DEPLOYMENT_GUIDE.md](STAGING_DEPLOYMENT_GUIDE.md)** - Production deployment
- **[PATH_C_ENHANCEMENTS_SUMMARY.md](PATH_C_ENHANCEMENTS_SUMMARY.md)** - Enhanced review workflow
- **[WEB_UI_ENHANCEMENTS_COMPLETE.md](WEB_UI_ENHANCEMENTS_COMPLETE.md)** - UI features

### Operations Guides
- **[docs/PRODUCTION_OPERATIONS_GUIDE.md](docs/PRODUCTION_OPERATIONS_GUIDE.md)** - Production operations
- **[docs/BACKUP_PROCEDURES.md](docs/BACKUP_PROCEDURES.md)** - Backup & recovery
- **[docs/DATA_SOURCES_GUIDE.md](docs/DATA_SOURCES_GUIDE.md)** - Data pipeline setup
- **[docs/API_INTEGRATION_GUIDE.md](docs/API_INTEGRATION_GUIDE.md)** - API integration

### Scripts & Utilities
- **[scripts/README.md](scripts/README.md)** - Script documentation

## 🛠️ Development Commands

### Code Quality
```bash
# Format code
black bimcalc tests

# Lint
ruff check --fix bimcalc tests

# Type checking
mypy bimcalc

# All checks
ruff check --fix && black . && mypy bimcalc
```

### Database Management
```bash
# Initialize schema
bimcalc init

# Run migrations
alembic upgrade head

# Create migration
alembic revision -m "description"

# Rollback
alembic downgrade -1
```

### CLI Commands
```bash
# Ingest data
bimcalc ingest-prices <files> --org <org-id>
bimcalc ingest-schedules <files> --project <project-id>

# Matching
bimcalc match --project <project-id> --org <org-id>

# Review
bimcalc review ui --project <project-id>
bimcalc web serve --host 0.0.0.0 --port 8001

# Reporting
bimcalc report --project <project-id> --output report.csv
```

## 🐳 Docker Tips

### Development
```bash
# Interactive shell
docker compose run --rm app bash

# Run specific command
docker compose run --rm app bimcalc --help

# View logs
docker compose logs -f app
docker compose logs -f db
```

### Production
```bash
# Start services
docker compose up -d

# Check status
docker compose ps

# Restart service
docker compose restart app

# Scale (if needed)
docker compose up -d --scale app=3
```

## 📝 Audit & Compliance

### Audit Trail
- Every accept/reject action logged with user, timestamp, reason
- Mapping history preserved with SCD Type-2
- Price changes tracked across ingestion runs
- Report reproducibility with as-of timestamps

### Deterministic Reporting
```bash
# Generate historical report
bimcalc report \
  --project project-a \
  --as-of "2025-01-15T12:00:00Z" \
  --output reports/project_a_jan15.csv

# Same inputs + same mappings + same timestamp = same result
```

## Crail4 AI Integration

BIMCalc supports automated price synchronization from Crail4 AI pricing catalogs.

### Setup

1. Set environment variables:
   ```bash
   export CRAIL4_API_KEY="your_api_key"
   export CRAIL4_BASE_URL="https://www.crawl4ai-cloud.com/query"
   export CRAIL4_SOURCE_URL="https://example.com/your-feed"
   ```
2. Seed classification mappings:
   ```bash
   python -m bimcalc.integration.seed_classification_mappings
   ```
3. Test manual sync:
   ```bash
   bimcalc sync-crail4 --org your-org-id --classifications 62,63,64,66
   ```

### Automated Sync

Enable daily sync via systemd:

```bash
sudo cp deployment/crail4-sync.* /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable crail4-sync.timer
sudo systemctl start crail4-sync.timer
```

Check sync status:
```bash
sudo systemctl status crail4-sync.timer
sudo journalctl -u crail4-sync.service -f
```

### API Usage

Import prices programmatically:
```bash
curl -X POST http://localhost:8001/api/price-items/bulk-import \
  -H "Content-Type: application/json" \
  -d '{
    "org_id": "your-org",
    "source": "crail4_api",
    "target_scheme": "UniClass2015",
    "items": [...]
  }'
```

Query import history:
```bash
curl http://localhost:8001/api/price-imports/{run_id}
```

### Classification Mapping

Add custom taxonomy translations:

```python
from bimcalc.integration.classification_mapper import ClassificationMapper
from bimcalc.db.connection import get_session

async with get_session() as session:
    mapper = ClassificationMapper(session, "your-org")
    await mapper.add_mapping(
        source_code="23-17 11 23",
        source_scheme="OmniClass",
        target_code="66",
        target_scheme="UniClass2015",
        mapping_source="manual",
        created_by="admin"
    )
```

## 🤝 Contributing

### Development Workflow
1. Create feature branch from `main`
2. Implement changes with tests
3. Run quality checks: `ruff check --fix && black . && mypy bimcalc`
4. Run test suite: `pytest -v --cov=bimcalc`
5. Create pull request with description

### Code Standards
- Python 3.11+ with type hints
- Modules < 500 lines
- Test coverage ≥ 80%
- Structured logging with context
- Clear error messages with actionable info

## 📄 License

See [LICENSE](LICENSE) file for details.

## 🆘 Support

- **Issues**: Report bugs at project issue tracker
- **Documentation**: Check `docs/` directory
- **Community**: See contribution guidelines

---

**Version**: 2.0.0
**Last Updated**: 2025-01-14
**Status**: Production Ready ✅
