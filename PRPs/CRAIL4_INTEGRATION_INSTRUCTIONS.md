# Crail4 AI Integration - Implementation Instructions for Codex

## Prerequisites & Context

**Goal**: Create an automated ETL pipeline to sync pricing data from Crail4 AI into BIMCalc's price database.

**Key Principles** (from CLAUDE.md):
- Auditability: Every € must be traceable to (Revit row, Price row, Mapping version)
- Deterministic reruns: Same inputs + same mappings + same timestamp ⇒ same result
- Classification-first blocking: Only match items with same classification codes
- Canonical key + Mapping Memory: Use normalized keys, persist human-approved links
- SCD Type-2 for mappings: One active row per (org_id, canonical_key)
- EU defaults: Currency EUR, VAT explicit

**Tech Stack**:
- Python 3.11+
- SQLAlchemy (async)
- FastAPI
- PostgreSQL/SQLite
- Existing BIMCalc models in `bimcalc/db/models.py`

---

## TASK 0: Fix Critical SQLite Bugs (MUST DO FIRST)

**Location**: `bimcalc/reporting/review_metrics.py`

**Problem**: Line 99 references CTE as `latest_results` but CTE is named `ranked_results`. Also has duplicate `mr.item_id` in SELECT clause.

**Fix Required**:
```python
# Line 77-101 in review_metrics.py
pending_query = text("""
    WITH ranked_results AS (
        SELECT
            mr.item_id,
            mr.decision,
            mr.confidence_score,
            mr.timestamp,
            i.classification_code,
            ROW_NUMBER() OVER (PARTITION BY mr.item_id ORDER BY mr.timestamp DESC) as rn
        FROM match_results mr
        JOIN items i ON i.id = mr.item_id
        WHERE i.org_id = :org_id
          AND i.project_id = :project_id
    )
    SELECT
        rr.item_id,
        rr.decision,
        rr.confidence_score,
        rr.timestamp,
        rr.classification_code,
        (julianday('now') - julianday(rr.timestamp)) as age_days
    FROM ranked_results rr
    WHERE rr.rn = 1
      AND rr.decision IN ('manual-review', 'pending-review')
""")
```

**Change Summary**:
1. Remove duplicate `mr.item_id` from SELECT (line 79)
2. Change alias from `lr` to `rr` (line 93-99)
3. Add `WHERE rn = 1` filter for latest results only
4. Replace `EXTRACT(EPOCH FROM ...)` with SQLite-compatible `julianday()` function

**Test**:
```bash
curl http://localhost:8001/review?org=acme-construction&project=default&view=executive
# Should return 200, not 500
```

---

## TASK 1: Create Database Schema Extensions

**Location**: Create new file `bimcalc/db/migrations/add_crail4_support.sql`

**SQL to add**:

```sql
-- Track ETL job runs for auditability
CREATE TABLE IF NOT EXISTS price_import_runs (
    id TEXT PRIMARY KEY,  -- UUID
    org_id TEXT NOT NULL,
    source TEXT NOT NULL,  -- 'crail4_api', 'manual', etc.
    started_at TIMESTAMP NOT NULL,
    completed_at TIMESTAMP,
    status TEXT NOT NULL,  -- 'running', 'completed', 'failed'
    items_fetched INTEGER DEFAULT 0,
    items_loaded INTEGER DEFAULT 0,
    items_rejected INTEGER DEFAULT 0,
    rejection_reasons JSON,  -- {"missing_classification": 45, "invalid_unit": 12}
    error_message TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Classification code mapping for taxonomy translation
CREATE TABLE IF NOT EXISTS classification_mappings (
    id TEXT PRIMARY KEY,  -- UUID
    org_id TEXT NOT NULL,
    source_scheme TEXT NOT NULL,  -- 'OmniClass', 'UniClass2015', etc.
    source_code TEXT NOT NULL,
    target_scheme TEXT NOT NULL,
    target_code TEXT NOT NULL,
    confidence REAL DEFAULT 1.0,  -- 0.0-1.0, for fuzzy mappings
    mapping_source TEXT,  -- 'csi_crosswalk', 'manual', 'vendor'
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_by TEXT,
    UNIQUE(org_id, source_scheme, source_code, target_scheme)
);

-- Add vendor tracking to price_items
ALTER TABLE price_items ADD COLUMN IF NOT EXISTS vendor_code TEXT;
ALTER TABLE price_items ADD COLUMN IF NOT EXISTS last_updated TIMESTAMP;
ALTER TABLE price_items ADD COLUMN IF NOT EXISTS region TEXT;
ALTER TABLE price_items ADD COLUMN IF NOT EXISTS import_run_id TEXT REFERENCES price_import_runs(id);
```

