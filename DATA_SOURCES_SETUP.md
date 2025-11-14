# ✅ Data Sources Setup Guide

**Date:** November 13, 2024
**Status:** Ready for Configuration
**Region:** Multi-Region Support

---

## Current Status

### Pipeline Configuration
```
Location:        config/pipeline_sources.yaml
Active sources:  1 (test data only)
Status:          ✅ Working
Ready for:       Production sources
```

### What You Have Now

✅ **Working pipeline system**
- Test data source configured and working
- SCD Type-2 price history enabled
- Web UI monitoring at http://localhost:8001/pipeline
- Automated backups configured

✅ **Documentation**
- Comprehensive data sources guide (30+ pages)
- Template configuration file
- Step-by-step instructions

✅ **Ready to add real data**
- Multi-region support (UK, IE, DE, etc.)
- Multiple source types (CSV, API, FTP, etc.)
- Isolated error handling per source

---

## Quick Setup: Add Your First Real Source

### For CSV/Excel Files

**Step 1: Prepare your file**
```bash
# Create data directory
mkdir -p data/prices

# Copy your price list
cp ~/Downloads/vendor_pricelist.csv data/prices/
```

**Step 2: Edit configuration**
```bash
nano config/pipeline_sources.yaml
```

**Step 3: Add your source** (copy this template):
```yaml
  # Your production source
  - name: my_vendor_uk
    type: csv
    enabled: true
    config:
      file_path: /Users/ciarancox/BIMCalcKM/data/prices/vendor_pricelist.csv
      region: UK  # or IE, DE, FR, etc.
      vendor_id: MY_VENDOR
      column_mapping:
        "Product Code": "item_code"
        "Description": "description"
        "Price": "unit_price"
        "Currency": "currency"
        "Unit": "unit"
```

**Step 4: Test it**
```bash
# Validate configuration
python scripts/validate_config.py

# Test your source
docker exec bimcalckm-app-1 python -m bimcalc.cli sync-prices --source my_vendor_uk

# Check results
open http://localhost:8001/pipeline
```

---

### For API Sources

**Step 1: Get API credentials**
- Contact your distributor (RS Components, Farnell, etc.)
- Request API key
- Note the API endpoint URL

**Step 2: Set environment variable**
```bash
# Add to your shell profile
echo 'export VENDOR_API_KEY="your_api_key_here"' >> ~/.zshrc
source ~/.zshrc

# Or add to docker-compose.yml
environment:
  - VENDOR_API_KEY=${VENDOR_API_KEY}
```

**Step 3: Configure source**
```yaml
  - name: rs_components_uk
    type: api
    enabled: true
    config:
      api_url: https://api.rs-online.com/v1/catalogue/products
      api_key_env: VENDOR_API_KEY
      region: UK
      vendor_id: RS_COMPONENTS
      rate_limit: 10
      field_mapping:
        stockNumber: "item_code"
        productDescription: "description"
        priceBreaks[0].price: "unit_price"
```

**Step 4: Test it**
```bash
docker exec bimcalckm-app-1 python -m bimcalc.cli sync-prices --source rs_components_uk
```

---

## What Data Sources Can You Add?

### 1. Manufacturer Price Lists (CSV/Excel)
**Examples:**
- OBO Bettermann (cable management)
- Philips (lighting)
- Schneider Electric (electrical)
- Any quarterly price lists

**Setup time:** 5 minutes
**Best for:** Quarterly updates, stable pricing

### 2. Distributor APIs
**Examples:**
- RS Components UK
- Farnell (Element14)
- Grainger
- Wesco

**Setup time:** 15 minutes
**Best for:** Real-time pricing, large catalogs

### 3. Price Aggregators
**Examples:**
- Trimble Luckins (UK - 40+ manufacturers)
- 2BA (Ireland)
- ICS (Germany)

**Setup time:** 15 minutes
**Best for:** Multi-vendor coverage

### 4. Custom Sources
**Examples:**
- FTP downloads
- Email attachments
- Internal databases
- ERP exports

**Setup time:** 20-30 minutes
**Best for:** Specific workflows

---

## Multi-Region Setup

**Your system supports multiple regions simultaneously:**

```yaml
sources:
  # UK pricing
  - name: uk_distributor
    type: csv
    enabled: true
    config:
      region: UK
      # ... prices in GBP

  # Irish pricing
  - name: ireland_distributor
    type: csv
    enabled: true
    config:
      region: IE
      # ... prices in EUR

  # German pricing
  - name: german_manufacturer
    type: csv
    enabled: true
    config:
      region: DE
      # ... prices in EUR
```

**Query by region:**
```sql
-- UK prices only
SELECT * FROM price_items WHERE region = 'UK' AND is_current = true;

-- Irish prices only
SELECT * FROM price_items WHERE region = 'IE' AND is_current = true;

-- All EUR prices
SELECT * FROM price_items WHERE currency = 'EUR' AND is_current = true;
```

---

## When You're Ready to Add Sources

### Immediate Options

**Option A: Start with sample/test data**
- Keep using existing test source
- Learn the system with safe data
- No vendor setup needed

**Option B: Add one real CSV file**
- Quick 5-minute setup
- Test with real data
- Low risk (CSV files are safe)

**Option C: Wait and plan**
- Review documentation
- Contact vendors for API access
- Prepare data files
- Come back when ready

---

## Essential Commands

