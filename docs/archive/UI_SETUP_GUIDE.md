# BIMCalc Web UI Setup & Configuration Guide

**Last Updated**: 2025-11-07
**UI Version**: 1.0 (FastAPI + Jinja2)

---

## 🎯 Quick Start

### Correct URL for Your Current Data

Your test data is in:
- **Organization**: `acme-construction`
- **Project**: `project-a`

**✅ Use this URL**:
```
http://localhost:8001/?org=acme-construction&project=project-a
```

**❌ Don't use** (returns no data):
```
http://localhost:8001/?org=default&project=default
```

---

## 📋 URL Parameters Reference

### Base URL Structure
```
http://localhost:8001/?org={ORG_ID}&project={PROJECT_ID}&flag={FLAG_TYPE}&severity={SEVERITY}
```

### Parameters

| Parameter | Required | Default | Values | Description |
|-----------|----------|---------|--------|-------------|
| `org` | No | From `.env` | Any string | Organization ID (tenant scope) |
| `project` | No | `"default"` | Any string | Project ID within organization |
| `flag` | No | `"all"` | See flag types below | Filter by specific flag type |
| `severity` | No | `"all"` | `all`, `Critical-Veto`, `Advisory` | Filter by flag severity |

### Available Flag Types

| Flag Type | Display Name | Severity | Description |
|-----------|--------------|----------|-------------|
| `UnitConflict` | Unit Conflict | Critical-Veto | Item unit ≠ price unit (m ↔ ea) |
| `SizeMismatch` | Size Mismatch | Critical-Veto | Width/height outside tolerance |
| `AngleMismatch` | Angle Mismatch | Critical-Veto | Angle outside tolerance (±5°) |
| `MaterialConflict` | Material Conflict | Critical-Veto | Material doesn't match |
| `ClassMismatch` | Class Mismatch | Critical-Veto | Classification code mismatch |
| `StalePrice` | Stale Price | Advisory | Price > 6 months old |
| `CurrencyMismatch` | Currency/VAT | Advisory | Currency or VAT ambiguity |
| `VATUnclear` | VAT Unclear | Advisory | Missing or unclear VAT rate |
| `VendorNote` | Vendor Note | Advisory | Vendor has a note (lead time, etc.) |

### Example URLs

```bash
# View all review items for project-a
http://localhost:8001/?org=acme-construction&project=project-a

# View only items with Unit Conflicts
http://localhost:8001/?org=acme-construction&project=project-a&flag=UnitConflict

# View only Critical flags
http://localhost:8001/?org=acme-construction&project=project-a&severity=Critical-Veto

# View only Advisory flags
http://localhost:8001/?org=acme-construction&project=project-a&severity=Advisory

# View VendorNote flags only
http://localhost:8001/?org=acme-construction&project=project-a&flag=VendorNote

# Combine filters (VendorNote + Advisory only)
http://localhost:8001/?org=acme-construction&project=project-a&flag=VendorNote&severity=Advisory
```

---

## ⚙️ Backend Configuration

### Environment Variables (.env)

The Web UI reads defaults from your `.env` file:

```bash
# Organization ID (used when ?org= parameter is not provided)
DEFAULT_ORG_ID=acme-construction

# Database connection
DATABASE_URL=sqlite+aiosqlite:///./bimcalc.db

# Matching thresholds (affects auto-accept decisions)
AUTO_ACCEPT_MIN_CONFIDENCE=85
FUZZY_MIN_SCORE=70

# Physical tolerances (affects Size/Angle/DN mismatch flags)
SIZE_TOLERANCE_MM=10
ANGLE_TOLERANCE_DEG=5
DN_TOLERANCE_MM=5

# EU defaults
DEFAULT_CURRENCY=EUR
VAT_RATE=0.23
```

### How Defaults Work

**Web App Logic** (`bimcalc/web/app.py`):
```python
@app.get("/")
async def review_dashboard(
    request: Request,
    org: Optional[str] = None,
    project: Optional[str] = None,
    # ...
):
    config = get_config()
    org_id = org or config.org_id  # Falls back to DEFAULT_ORG_ID from .env
    project_id = project or "default"  # Falls back to "default"
```