**Location**: Update `bimcalc/db/models.py`

**Add new models**:

```python
class PriceImportRunModel(Base):
    __tablename__ = "price_import_runs"

    id = Column(String, primary_key=True)
    org_id = Column(String, nullable=False, index=True)
    source = Column(String, nullable=False)
    started_at = Column(DateTime, nullable=False)
    completed_at = Column(DateTime)
    status = Column(String, nullable=False)  # running, completed, failed
    items_fetched = Column(Integer, default=0)
    items_loaded = Column(Integer, default=0)
    items_rejected = Column(Integer, default=0)
    rejection_reasons = Column(JSON)
    error_message = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)


class ClassificationMappingModel(Base):
    __tablename__ = "classification_mappings"

    id = Column(String, primary_key=True)
    org_id = Column(String, nullable=False, index=True)
    source_scheme = Column(String, nullable=False)
    source_code = Column(String, nullable=False)
    target_scheme = Column(String, nullable=False)
    target_code = Column(String, nullable=False)
    confidence = Column(Float, default=1.0)
    mapping_source = Column(String)  # 'csi_crosswalk', 'manual', 'vendor'
    created_at = Column(DateTime, default=datetime.utcnow)
    created_by = Column(String)

    __table_args__ = (
        UniqueConstraint('org_id', 'source_scheme', 'source_code', 'target_scheme'),
    )


# Update PriceItemModel to add new fields
# Add these columns to existing PriceItemModel:
vendor_code = Column(String)
last_updated = Column(DateTime)
region = Column(String)
import_run_id = Column(String, ForeignKey('price_import_runs.id'))
```

---

## TASK 2: Create Classification Mapping Service

**Location**: Create new file `bimcalc/integration/classification_mapper.py`

**Purpose**: Translate classification codes between schemes (OmniClass → UniClass, etc.)

**Code**:

