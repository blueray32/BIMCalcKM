# Crail4 AI Integration - Deployment Setup Instructions

**Status**: Implementation ✅ Complete | Deployment Setup ⏳ In Progress

---

## Next Steps for Codex

These tasks complete the deployment preparation. Execute them in order.

---

## STEP 1: Run Database Migration

**Objective**: Create the new tables (`price_import_runs`, `classification_mappings`) and add columns to `price_items`.

**Command**:
```bash
sqlite3 bimcalc.db < bimcalc/db/migrations/add_crail4_support.sql
```

**Verification**:
```bash
# Check that new tables exist
sqlite3 bimcalc.db "SELECT name FROM sqlite_master WHERE type='table' AND name IN ('price_import_runs', 'classification_mappings');"

# Expected output:
# price_import_runs
# classification_mappings

# Check that price_items has new columns
sqlite3 bimcalc.db "PRAGMA table_info(price_items);" | grep -E "vendor_code|import_run_id|last_updated"

# Expected: Should show these 3 columns
```

**Troubleshooting**:
- If migration fails, check if tables already exist: `sqlite3 bimcalc.db ".tables"`
- If columns already exist on price_items, migration may have run previously
- Use `--force` or drop tables first if needed (⚠️ only in dev environment)

---

## STEP 2: Seed Classification Mappings

**Objective**: Pre-populate OmniClass → UniClass code translations for common MEP items.

**Command**:
```bash
python -m bimcalc.integration.seed_classification_mappings
```

**Expected Output**:
```
Seeded classification mappings for acme-construction
```

**Verification**:
```bash
sqlite3 bimcalc.db "SELECT source_code, target_code, source_scheme, target_scheme FROM classification_mappings LIMIT 5;"

# Expected: Should show 5 OmniClass → UniClass mappings like:
# 23-17 11 23|66|OmniClass|UniClass2015
# 23-17 13 11|62|OmniClass|UniClass2015
```

**If Error**:
- Check that `data/classification_mappings.csv` exists
- Verify database migration ran successfully (STEP 1)
- Check that `org_id` matches your test org (default: `acme-construction`)

---

## STEP 3: Create Sample Test Data for Crail4 Sync

**Objective**: Create mock Crail4 response data to test the full ETL pipeline without hitting the real API.

**File to Create**: `tests/fixtures/crail4_sample_response.json`

**Content**:
```json
{
  "items": [
    {
      "id": "crail4-test-001",
      "classification_code": "23-17 11 23",
      "classification_scheme": "OmniClass",
      "name": "Cable Tray Elbow 90° 200x50mm Galvanized",
      "description": "Pre-galvanized steel cable tray elbow fitting, 90 degree bend",
      "unit": "ea",
      "unit_price": 45.50,
      "currency": "EUR",
      "vat_rate": 0.23,
      "vendor_code": "CTL-ELB-90-200X50-GALV",
      "item_code": "CTL-ELB-90-200X50-GALV",
      "region": "IE",
      "last_updated": "2025-01-15T10:30:00Z"
    },
    {
      "id": "crail4-test-002",
      "classification_code": "23-17 13 11",
      "classification_scheme": "OmniClass",
      "name": "13A Socket Outlet White Single Gang",
      "description": "Single gang 13A switched socket outlet, white finish",
      "unit": "ea",
      "unit_price": 12.75,
      "currency": "EUR",
      "vat_rate": 0.23,
      "vendor_code": "SO-13A-1G-WH",
      "item_code": "SO-13A-1G-WH",
      "region": "IE",
      "last_updated": "2025-01-14T14:20:00Z"
    },
    {
      "id": "crail4-test-003",
      "classification_code": "23-17 15 11",
      "classification_scheme": "OmniClass",
      "name": "LED Bulkhead Light 18W Emergency",
      "description": "LED bulkhead fitting 18W with 3hr emergency backup",
      "unit": "ea",
      "unit_price": 89.00,
      "currency": "EUR",
      "vat_rate": 0.23,
      "vendor_code": "LED-BH-18W-EM",
      "item_code": "LED-BH-18W-EM",
      "region": "IE",
      "last_updated": "2025-01-16T09:15:00Z"
    }
  ]
}
```

**Purpose**: This provides realistic test data covering different classifications (66=Containment, 62=Power, 64=Lighting).

---

## STEP 4: Create Unit Tests

**Objective**: Test the core ETL components in isolation before integration testing.

**File to Create**: `tests/integration/test_crail4_etl.py`

