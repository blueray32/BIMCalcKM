# BIMCalc Test Data

This directory contains sample data for testing the BIMCalc web UI and demonstrating CMM features.

## Files

### 1. `revit_schedule_demo.csv`
**Purpose**: Sample Revit schedule export with 20 items

**Items Include**:
- Cable trays (ladder type) - various sizes and angles
- Pipes (MEP fabrication) - DN50, DN100
- Conduits (rigid PVC) - 25mm
- Ducts (rectangular) - 300x200mm
- Copper pipes - DN32
- Lighting fixtures - LED panels and downlights

**Usage**:
```bash
# Via CLI
python -m bimcalc.cli ingest-schedules test_data/revit_schedule_demo.csv --org demo --project test-project-1

# Via Web UI
1. Go to http://localhost:8002/ingest
2. Upload revit_schedule_demo.csv
3. Set Org: demo, Project: test-project-1
```

### 2. `pricebook_standard.csv`
**Purpose**: Standard format price book (20 items) - matches most items from Revit schedule

**Format**: Standard BIMCalc columns
- SKU, Description, Classification Code
- Unit Price, Unit, Currency, VAT Rate
- Physical attributes (Width, Height, DN, Angle, Material)

**Matching Results Expected**:
- ✅ High confidence matches: ~15 items (auto-approved)
- ⚠️ Medium confidence: ~3 items (manual review)
- ❌ No match: ~2 items (unmapped)

**Usage**:
```bash
# Via CLI
python -m bimcalc.cli ingest-pricebook test_data/pricebook_standard.csv --vendor standard

# Via Web UI
1. Go to http://localhost:8002/ingest
2. Upload pricebook_standard.csv
3. Select Vendor: Default (Generic Mapping)
4. Keep "Enable CMM" checked (though not needed for standard format)
```

### 3. `pricebook_vendor_cmm.csv`
**Purpose**: Vendor-specific format with quirky codes - **tests CMM translation**

**Format**: Vendor columns (NOT standard BIMCalc format)
- Containment, Description1, Description2
- Width, Depth, Finish
- Unit Price, Currency, SKU

**CMM Translation**:
- `Containment: ES_CONTMNT` → Classification Code: 2650 (Cable Tray)
- `Containment: PIPE_SYS` → Classification Code: 2211 (Piping)
- Width/Depth parsing: "200mm" → 200.0
- Finish mapping: "Galvanized" → material

**Usage**:
```bash
# Via CLI with CMM enabled
python -m bimcalc.cli ingest-pricebook test_data/pricebook_vendor_cmm.csv \
  --vendor default \
  --use-cmm

# Via Web UI (RECOMMENDED - shows CMM in action)
1. Go to http://localhost:8002/ingest
2. Upload pricebook_vendor_cmm.csv
3. Select Vendor: Default (Generic Mapping)
4. ✅ Keep "Enable CMM" checked
5. Check success message: "Imported 13 price items (with CMM enabled)"
```

---

## Complete Testing Workflow

### Step 1: Start Services
```bash
# Terminal 1: PostgreSQL
docker compose up -d db

# Terminal 2: Web UI
python -m bimcalc.cli web serve --host 127.0.0.1 --port 8002 --reload
```

### Step 2: Initialize Database (First Time Only)
```bash
python -m bimcalc.cli init --drop
```

### Step 3: Ingest Data via Web UI

**A. Upload Revit Schedule**
1. Go to http://localhost:8002/ingest
2. Select `revit_schedule_demo.csv`
3. Org: `demo`, Project: `test-project-1`
4. Click "Upload Schedule"
5. ✅ Should import 20 items

**B. Upload Standard Price Book**
1. Select `pricebook_standard.csv`
2. Vendor: "Default (Generic Mapping)"
3. CMM: ✅ Enabled (though not needed)
4. Click "Upload Price Book"
5. ✅ Should import 20 price items

**C. Upload Vendor Price Book (CMM Demo)**
1. Select `pricebook_vendor_cmm.csv`
2. Vendor: "Default (Generic Mapping)"
3. CMM: ✅ Enabled (IMPORTANT!)
4. Click "Upload Price Book"
5. ✅ Should import 13 price items (with CMM enabled)
6. Check vendor_note field - should show "CMM: mapped"

### Step 4: Run Matching
1. Go to http://localhost:8002/match
2. Org: `demo`, Project: `test-project-1`
3. Leave limit blank (match all)
4. Click "Run Matching"
5. Wait for results (~5-10 seconds)