```python
"""Classification code translation service for multi-taxonomy support."""

from __future__ import annotations

from typing import Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bimcalc.db.models import ClassificationMappingModel


class ClassificationMapper:
    """Translates classification codes between different taxonomies."""

    def __init__(self, session: AsyncSession, org_id: str):
        self.session = session
        self.org_id = org_id
        self._cache: dict[tuple[str, str, str], Optional[str]] = {}

    async def translate(
        self,
        source_code: str,
        source_scheme: str,
        target_scheme: str
    ) -> Optional[str]:
        """Translate a classification code from source scheme to target scheme.

        Args:
            source_code: Code to translate (e.g., "23-17 11 23")
            source_scheme: Source taxonomy (e.g., "OmniClass")
            target_scheme: Target taxonomy (e.g., "UniClass2015")

        Returns:
            Translated code or None if no mapping exists
        """
        # Check cache first
        cache_key = (source_scheme, source_code, target_scheme)
        if cache_key in self._cache:
            return self._cache[cache_key]

        # Query database
        stmt = select(ClassificationMappingModel.target_code).where(
            ClassificationMappingModel.org_id == self.org_id,
            ClassificationMappingModel.source_scheme == source_scheme,
            ClassificationMappingModel.source_code == source_code,
            ClassificationMappingModel.target_scheme == target_scheme
        )

        result = await self.session.execute(stmt)
        target_code = result.scalar_one_or_none()

        # Cache result
        self._cache[cache_key] = target_code
        return target_code

    async def translate_batch(
        self,
        codes: list[str],
        source_scheme: str,
        target_scheme: str
    ) -> dict[str, Optional[str]]:
        """Translate multiple codes in one query.

        Returns:
            Dictionary mapping source_code → target_code (or None)
        """
        stmt = select(
            ClassificationMappingModel.source_code,
            ClassificationMappingModel.target_code
        ).where(
            ClassificationMappingModel.org_id == self.org_id,
            ClassificationMappingModel.source_scheme == source_scheme,
            ClassificationMappingModel.source_code.in_(codes),
            ClassificationMappingModel.target_scheme == target_scheme
        )

        result = await self.session.execute(stmt)
        mapping = {row.source_code: row.target_code for row in result}

        # Fill in missing codes with None
        return {code: mapping.get(code) for code in codes}

    async def add_mapping(
        self,
        source_code: str,
        source_scheme: str,
        target_code: str,
        target_scheme: str,
        mapping_source: str = "manual",
        confidence: float = 1.0,
        created_by: str = "system"
    ) -> None:
        """Add a new classification mapping to the database."""
        import uuid

        mapping = ClassificationMappingModel(
            id=str(uuid.uuid4()),
            org_id=self.org_id,
            source_scheme=source_scheme,
            source_code=source_code,
            target_scheme=target_scheme,
            target_code=target_code,
            confidence=confidence,
            mapping_source=mapping_source,
            created_by=created_by
        )

        self.session.add(mapping)
        await self.session.flush()

        # Invalidate cache
        cache_key = (source_scheme, source_code, target_scheme)
        self._cache.pop(cache_key, None)
```

---

## TASK 3: Create Crail4 API Client

**Location**: Create new file `bimcalc/integration/crail4_client.py`

**Purpose**: Handle API authentication and data extraction from Crail4 AI

**Code**:

```python
"""Crail4 AI API client for pricing data extraction."""

from __future__ import annotations

import os
from typing import Optional
import httpx
from datetime import datetime


class Crail4Client:
    """Client for Crail4 AI pricing API."""

    def __init__(self, api_key: Optional[str] = None, base_url: Optional[str] = None):
        self.api_key = api_key or os.getenv("CRAIL4_API_KEY")
        self.base_url = base_url or os.getenv("CRAIL4_BASE_URL", "https://api.crail4.ai/v1")

        if not self.api_key:
            raise ValueError("CRAIL4_API_KEY environment variable not set")

        self.client = httpx.AsyncClient(
            base_url=self.base_url,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Accept": "application/json"
            },
            timeout=30.0
        )

    async def fetch_all_items(
        self,
        classification_filter: Optional[list[str]] = None,
        updated_since: Optional[datetime] = None,
        region: Optional[str] = None
    ) -> list[dict]:
        """Fetch all price items from Crail4 API.

        Args:
            classification_filter: List of classification codes to filter by
            updated_since: Only fetch items updated after this timestamp
            region: Geographic region filter (e.g., 'UK', 'IE')

        Returns:
            List of price item dictionaries
        """
        params = {}
        if classification_filter:
            params["classification"] = ",".join(classification_filter)
        if updated_since:
            params["updated_since"] = updated_since.isoformat()
        if region:
            params["region"] = region

        try:
            response = await self.client.get("/items", params=params)
            response.raise_for_status()
            data = response.json()
            return data.get("items", [])
        except httpx.HTTPStatusError as e:
            raise RuntimeError(f"Crail4 API error: {e.response.status_code} {e.response.text}")
        except httpx.RequestError as e:
            raise RuntimeError(f"Crail4 API request failed: {str(e)}")

    async def fetch_delta(self, last_sync: datetime) -> list[dict]:
        """Fetch only items updated since last sync (delta query)."""
        return await self.fetch_all_items(updated_since=last_sync)

    async def close(self):
        """Close the HTTP client."""
        await self.client.aclose()

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()
```

---

## TASK 4: Create ETL Transform Service

**Location**: Create new file `bimcalc/integration/crail4_transformer.py`