**Content**:
```python
"""Integration tests for Crail4 ETL pipeline."""

import pytest
from decimal import Decimal
from bimcalc.integration.classification_mapper import ClassificationMapper
from bimcalc.integration.crail4_transformer import Crail4Transformer
from bimcalc.db.connection import get_session


@pytest.mark.asyncio
async def test_classification_mapper_translate():
    """Test that OmniClass codes translate to UniClass."""
    async with get_session() as session:
        mapper = ClassificationMapper(session, "acme-construction")

        # Should translate OmniClass cable tray code to UniClass containment
        result = await mapper.translate(
            source_code="23-17 11 23",
            source_scheme="OmniClass",
            target_scheme="UniClass2015"
        )

        assert result == "66", f"Expected '66', got '{result}'"


@pytest.mark.asyncio
async def test_transformer_valid_item():
    """Test transformer handles valid Crail4 item."""
    async with get_session() as session:
        mapper = ClassificationMapper(session, "acme-construction")
        transformer = Crail4Transformer(mapper, "UniClass2015")

        raw_item = {
            "id": "test-001",
            "classification_code": "23-17 11 23",
            "classification_scheme": "OmniClass",
            "name": "Cable Tray Elbow 90° 200x50mm",
            "unit": "ea",
            "unit_price": 45.50,
            "currency": "EUR",
            "vat_rate": 0.23,
            "vendor_code": "CTL-ELB-90-200X50"
        }

        result = await transformer.transform_item(raw_item)

        assert result is not None, "Valid item should not be rejected"
        assert result["classification_code"] == "66", "Should translate to UniClass 66"
        assert result["unit"] == "ea"
        assert result["unit_price"] == Decimal("45.50")
        assert result["currency"] == "EUR"
        assert result["canonical_key"] is not None, "Should generate canonical key for MEP item"


@pytest.mark.asyncio
async def test_transformer_missing_fields():
    """Test transformer rejects item with missing mandatory fields."""
    async with get_session() as session:
        mapper = ClassificationMapper(session, "acme-construction")
        transformer = Crail4Transformer(mapper, "UniClass2015")

        # Missing unit_price
        raw_item = {
            "classification_code": "23-17 11 23",
            "classification_scheme": "OmniClass",
            "name": "Cable Tray Elbow",
            "unit": "ea"
            # unit_price missing!
        }

        result = await transformer.transform_item(raw_item)
        assert result is None, "Should reject item with missing unit_price"


@pytest.mark.asyncio
async def test_transformer_batch_statistics():
    """Test batch transformer returns rejection statistics."""
    async with get_session() as session:
        mapper = ClassificationMapper(session, "acme-construction")
        transformer = Crail4Transformer(mapper, "UniClass2015")

        raw_items = [
            # Valid item
            {
                "classification_code": "23-17 11 23",
                "classification_scheme": "OmniClass",
                "name": "Cable Tray",
                "unit": "ea",
                "unit_price": 45.50
            },
            # Missing unit_price
            {
                "classification_code": "23-17 11 23",
                "classification_scheme": "OmniClass",
                "name": "Cable Tray",
                "unit": "ea"
            },
            # Invalid classification (no mapping)
            {
                "classification_code": "99-99 99 99",
                "classification_scheme": "OmniClass",
                "name": "Unknown Item",
                "unit": "ea",
                "unit_price": 10.00
            }
        ]

        valid, rejections = await transformer.transform_batch(raw_items)

        assert len(valid) == 1, "Should accept 1 valid item"
        assert rejections["missing_fields"] >= 1, "Should count missing field rejections"
        assert rejections["no_classification_mapping"] >= 1, "Should count unmapped codes"


@pytest.mark.asyncio
async def test_unit_standardization():
    """Test that units are normalized correctly."""
    async with get_session() as session:
        mapper = ClassificationMapper(session, "acme-construction")
        transformer = Crail4Transformer(mapper, "UniClass2015")

        test_cases = [
            ("sq.m", "m²"),
            ("sqm", "m²"),
            ("square meter", "m²"),
            ("piece", "ea"),
            ("each", "ea"),
            ("meter", "m"),
        ]

        for input_unit, expected_unit in test_cases:
            normalized = transformer._standardize_unit(input_unit)
            assert normalized == expected_unit, f"'{input_unit}' should normalize to '{expected_unit}', got '{normalized}'"
```

**Run Tests**:
```bash
pytest tests/integration/test_crail4_etl.py -v
```

**Expected Output**: All tests pass ✅

---

## STEP 5: Test Manual Sync (Dry Run)

**Objective**: Verify the full ETL pipeline works end-to-end.

**Option A: Test with Mock Data (Recommended First)**

Create a test script: `scripts/test_crail4_sync.py`