**Current Configuration**:
- If you visit `http://localhost:8001/` with **no parameters**, it uses:
  - `org_id = "acme-construction"` (from `.env`)
  - `project_id = "default"` (hardcoded fallback)

**Your Data Location**:
- Database has items in `org=acme-construction`, `project=project-a`

**Result**:
- Default URL shows **no items** because project_id defaults to `"default"` instead of `"project-a"`
- You must explicitly provide `?project=project-a` in the URL

---

## 🔧 Configuration Options

### Option 1: Always Specify URL Parameters (Current Approach)

**Pros**:
- ✅ Explicit control
- ✅ Multi-project support
- ✅ Easy to switch between projects

**Cons**:
- ❌ Longer URLs
- ❌ Must remember project names

**Usage**:
```bash
# Bookmark this URL for your main project
http://localhost:8001/?org=acme-construction&project=project-a
```

### Option 2: Update .env Default Project

Add a `DEFAULT_PROJECT_ID` to your `.env`:

```bash
# Add to .env
DEFAULT_ORG_ID=acme-construction
DEFAULT_PROJECT_ID=project-a
```

Then update `bimcalc/web/app.py`:
```python
project_id = project or config.project_id  # Use config default
```

**Pros**:
- ✅ Shorter URL (just `http://localhost:8001/`)
- ✅ Better default experience

**Cons**:
- ❌ Requires code change
- ❌ Less flexible for multi-project workflows

### Option 3: Add Homepage with Project Selector

Create a landing page at `/` that shows:
- List of all available projects
- Click to navigate to review dashboard
- Recent activity summary

**Pros**:
- ✅ Best UX
- ✅ No need to remember project names
- ✅ Discoverable

**Cons**:
- ❌ Requires new UI page

---

## 🗂️ Multi-Organization/Multi-Project Setup

### Database Structure

Your database supports multi-tenancy:

```sql
-- Items are scoped by org_id and project_id
CREATE TABLE items (
    id UUID PRIMARY KEY,
    org_id TEXT NOT NULL,      -- Tenant identifier
    project_id TEXT NOT NULL,   -- Project within tenant
    -- ...
);

-- Mappings are scoped by org_id only (shared across projects in org)
CREATE TABLE item_mapping (
    id UUID PRIMARY KEY,
    org_id TEXT NOT NULL,       -- Tenant identifier
    canonical_key TEXT NOT NULL,
    price_item_id UUID NOT NULL,
    -- ...
);
```

### How It Works

1. **Items are project-specific**: Each Revit schedule you ingest goes into a specific `(org_id, project_id)` combination
2. **Mappings are org-wide**: When you approve a match, the mapping is stored at org level and **reused across all projects in that org**
3. **Price books are global**: Price items don't have org_id scope (shared catalog)

### Example Scenario

```bash
# Project A: High-rise building
bimcalc ingest-schedules project_a.csv --org acme --project highrise-tower

# Project B: Office fit-out
bimcalc ingest-schedules project_b.csv --org acme --project office-fitout

# Both projects share the same price catalog and approved mappings!
```

**Result**:
- Items for "highrise-tower" and "office-fitout" are kept separate
- But if you approve "Cable Tray 200x50 90°" in Project A, Project B will **auto-match** the same item via mapping memory

---

## 🎨 UI Features & Workflow

### Review Dashboard

**What You See**:
- Table of all items requiring manual review
- For each item:
  - Item description (family / type)
  - Candidate price (SKU, description)
  - Confidence score (0-100%)
  - Flags (with color-coded badges)
  - Annotation text box
  - Approve button

**Business Rules**:
| Condition | Button State | Required Action |
|-----------|--------------|-----------------|
| ✅ No flags | Enabled | None |
| ⚠️ Advisory flags only | Enabled | Must add annotation |
| 🛑 Critical flag(s) | **Disabled** | Resolve flag first (update data, change candidate) |
| ❌ No candidate price | **Disabled** | Cannot approve without match |

### Approval Flow

1. **User adds annotation** (required for Advisory flags)
   - Example: `"Approved - standard delivery time is acceptable"`
2. **User clicks "Approve" button**
3. **Backend creates mapping**:
   ```python
   # SCD2 mapping memory entry
   {
       "org_id": "acme-construction",
       "canonical_key": "4ab92e53d5890d4b",  # Normalized item key
       "price_item_id": "04697f08-...",
       "start_ts": "2025-11-07T13:45:00Z",
       "end_ts": null,  # Active mapping
       "created_by": "web-ui",
       "reason": "Approved - standard delivery time is acceptable"
   }
   ```