**Purpose**: Clean, normalize, and validate Crail4 data for BIMCalc ingestion

**Code**:

```python
"""Data transformation logic for Crail4 → BIMCalc ETL pipeline."""

from __future__ import annotations

from decimal import Decimal
from typing import Optional
import logging

from bimcalc.canonical.normalize import normalize_text, parse_fitting_attributes
from bimcalc.integration.classification_mapper import ClassificationMapper

logger = logging.getLogger(__name__)


class Crail4Transformer:
    """Transforms raw Crail4 data into BIMCalc-compatible format."""

    def __init__(self, mapper: ClassificationMapper, target_scheme: str = "UniClass2015"):
        self.mapper = mapper
        self.target_scheme = target_scheme

    async def transform_item(self, raw_item: dict) -> Optional[dict]:
        """Transform a single Crail4 item.

        Args:
            raw_item: Raw item from Crail4 API

        Returns:
            Transformed item dict or None if validation fails
        """
        try:
            # Extract source fields
            source_code = raw_item.get("classification_code")
            source_scheme = raw_item.get("classification_scheme", "OmniClass")
            description = raw_item.get("name") or raw_item.get("description")
            unit = raw_item.get("unit")
            unit_price = raw_item.get("unit_price")
            currency = raw_item.get("currency", "EUR")
            vat_rate = raw_item.get("vat_rate", 0.0)
            vendor_code = raw_item.get("vendor_code") or raw_item.get("item_code")

            # Validation: mandatory fields
            if not all([source_code, description, unit, unit_price]):
                logger.warning(f"Skipping item with missing mandatory fields: {raw_item.get('id')}")
                return None

            # Translate classification code
            target_code = await self.mapper.translate(
                source_code, source_scheme, self.target_scheme
            )

            if not target_code:
                logger.warning(
                    f"No mapping for {source_scheme} {source_code} → {self.target_scheme}"
                )
                return None

            # Normalize description
            normalized_desc = normalize_text(description)

            # Parse canonical key if this is a fitting/device
            canonical_key = None
            if target_code in ["66", "62", "63", "64", "67", "68"]:  # MEP codes
                attrs = parse_fitting_attributes(normalized_desc)
                if attrs:
                    canonical_key = self._build_canonical_key(target_code, attrs)

            # Standardize unit
            unit = self._standardize_unit(unit)

            # Build transformed item
            return {
                "classification_code": target_code,
                "classification_scheme": self.target_scheme,
                "description": description,
                "unit": unit,
                "unit_price": Decimal(str(unit_price)),
                "currency": currency.upper(),
                "vat_rate": Decimal(str(vat_rate)),
                "vendor_code": vendor_code,
                "canonical_key": canonical_key,
                "source_data": raw_item  # Keep original for audit
            }

        except Exception as e:
            logger.error(f"Transform error for item {raw_item.get('id')}: {e}")
            return None

    async def transform_batch(self, raw_items: list[dict]) -> tuple[list[dict], dict]:
        """Transform a batch of items.

        Returns:
            (valid_items, rejection_stats)
        """
        valid = []
        rejections = {
            "missing_fields": 0,
            "no_classification_mapping": 0,
            "transform_error": 0
        }

        for raw_item in raw_items:
            transformed = await self.transform_item(raw_item)
            if transformed:
                valid.append(transformed)
            else:
                # Categorize rejection reason
                if not all([raw_item.get("classification_code"), raw_item.get("unit_price")]):
                    rejections["missing_fields"] += 1
                else:
                    rejections["no_classification_mapping"] += 1

        return valid, rejections

    def _standardize_unit(self, unit: str) -> str:
        """Normalize unit of measure to BIMCalc standard."""
        unit_map = {
            "sq.m": "m²",
            "sqm": "m²",
            "square meter": "m²",
            "meter": "m",
            "metre": "m",
            "piece": "ea",
            "each": "ea",
            "nr": "ea",
        }
        return unit_map.get(unit.lower().strip(), unit)

    def _build_canonical_key(self, classification: str, attrs: dict) -> str:
        """Build canonical key from parsed attributes."""
        parts = [classification]

        if "family" in attrs:
            parts.append(normalize_text(attrs["family"]))
        if "type" in attrs:
            parts.append(normalize_text(attrs["type"]))
        if "width_mm" in attrs:
            parts.append(f"w={attrs['width_mm']}")
        if "height_mm" in attrs or "dn" in attrs:
            h = attrs.get("height_mm") or attrs.get("dn")
            parts.append(f"h={h}")
        if "angle_deg" in attrs:
            parts.append(f"a={attrs['angle_deg']}")
        if "material" in attrs:
            parts.append(f"mat={attrs['material']}")
        if "unit" in attrs:
            parts.append(f"u={attrs['unit']}")

        return "|".join(parts)
```