```python
"""Test Crail4 sync with mock data."""

import asyncio
import json
from pathlib import Path
from bimcalc.integration.crail4_transformer import Crail4Transformer
from bimcalc.integration.classification_mapper import ClassificationMapper
from bimcalc.db.connection import get_session


async def test_sync():
    """Test ETL with sample data."""

    # Load sample data
    fixture_path = Path("tests/fixtures/crail4_sample_response.json")
    with fixture_path.open() as f:
        data = json.load(f)

    raw_items = data["items"]
    print(f"Loaded {len(raw_items)} test items")

    # Transform
    async with get_session() as session:
        mapper = ClassificationMapper(session, "acme-construction")
        transformer = Crail4Transformer(mapper, "UniClass2015")

        valid, rejections = await transformer.transform_batch(raw_items)

        print(f"✅ Valid items: {len(valid)}")
        print(f"❌ Rejected: {sum(rejections.values())}")
        print(f"Rejection breakdown: {rejections}")

        # Print first valid item
        if valid:
            print("\nSample transformed item:")
            import pprint
            pprint.pprint(valid[0])


if __name__ == "__main__":
    asyncio.run(test_sync())
```

**Run**:
```bash
python scripts/test_crail4_sync.py
```

**Expected Output**:
```
Loaded 3 test items
✅ Valid items: 3
❌ Rejected: 0
Rejection breakdown: {'missing_fields': 0, 'no_classification_mapping': 0, 'transform_error': 0}

Sample transformed item:
{
  'classification_code': '66',
  'classification_scheme': 'UniClass2015',
  'description': 'Cable Tray Elbow 90° 200x50mm Galvanized',
  'unit': 'ea',
  'unit_price': Decimal('45.50'),
  'currency': 'EUR',
  'vat_rate': Decimal('0.23'),
  'vendor_code': 'CTL-ELB-90-200X50-GALV',
  'canonical_key': '66|cable_tray|elbow|w=200|h=50|a=90|mat=galv|u=ea',
  'source_data': {...}
}
```

**Option B: Test with Real Crail4 API (If API Key Available)**

```bash
# Ensure env vars are set
export CRAIL4_API_KEY="your_key_here"
export CRAIL4_BASE_URL="https://www.crawl4ai-cloud.com/query"
export CRAIL4_SOURCE_URL="your_source_url"

# Run sync with classification filter (start small)
bimcalc sync-crail4 --org acme-construction --classifications 66 --region IE
```

**Expected Output**:
```
Sync Status: completed
Items Loaded: X/Y
Transform Rejections:
  - missing_fields: 0
  - no_classification_mapping: 2
  - transform_error: 0
```

---

## STEP 6: Test Bulk Import API Endpoint

**Objective**: Verify the REST API accepts transformed data and creates audit records.

**Test Script**: `scripts/test_bulk_import_api.py`

```python
"""Test bulk import API endpoint."""

import asyncio
import httpx
import json
from pathlib import Path


async def test_bulk_import():
    """Test POST /api/price-items/bulk-import."""

    # Load sample transformed data
    # (You'd normally get this from transformer output)
    test_payload = {
        "org_id": "acme-construction",
        "source": "manual_test",
        "target_scheme": "UniClass2015",
        "items": [
            {
                "classification_code": "66",
                "classification_scheme": "UniClass2015",
                "description": "Cable Tray Elbow 90° Test",
                "unit": "ea",
                "unit_price": "45.50",
                "currency": "EUR",
                "vat_rate": "0.23",
                "vendor_code": "TEST-001",
                "canonical_key": "66|cable_tray|elbow|w=200|h=50|a=90|u=ea"
            }
        ]
    }

    async with httpx.AsyncClient() as client:
        response = await client.post(
            "http://localhost:8001/api/price-items/bulk-import",
            json=test_payload,
            timeout=30.0
        )

        print(f"Status: {response.status_code}")

        if response.status_code == 200:
            result = response.json()
            print(f"✅ Import successful!")
            print(f"Run ID: {result['run_id']}")
            print(f"Items loaded: {result['items_loaded']}/{result['items_received']}")
            print(f"Items rejected: {result['items_rejected']}")

            # Query import run details
            run_id = result['run_id']
            run_response = await client.get(f"http://localhost:8001/api/price-imports/{run_id}")

            if run_response.status_code == 200:
                run_details = run_response.json()
                print(f"\nImport Run Details:")
                print(f"  Status: {run_details['status']}")
                print(f"  Started: {run_details['started_at']}")
                print(f"  Completed: {run_details['completed_at']}")
        else:
            print(f"❌ Import failed: {response.text}")


if __name__ == "__main__":
    asyncio.run(test_bulk_import())
```

**Run**:
```bash
python scripts/test_bulk_import_api.py
```

**Expected Output**:
```
Status: 200
✅ Import successful!
Run ID: <uuid>
Items loaded: 1/1
Items rejected: 0

Import Run Details:
  Status: completed
  Started: 2025-01-17T10:30:00.123Z
  Completed: 2025-01-17T10:30:01.456Z
```

