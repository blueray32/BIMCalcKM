# API Integration Guide

**BIMCalc API Data Source Integration**
*From Demo to Production APIs*

---

## Overview

This guide shows you how to integrate vendor APIs into the BIMCalc pipeline system. We'll use the working **Demo API** as a starting point and show you how to adapt it for real vendor APIs like RS Components, Farnell, and others.

---

## Table of Contents

1. [Understanding the Demo API](#understanding-the-demo-api)
2. [How API Importers Work](#how-api-importers-work)
3. [Adapting for Real APIs](#adapting-for-real-apis)
4. [Common Patterns](#common-patterns)
5. [Testing and Debugging](#testing-and-debugging)
6. [Examples by Vendor](#examples-by-vendor)

---

## Understanding the Demo API

### What the Demo API Does

The Demo API (`demo_api_multi_region`) is currently running and has successfully imported **30 price items** across **3 regions** (UK, IE, DE).

**Current Status:**
```
Source: demo_api_multi_region
Status: SUCCESS
Records: 30 inserted (10 items × 3 regions)
Duration: < 1 second
```

**Sample Data Generated:**
```
Region | Items | Currency | Example Product
-------|-------|----------|----------------
UK     | 10    | GBP      | Cable Tray Elbow 90° 200x50mm [UK] - £42.50
IE     | 10    | EUR      | Cable Tray Elbow 90° 200x50mm [IE] - €46.00
DE     | 10    | EUR      | Cable Tray Elbow 90° 200x50mm [DE] - €44.00
```

### Demo API Features

The Demo API demonstrates:

1. **Multi-region support** - One source, multiple regions
2. **Pagination** - Splitting data into pages
3. **Rate limiting** - Simulating API delays
4. **Realistic data** - Actual electrical/MEP product types
5. **No HTTP calls** - Perfect for learning and testing

### Demo API Code Structure

```python
# Location: bimcalc/pipeline/importers/demo_api_importer.py

class DemoAPIImporter(BaseImporter):
    async def fetch_data(self) -> AsyncIterator[PriceRecord]:
        # 1. Read configuration
        regions = self._get_config_value("regions", ["UK"])

        # 2. Generate data for each region
        for region in regions:
            currency = self._get_currency_for_region(region)

            # 3. Simulate pagination
            for page in pages:
                # 4. Simulate API delay
                await asyncio.sleep(simulate_delay)

                # 5. Yield price records
                for product in page_products:
                    yield self._create_price_record(product, region, currency)
```

---

## How API Importers Work

### The Import Lifecycle

```
1. Configuration Loading
   ↓
2. Importer Initialization
   ↓
3. Data Fetching (your fetch_data() method)
   ↓
4. SCD Type-2 Processing
   ↓
5. Database Storage
   ↓
6. Results Logging
```

### Base Importer Contract

Every API importer must:

```python
from bimcalc.pipeline.base_importer import BaseImporter
from bimcalc.pipeline.types import PriceRecord

class YourAPIImporter(BaseImporter):
    async def fetch_data(self) -> AsyncIterator[PriceRecord]:
        """Fetch and yield price records from your API.

        This is the ONLY method you need to implement!
        """
        # Your API logic here
        yield PriceRecord(...)
```

### PriceRecord Format

Every record you yield must include:

```python
PriceRecord(
    item_code="VENDOR-PART-123",      # Required: Unique part number
    region="UK",                        # Required: Region code
    classification_code=66,             # Required: OmniClass code
    description="Cable Tray Elbow",    # Required: Product description
    unit="ea",                         # Required: Unit (ea, m, kg, etc.)
    unit_price=Decimal("42.50"),       # Required: Price as Decimal
    currency="GBP",                    # Required: Currency code
    source_currency="GBP",             # Required: Original currency
    sku="VENDOR-SKU",                  # Optional: SKU if different
    vendor_id="vendor_name",           # Optional: Vendor identifier
    source_name=self.source_name,      # Required: From config
)
```

---

## Adapting for Real APIs

### Step 1: Copy the Demo API Template

```bash
# Create your vendor-specific importer
cp bimcalc/pipeline/importers/demo_api_importer.py \
   bimcalc/pipeline/importers/your_vendor_importer.py
```

### Step 2: Modify for Real HTTP Calls

Replace the demo data generation with real API calls:

```python
import aiohttp
from typing import AsyncIterator

class YourVendorImporter(BaseImporter):
    async def fetch_data(self) -> AsyncIterator[PriceRecord]:
        # Get config
        api_url = self._get_config_value("api_url", required=True)
        api_key = self._get_config_value("api_key", required=True)
        region = self._get_config_value("region", required=True)

        # Set up HTTP session
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Accept": "application/json",
        }

        async with aiohttp.ClientSession(headers=headers) as session:
            # Fetch from API
            async with session.get(f"{api_url}/products") as response:
                response.raise_for_status()
                data = await response.json()

                # Parse and yield records
                for item in data["products"]:
                    yield self._parse_product(item, region)

    def _parse_product(self, item: dict, region: str) -> PriceRecord:
        """Parse vendor-specific format to PriceRecord."""
        return PriceRecord(
            item_code=item["partNumber"],
            region=region,
            classification_code=self._map_category(item["category"]),
            description=item["title"],
            unit=item["salesUnit"],
            unit_price=Decimal(str(item["price"])),
            currency=item["currency"],
            source_currency=item["currency"],
            sku=item["sku"],
            vendor_id="your_vendor",
            source_name=self.source_name,
        )
```

### Step 3: Add Pagination Support

Most APIs use pagination. Here's the pattern:

```python
async def fetch_data(self) -> AsyncIterator[PriceRecord]:
    page = 1
    has_more = True

    while has_more:
        # Fetch one page
        data = await self._fetch_page(page)

        # Yield records
        for item in data["products"]:
            yield self._parse_product(item)

        # Check if more pages exist
        has_more = len(data["products"]) > 0
        page += 1

        # Rate limiting
        await asyncio.sleep(0.1)
```

### Step 4: Handle Rate Limiting

Respect vendor rate limits:

```python
import asyncio

async def fetch_data(self) -> AsyncIterator[PriceRecord]:
    rate_limit = self._get_config_value("rate_limit_delay", 0.2)

    for batch in batches:
        # Fetch batch
        records = await self._fetch_batch(batch)

        for record in records:
            yield record

        # Wait between requests
        await asyncio.sleep(rate_limit)
```

### Step 5: Add Error Handling

Handle API errors gracefully:

```python
async def fetch_data(self) -> AsyncIterator[PriceRecord]:
    try:
        async with aiohttp.ClientSession() as session:
            # API calls...
            pass

    except aiohttp.ClientError as e:
        self.logger.error(f"API connection error: {e}")
        raise  # Let orchestrator handle it

    except Exception as e:
        self.logger.error(f"Unexpected error: {e}", exc_info=True)
        raise
```

### Step 6: Register Your Importer

Add to `config_loader.py`:

```python
# In bimcalc/pipeline/config_loader.py

def _create_importer(source_config: dict) -> BaseImporter:
    importer_type = source_config.get("type")

    # ... existing types ...

    elif importer_type == "your_vendor":
        from bimcalc.pipeline.importers.your_vendor_importer import YourVendorImporter
        return YourVendorImporter(source_name, source_config["config"])
```

### Step 7: Add Configuration

Add to `config/pipeline_sources.yaml`:

```yaml
sources:
  - name: your_vendor_production
    type: your_vendor
    enabled: true
    config:
      api_url: https://api.vendor.com/v1
      api_key: ${YOUR_VENDOR_API_KEY}  # From environment
      region: UK
      rate_limit_delay: 0.2  # seconds between requests
```

---

## Common Patterns

### Pattern 1: Multi-Region from Single API

**Demo API does this!** Look at the code:

```python
# One API, multiple regions
for region in regions:
    currency = self._get_currency_for_region(region)
    for product in products:
        yield self._create_price_record(product, region, currency)
```

### Pattern 2: API Key from Environment

Never hardcode API keys!

```yaml
# In config
api_key: ${VENDOR_API_KEY}
```

```python
# In code
import os
api_key = self._get_config_value("api_key")
# If it starts with ${, it's an env var name
if api_key.startswith("${") and api_key.endswith("}"):
    env_var = api_key[2:-1]
    api_key = os.environ.get(env_var)
    if not api_key:
        raise ValueError(f"Environment variable {env_var} not set")
```

### Pattern 3: Batch Requests

Fetch multiple items per request:

```python
async def fetch_data(self) -> AsyncIterator[PriceRecord]:
    batch_size = self._get_config_value("batch_size", 100)

    offset = 0
    while True:
        url = f"{api_url}?limit={batch_size}&offset={offset}"
        data = await self._fetch_url(url)

        if not data["products"]:
            break

        for product in data["products"]:
            yield self._parse_product(product)

        offset += len(data["products"])
```

### Pattern 4: Authentication Patterns

**Bearer Token:**
```python
headers = {"Authorization": f"Bearer {api_key}"}
```

**Basic Auth:**
```python
auth = aiohttp.BasicAuth(username, password)
async with session.get(url, auth=auth) as response:
    ...
```

**API Key in Header:**
```python
headers = {"X-API-Key": api_key}
```

**API Key in Query:**
```python
params = {"apikey": api_key}
async with session.get(url, params=params) as response:
    ...
```

---

## Testing and Debugging

### Test with Demo API First

Before writing any code, run the demo:

```bash
# Check it's working
docker exec bimcalckm-app-1 python -m bimcalc.cli sync-prices

# View results
docker exec bimcalc-postgres psql -U bimcalc -d bimcalc -c \
  "SELECT region, COUNT(*) FROM price_items
   WHERE source_name = 'demo_api_multi_region'
   GROUP BY region;"
```

### Test New Importer in Isolation

Create a test script:

```python
# test_your_api.py
import asyncio
from bimcalc.pipeline.importers.your_vendor_importer import YourVendorImporter

async def test():
    config = {
        "api_url": "https://api.vendor.com",
        "api_key": "test_key",
        "region": "UK",
    }

    importer = YourVendorImporter("test_source", config)

    count = 0
    async for record in importer.fetch_data():
        print(f"Got: {record.item_code} - {record.description}")
        count += 1
        if count >= 5:  # Just test first 5
            break

asyncio.run(test())
```

### Dry Run Mode

Test without writing to database:

```bash
docker exec bimcalckm-app-1 python -m bimcalc.cli sync-prices --dry-run
```

### Check Logs

```bash
# Pipeline logs
tail -f logs/pipeline.log

# Container logs
docker logs bimcalckm-app-1 --tail 100 -f
```

### Debug SQL Queries

```bash
# Check what was inserted
docker exec bimcalc-postgres psql -U bimcalc -d bimcalc -c \
  "SELECT item_code, region, description, unit_price, currency
   FROM price_items
   WHERE source_name = 'your_source_name'
   AND is_current = true
   LIMIT 10;"
```

---

## Examples by Vendor

### Example 1: RS Components UK

```python
# rs_components_importer.py
class RSComponentsImporter(BaseImporter):
    async def fetch_data(self) -> AsyncIterator[PriceRecord]:
        api_key = self._get_config_value("api_key", required=True)

        headers = {"x-api-key": api_key}

        async with aiohttp.ClientSession(headers=headers) as session:
            page = 0

            while True:
                url = f"https://api.rs-online.com/v1/products/search"
                params = {
                    "searchTerm": "*",
                    "offset": page * 100,
                    "rows": 100,
                }

                async with session.get(url, params=params) as resp:
                    resp.raise_for_status()
                    data = await resp.json()

                    if not data.get("products"):
                        break

                    for product in data["products"]:
                        yield PriceRecord(
                            item_code=product["stockNumber"],
                            region="UK",
                            classification_code=9999,  # Map category
                            description=product["productName"],
                            unit="ea",
                            unit_price=Decimal(str(product["unitPrice"])),
                            currency="GBP",
                            source_currency="GBP",
                            sku=product["stockNumber"],
                            vendor_id="rs_components",
                            source_name=self.source_name,
                        )

                page += 1
                await asyncio.sleep(0.2)  # 5 req/sec limit
```

**Configuration:**
```yaml
- name: rs_components_uk
  type: rs_components
  enabled: true
  config:
    api_key: ${RS_API_KEY}
    region: UK
    rate_limit_delay: 0.2
```

### Example 2: Farnell/element14

```python
class FarnellImporter(BaseImporter):
    async def fetch_data(self) -> AsyncIterator[PriceRecord]:
        api_key = self._get_config_value("api_key", required=True)

        headers = {"Authorization": f"Bearer {api_key}"}

        async with aiohttp.ClientSession(headers=headers) as session:
            offset = 0

            while True:
                url = "https://api.element14.com/catalog/products"
                params = {"offset": offset, "limit": 100}

                async with session.get(url, params=params) as resp:
                    resp.raise_for_status()
                    data = await resp.json()

                    products = data.get("products", [])
                    if not products:
                        break

                    for product in products:
                        # Farnell has nested pricing structure
                        prices = product.get("prices", [])
                        if not prices:
                            continue

                        # Use first price tier
                        price_info = prices[0]

                        yield PriceRecord(
                            item_code=product["sku"],
                            region=self._get_config_value("region"),
                            classification_code=9999,
                            description=product["displayName"],
                            unit="ea",
                            unit_price=Decimal(str(price_info["cost"])),
                            currency=price_info["currency"],
                            source_currency=price_info["currency"],
                            sku=product["sku"],
                            vendor_id="farnell",
                            source_name=self.source_name,
                        )

                offset += len(products)
                await asyncio.sleep(0.1)
```

### Example 3: Simple REST API

For any standard REST API:

```python
class GenericRESTImporter(BaseImporter):
    async def fetch_data(self) -> AsyncIterator[PriceRecord]:
        base_url = self._get_config_value("api_url", required=True)
        api_key = self._get_config_value("api_key")
        region = self._get_config_value("region", required=True)

        headers = {}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

        async with aiohttp.ClientSession(headers=headers) as session:
            async with session.get(f"{base_url}/products") as resp:
                resp.raise_for_status()
                data = await resp.json()

                for item in data:
                    yield PriceRecord(
                        item_code=item.get("code") or item.get("id"),
                        region=region,
                        classification_code=int(item.get("category", 9999)),
                        description=item["description"],
                        unit=item.get("unit", "ea"),
                        unit_price=Decimal(str(item["price"])),
                        currency=item.get("currency", "EUR"),
                        source_currency=item.get("currency", "EUR"),
                        sku=item.get("sku"),
                        vendor_id=self._get_config_value("vendor_id"),
                        source_name=self.source_name,
                    )
```

---

## Quick Start Checklist

When integrating a new vendor API:

- [ ] Review vendor API documentation
- [ ] Get API key/credentials
- [ ] Look at Demo API code (`demo_api_importer.py`)
- [ ] Copy demo as template
- [ ] Replace fake data with real HTTP calls
- [ ] Map vendor fields to PriceRecord format
- [ ] Add pagination if needed
- [ ] Add rate limiting
- [ ] Test with small dataset first
- [ ] Register in `config_loader.py`
- [ ] Add to `pipeline_sources.yaml`
- [ ] Test with `--dry-run`
- [ ] Run full import
- [ ] Verify data in database
- [ ] Check web UI displays correctly
- [ ] Enable in production

---

## Getting Help

**Documentation:**
- Demo API code: `bimcalc/pipeline/importers/demo_api_importer.py`
- Base importer: `bimcalc/pipeline/base_importer.py`
- Config loader: `bimcalc/pipeline/config_loader.py`
- Configuration: `config/pipeline_sources.yaml`

**Testing:**
```bash
# View demo data
open http://localhost:8001/prices

# Check database
docker exec bimcalc-postgres psql -U bimcalc -d bimcalc -c \
  "SELECT * FROM price_items WHERE source_name = 'demo_api_multi_region' LIMIT 5;"

# View logs
tail -f logs/pipeline.log
```

---

## Summary

1. **Start with Demo API** - It's working now with 30 records across 3 regions
2. **Copy the pattern** - Use demo as your template
3. **Replace data source** - Swap fake data for real API calls
4. **Test incrementally** - Start small, expand gradually
5. **Monitor results** - Check logs, database, and web UI

The demo API proves your pipeline works. Now you just need to adapt it for your vendor's specific API format!

---

**Ready to integrate your first real API?** Start with the Demo API code and modify step by step!