---

## TASK 5: Create FastAPI Bulk Import Endpoint

**Location**: Add to `bimcalc/web/app_enhanced.py`

**Purpose**: REST API endpoint for programmatic price imports

**Code to add**:

```python
from bimcalc.db.models import PriceItemModel, PriceImportRunModel
from bimcalc.integration.classification_mapper import ClassificationMapper
from bimcalc.integration.crail4_transformer import Crail4Transformer
from pydantic import BaseModel
from typing import Optional
import uuid
from datetime import datetime


class BulkPriceImportRequest(BaseModel):
    """Request schema for bulk price import."""
    org_id: str
    items: list[dict]
    source: str = "crail4_api"
    target_scheme: str = "UniClass2015"
    created_by: str = "system"


class BulkPriceImportResponse(BaseModel):
    """Response schema for bulk import."""
    run_id: str
    status: str
    items_received: int
    items_loaded: int
    items_rejected: int
    rejection_reasons: dict
    errors: list[str]


@app.post("/api/price-items/bulk-import", response_model=BulkPriceImportResponse)
async def bulk_import_prices(
    request: BulkPriceImportRequest,
    session: AsyncSession = Depends(get_session)
):
    """Bulk import price items from external source.

    This endpoint is designed for automated ETL pipelines (e.g., Crail4 sync).
    It validates, transforms, and loads price items with full audit trail.
    """
    run_id = str(uuid.uuid4())
    errors = []

    # Create import run record
    import_run = PriceImportRunModel(
        id=run_id,
        org_id=request.org_id,
        source=request.source,
        started_at=datetime.utcnow(),
        status="running",
        items_fetched=len(request.items)
    )
    session.add(import_run)
    await session.flush()

    try:
        # Initialize transformer
        mapper = ClassificationMapper(session, request.org_id)
        transformer = Crail4Transformer(mapper, request.target_scheme)

        # Transform items
        valid_items, rejection_stats = await transformer.transform_batch(request.items)

        # Load valid items
        loaded_count = 0
        for item_data in valid_items:
            try:
                price_item = PriceItemModel(
                    id=str(uuid.uuid4()),
                    org_id=request.org_id,
                    classification_code=item_data["classification_code"],
                    description=item_data["description"],
                    unit=item_data["unit"],
                    unit_price=item_data["unit_price"],
                    currency=item_data["currency"],
                    vat_rate=item_data.get("vat_rate", Decimal("0.0")),
                    vendor_code=item_data.get("vendor_code"),
                    import_run_id=run_id,
                    last_updated=datetime.utcnow()
                )
                session.add(price_item)
                loaded_count += 1
            except Exception as e:
                errors.append(f"Failed to insert item {item_data.get('vendor_code')}: {str(e)}")

        # Update import run
        import_run.completed_at = datetime.utcnow()
        import_run.status = "completed" if not errors else "completed_with_errors"
        import_run.items_loaded = loaded_count
        import_run.items_rejected = len(request.items) - loaded_count
        import_run.rejection_reasons = rejection_stats
        if errors:
            import_run.error_message = "\n".join(errors[:10])  # Limit error message size

        await session.commit()

        return BulkPriceImportResponse(
            run_id=run_id,
            status=import_run.status,
            items_received=len(request.items),
            items_loaded=loaded_count,
            items_rejected=import_run.items_rejected,
            rejection_reasons=rejection_stats,
            errors=errors
        )

    except Exception as e:
        import_run.status = "failed"
        import_run.error_message = str(e)
        import_run.completed_at = datetime.utcnow()
        await session.commit()

        raise HTTPException(status_code=500, detail=f"Import failed: {str(e)}")


@app.get("/api/price-imports/{run_id}")
async def get_import_run(run_id: str, session: AsyncSession = Depends(get_session)):
    """Get status and details of a price import run."""
    stmt = select(PriceImportRunModel).where(PriceImportRunModel.id == run_id)
    result = await session.execute(stmt)
    run = result.scalar_one_or_none()

    if not run:
        raise HTTPException(status_code=404, detail="Import run not found")

    return {
        "run_id": run.id,
        "org_id": run.org_id,
        "source": run.source,
        "status": run.status,
        "started_at": run.started_at,
        "completed_at": run.completed_at,
        "items_fetched": run.items_fetched,
        "items_loaded": run.items_loaded,
        "items_rejected": run.items_rejected,
        "rejection_reasons": run.rejection_reasons,
        "error_message": run.error_message
    }
```