**Verification**:
```bash
# Check that price item was inserted
sqlite3 bimcalc.db "SELECT description, unit_price, vendor_code FROM price_items WHERE vendor_code='TEST-001';"

# Expected: Should show the test item
# Cable Tray Elbow 90° Test|45.5|TEST-001

# Check that import run was recorded
sqlite3 bimcalc.db "SELECT source, status, items_loaded FROM price_import_runs ORDER BY started_at DESC LIMIT 1;"

# Expected:
# manual_test|completed|1
```

---

## STEP 7: Update Documentation

**File to Update**: `README.md`

**Section to Add**:

```markdown
## Crail4 AI Integration

BIMCalc supports automated price synchronization from Crail4 AI pricing catalogs.

### Setup

1. Set environment variables:
   ```bash
   export CRAIL4_API_KEY="your_api_key"
   export CRAIL4_BASE_URL="https://www.crawl4ai-cloud.com/query"
   export CRAIL4_SOURCE_URL="your_source_url"
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
```

---

## STEP 8: Create Deployment Checklist

**File to Create**: `deployment/DEPLOYMENT_CHECKLIST.md`

```markdown
# Crail4 Integration - Production Deployment Checklist

## Pre-Deployment

- [ ] Database backup created
- [ ] Environment variables set in production .env
- [ ] API key validated with Crail4
- [ ] Classification mappings reviewed and approved
- [ ] Test sync completed successfully in staging

## Deployment Steps

1. [ ] Run database migration
   ```bash
   sqlite3 /path/to/prod/bimcalc.db < bimcalc/db/migrations/add_crail4_support.sql
   ```

2. [ ] Seed classification mappings
   ```bash
   python -m bimcalc.integration.seed_classification_mappings
   ```

3. [ ] Copy systemd units
   ```bash
   sudo cp deployment/crail4-sync.* /etc/systemd/system/
   sudo systemctl daemon-reload
   ```

4. [ ] Enable and start timer
   ```bash
   sudo systemctl enable crail4-sync.timer
   sudo systemctl start crail4-sync.timer
   ```

5. [ ] Verify timer is active
   ```bash
   sudo systemctl status crail4-sync.timer
   ```

## Post-Deployment Verification

- [ ] Manual sync test: `bimcalc sync-crail4 --org <prod-org> --classifications 66`
- [ ] Check import run created: Query `price_import_runs` table
- [ ] Verify price items imported: Query `price_items` WHERE `import_run_id` IS NOT NULL
- [ ] Test API endpoint: POST to `/api/price-items/bulk-import`
- [ ] Check systemd logs: `sudo journalctl -u crail4-sync.service -n 50`
- [ ] Confirm next scheduled run: `sudo systemctl list-timers crail4-sync.timer`

## Rollback Plan

If issues occur:

1. [ ] Stop timer: `sudo systemctl stop crail4-sync.timer`
2. [ ] Disable timer: `sudo systemctl disable crail4-sync.timer`
3. [ ] Restore database from backup
4. [ ] Investigate logs: `sudo journalctl -u crail4-sync.service --since "1 hour ago"`

## Monitoring

- [ ] Set up alerting for failed sync jobs
- [ ] Monitor `price_import_runs` table for status='failed'
- [ ] Track rejection rates (items_rejected / items_fetched)
- [ ] Review API endpoint error rates

## Support

- Logs location: `/var/log/syslog` or `journalctl`
- Config location: `/etc/systemd/system/crail4-sync.*`
- Environment vars: `/opt/bimcalc/.env`
```

---

## Summary: What Codex Should Execute

Execute these in order:

1. ✅ **STEP 1**: Run migration → Creates tables
2. ✅ **STEP 2**: Seed mappings → Populates classification translations
3. ✅ **STEP 3**: Create test fixtures → Sample Crail4 response JSON
4. ✅ **STEP 4**: Write unit tests → Test ETL components
5. ✅ **STEP 5**: Test sync → Verify end-to-end with mock data
6. ✅ **STEP 6**: Test API → Verify bulk import endpoint
7. ✅ **STEP 7**: Update README → Document usage
8. ✅ **STEP 8**: Create deployment checklist → Production guide

---

## Success Criteria

After completing these steps, you should have:

- ✅ Database schema updated with new tables
- ✅ Classification mappings seeded (5+ entries)
- ✅ Unit tests passing (8+ tests)
- ✅ Manual sync test successful (items loaded > 0)
- ✅ API endpoint functional (returns 200 with run_id)
- ✅ Documentation updated
- ✅ Deployment guide created

**Status**: Ready for production deployment 🚀
