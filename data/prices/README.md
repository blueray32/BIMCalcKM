# Price Lists Directory

## Purpose
This directory stores CSV/Excel price lists from suppliers for manual import into BIMCalc.

## Structure
```
data/prices/
├── README.md (this file)
├── active/          # Current price lists in use
├── archive/         # Historical price lists
└── templates/       # Example formats for suppliers
```

## How to Add a Price List

### 1. Get CSV from Supplier
Request from your account manager:
- Format: CSV or Excel
- Encoding: UTF-8 preferred
- Columns needed: SKU/Item Code, Description, Price, Currency, Unit

### 2. Place File Here
```bash
# Copy downloaded file to active directory
cp ~/Downloads/supplier_pricelist.csv data/prices/active/

# Or for this directory
cp ~/Downloads/supplier_pricelist.csv data/prices/
```

### 3. Configure Pipeline
Edit: `config/pipeline_sources.yaml`

Add new source:
```yaml
- name: supplier_name_YYYYMM
  type: csv
  enabled: true
  config:
    file_path: /app/data/prices/active/supplier_pricelist.csv
    region: IE  # or UK, DE, etc.
    vendor_id: SUPPLIER_NAME
    column_mapping:
      "Product Code": "item_code"
      "Description": "description"
      "Price": "unit_price"
      "Currency": "currency"
      "Unit": "unit"
```

### 4. Import
```bash
# Test configuration
docker exec bimcalckm-app-1 python scripts/validate_config.py

# Import prices
docker exec bimcalckm-app-1 python -m bimcalc.cli sync-prices --source supplier_name_YYYYMM

# Check results
open http://localhost:8001/pipeline
```

## File Naming Convention

Use this format:
```
{supplier}_{region}_{YYYYMMDD}.csv

Examples:
- rexel_ie_20251114.csv
- cef_uk_20251114.csv
- kellihers_ie_20251101.csv
```

## Archiving Old Files

After successful import:
```bash
mv data/prices/active/old_file.csv data/prices/archive/
```

Keep for audit trail and price history analysis.