```bash
# View current configuration
cat config/pipeline_sources.yaml

# View template (copy examples from here)
cat config/pipeline_sources_template.yaml

# Validate configuration
python scripts/validate_config.py

# Test specific source
docker exec bimcalckm-app-1 python -m bimcalc.cli sync-prices --source source_name

# Run all enabled sources
docker exec bimcalckm-app-1 python -m bimcalc.cli sync-prices

# Check results
open http://localhost:8001/pipeline
open http://localhost:8001/prices

# View system status
docker exec bimcalckm-app-1 python scripts/dashboard.py
```

---

## Documentation

### Created Files

**Guides:**
- `docs/DATA_SOURCES_GUIDE.md` - Comprehensive 30+ page guide
  - All source types explained
  - Step-by-step configuration
  - Multi-region setup
  - Testing procedures
  - Troubleshooting

- `DATA_SOURCES_SETUP.md` - This quick start guide

**Templates:**
- `config/pipeline_sources_template.yaml` - Ready-to-use templates
  - CSV source template
  - API source template
  - Multi-region examples
  - Field mapping reference

**Examples:**
- `config/pipeline_sources_examples.yaml` - Real-world examples
  - 15+ vendor configurations
  - RS Components, Farnell, OBO, Philips, etc.
  - Different source types

---

## Current Test Configuration

**You have one working test source:**

```yaml
- name: test_prices_local
  type: csv
  enabled: true
  config:
    file_path: tests/fixtures/sample_prices.csv
    region: UK
    vendor_id: test_vendor
```

**This is perfect for:**
- ✅ Testing pipeline functionality
- ✅ Learning the system
- ✅ Verifying web UI works
- ✅ Understanding data flow

**When ready, add real sources alongside this test source.**

---

## Next Steps

### Option 1: Start Adding Sources Now

**If you have data ready:**
1. Read `docs/DATA_SOURCES_GUIDE.md`
2. Copy template from `config/pipeline_sources_template.yaml`
3. Customize for your vendor
4. Test with `sync-prices --source your_source`
5. Monitor at http://localhost:8001/pipeline

**Time required:** 15-30 minutes per source

### Option 2: Prepare First

**If you need to gather data:**
1. Identify your vendors
2. Request price lists (CSV/Excel) or API access
3. Collect vendor contacts
4. Plan multi-region setup
5. Return to Option 1 when ready

**Time required:** Days to weeks (vendor-dependent)

### Option 3: Stay with Test Data

**If you want to learn the system first:**
1. Continue using test data
2. Explore web UI features
3. Test matching workflow
4. Generate reports
5. Add real sources when comfortable

**Benefits:** Risk-free learning environment

---

## Support Resources

### Documentation
- **Configuration guide:** `docs/DATA_SOURCES_GUIDE.md`
- **Template file:** `config/pipeline_sources_template.yaml`
- **Real examples:** `config/pipeline_sources_examples.yaml`

### Common Vendor Contacts
- **RS Components API:** api-support@rs-components.com
- **Farnell API:** apisupport@element14.com
- **OBO Bettermann:** verkauf@obo.de

### Testing Commands
```bash
# Validate config syntax
python scripts/validate_config.py

# Test single source
docker exec bimcalckm-app-1 python -m bimcalc.cli sync-prices --source name

# View results
open http://localhost:8001/pipeline
```

---

## What Happens When You Add Sources

### First Import
1. Pipeline reads your configuration
2. Connects to source (file/API/FTP)
3. Validates data format
4. Imports price records
5. Creates initial SCD Type-2 records (all `is_current = true`)
6. Logs success/failure to `data_sync_log`

### Subsequent Imports
1. Reads new data from source
2. Compares with current prices
3. **Price unchanged:** No action
4. **Price changed:**
   - Closes old record (`valid_to = now()`, `is_current = false`)
   - Creates new record (`valid_from = now()`, `is_current = true`)
5. **New item:** Creates new record
6. **Item removed:** Closes record (expires)

### Result
- ✅ Complete price history
- ✅ Point-in-time queries
- ✅ Audit trail
- ✅ Source attribution
- ✅ No data loss

---

## Summary

### You Have
- ✅ Working pipeline system
- ✅ Test data source configured
- ✅ Multi-region support ready
- ✅ Comprehensive documentation
- ✅ Template configurations
- ✅ Web UI monitoring

### You Can
- ✅ Add CSV/Excel sources (5 min)
- ✅ Add API sources (15 min)
- ✅ Configure multiple regions
- ✅ Test sources individually
- ✅ Monitor import status
- ✅ Track price history

### You Need
- 📋 Vendor price lists (CSV/Excel)
- 🔑 API credentials (if using APIs)
- 🌍 Region information
- 📊 Column mappings (CSV headers → BIMCalc fields)

---

## Ready When You Are!

**The system is ready to accept production data sources whenever you want to add them.**

No pressure - the test data works perfectly for learning and testing. Add real sources when you're ready!

---

**Questions to consider:**

1. **Do you have price lists ready?**
   - CSV/Excel files from vendors?
   - Where are they located?

2. **Do you have API access?**
   - RS Components, Farnell, etc.?
   - Do you have API keys?

3. **What regions do you need?**
   - UK, IE, DE, or others?
   - Multiple regions simultaneously?

4. **What's your priority?**
   - Get one source working ASAP?
   - Plan comprehensive setup?
   - Stay with test data for now?

**Let me know how you'd like to proceed!**

---

**Status:** ✅ Ready for Production Sources
**Next:** Your choice - add sources or continue exploring
**Support:** Check `docs/DATA_SOURCES_GUIDE.md` for detailed help