---

## TASK 6: Create ETL Orchestration Script

**Location**: Create new file `bimcalc/integration/crail4_sync.py`

**Purpose**: Main ETL script to orchestrate the full sync process

**Code**:

```python
"""Crail4 AI → BIMCalc ETL orchestration script."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bimcalc.db.connection import get_async_session
from bimcalc.db.models import PriceImportRunModel
from bimcalc.integration.crail4_client import Crail4Client
from bimcalc.integration.classification_mapper import ClassificationMapper
from bimcalc.integration.crail4_transformer import Crail4Transformer

logger = logging.getLogger(__name__)


async def sync_crail4_prices(
    org_id: str,
    target_scheme: str = "UniClass2015",
    delta_days: Optional[int] = 7,
    classification_filter: Optional[list[str]] = None
) -> dict:
    """Execute Crail4 → BIMCalc price sync.

    Args:
        org_id: Organization ID
        target_scheme: Target classification scheme (e.g., UniClass2015)
        delta_days: Only fetch items updated in last N days (None = full sync)
        classification_filter: List of classification codes to filter

    Returns:
        Sync statistics dictionary
    """
    async with get_async_session() as session:
        # Determine last sync time for delta query
        updated_since = None
        if delta_days:
            updated_since = datetime.utcnow() - timedelta(days=delta_days)

        # Extract from Crail4
        logger.info(f"Fetching items from Crail4 (delta_days={delta_days})")
        async with Crail4Client() as client:
            raw_items = await client.fetch_all_items(
                classification_filter=classification_filter,
                updated_since=updated_since
            )

        logger.info(f"Fetched {len(raw_items)} items from Crail4")

        if not raw_items:
            return {
                "status": "no_data",
                "items_fetched": 0,
                "items_loaded": 0
            }

        # Transform
        mapper = ClassificationMapper(session, org_id)
        transformer = Crail4Transformer(mapper, target_scheme)

        logger.info("Transforming items...")
        valid_items, rejection_stats = await transformer.transform_batch(raw_items)
        logger.info(f"Transformed {len(valid_items)} valid items, {sum(rejection_stats.values())} rejected")

        # Load via API
        import httpx
        api_url = "http://localhost:8001/api/price-items/bulk-import"

        async with httpx.AsyncClient() as http_client:
            response = await http_client.post(
                api_url,
                json={
                    "org_id": org_id,
                    "items": valid_items,
                    "source": "crail4_api",
                    "target_scheme": target_scheme
                },
                timeout=300.0
            )
            response.raise_for_status()
            result = response.json()

        logger.info(f"Import completed: {result['status']}")
        return result


async def scheduled_sync():
    """Run scheduled sync (for cron/systemd timer)."""
    try:
        result = await sync_crail4_prices(
            org_id="acme-construction",
            target_scheme="UniClass2015",
            delta_days=7,  # Weekly delta sync
            classification_filter=["62", "63", "64", "66", "67", "68"]  # MEP only
        )
        logger.info(f"Scheduled sync completed: {result}")
    except Exception as e:
        logger.error(f"Scheduled sync failed: {e}", exc_info=True)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(scheduled_sync())
```