**Expected Results**:
- Auto-approved: ~12 items (high confidence, no flags)
- Manual review: ~6 items (medium confidence or flags)
- No match: ~2 items (unmapped)

### Step 5: Review Items
1. Go to http://localhost:8002/review
2. Filter by different options:
   - All items
   - ✅ Check "Unmapped Only" - see items with no price match
   - Select severity: "Critical-Veto" - see items with blocking issues
3. Approve items that need manual review
4. Add annotations for advisory flags

### Step 6: View Results

**Items Page** (http://localhost:8002/items):
- Browse all 20 Revit items
- See canonical keys, classifications
- Pagination works

**Mappings Page** (http://localhost:8002/mappings):
- View approved mappings (SCD Type-2)
- See canonical_key → price_item links
- Check version numbers, timestamps

**Statistics** (http://localhost:8002/reports/statistics):
- Total items: 20
- Matched items: ~18
- Total cost (NET): ~€1,200
- Total cost (GROSS): ~€1,476 (with 23% VAT)
- Match decision breakdown chart

**Audit Trail** (http://localhost:8002/audit):
- Complete decision history
- See timestamps, confidence scores
- Filter by decision type

### Step 7: Generate Report
1. Go to http://localhost:8002/reports
2. Set "As-of Date" (or use current time)
3. Format: CSV or XLSX
4. Click "Generate & Download Report"
5. ✅ Excel file downloads with cost breakdown

---

## Testing CMM Features

### Verify CMM Translation
```bash
# Check database for CMM metadata
docker exec bimcalc-postgres psql -U bimcalc -d bimcalc -c "
  SELECT sku, description, classification_code, vendor_note
  FROM price_items
  WHERE vendor_id = 'default'
  AND vendor_note LIKE 'CMM:%'
  LIMIT 5;
"
```

**Expected Output**:
- `vendor_note` contains "CMM: mapped" or "CMM: L-ELB90-W200-D50-GALV"
- `classification_code` is populated (e.g., 2650, 2211)
- Original vendor fields preserved in metadata

### Test Unmapped Filter
1. Upload only `revit_schedule_demo.csv` (no prices)
2. Run matching → all items will be "manual-review" with no price
3. Go to http://localhost:8002/review
4. ✅ Check "Unmapped Only"
5. Should show all 20 items (none have matched prices)

### Test Temporal Reporting
1. Generate report with current timestamp
2. Approve some mappings in Review page
3. Generate another report with same timestamp as step 1
4. Both reports should be identical (SCD Type-2 working)

---

## Expected Database State After Full Workflow

```sql
-- Items: 20 (from Revit schedule)
SELECT COUNT(*) FROM items WHERE org_id = 'demo' AND project_id = 'test-project-1';

-- Price Items: 33 (20 standard + 13 vendor CMM)
SELECT COUNT(*) FROM price_items;

-- Match Results: 20 (one per item)
SELECT decision, COUNT(*) FROM match_results GROUP BY decision;
-- Expected: auto-approved: 12, manual-review: 6, no-match: 2

-- Active Mappings: ~12 (auto-approved items)
SELECT COUNT(*) FROM item_mappings WHERE end_ts IS NULL;
```

---

## Troubleshooting

### Issue: "No items found"
**Solution**: Make sure you set `org_id=demo` and `project_id=test-project-1` consistently

### Issue: "All items unmapped"
**Solution**: Upload a price book first, then run matching

### Issue: "CMM not translating"
**Solution**:
1. Check "Enable CMM" checkbox is checked
2. Verify `USE_CMM=true` in .env
3. Check YAML file exists: `config/vendors/config_vendor_default_classification_map.yaml`

### Issue: "Auto-reload not working"
**Solution**: Make sure you started with `--reload` flag:
```bash
python -m bimcalc.cli web serve --host 127.0.0.1 --port 8002 --reload
```

---

## Data Cleanup

To start fresh:
```bash
# Drop all data and reinitialize
python -m bimcalc.cli init --drop

# Or remove Docker volume (nuclear option)
docker compose down -v
docker compose up -d db
python -m bimcalc.cli init
```

---

## Next Steps

1. ✅ Test all pages with dummy data
2. ✅ Verify CMM translation working
3. ✅ Test temporal reporting (as-of dates)
4. ✅ Test unmapped items filter
5. Create your own vendor YAML files for real vendors
6. Import real project data

**Enjoy testing!** 🚀
