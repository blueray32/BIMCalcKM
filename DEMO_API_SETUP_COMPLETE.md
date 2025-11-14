# Demo API Setup Complete!

**Date:** November 14, 2025
**Status:** ✅ **WORKING & TESTED**

---

## What Was Built

You now have a **fully functional Demo API** integration that:

- ✅ Simulates a real vendor API (no actual HTTP calls needed)
- ✅ Generates realistic electrical/MEP product data
- ✅ Supports **multiple regions** (UK, IE, DE)
- ✅ Demonstrates **pagination** and **rate limiting**
- ✅ Successfully imported **30 price items**
- ✅ Ready to use as a template for real vendor APIs

---

## Current Status

### Data Imported

```
Source:               demo_api_multi_region
Status:               SUCCESS ✅
Records Inserted:     30
Duration:             < 1 second
Regions:              UK (10 items), IE (10 items), DE (10 items)
```

### Database Stats

**Before Demo API:**
- Current prices: 31 items

**After Demo API:**
- Current prices: **61 items** (31 original + 30 from demo)
- Multi-region data: UK (GBP), IE (EUR), DE (EUR)

### Sample Products Generated

| Region | Item Code | Description | Price | Currency |
|--------|-----------|-------------|-------|----------|
| UK | DEMO-UK-CB-90-200x50 | Cable Tray Elbow 90° 200x50mm [UK] | £42.50 | GBP |
| IE | DEMO-IE-CB-90-200x50 | Cable Tray Elbow 90° 200x50mm [IE] | €46.00 | EUR |
| DE | DEMO-DE-CB-90-200x50 | Cable Tray Elbow 90° 200x50mm [DE] | €44.00 | EUR |
| UK | DEMO-UK-CT-LAD | Cable Tray Ladder Type [UK] | £85.00 | GBP |
| UK | DEMO-UK-TEE-200x50 | Cable Tray Tee 200x50mm [UK] | £55.00 | GBP |
| DE | DEMO-DE-CROSS-200x50 | Cable Tray Cross 200x50mm [DE] | €70.50 | EUR |

---

## Files Created

### 1. Demo API Importer
**Location:** `bimcalc/pipeline/importers/demo_api_importer.py`
**Lines:** 200+
**Purpose:** Simulates a vendor API with realistic data

**Features:**
- Multi-region support
- Configurable pagination
- Rate limiting simulation
- 10 realistic MEP products
- Proper PriceRecord formatting

### 2. API Integration Guide
**Location:** `docs/API_INTEGRATION_GUIDE.md`
**Pages:** 25+
**Purpose:** Complete guide for adapting demo to real APIs

**Contents:**
- Understanding the Demo API
- How API importers work
- Step-by-step adaptation guide
- Common patterns and best practices
- Real vendor examples (RS Components, Farnell)
- Testing and debugging strategies

### 3. Updated Configuration
**Location:** `config/pipeline_sources.yaml`
**Changes:** Added demo_api_multi_region source

```yaml
- name: demo_api_multi_region
  type: demo_api
  enabled: true
  config:
    regions: ["UK", "IE", "DE"]
    items_per_region: 10
    simulate_delay: 0.1
    simulate_pagination: true
    page_size: 5
```

### 4. Updated Config Loader
**Location:** `bimcalc/pipeline/config_loader.py`
**Changes:** Added demo_api type recognition

---

## How to Use

### View Demo Data in Web UI

```bash
# Open web UI
open http://localhost:8001/prices

# Filter by source: "demo_api_multi_region"
# You'll see 30 items across UK, IE, DE regions
```

### Run Demo API Again

```bash
# Run full pipeline (includes demo)
docker exec bimcalckm-app-1 python -m bimcalc.cli sync-prices

# Results will show:
# demo_api_multi_region: SUCCESS, Updated: 30 (prices refreshed)
```

### Check Demo Data in Database

```bash
# Count by region
docker exec bimcalc-postgres psql -U bimcalc -d bimcalc -c \
  "SELECT region, COUNT(*) FROM price_items
   WHERE source_name = 'demo_api_multi_region' AND is_current = true
   GROUP BY region;"

# View sample items
docker exec bimcalc-postgres psql -U bimcalc -d bimcalc -c \
  "SELECT item_code, description, unit_price, currency
   FROM price_items
   WHERE source_name = 'demo_api_multi_region' AND is_current = true
   LIMIT 5;"
```

### Customize Demo Configuration

Edit `config/pipeline_sources.yaml`:

```yaml
config:
  regions: ["UK", "IE", "DE", "FR", "ES"]  # Add more regions
  items_per_region: 20  # Generate more items
  simulate_delay: 0.5  # Slower rate limiting
  simulate_pagination: false  # No pagination
```

---

## Understanding the Code

### Demo API Structure

