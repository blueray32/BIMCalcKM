# Manual CSV Import - Quick Start Guide

**Status:** ✅ Ready to use
**Setup Time:** 10 minutes for first import
**Location:** `/Users/ciarancox/BIMCalcKM/data/prices/`

---

## Overview

This guide shows you how to manually import supplier price lists into BIMCalc using CSV files.

**What you need:**
- CSV or Excel file from supplier
- 10 minutes
- Supplier's account manager email (to request price lists)

---

## Step 1: Request Price Lists from Suppliers

### Quick Email Template

Copy/paste this and send to your main suppliers:

```
Subject: Request for Product Price List

Hi [Account Manager Name],

We're setting up a new cost estimation system for our BIM projects and
would like to include your products.

Could you please send us a CSV or Excel export of your current price list
with these columns?

Required:
- Product Code
- Description
- Price
- Currency
- Unit

This is for our internal estimating only. Even a one-time export would be
helpful to get started.

Thanks,
[Your Name]
```

**More templates:** See `data/prices/EMAIL_TEMPLATES.md`

---

## Step 2: When You Receive a Price List

### A. Save the File

```bash
# 1. Download the file from email to your Downloads folder
# 2. Open Terminal and run:

cd /Users/ciarancox/BIMCalcKM

# 3. Copy to BIMCalc data directory
cp ~/Downloads/supplier_pricelist.csv data/prices/active/

# 4. Rename with date (good practice)
mv data/prices/active/supplier_pricelist.csv data/prices/active/rexel_ie_20251114.csv
```

**File naming:** `{supplier}_{region}_{YYYYMMDD}.csv`

Examples:
- `rexel_ie_20251114.csv`
- `cef_uk_20251114.csv`
- `kellihers_ie_20251101.csv`

### B. Check the File

```bash
# View first 10 rows to see column names
head -10 data/prices/active/rexel_ie_20251114.csv

# Count total rows
wc -l data/prices/active/rexel_ie_20251114.csv
```

**Look for:**
- ✅ Header row with column names
- ✅ Data rows with products
- ✅ Comma or semicolon separated
- ✅ Readable text (not binary/encoded)

---

## Step 3: Configure the Import

### Edit Pipeline Configuration

```bash
# Open the configuration file
nano config/pipeline_sources.yaml
```

### Add Your Source

Scroll to the `sources:` section and add:

```yaml
  # YOUR NEW SOURCE - Add this block
  - name: rexel_ie_nov2024
    type: csv
    enabled: true
    config:
      file_path: /app/data/prices/active/rexel_ie_20251114.csv
      region: IE
      vendor_id: rexel_ireland

      # MAP YOUR CSV COLUMNS TO BIMCALC FIELDS
      # Format: "CSV Column Name": "bimcalc_field"
      column_mapping:
        "Product Code": "item_code"        # Required
        "Description": "description"       # Required
        "Price": "unit_price"              # Required
        "Currency": "currency"             # Required (EUR, GBP, etc.)
        "Unit": "unit"                     # Required (ea, m, m2, etc.)
        "Category": "classification_code"  # Optional
        "Width": "width_mm"                # Optional
        "Height": "height_mm"              # Optional
        "Diameter": "dn_mm"                # Optional
        "Material": "material"             # Optional
```

**Important:**
- Column names must **exactly match** your CSV headers (case-sensitive)
- Use `/app/data/prices/...` (Docker path, not local path)
- Change `region` to match supplier location (IE, UK, DE, etc.)

### Save and Exit
- Press `Ctrl+O` to save
- Press `Enter` to confirm
- Press `Ctrl+X` to exit

---

## Step 4: Validate Configuration

```bash
# Check configuration syntax
docker exec bimcalckm-app-1 python scripts/validate_config.py
```

**Expected output:**
```
✅ Configuration valid
✅ Found 2 sources (1 test, 1 production)
✅ All file paths accessible
✅ Column mappings complete
```

**If you see errors:**
- Check CSV column names match exactly
- Check file path is correct
- Check YAML indentation (use spaces, not tabs)

---

## Step 5: Import the Prices

### Test Import (Dry Run)

```bash
# Import just your new source
docker exec bimcalckm-app-1 python -m bimcalc.cli sync-prices --source rexel_ie_nov2024
```

**Watch for:**
```
✓ Connected to database
✓ Processing: rexel_ie_nov2024
✓ Read 1,234 rows from CSV
✓ Inserted 1,150 items
✓ Updated 84 items
✓ Skipped 0 items (errors)
✓ Duration: 2.3 seconds
```

### Check Results

**Option 1: Web UI**
```bash
open http://localhost:8001/pipeline
```

**Option 2: Database Query**
```bash
docker exec bimcalc-postgres psql -U bimcalc -d bimcalc -c "
  SELECT
    source_name,
    COUNT(*) as items,
    MIN(valid_from) as imported_at
  FROM price_items
  WHERE is_current = true
  GROUP BY source_name;
"
```

Expected output:
```
     source_name     | items | imported_at
---------------------+-------+-------------
 test_vendor         |    10 | 2025-11-13
 rexel_ireland       |  1150 | 2025-11-14  ← Your new data!
```

---

## Step 6: Verify Data Quality

### Check Sample Records

```bash
docker exec bimcalc-postgres psql -U bimcalc -d bimcalc -c "
  SELECT
    item_code,
    description,
    unit_price,
    currency,
    unit
  FROM price_items
  WHERE source_name = 'rexel_ireland'
    AND is_current = true
  LIMIT 10;
"
```

