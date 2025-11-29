# BIMCalc Live Pricing Pipeline - Upgrade Guide

## Overview

This guide documents the major architectural upgrade to BIMCalcKM's pricing data system. The system has been enhanced with:

1. **Full SCD Type-2 Price History** - Complete auditable timeline of all price changes
2. **Governance Fields** - Data provenance tracking for financial audits
3. **Modular Pipeline Architecture** - Resilient, source-isolated data ingestion
4. **Operational Monitoring** - Granular per-source logging and alerting

## What's New

### Database Schema Changes

The `PriceItemModel` has been upgraded with new fields:

**Governance Fields (Data Provenance):**
- `item_code` - Standardized product code (replaces SKU as primary identifier)
- `region` - Geographic market (e.g., 'UK', 'DE')
- `source_name` - Specific data source identifier
- `source_currency` - Original currency before any conversion
- `original_effective_date` - Manufacturer's stated effective date

**SCD Type-2 Temporal Fields:**
- `valid_from` - When this price became active
- `valid_to` - When this price was superseded (NULL for current)
- `is_current` - Boolean flag for current active price

**New Table:**
- `data_sync_log` - Granular logging for pipeline operations

### Pipeline Architecture

**New Modules:**
- `bimcalc/pipeline/` - Core pipeline system
  - `orchestrator.py` - Pipeline coordinator
  - `scd2_updater.py` - SCD Type-2 update logic
  - `base_importer.py` - Base class for importers
  - `types.py` - Type definitions
  - `config_loader.py` - Configuration management
  - `importers/` - Source-specific importer modules
    - `csv_importer.py` - File-based imports
    - `api_importer.py` - REST API imports

**Configuration:**
- `config/pipeline_sources.yaml` - Data source configuration

**Utilities:**
- `bimcalc/db/price_queries.py` - Helper functions for SCD Type-2 queries

### CLI Commands

**New Commands:**
```bash
# Run database migration
python -m bimcalc.cli migrate --execute

# Run price synchronization pipeline
python -m bimcalc.cli sync-prices

# Check pipeline status
python -m bimcalc.cli pipeline-status
```

## Migration Instructions

### Step 1: Backup Your Database

**CRITICAL:** Backup your database before migration!

```bash
# PostgreSQL backup
pg_dump -h localhost -U username bimcalc > backup_$(date +%Y%m%d).sql

# SQLite backup
cp bimcalc.db bimcalc_backup_$(date +%Y%m%d).db
```

### Step 2: Review Migration (Dry Run)

```bash
python -m bimcalc.cli migrate
```

This shows what the migration will do without making changes.

### Step 3: Execute Migration

```bash
python -m bimcalc.cli migrate --execute
```

The migration will:
1. Add new columns to `price_items` table
2. Populate `item_code` from existing `sku`
3. Set default `region` to 'UK'
4. Populate governance fields with defaults
5. Create SCD Type-2 indexes
6. Create `data_sync_log` table

**Expected Output:**
```
Executing migration...
✓ Migration completed successfully!
✓ data_sync_log table created
✓ 1,234 active price records
```

### Step 4: Configure Data Sources

Edit `config/pipeline_sources.yaml` to configure your data sources:

```yaml
sources:
  - name: my_vendor_csv
    type: csv
    enabled: true
    config:
      file_path: /data/prices/vendor_prices.csv
      region: UK
      vendor_id: my_vendor
      column_mapping:
        Item Code: item_code
        Description: description
        Classification: classification_code
        Price: unit_price
        Currency: currency
        Unit: unit
```

### Step 5: Test the Pipeline

Run with test data:

```bash
# Dry run (no database writes)
python -m bimcalc.cli sync-prices --dry-run

# Execute with test config
python -m bimcalc.cli sync-prices --config tests/fixtures/test_pipeline.yaml
```

### Step 6: Schedule Nightly Runs

Add to crontab for automated daily updates:

```bash
# Run daily at 2:00 AM
0 2 * * * cd /path/to/BIMCalcKM && python -m bimcalc.cli sync-prices --config config/pipeline_sources.yaml >> /var/log/bimcalc_pipeline.log 2>&1
```