```
demo_api_importer.py
│
├── DemoAPIImporter (main class)
│   │
│   ├── fetch_data()
│   │   ├── Read configuration
│   │   ├── Loop through regions
│   │   ├── Simulate pagination
│   │   ├── Simulate delays
│   │   └── Yield PriceRecords
│   │
│   ├── _create_price_record()
│   │   └── Convert product template to PriceRecord
│   │
│   └── _get_currency_for_region()
│       └── Map region to currency
│
└── SAMPLE_PRODUCTS (data template)
    └── 10 realistic MEP products
```

### Key Methods Explained

**1. fetch_data() - Main entry point**
```python
async def fetch_data(self) -> AsyncIterator[PriceRecord]:
    # This is called by the pipeline orchestrator
    # It yields PriceRecord objects one at a time
    for region in regions:
        for product in products:
            yield self._create_price_record(product, region, currency)
```

**2. _create_price_record() - Format converter**
```python
def _create_price_record(self, product: dict, region: str, currency: str) -> PriceRecord:
    # Converts demo product template to standard PriceRecord format
    # This is where you'd parse real API responses
    return PriceRecord(
        item_code=f"DEMO-{region}-{product['base_code']}",
        description=product["description"],
        unit_price=Decimal(str(price)),
        # ... all other fields
    )
```

---

## Adapting for Real APIs

### Quick Adaptation Steps

1. **Copy the demo:**
   ```bash
   cp bimcalc/pipeline/importers/demo_api_importer.py \
      bimcalc/pipeline/importers/vendor_name_importer.py
   ```

2. **Replace SAMPLE_PRODUCTS with real HTTP calls:**
   ```python
   # Instead of:
   products = self.SAMPLE_PRODUCTS

   # Use:
   async with aiohttp.ClientSession() as session:
       async with session.get(api_url) as response:
           data = await response.json()
           products = data["products"]
   ```

3. **Update _create_price_record() to parse vendor format:**
   ```python
   def _create_price_record(self, api_item: dict, region: str) -> PriceRecord:
       # Map vendor's field names to PriceRecord
       return PriceRecord(
           item_code=api_item["partNumber"],  # Vendor's field
           description=api_item["title"],      # Vendor's field
           unit_price=Decimal(api_item["price"]),  # Vendor's field
           # ...
       )
   ```

4. **Register new importer in config_loader.py**

5. **Add to pipeline_sources.yaml**

6. **Test!**

See `docs/API_INTEGRATION_GUIDE.md` for detailed instructions.

---

## Testing the Demo

### Test 1: Verify Data Import

```bash
# Run sync
docker exec bimcalckm-app-1 python -m bimcalc.cli sync-prices

# Expected output:
# demo_api_multi_region: SUCCESS, 30 records
```

### Test 2: Check Database

```bash
# Should show 10 items per region
docker exec bimcalc-postgres psql -U bimcalc -d bimcalc -c \
  "SELECT region, COUNT(*) FROM price_items
   WHERE source_name = 'demo_api_multi_region' AND is_current = true
   GROUP BY region;"

# Expected:
#  region | count
# --------+-------
#  DE     |    10
#  IE     |    10
#  UK     |    10
```

### Test 3: View in Web UI

```bash
open http://localhost:8001/prices
```

1. Look for items with code starting with "DEMO-"
2. Filter by region (UK, IE, DE)
3. Check prices are in correct currency (GBP, EUR, EUR)

### Test 4: Verify SCD Type-2

```bash
# Run sync twice - second time should UPDATE not INSERT
docker exec bimcalckm-app-1 python -m bimcalc.cli sync-prices
sleep 2
docker exec bimcalckm-app-1 python -m bimcalc.cli sync-prices

# Second run should show:
# demo_api_multi_region: SUCCESS, Updated: 30, Inserted: 0
```

---

## Configuration Options

The demo API is highly configurable:

### Option 1: Change Regions

```yaml
config:
  regions: ["UK"]  # Single region only
  # or
  regions: ["UK", "IE", "DE", "FR", "ES", "IT", "NL"]  # Many regions
```

### Option 2: Change Data Volume

```yaml
config:
  items_per_region: 5   # Fewer items
  # or
  items_per_region: 10  # All 10 products (current)
```

### Option 3: Disable Pagination

```yaml
config:
  simulate_pagination: false  # Fetch all at once
```

### Option 4: Adjust Rate Limiting

```yaml
config:
  simulate_delay: 0.0  # No delay
  # or
  simulate_delay: 1.0  # 1 second between pages
```

### Option 5: Change Page Size

```yaml
config:
  page_size: 3   # Smaller pages
  # or
  page_size: 20  # Larger pages
```

---

## Product Catalog

The demo generates these 10 products per region:

| Code | Description | Classification | Unit | UK Price | IE Price | DE Price |
|------|-------------|----------------|------|----------|----------|----------|
| CT-LAD | Cable Tray Ladder Type | 66 | m | £85.00 | €92.50 | €88.00 |
| CB-90-200x50 | Cable Tray Elbow 90° 200x50mm | 66 | ea | £42.50 | €46.00 | €44.00 |
| CB-45-300x50 | Cable Tray Elbow 45° 300x50mm | 66 | ea | £38.75 | €42.00 | €40.00 |
| TEE-200x50 | Cable Tray Tee 200x50mm | 66 | ea | £55.00 | €59.50 | €57.00 |
| CROSS-200x50 | Cable Tray Cross 200x50mm | 66 | ea | £68.00 | €73.50 | €70.50 |
| REDUCER-300-200 | Cable Tray Reducer 300-200mm | 66 | ea | £32.50 | €35.00 | €33.50 |
| CP-200x50 | Cable Tray Cover Plate 200x50mm | 66 | m | £18.00 | €19.50 | €18.50 |
| SUSP-ADJ | Adjustable Cable Tray Suspension | 66 | ea | £12.50 | €13.50 | €13.00 |
| COUPLER-200 | Cable Tray Coupler 200mm | 66 | ea | £8.75 | €9.50 | €9.00 |
| ENDCAP-200 | Cable Tray End Cap 200mm | 66 | ea | £5.50 | €6.00 | €5.75 |

All products use OmniClass 66 (Electrical - Cable Tray & Conduit Systems).

---

## Next Steps

### Immediate (Now)

**1. Explore the Demo Data**
```bash
# View in web UI
open http://localhost:8001/prices

# Check different regions
# Notice currency differences (GBP vs EUR)
# Examine price variations by region
```

**2. Read the Integration Guide**
```bash
# Open the guide
open docs/API_INTEGRATION_GUIDE.md

# Study the examples
# Understand the patterns
```

### Short Term (When Ready)

**3. Connect Your First Real API**

When you have a vendor API key ready:

```bash
# 1. Copy demo as template
cp bimcalc/pipeline/importers/demo_api_importer.py \
   bimcalc/pipeline/importers/rs_components_importer.py

# 2. Edit for real API calls
nano bimcalc/pipeline/importers/rs_components_importer.py

# 3. Add to config_loader.py
nano bimcalc/pipeline/config_loader.py

# 4. Configure in YAML
nano config/pipeline_sources.yaml

# 5. Test
docker exec bimcalckm-app-1 python -m bimcalc.cli sync-prices --dry-run
```

**4. Disable Demo (Optional)**

Once you have real data sources:

```yaml
# In config/pipeline_sources.yaml
- name: demo_api_multi_region
  type: demo_api
  enabled: false  # Disable demo
```

---

## Troubleshooting

### Demo Not Running?

Check it's enabled:
```bash
grep -A 10 "demo_api_multi_region" config/pipeline_sources.yaml
# Should show: enabled: true
```

### No Data Showing?

Verify database:
```bash
docker exec bimcalc-postgres psql -U bimcalc -d bimcalc -c \
  "SELECT COUNT(*) FROM price_items
   WHERE source_name = 'demo_api_multi_region';"
# Should show: 30
```

### Container Needs Restart?

After code changes:
```bash
docker restart bimcalckm-app-1
sleep 3
docker exec bimcalckm-app-1 python -m bimcalc.cli sync-prices
```

---

## Summary

You now have:

✅ **Working Demo API** - 30 items across 3 regions
✅ **Comprehensive Documentation** - 25+ page integration guide
✅ **Template for Real APIs** - Copy and adapt pattern
✅ **Multi-region Example** - Shows how to handle multiple regions
✅ **Pagination Example** - Shows how to handle API pagination
✅ **Rate Limiting Example** - Shows how to respect API limits

**The demo proves your pipeline works!**

Now you just need to adapt it for your specific vendor APIs. The pattern is proven, the infrastructure is ready, and the documentation is complete.

---

## Quick Reference

### Run Pipeline
```bash
docker exec bimcalckm-app-1 python -m bimcalc.cli sync-prices
```

### View Demo Data
```bash
open http://localhost:8001/prices
```

### Check Database
```bash
docker exec bimcalc-postgres psql -U bimcalc -d bimcalc -c \
  "SELECT * FROM price_items WHERE source_name = 'demo_api_multi_region' LIMIT 5;"
```

### Read Documentation
```bash
open docs/API_INTEGRATION_GUIDE.md
```

### View Demo Code
```bash
open bimcalc/pipeline/importers/demo_api_importer.py
```

---

**Setup Date:** November 14, 2025
**Status:** ✅ **COMPLETE & TESTED**
**Demo Data:** 30 items (10 per region × 3 regions)
**Next:** Connect your first real vendor API!

---

*The demo API is ready to use and adapt. Happy integrating!*