### Look for Issues

```bash
# Items without classification
docker exec bimcalc-postgres psql -U bimcalc -d bimcalc -c "
  SELECT COUNT(*)
  FROM price_items
  WHERE source_name = 'rexel_ireland'
    AND classification_code IS NULL
    AND is_current = true;
"

# Items with zero/negative price
docker exec bimcalc-postgres psql -U bimcalc -d bimcalc -c "
  SELECT COUNT(*)
  FROM price_items
  WHERE source_name = 'rexel_ireland'
    AND unit_price <= 0
    AND is_current = true;
"
```

---

## Step 7: Archive Old Price List (Optional)

After successful import:

```bash
# Move imported file to archive
mv data/prices/active/rexel_ie_20251114.csv data/prices/archive/

# Keep directory clean
# But keep archives for audit trail
```

---

## Adding More Suppliers

Repeat Steps 1-6 for each new supplier:

1. Request price list via email
2. Save to `data/prices/active/`
3. Add new source block to `config/pipeline_sources.yaml`
4. Run `sync-prices --source supplier_name`
5. Verify in web UI or database

**Target:** 3-5 suppliers in first month

---

## Common Issues & Solutions

### Issue: "Column not found in CSV"

**Error:** `KeyError: 'Product Code'`

**Solution:**
1. Check exact column name in CSV:
   ```bash
   head -1 data/prices/active/your_file.csv
   ```
2. Update `column_mapping` to match exactly
3. Column names are case-sensitive!

---

### Issue: "File not found"

**Error:** `FileNotFoundError: /app/data/prices/file.csv`

**Solution:**
1. Check file exists:
   ```bash
   ls -la data/prices/active/
   ```
2. Check file path uses `/app/data/...` not `/Users/...`
3. Make sure file is in `active/` subdirectory

---

### Issue: "No data imported"

**Symptoms:** Import runs but 0 records added

**Solutions:**
1. Check file isn't empty:
   ```bash
   wc -l data/prices/active/your_file.csv
   ```
2. Check file encoding:
   ```bash
   file -I data/prices/active/your_file.csv
   ```
   Should say: `charset=utf-8` or `charset=us-ascii`
3. Check for duplicate headers or footer rows
4. Enable debug logging:
   ```bash
   export LOG_LEVEL=DEBUG
   ```

---

### Issue: "Character encoding errors"

**Error:** `UnicodeDecodeError`

**Solution:**
Open CSV in Excel/Numbers and "Save As" with UTF-8 encoding:
1. Open file in Excel
2. File → Save As
3. Format: CSV UTF-8 (Comma delimited)
4. Save

---

## Monthly Update Process

When supplier sends updated price list:

```bash
# 1. Save new file with new date
cp ~/Downloads/new_pricelist.csv data/prices/active/rexel_ie_20251214.csv

# 2. Update file_path in config/pipeline_sources.yaml
# Change: /app/data/prices/active/rexel_ie_20251114.csv
# To:     /app/data/prices/active/rexel_ie_20251214.csv

# 3. Run import
docker exec bimcalckm-app-1 python -m bimcalc.cli sync-prices --source rexel_ie_nov2024

# 4. Archive old file
mv data/prices/active/rexel_ie_20251114.csv data/prices/archive/
```

**SCD Type-2 Magic:**
- Old prices are automatically closed (valid_to = now)
- New prices become active (valid_from = now, is_current = true)
- Historical pricing preserved for audit trail
- Can run reports "as of" any date

---

## Next Steps

### Week 1: Get First 3 Suppliers
- [ ] Email Rexel for price list
- [ ] Email CEF for price list
- [ ] Email Kellihers for price list

### Week 2: Import & Validate
- [ ] Import all 3 price lists
- [ ] Verify data quality
- [ ] Check 500+ products imported

### Week 3: Test Matching
- [ ] Import a small Revit schedule (10-20 items)
- [ ] Run matching pipeline
- [ ] Review matches in web UI
- [ ] Check auto-match vs manual review split

### Week 4: Optimize
- [ ] Request monthly updates from suppliers
- [ ] Set up email automation (future)
- [ ] Add 2-3 more suppliers

---

## Support Files

All in `data/prices/` directory:

- **README.md** - Directory structure and conventions
- **EMAIL_TEMPLATES.md** - 6+ email templates for suppliers
- **templates/ideal_format.csv** - Show suppliers ideal format

---

## Quick Reference

### Import Commands

```bash
# Import single source
docker exec bimcalckm-app-1 python -m bimcalc.cli sync-prices --source SOURCE_NAME

# Import all enabled sources
docker exec bimcalckm-app-1 python -m bimcalc.cli sync-prices

# View pipeline status
docker exec bimcalckm-app-1 python -m bimcalc.cli pipeline-status

# Web UI
open http://localhost:8001/pipeline
open http://localhost:8001/prices
```

### File Locations

```bash
# Price list files
/Users/ciarancox/BIMCalcKM/data/prices/active/

# Configuration
/Users/ciarancox/BIMCalcKM/config/pipeline_sources.yaml

# Email templates
/Users/ciarancox/BIMCalcKM/data/prices/EMAIL_TEMPLATES.md
```

---

**Ready to start!**

Send those emails to your suppliers now. Most respond within 1-2 days with price lists.

Good luck! 🚀
