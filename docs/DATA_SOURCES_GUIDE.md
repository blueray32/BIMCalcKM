# BIMCalc Data Sources Configuration Guide

**Version:** 1.0
**Last Updated:** November 13, 2024
**For:** Multi-Region Setup

---

## Table of Contents

1. [Overview](#overview)
2. [Quick Start](#quick-start)
3. [Data Source Types](#data-source-types)
4. [Configuration Steps](#configuration-steps)
5. [Region-Specific Setup](#region-specific-setup)
6. [Testing Your Sources](#testing-your-sources)
7. [Common Sources](#common-sources)
8. [Troubleshooting](#troubleshooting)

---

## Overview

BIMCalc's pipeline supports multiple data sources across different regions. Each source:
- Runs independently (failures are isolated)
- Updates prices using SCD Type-2 (full history)
- Tracks source attribution and timestamps
- Logs all operations for monitoring

### Supported Source Types

| Type | Description | Use Case | Setup Time |
|------|-------------|----------|------------|
| **CSV** | Local CSV/Excel files | Manufacturer price lists | 5 minutes |
| **API** | REST API endpoints | Distributor catalogs | 15 minutes |
| **FTP** | Automated FTP download | Scheduled vendor feeds | 20 minutes |
| **Email** | Parse attachments | Email-based updates | 30 minutes |
| **DATANORM** | German standard format | German manufacturers | 10 minutes |
| **BMEcat** | European XML standard | Multi-vendor catalogs | 15 minutes |

---

## Quick Start

### 1. Understand Current Configuration

**Your current setup:**
```yaml
Location: config/pipeline_sources.yaml
Active sources: 1 (test_prices_local)
Status: Working (test data only)
```

**View current config:**
```bash
cat config/pipeline_sources.yaml
```

### 2. Add Your First Real Source

**Choose based on what you have:**

#### Option A: CSV/Excel File from Manufacturer

```yaml
sources:
  - name: my_vendor_prices
    type: csv
    enabled: true
    config:
      file_path: /path/to/vendor_pricelist.csv
      region: UK
      vendor_id: MY_VENDOR
      column_mapping:
        "Product Code": "item_code"
        "Description": "description"
        "Price": "unit_price"
        "Currency": "currency"
```

#### Option B: Distributor API

```yaml
sources:
  - name: rs_components_uk
    type: api
    enabled: true
    config:
      api_url: https://api.rs-online.com/v1/catalogue/products
      api_key_env: RS_API_KEY
      region: UK
      vendor_id: RS_COMPONENTS
```

### 3. Test Your Source

```bash
# Test configuration syntax
python scripts/validate_config.py

# Run pipeline (processes all enabled sources)
docker exec bimcalckm-app-1 python -m bimcalc.cli sync-prices

# Check results
docker exec bimcalckm-app-1 python scripts/dashboard.py
```

---

## Data Source Types

### 1. CSV/Excel Files

**Best for:**
- Manufacturer quarterly price lists
- One-time imports
- Small to medium datasets (<100k items)

**Configuration:**
```yaml
- name: obo_cables_q1_2025
  type: csv
  enabled: true
  config:
    file_path: /data/prices/obo_q1_2025.csv
    region: DE
    vendor_id: OBO_BETTERMANN

    # Map CSV columns to BIMCalc fields
    column_mapping:
      "Article Number": "item_code"
      "Description": "description"
      "Product Group": "classification_code"
      "Price": "unit_price"
      "Currency": "currency"
      "Unit": "unit"
      "Width (mm)": "width_mm"
      "Height (mm)": "height_mm"
      "Material": "material"

    # Optional: Skip header rows
    skip_rows: 1

    # Optional: Filter rows
    filters:
      - column: "Status"
        value: "Active"
```

**File location options:**
1. **Local disk:** `/Users/username/data/prices/file.csv`
2. **Docker volume:** `/data/prices/file.csv` (mounted in docker-compose.yml)
3. **Network drive:** `/mnt/network/prices/file.csv`

### 2. REST API

**Best for:**
- Real-time distributor pricing
- Large catalogs (>100k items)
- Frequent updates (daily/hourly)

**Configuration:**
```yaml
- name: rs_components_uk
  type: api
  enabled: true
  config:
    api_url: https://api.rs-online.com/v1/catalogue/products
    api_key_env: RS_API_KEY  # Load from environment
    region: UK
    vendor_id: RS_COMPONENTS

    # Rate limiting
    rate_limit: 10  # requests per second

    # Pagination
    pagination:
      page_size: 100
      max_pages: 1000

    # HTTP headers
    headers:
      Accept: application/json
      Content-Type: application/json

    # Map API response to PriceRecord
    field_mapping:
      stockNumber: "item_code"
      productDescription: "description"
      categoryCode: "classification_code"
      priceBreaks[0].price: "unit_price"
      currency: "currency"
      unitOfMeasure: "unit"
```

**Set API key:**
```bash
# Add to your environment
export RS_API_KEY="your_api_key_here"

# Or add to docker-compose.yml
environment:
  - RS_API_KEY=${RS_API_KEY}
```

### 3. FTP Downloads

**Best for:**
- Automated vendor feeds
- Scheduled updates (nightly)
- Large files (vendors push updates)

**Configuration:**
```yaml
- name: vendor_ftp_feed
  type: ftp
  enabled: true
  config:
    ftp_host: ftp.vendor.com
    ftp_user_env: FTP_USER
    ftp_password_env: FTP_PASSWORD
    ftp_path: /prices/latest.csv
    local_path: /data/prices/vendor_latest.csv
    region: UK
    vendor_id: VENDOR_NAME

    # Process as CSV after download
    column_mapping:
      # ... same as CSV configuration
```

### 4. Email Attachments

**Best for:**
- Manual vendor updates
- Irregular updates
- Small vendors without automation

**Configuration:**
```yaml
- name: vendor_email_updates
  type: email
  enabled: true
  config:
    imap_host: imap.gmail.com
    imap_user_env: EMAIL_USER
    imap_password_env: EMAIL_PASSWORD
    from_filter: vendor@example.com
    subject_filter: "Price Update"
    attachment_pattern: "*.csv"
    download_path: /data/prices/email_imports/
    region: UK
    vendor_id: VENDOR_NAME
```

### 5. DATANORM (Germany)

**Best for:**
- German manufacturers (OBO, DEHN, etc.)
- DATANORM 4.0 or 5.0 format
- Comprehensive product data

**Configuration:**
```yaml
- name: obo_datanorm
  type: datanorm
  enabled: true
  config:
    file_path: /data/prices/OBO_DATANORM.001
    region: DE
    vendor_id: OBO_BETTERMANN
    version: "5.0"  # DATANORM version
    encoding: "iso-8859-1"  # German encoding
```

### 6. BMEcat (European Standard)

**Best for:**
- Multi-vendor catalogs
- European manufacturers
- Rich product metadata

**Configuration:**
```yaml
- name: aggregator_bmecat
  type: bmecat
  enabled: true
  config:
    file_path: /data/prices/catalog.xml
    region: EU
    vendor_id: AGGREGATOR_NAME
    validate_xml: true
```

---

## Configuration Steps

### Step 1: Identify Your Data Sources

**What do you have?**
- [ ] Manufacturer CSV/Excel files
- [ ] Distributor API access
- [ ] Vendor FTP credentials
- [ ] Email-based price updates
- [ ] Aggregator service subscription

**Where are they located?**
- [ ] Local file system
- [ ] Network drive
- [ ] Cloud storage
- [ ] Email inbox
- [ ] FTP server

### Step 2: Prepare File Access

**For CSV/Excel files:**

```bash
# Create data directory
mkdir -p /Users/ciarancox/BIMCalcKM/data/prices

# Copy files
cp ~/Downloads/vendor_pricelist.csv data/prices/

# Or mount in Docker (edit docker-compose.yml)
volumes:
  - ./data:/data
```

**For API access:**

```bash
# Get API keys from vendors
# Store in environment variables
echo 'export RS_API_KEY="your_key"' >> ~/.zshrc
source ~/.zshrc

# Or add to docker-compose.yml
environment:
  - RS_API_KEY=${RS_API_KEY}
```

### Step 3: Configure pipeline_sources.yaml

**Edit configuration:**
```bash
nano config/pipeline_sources.yaml
```

**Add your source (example):**
```yaml
sources:
  # Keep existing test source for validation
  - name: test_prices_local
    type: csv
    enabled: true
    config:
      file_path: tests/fixtures/sample_prices.csv
      region: UK
      vendor_id: test_vendor
      column_mapping:
        # ... existing mapping

  # Add your real source
  - name: my_production_source
    type: csv
    enabled: true
    config:
      file_path: /data/prices/my_vendor.csv
      region: UK  # or IE, DE, FR, etc.
      vendor_id: MY_VENDOR
      column_mapping:
        "SKU": "item_code"
        "Description": "description"
        "Price": "unit_price"
        "Currency": "currency"
```

### Step 4: Validate Configuration

```bash
# Check syntax
python scripts/validate_config.py

# Expected output:
# ✅ Configuration valid
# ✅ 2 sources configured
# ✅ All file paths exist
# ✅ Column mappings valid
```

### Step 5: Test Individual Source

```bash
# Test just one source first
docker exec bimcalckm-app-1 python -m bimcalc.cli sync-prices --source my_production_source

# Check results
docker exec bimcalckm-app-1 python scripts/dashboard.py
```

### Step 6: Enable Full Pipeline

```bash
# Run all enabled sources
docker exec bimcalckm-app-1 python -m bimcalc.cli sync-prices

# Check web UI
open http://localhost:8001/pipeline
```

---

## Region-Specific Setup

### Multi-Region Configuration

**Your setup supports multiple regions:**

```yaml
sources:
  # UK sources
  - name: uk_distributor
    type: csv
    enabled: true
    config:
      file_path: /data/prices/uk_prices.csv
      region: UK
      vendor_id: UK_VENDOR
      # Prices in GBP

  # Irish sources
  - name: ireland_distributor
    type: csv
    enabled: true
    config:
      file_path: /data/prices/ie_prices.csv
      region: IE
      vendor_id: IE_VENDOR
      # Prices in EUR

  # German sources
  - name: german_manufacturer
    type: datanorm
    enabled: true
    config:
      file_path: /data/prices/de_datanorm.001
      region: DE
      vendor_id: DE_MANUFACTURER
      # Prices in EUR
```

### Currency Handling

**Automatic currency detection:**
- System reads `currency` column from each source
- Stores original currency (GBP, EUR, USD, etc.)
- SCD Type-2 tracks currency changes over time

**Multi-currency queries:**
```sql
-- Get prices in specific currency
SELECT * FROM price_items
WHERE currency = 'GBP' AND is_current = true;

-- Get prices for specific region
SELECT * FROM price_items
WHERE region = 'UK' AND is_current = true;
```

### Region Codes

| Region | Code | Currency | Notes |
|--------|------|----------|-------|
| United Kingdom | UK | GBP | |
| Ireland | IE | EUR | |
| Germany | DE | EUR | |
| France | FR | EUR | |
| Netherlands | NL | EUR | |
| Belgium | BE | EUR | |
| Spain | ES | EUR | |
| Italy | IT | EUR | |
| Europe (General) | EU | EUR | Multi-country |

---

## Testing Your Sources

### 1. Dry Run (Validation Only)

```bash
# Validate without importing
python scripts/validate_config.py

# Check:
# ✅ YAML syntax
# ✅ File paths exist
# ✅ Required fields present
# ✅ Column mappings complete
```

### 2. Single Source Test

```bash
# Import from one source only
docker exec bimcalckm-app-1 python -m bimcalc.cli sync-prices --source my_source_name

# Monitor output:
# - Records processed
# - Records inserted/updated
# - Errors encountered
# - Duration
```

### 3. Check Import Results

```bash
# View imported data
docker exec bimcalc-postgres psql -U bimcalc -d bimcalc -c "
  SELECT source_name, COUNT(*) as items, MIN(valid_from) as first_import
  FROM price_items
  WHERE is_current = true
  GROUP BY source_name;
"

# Expected output:
#   source_name    | items | first_import
# -----------------+-------+--------------
#   test_vendor    |    10 | 2025-11-13
#   MY_VENDOR      |   150 | 2025-11-14
```

### 4. Verify Data Quality

```bash
# Check for issues
docker exec bimcalc-postgres psql -U bimcalc -d bimcalc -c "
  -- Items without classification
  SELECT item_code, description, source_name
  FROM price_items
  WHERE classification_code IS NULL AND is_current = true
  LIMIT 10;

  -- Items with zero price
  SELECT item_code, unit_price, source_name
  FROM price_items
  WHERE unit_price <= 0 AND is_current = true
  LIMIT 10;
"
```

### 5. Monitor Pipeline Status

```bash
# Check pipeline dashboard
open http://localhost:8001/pipeline

# Or via CLI
docker exec bimcalckm-app-1 python -m bimcalc.cli pipeline-status

# View logs
docker logs bimcalckm-app-1 --tail 100
```

---

## Common Sources

### RS Components (UK)

**API Access:**
1. Sign up at https://uk.rs-online.com/
2. Request API key from account manager
3. Read API docs: https://docs.rs-online.com/

**Configuration:**
```yaml
- name: rs_components_uk
  type: api
  enabled: true
  config:
    api_url: https://api.rs-online.com/v1/catalogue/products
    api_key_env: RS_API_KEY
    region: UK
    vendor_id: RS_COMPONENTS
    rate_limit: 10
    field_mapping:
      stockNumber: "item_code"
      productDescription: "description"
      priceBreaks[0].price: "unit_price"
```

### Farnell (Element14)

**API Access:**
1. Sign up at https://www.element14.com/
2. Apply for API access
3. Docs: https://partner.element14.com/

**Configuration:**
```yaml
- name: farnell_uk
  type: api
  enabled: true
  config:
    api_url: https://api.element14.com/catalog/products
    api_key_env: FARNELL_API_KEY
    region: UK
    vendor_id: FARNELL
```

### OBO Bettermann (Germany)

**CSV Price List:**
1. Request from sales: verkauf@obo.de
2. Quarterly updates (Q1, Q2, Q3, Q4)
3. Format: DATANORM or CSV

**Configuration:**
```yaml
- name: obo_q1_2025
  type: csv
  enabled: true
  config:
    file_path: /data/prices/OBO_Q1_2025.csv
    region: DE
    vendor_id: OBO_BETTERMANN
    column_mapping:
      "Artikel-Nr": "item_code"
      "Bezeichnung": "description"
      "Preis": "unit_price"
```

### Trimble Luckins (UK Aggregator)

**API Access:**
1. Subscribe at https://www.trimble-luckins.com/
2. Covers 40+ UK manufacturers
3. Real-time pricing updates

**Configuration:**
```yaml
- name: trimble_luckins_uk
  type: api
  enabled: true
  config:
    api_url: https://api.trimble-luckins.com/v2/pricing
    api_key_env: LUCKINS_API_KEY
    region: UK
    vendor_id: TRIMBLE_LUCKINS
```

---

## Troubleshooting

### Issue: "File not found"

**Symptoms:** `FileNotFoundError` during pipeline run

**Solutions:**
1. Check file path is absolute
2. Check file exists:
   ```bash
   ls -la /data/prices/file.csv
   ```
3. Check Docker volume mount:
   ```bash
   docker exec bimcalckm-app-1 ls -la /data/prices/
   ```

### Issue: "API authentication failed"

**Symptoms:** `401 Unauthorized` or `403 Forbidden`

**Solutions:**
1. Verify API key is set:
   ```bash
   docker exec bimcalckm-app-1 env | grep API_KEY
   ```
2. Check key hasn't expired
3. Test API manually:
   ```bash
   curl -H "X-API-Key: $RS_API_KEY" https://api.rs-online.com/v1/catalogue/products
   ```

### Issue: "Column mapping error"

**Symptoms:** `KeyError: 'column_name'`

**Solutions:**
1. Check CSV headers match exactly:
   ```bash
   head -1 /data/prices/file.csv
   ```
2. Check for hidden characters (BOM):
   ```bash
   file /data/prices/file.csv
   hexdump -C /data/prices/file.csv | head
   ```
3. Try case-insensitive mapping

### Issue: "No data imported"

**Symptoms:** Pipeline runs but 0 records inserted

**Solutions:**
1. Check file isn't empty:
   ```bash
   wc -l /data/prices/file.csv
   ```
2. Check filters aren't too restrictive
3. Check encoding (should be UTF-8):
   ```bash
   file -i /data/prices/file.csv
   ```
4. Enable debug logging:
   ```bash
   export LOG_LEVEL=DEBUG
   ```

### Issue: "Rate limit exceeded"

**Symptoms:** `429 Too Many Requests`

**Solutions:**
1. Reduce `rate_limit` in config:
   ```yaml
   rate_limit: 5  # reduce from 10
   ```
2. Add delays between requests
3. Contact vendor for higher limits

---

## Next Steps

### Immediate

1. **Identify your sources** - List what you have available
2. **Start with one** - Configure and test single source
3. **Verify data** - Check quality and completeness
4. **Add more sources** - Scale up gradually

### Short Term

1. **Automate updates** - Enable pipeline schedule
2. **Monitor health** - Set up alerts
3. **Optimize performance** - Tune rate limits
4. **Document sources** - Track vendor contacts

### Long Term

1. **Add redundancy** - Multiple sources for critical items
2. **Currency conversion** - If multi-currency needed
3. **Price alerts** - Notify on significant changes
4. **Analytics** - Track price trends

---

## Support

**Need help configuring a specific source?**

1. Check examples: `config/pipeline_sources_examples.yaml`
2. Review vendor API docs
3. Test with sample data first
4. Enable debug logging: `export LOG_LEVEL=DEBUG`

**Common vendor contacts:**
- RS Components API: api-support@rs-components.com
- Farnell API: apisupport@element14.com
- OBO Bettermann: verkauf@obo.de

---

**Document Version:** 1.0
**Last Updated:** November 13, 2024
**Status:** Ready for Configuration