4. **Item disappears from review queue**
5. **Future matches use this mapping instantly**

### Filter Workflow

**Flag Filter**:
```bash
# Click dropdown → Select "Unit Conflict"
# URL updates to: ?flag=UnitConflict
# Table shows only items with Unit Conflict flags
```

**Severity Filter**:
```bash
# Click dropdown → Select "Critical"
# URL updates to: ?severity=Critical-Veto
# Table shows only items with Critical flags (blocks approval)
```

**Combined**:
- Filters are **additive** (AND logic)
- Example: `?flag=VendorNote&severity=Advisory` shows only VendorNote flags with Advisory severity

---

## 🔍 Debugging & Troubleshooting

### Problem: "No items waiting for review"

**Possible Causes**:

1. **Wrong org/project parameters**
   ```bash
   # Check what data you have:
   python -c "
   import asyncio
   from sqlalchemy import select, func
   from bimcalc.db.connection import get_session
   from bimcalc.db.models import ItemModel

   async def check():
       async with get_session() as session:
           result = await session.execute(
               select(ItemModel.org_id, ItemModel.project_id, func.count())
               .group_by(ItemModel.org_id, ItemModel.project_id)
           )
           for row in result:
               print(f'org={row[0]}, project={row[1]}, items={row[2]}')

   asyncio.run(check())
   "
   ```

2. **No manual-review items** (all auto-accepted or rejected)
   ```bash
   # Check match results:
   python -m bimcalc.cli stats --org acme-construction --project project-a
   ```

3. **Filters too restrictive**
   - Remove flag/severity filters: `http://localhost:8001/?org=acme-construction&project=project-a`

### Problem: Can't approve item (button disabled)

**Check for**:

1. **Critical flags** (red badges)
   - Item has UnitConflict, SizeMismatch, AngleMismatch, MaterialConflict, or ClassMismatch
   - **Fix**: Update item data or select different candidate

2. **No candidate price**
   - Shows "No candidate" instead of SKU
   - **Fix**: Run fuzzy matching again or add matching price to catalog

### Problem: "Annotation required for advisory flags"

**This is expected behavior**:
- Advisory flags (yellow badges) require you to add a note explaining why you're approving despite the flag
- Add text in the annotation box: e.g., `"Approved - vendor lead time is acceptable"`

### Problem: Server won't start / port in use

**Check running servers**:
```bash
# List all running servers
lsof -i :8000
lsof -i :8001
lsof -i :8080

# Kill a specific process
kill -9 <PID>
```

**Or use a different port**:
```bash
python -m bimcalc.cli web serve --port 8888
```

---

## 📊 Database Inspection Commands

### Check Available Data

```bash
# View all org/project combinations
sqlite3 bimcalc.db "
SELECT org_id, project_id, COUNT(*) as items
FROM items
GROUP BY org_id, project_id;
"

# View match results summary
sqlite3 bimcalc.db "
SELECT decision, COUNT(*) as count
FROM match_results
JOIN items ON match_results.item_id = items.id
WHERE items.org_id = 'acme-construction'
  AND items.project_id = 'project-a'
GROUP BY decision;
"

# View items waiting for review
sqlite3 bimcalc.db "
SELECT i.family, i.type_name, mr.confidence_score, mr.reason
FROM match_results mr
JOIN items i ON mr.item_id = i.id
WHERE i.org_id = 'acme-construction'
  AND i.project_id = 'project-a'
  AND mr.decision = 'manual-review'
  AND mr.id IN (
      SELECT id FROM (
          SELECT id, ROW_NUMBER() OVER (PARTITION BY item_id ORDER BY timestamp DESC) as rn
          FROM match_results
      ) WHERE rn = 1
  );
"

# View active mappings
sqlite3 bimcalc.db "
SELECT canonical_key, created_by, reason, start_ts
FROM item_mapping
WHERE org_id = 'acme-construction'
  AND end_ts IS NULL;
"
```

### Python Inspection