---

## TASK 7: Create Classification Mapping Seed Data

**Location**: Create new file `data/classification_mappings.csv`

**Purpose**: Pre-populate common OmniClass → UniClass mappings

**CSV Content**:

```csv
source_scheme,source_code,target_scheme,target_code,confidence,mapping_source
OmniClass,23-17 11 23,UniClass2015,66,1.0,csi_crosswalk
OmniClass,23-17 13 11,UniClass2015,62,1.0,csi_crosswalk
OmniClass,23-17 15 11,UniClass2015,64,1.0,csi_crosswalk
OmniClass,23-17 21 11,UniClass2015,68,1.0,csi_crosswalk
OmniClass,23-17 31 11,UniClass2015,67,1.0,csi_crosswalk
```

**Location**: Create seed script `bimcalc/integration/seed_classification_mappings.py`

```python
"""Seed classification mappings from CSV."""

import asyncio
import csv
from pathlib import Path
import uuid

from bimcalc.db.connection import get_async_session
from bimcalc.db.models import ClassificationMappingModel


async def seed_mappings(org_id: str, csv_path: str):
    """Load classification mappings from CSV into database."""
    async with get_async_session() as session:
        csv_file = Path(csv_path)

        with csv_file.open('r') as f:
            reader = csv.DictReader(f)
            for row in reader:
                mapping = ClassificationMappingModel(
                    id=str(uuid.uuid4()),
                    org_id=org_id,
                    source_scheme=row["source_scheme"],
                    source_code=row["source_code"],
                    target_scheme=row["target_scheme"],
                    target_code=row["target_code"],
                    confidence=float(row["confidence"]),
                    mapping_source=row["mapping_source"],
                    created_by="seed_script"
                )
                session.add(mapping)

        await session.commit()
        print(f"Seeded classification mappings for {org_id}")


if __name__ == "__main__":
    asyncio.run(seed_mappings(
        org_id="acme-construction",
        csv_path="data/classification_mappings.csv"
    ))
```

---

## TASK 8: Add Environment Variables

**Location**: Update `.env` file or document required vars

**Required Environment Variables**:

```bash
# Crail4 AI Integration
CRAIL4_API_KEY=your_api_key_here
CRAIL4_BASE_URL=https://api.crail4.ai/v1  # Optional, defaults to this
CRAIL4_SYNC_SCHEDULE=0 2 * * *  # Cron format, 2 AM daily
```

---

## TASK 9: Create CLI Command for Manual Sync

**Location**: Update `bimcalc/cli.py`

**Add command**:

```python
@app.command()
def sync_crail4(
    org_id: str = typer.Option("acme-construction", help="Organization ID"),
    target_scheme: str = typer.Option("UniClass2015", help="Target classification scheme"),
    full_sync: bool = typer.Option(False, help="Full sync (ignore delta)"),
    classifications: Optional[str] = typer.Option(None, help="Comma-separated classification codes to filter")
):
    """Sync pricing data from Crail4 AI."""
    from bimcalc.integration.crail4_sync import sync_crail4_prices

    delta_days = None if full_sync else 7
    class_filter = classifications.split(",") if classifications else None

    result = asyncio.run(sync_crail4_prices(
        org_id=org_id,
        target_scheme=target_scheme,
        delta_days=delta_days,
        classification_filter=class_filter
    ))

    typer.echo(f"Sync completed: {result['status']}")
    typer.echo(f"Items loaded: {result['items_loaded']}/{result['items_received']}")
    if result.get('errors'):
        typer.echo(f"Errors: {len(result['errors'])}")
```

---

## TASK 10: Create Systemd Timer for Scheduled Sync

**Location**: Create new file `deployment/crail4-sync.service`