## Using the New System

### Querying Current Prices

```python
from bimcalc.db.price_queries import get_current_price

# Get latest price
price = await get_current_price(session, item_code="ELBOW-001", region="UK")
```

### Historical Price Analysis

```python
from bimcalc.db.price_queries import get_historical_price
from datetime import datetime

# Get price at specific date
as_of = datetime(2024, 1, 15)
price = await get_historical_price(session, "ELBOW-001", "UK", as_of)
```

### Price History Timeline

```python
from bimcalc.db.price_queries import get_price_history

# Get all historical prices
history = await get_price_history(session, "ELBOW-001", "UK", limit=10)

for price in history:
    print(f"{price.valid_from}: €{price.unit_price}")
```

### Monitoring Pipeline Health

```bash
# Check last 10 runs
python -m bimcalc.cli pipeline-status --last 10
```

## Key Architectural Principles

### 1. Always Filter by `is_current = True`

When fetching prices for calculations, ALWAYS filter by `is_current`:

```python
stmt = select(PriceItemModel).where(
    and_(
        PriceItemModel.item_code == item_code,
        PriceItemModel.region == region,
        PriceItemModel.is_current == True,  # CRITICAL!
    )
)
```

### 2. Never Overwrite Price Records

The SCD Type-2 pattern means:
- ❌ **NEVER** update price records in place
- ✅ **ALWAYS** expire old record + insert new record
- ✅ Use `SCD2PriceUpdater` class for all price updates

### 3. Source Isolation

Each data source is independent:
- Failures are contained per-source
- Each source logs independently
- Pipeline continues even if one source fails

### 4. Auditability

Every price change is tracked:
- Who changed it (`source_name`)
- When it changed (`valid_from`, `valid_to`)
- What changed (`unit_price`, `source_currency`)

## Rollback Procedure

If you need to rollback the migration:

```bash
# WARNING: This DESTROYS SCD Type-2 history!
python -m bimcalc.cli migrate --rollback --execute
```

Then restore from backup:

```bash
# PostgreSQL restore
psql -h localhost -U username bimcalc < backup_20241113.sql

# SQLite restore
cp bimcalc_backup_20241113.db bimcalc.db
```

## Troubleshooting

### Migration Fails

**Problem:** Migration fails with constraint violation

**Solution:**
1. Check for NULL values in required fields
2. Ensure unique constraints aren't violated
3. Review migration logs for specific error

### Pipeline Import Failures

**Problem:** Source fails with parsing error

**Solution:**
1. Check `pipeline-status` for error details
2. Verify file format matches column mapping
3. Check source file encoding (UTF-8 expected)
4. Review `data_sync_log` table for diagnostics

### Query Performance Issues

**Problem:** Slow price lookups

**Solution:**
1. Verify indexes exist: `idx_price_current`, `idx_price_active_unique`
2. Ensure `ANALYZE` has been run on PostgreSQL
3. Check query uses `is_current = true` filter

## Configuration Examples

### CSV File Source

```yaml
- name: obo_q4_2024
  type: csv
  enabled: true
  config:
    file_path: /data/prices/obo_q4_2024.csv
    region: DE
    vendor_id: obo_bettermann
    column_mapping:
      Item Code: item_code
      Description: description
      Classification: classification_code
      Price: unit_price
      Currency: currency
      Unit: unit
```

### API Source (RS Components)

```yaml
- name: rs_components_uk
  type: rs_components
  enabled: true
  config:
    api_base_url: https://api.rs-online.com
    api_key: ${RS_API_KEY}  # From environment
    region: UK
    rate_limit_delay: 0.2
    batch_size: 100
```

## Support

For issues or questions:
1. Check `PIPELINE_UPGRADE_GUIDE.md` (this file)
2. Review implementation documents in project root
3. Examine `data_sync_log` table for diagnostics
4. Check application logs

## References

- Implementation Guide (flowchart image)
- Architectural Proposals (detailed design docs)
- CLAUDE.md (core principles and invariants)