```python
import asyncio
from bimcalc.db.connection import get_session
from bimcalc.review import fetch_pending_reviews

async def check_review_queue():
    async with get_session() as session:
        records = await fetch_pending_reviews(
            session,
            "acme-construction",
            "project-a",
            None,  # No flag filter
            None   # No severity filter
        )

        print(f"Review queue: {len(records)} items")
        for record in records:
            print(f"  - {record.item.family} / {record.item.type_name}")
            print(f"    Confidence: {record.confidence_score:.0f}%")
            print(f"    Flags: {[f.type for f in record.flags]}")
            print()

asyncio.run(check_review_queue())
```

---

## 🚀 Production Deployment Recommendations

### Security

1. **Add CSRF Protection**:
   ```bash
   pip install fastapi-csrf
   ```
   ```python
   # In bimcalc/web/app.py
   from fastapi_csrf import CsrfProtect

   app.add_middleware(
       CsrfProtect,
       secret="your-secret-key-here",  # Load from env
   )
   ```

2. **Add Authentication**:
   - Use FastAPI OAuth2/JWT middleware
   - Map authenticated user to `created_by` field in mappings

3. **HTTPS Only**:
   ```bash
   # Use reverse proxy (nginx/traefik) with SSL
   uvicorn bimcalc.web.app:app --host 0.0.0.0 --port 8000 --proxy-headers
   ```

### Performance

1. **Use PostgreSQL** (not SQLite):
   ```bash
   DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/bimcalc
   ```

2. **Enable Connection Pooling**:
   ```bash
   DB_POOL_SIZE=20
   DB_POOL_MAX_OVERFLOW=40
   ```

3. **Add Redis Cache** (for review queue):
   - Cache review query results for 30 seconds
   - Invalidate on approval

### Scalability

1. **Add Pagination**:
   ```python
   # Add to review_dashboard()
   page: int = Query(default=1, ge=1)
   per_page: int = Query(default=25, le=100)
   ```

2. **Add Background Tasks** (Celery/RQ):
   - Move matching pipeline to async worker
   - Show "Processing..." status in UI

3. **WebSocket Updates**:
   - Real-time queue updates when items approved
   - Show active reviewers

---

## 📝 Configuration Checklist

- [ ] `.env` file configured with correct `DEFAULT_ORG_ID`
- [ ] Database initialized (`bimcalc init`)
- [ ] Price book ingested (`bimcalc ingest-prices`)
- [ ] Schedule ingested (`bimcalc ingest-schedules --project YOUR_PROJECT`)
- [ ] Matching run (`bimcalc match --project YOUR_PROJECT`)
- [ ] Server started (`bimcalc web serve`)
- [ ] Correct URL with org/project parameters
- [ ] Filters applied if needed
- [ ] Annotation added for Advisory flags

---

## 🎯 Current Setup Summary

**Your Configuration**:
```bash
# .env
DEFAULT_ORG_ID=acme-construction
DATABASE_URL=sqlite+aiosqlite:///./bimcalc.db

# Data
org_id=acme-construction
project_id=project-a
items=6
manual_review=4

# Server
http://localhost:8001
```

**Correct Access URL**:
```
http://localhost:8001/?org=acme-construction&project=project-a
```

**Expected Results**:
- 4 items in review queue
- All have VendorNote flag (Advisory)
- All require annotation before approval
- 3 Cable Tray items (86-90% confidence)
- 1 LED Panel (74% confidence)

---

## 📞 Next Steps

1. **Access UI** with correct URL: `http://localhost:8001/?org=acme-construction&project=project-a`
2. **Review first item** (Cable Tray 90° Elbow)
3. **Add annotation**: `"Approved - standard delivery time acceptable"`
4. **Click Approve** button
5. **Verify mapping created**:
   ```bash
   sqlite3 bimcalc.db "SELECT COUNT(*) FROM item_mapping WHERE org_id='acme-construction';"
   ```
6. **Run matching again** on new project to test instant rematching

---

## 🐛 Known Issues

1. **No homepage/project selector** - Must manually construct URLs
2. **No CSRF protection** - Don't use in production yet
3. **No authentication** - Open access to anyone with URL
4. **No pagination** - All review items load at once (fine for < 1000 items)
5. **No real-time updates** - Must refresh page manually

See `UI_BACKEND_ALIGNMENT_REPORT.md` for detailed recommendations.