```ini
[Unit]
Description=BIMCalc Crail4 Price Sync
After=network.target

[Service]
Type=oneshot
User=bimcalc
WorkingDirectory=/opt/bimcalc
Environment="DATABASE_URL=postgresql://..."
Environment="CRAIL4_API_KEY=..."
ExecStart=/opt/bimcalc/.venv/bin/python -m bimcalc.integration.crail4_sync

[Install]
WantedBy=multi-user.target
```

**Location**: Create `deployment/crail4-sync.timer`

```ini
[Unit]
Description=BIMCalc Crail4 Sync Timer
Requires=crail4-sync.service

[Timer]
OnCalendar=daily
OnCalendar=02:00
Persistent=true

[Install]
WantedBy=timers.target
```

---

## Testing Checklist

After implementation, verify:

1. ✅ **Bug Fix Test**: Executive dashboards load without 500 errors
   ```bash
   curl http://localhost:8001/review?org=acme-construction&project=default&view=executive
   ```

2. ✅ **Classification Mapping Test**: Seed mappings load correctly
   ```bash
   python -m bimcalc.integration.seed_classification_mappings
   ```

3. ✅ **API Client Test**: Crail4 client can fetch data
   ```python
   async with Crail4Client() as client:
       items = await client.fetch_all_items(classification_filter=["66"])
       assert len(items) > 0
   ```

4. ✅ **Transformer Test**: Items transform correctly
   ```python
   # Mock Crail4 item
   raw = {
       "classification_code": "23-17 11 23",
       "classification_scheme": "OmniClass",
       "name": "Cable Tray Elbow 90° 200x50",
       "unit": "ea",
       "unit_price": 45.50,
       "currency": "EUR"
   }
   transformed = await transformer.transform_item(raw)
   assert transformed["classification_code"] == "66"
   ```

5. ✅ **Bulk Import Test**: API endpoint accepts and loads items
   ```bash
   curl -X POST http://localhost:8001/api/price-items/bulk-import \
     -H "Content-Type: application/json" \
     -d '{"org_id": "acme-construction", "items": [...]}'
   ```

6. ✅ **End-to-End Test**: Full sync completes without errors
   ```bash
   python -m bimcalc.cli sync-crail4 --org-id acme-construction
   ```

7. ✅ **Audit Trail Test**: Import runs are recorded
   ```bash
   curl http://localhost:8001/api/price-imports/{run_id}
   ```

---

## Performance Requirements

- **Latency**: Bulk import of 1000 items should complete in <30 seconds
- **Throughput**: API should handle 10,000 items per sync without memory issues
- **Database**: Use batch inserts (SQLAlchemy bulk_insert_mappings) for >100 items
- **Filtering**: Only import relevant classifications to keep database lean

---

## Security & Compliance

- ✅ API keys stored in environment variables (never committed to git)
- ✅ All API calls over HTTPS only
- ✅ Audit trail for every import (PriceImportRunModel)
- ✅ Validate data integrity before commit (rollback on errors)
- ✅ Rate limit compliance (respect Crail4 API limits)

---

## Deliverables

When complete, you should have:

1. ✅ Fixed SQLite bugs in `review_metrics.py`
2. ✅ New database tables: `price_import_runs`, `classification_mappings`
3. ✅ New models in `bimcalc/db/models.py`
4. ✅ Classification mapper service
5. ✅ Crail4 API client
6. ✅ Data transformer
7. ✅ FastAPI bulk import endpoint
8. ✅ ETL orchestration script
9. ✅ CLI command for manual sync
10. ✅ Systemd timer for automation
11. ✅ Seed data and migration scripts
12. ✅ Comprehensive tests passing

---

## Notes for Codex

- Follow existing BIMCalc patterns (see `bimcalc/matching/`, `bimcalc/reporting/`)
- Use async/await throughout (AsyncSession, httpx.AsyncClient)
- Log all operations with structured logging
- Handle errors gracefully (try/except with clear error messages)
- Validate data before database writes
- Use type hints everywhere (`from __future__ import annotations`)
- Follow CLAUDE.md principles (auditability, determinism, classification-first)
