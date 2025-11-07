# BIMCalc Pydantic AI Tool API Specifications

**Purpose**: Minimal, deterministic API contracts for BIMCalc core matching engine.

**Philosophy**: Single-purpose functions, basic error handling, deterministic outputs.

---

## 1. classify_item

**Signature**: `classify_item(item: Item) -> int`

**Description**: Apply trust hierarchy (YAML-driven) to determine classification code for a BIM item.

**Parameters**:
- `item: Item` - Pydantic model with fields:
  - `family: str`
  - `type_name: str`
  - `category: Optional[str]`
  - `system_type: Optional[str]`
  - `omniclass_code: Optional[int]`
  - `uniformat_code: Optional[int]`

**Returns**: `int` - Classification code (e.g., 2301 for HVAC equipment, 9999 for Unknown)

**Trust Hierarchy Order** (stop at first match):
1. Explicit override fields (`omniclass_code`, `uniformat_code`)
2. Curated manual classification lists (CSV lookup on `family + type_name`)
3. Revit Category + System Type heuristics (YAML rules)
4. Fallback keyword heuristics (family contains "duct", "valve", etc.)
5. Unknown (9999) - requires manual review

**Error Handling**:
- Raise `ConfigurationError` if trust hierarchy YAML invalid/missing
- Raise `ValueError` if `item.family` is None or empty string
- Return `9999` for unclassifiable items (never fail silently)

**Example**:
```python
item = Item(
    family="Pipe Elbow",
    type_name="90° DN100 Steel",
    category="Pipe Fittings",
    system_type=None,
    omniclass_code=None
)
classification_code = classify_item(item)  # Returns 2215 (Pipe Fittings)
```

---

## 2. canonical_key

**Signature**: `canonical_key(item: Item) -> str`

**Description**: Generate deterministic 16-character hash representing normalized item identity.

**Parameters**:
- `item: Item` - Pydantic model with fields:
  - `classification_code: int`
  - `family: str`
  - `type_name: str`
  - `width_mm: Optional[float]`
  - `height_mm: Optional[float]`
  - `dn_mm: Optional[float]` (pipe diameter)
  - `angle_deg: Optional[float]`
  - `material: Optional[str]`
  - `unit: str` (e.g., "m", "ea", "m2")

**Normalization Rules**:
1. Text normalization:
   - Lowercase all strings
   - Unicode NFKD normalization
   - Strip special chars (`-`, `_`, `/`, spaces collapsed to single space)
   - Remove project-specific noise (regex: `revA|v2|proj-\d+`)
2. Numeric rounding:
   - `width_mm`, `height_mm`, `dn_mm` → round to nearest 5mm
   - `angle_deg` → round to nearest 5°
3. Unit normalization:
   - Convert to standard: `m`, `ea`, `m2`, `m3`
   - Handle EU/US variants: `metre → m`, `meter → m`, `each → ea`

**Returns**: `str` - 16-character SHA256 hash prefix (deterministic)

**Key Construction** (before hashing):
```
"{classification_code}|{family_slug}|{type_slug}|w={width_mm}|h={height_mm}|dn={dn_mm}|a={angle_deg}|mat={material_slug}|u={unit}"
```
(Omit None values; consistent ordering)

**Error Handling**:
- Raise `ValueError` if `classification_code` or `family` is None
- Raise `ValueError` if `unit` is invalid (not in standard set)

**Example**:
```python
item = Item(
    classification_code=2215,
    family="Cable Tray Elbow",
    type_name="Ladder Type 200x50mm 90° Galvanized",
    width_mm=200,
    height_mm=50,
    angle_deg=90,
    material="Galvanized Steel",
    unit="ea"
)
key = canonical_key(item)  # Returns "a1b2c3d4e5f6g7h8" (16-char hash)
```

---

## 3. mapping_lookup

**Signature**: `mapping_lookup(org_id: str, canonical_key: str) -> Optional[UUID]`

**Description**: SCD2 active row query - find current price_item_id for a canonical key.

**Parameters**:
- `org_id: str` - Organization identifier (multi-tenant scoping)
- `canonical_key: str` - 16-character hash from `canonical_key()` function

**Query Logic**:
```sql
SELECT price_item_id
FROM item_mapping
WHERE org_id = ? AND canonical_key = ? AND end_ts IS NULL
LIMIT 1
```

**Returns**:
- `UUID` - Price item ID if active mapping exists
- `None` - No mapping found (requires new match)

**Error Handling**:
- Raise `DatabaseError` if query fails (connection issues)
- Return `None` for missing keys (normal case, not an error)

**Example**:
```python
price_id = mapping_lookup("acme-construction", "a1b2c3d4e5f6g7h8")
if price_id:
    # Instant auto-match via mapping memory
    ...
else:
    # Run fuzzy matching pipeline
    ...
```

---

## 4. mapping_write

**Signature**: `mapping_write(org_id: str, canonical_key: str, price_item_id: UUID, created_by: str, reason: str) -> None`

**Description**: SCD2 write - close current mapping (if exists) and insert new active row.

**Parameters**:
- `org_id: str` - Organization identifier
- `canonical_key: str` - 16-character hash
- `price_item_id: UUID` - Target price item
- `created_by: str` - User/engineer email or "system"
- `reason: str` - Audit reason ("manual match", "auto-accept", "correction")

**Transaction Logic**:
```sql
BEGIN;
  -- Close current row
  UPDATE item_mapping
  SET end_ts = NOW()
  WHERE org_id = ? AND canonical_key = ? AND end_ts IS NULL;

  -- Insert new active row
  INSERT INTO item_mapping (id, org_id, canonical_key, price_item_id, start_ts, end_ts, created_by, reason)
  VALUES (gen_uuid(), ?, ?, ?, NOW(), NULL, ?, ?);
COMMIT;
```

**Returns**: `None` (write operation)

**Error Handling**:
- Raise `IntegrityError` if transaction violates unique constraint (overlapping validity)
- Raise `DatabaseError` if commit fails (rollback automatically)
- Raise `ValueError` if `canonical_key` or `price_item_id` is None

**Invariant**: At most one active row per `(org_id, canonical_key)` (enforced by unique partial index).

**Example**:
```python
mapping_write(
    org_id="acme-construction",
    canonical_key="a1b2c3d4e5f6g7h8",
    price_item_id=UUID("550e8400-e29b-41d4-a716-446655440000"),
    created_by="engineer@example.com",
    reason="manual match after flag resolution"
)
```

---

## 5. generate_candidates

**Signature**: `generate_candidates(item: Item, limit: int = 50) -> List[PriceItem]`

**Description**: Classification-first blocking - pre-filter price items by class, then numeric tolerances.

**Parameters**:
- `item: Item` - BIM item with `classification_code`, `width_mm`, `height_mm`, `dn_mm`, `unit`
- `limit: int` - Max candidates to return (default 50)

**Filter Logic** (applied in order):
1. **Classification blocking** (indexed):
   ```sql
   WHERE classification_code = item.classification_code
   ```
2. **Numeric pre-filters** (tolerance-based):
   - If `item.width_mm` present: `ABS(price.width_mm - item.width_mm) <= SIZE_TOLERANCE_MM`
   - If `item.height_mm` present: `ABS(price.height_mm - item.height_mm) <= SIZE_TOLERANCE_MM`
   - If `item.dn_mm` present: `ABS(price.dn_mm - item.dn_mm) <= SIZE_TOLERANCE_MM`
3. **Unit filter** (optional, strict match):
   - `price.unit = item.unit` OR `price.unit IS NULL`

**Returns**: `List[PriceItem]` - Candidate price items (sorted by relevance heuristic)

**Error Handling**:
- Raise `ValueError` if `item.classification_code` is None
- Return empty list if no candidates pass filters (normal case)
- Raise `DatabaseError` if query fails

**Expected Reduction**: 20× candidate space reduction vs unfiltered fuzzy matching.

**Example**:
```python
item = Item(classification_code=2215, width_mm=200, height_mm=50, unit="ea")
candidates = generate_candidates(item, limit=50)
# Returns max 50 PriceItem objects with classification_code=2215 and similar dimensions
```

---

## 6. fuzzy_rank

**Signature**: `fuzzy_rank(item: Item, candidates: List[PriceItem]) -> List[Tuple[PriceItem, float]]`

**Description**: RapidFuzz string similarity scoring on pre-filtered candidates.

**Parameters**:
- `item: Item` - BIM item with `family`, `type_name`, `material`
- `candidates: List[PriceItem]` - Pre-filtered candidates from `generate_candidates()`

**Ranking Logic**:
1. Construct search strings:
   - `item_text = f"{item.family} {item.type_name} {item.material or ''}".strip()`
   - `price_text = f"{price.description} {price.attributes.get('material', '')}".strip()`
2. Compute RapidFuzz `fuzz.token_sort_ratio(item_text, price_text)`
3. Filter: Keep only scores >= 70 (min threshold)
4. Sort: Descending by score

**Returns**: `List[Tuple[PriceItem, float]]` - List of `(price_item, score)` tuples, sorted descending

**Error Handling**:
- Return empty list if no candidates score >= 70
- Raise `ValueError` if `item.family` or `item.type_name` is None

**Example**:
```python
item = Item(family="Pipe Elbow", type_name="90° DN100 Steel")
candidates = generate_candidates(item)
ranked = fuzzy_rank(item, candidates)
# Returns [(PriceItem(...), 95.5), (PriceItem(...), 87.2), ...]
```

---

## 7. compute_flags

**Signature**: `compute_flags(item: Item, price: PriceItem) -> List[Flag]`

**Description**: Evaluate YAML-driven business risk flags for a matched pair.

**Parameters**:
- `item: Item` - BIM item
- `price: PriceItem` - Matched price item

**Flag Types** (from `config/flags.yaml`):
- **Critical-Veto** (block auto-accept):
  - `UnitConflict`: `item.unit != price.unit`
  - `SizeMismatch`: `abs(item.width_mm - price.width_mm) > SIZE_TOLERANCE_MM`
  - `AngleMismatch`: `abs(item.angle_deg - price.angle_deg) > ANGLE_TOLERANCE_DEG`
  - `MaterialConflict`: `slug(item.material) != slug(price.material)`
  - `ClassMismatch`: `item.classification_code != price.classification_code`
- **Advisory** (warn but allow):
  - `StalePrice`: `price.last_updated < today() - 365 days`
  - `CurrencyMismatch`: `price.currency != 'EUR'`
  - `VATUnclear`: `price.vat_rate is None`

**Returns**: `List[Flag]` - List of Flag objects (empty if no flags)

**Flag Model**:
```python
class Flag(BaseModel):
    type: str  # e.g., "UnitConflict"
    severity: Literal["Critical-Veto", "Advisory"]
    message: str  # e.g., "Item unit 'm' does not match price unit 'ea'"
```

**Error Handling**:
- Raise `ConfigurationError` if flags YAML invalid/missing
- Return empty list if no flags trigger (normal case)

**Example**:
```python
item = Item(unit="m", width_mm=200, material="Steel")
price = PriceItem(unit="ea", width_mm=200, material="Steel")
flags = compute_flags(item, price)
# Returns [Flag(type="UnitConflict", severity="Critical-Veto", message="...")]
```

---

## 8. report_as_of

**Signature**: `report_as_of(org_id: str, run_ts: datetime) -> DataFrame`

**Description**: Generate deterministic report using SCD2 temporal join for specified timestamp.

**Parameters**:
- `org_id: str` - Organization identifier
- `run_ts: datetime` - Report "as of" timestamp (ISO 8601)

**Query Logic** (SCD2 temporal join):
```sql
SELECT
  i.id AS item_id,
  i.family,
  i.type_name,
  i.quantity,
  i.unit,
  m.canonical_key,
  m.price_item_id,
  p.sku,
  p.description,
  p.unit_price,
  p.currency,
  p.vat_rate,
  (i.quantity * p.unit_price) AS total_price,
  m.created_by,
  m.reason
FROM items i
LEFT JOIN item_mapping m
  ON i.canonical_key = m.canonical_key
  AND m.org_id = ?
  AND m.start_ts <= ?
  AND (m.end_ts IS NULL OR m.end_ts > ?)
LEFT JOIN price_items p
  ON m.price_item_id = p.id
WHERE i.org_id = ?
ORDER BY i.family, i.type_name
```

**Returns**: `pandas.DataFrame` - Deterministic report data

**EU Formatting** (post-processing):
- Currency: EUR symbol (€)
- Thousands separator: comma (1.234,56)
- Decimal separator: period (or comma per EU locale)
- VAT explicit: Show both net and gross if `vat_rate` present

**Error Handling**:
- Raise `ValueError` if `run_ts` is future date
- Raise `DatabaseError` if query fails
- Return empty DataFrame if no items for org (normal case)

**Reproducibility**: Same `(org_id, run_ts)` produces bit-for-bit identical output.

**Example**:
```python
from datetime import datetime

report_df = report_as_of(
    org_id="acme-construction",
    run_ts=datetime(2024, 6, 1, 12, 0, 0)
)
# Returns DataFrame with mappings valid on 2024-06-01 12:00:00
```

---

## Error Types

```python
class ConfigurationError(Exception):
    """YAML configs invalid or missing"""

class IntegrityError(Exception):
    """SCD2 constraints violated (overlapping validity)"""

class DatabaseError(Exception):
    """Database connection or query failure"""
```

---

## Design Principles

1. **Determinism**: Same inputs always produce same outputs (no timestamps in keys, stable sorting)
2. **Single Purpose**: Each function does one thing well (classify OR normalize OR match)
3. **Fail Fast**: Raise specific exceptions for invalid inputs (never return corrupt data)
4. **Auditability**: SCD2 writes always log `created_by`, `reason`, `start_ts`
5. **Performance**: Classification blocking first (20× reduction), fuzzy matching second

---

## Integration with Pydantic AI

These tools will be wrapped as Pydantic AI agent tools:

```python
from pydantic_ai import Agent, RunContext

agent = Agent(
    'openai:gpt-4',
    system_prompt='You are BIMCalc cost matching assistant. Use tools to match items, query mappings, and explain decisions.',
)

@agent.tool
async def classify_item_tool(ctx: RunContext, item: Item) -> int:
    return classify_item(item)

@agent.tool
async def mapping_lookup_tool(ctx: RunContext, org_id: str, canonical_key: str) -> Optional[UUID]:
    return mapping_lookup(org_id, canonical_key)

# ... etc for all 8 tools
```

Agent can compose these tools to:
- Answer "Why was this matched?" (query SCD2 history)
- Suggest corrections (flag analysis)
- Explain classification decisions (trust hierarchy trace)

---

## Next Steps

1. Implement tools in `bimcalc/` modules (classification, canonical, mapping, matching, flags, reporting)
2. Write unit tests for each tool (determinism, edge cases, error handling)
3. Wrap as Pydantic AI tools in `bimcalc/agent/tools.py`
4. Integration test: Two-pass demo (Project A → B auto-match via mapping_lookup)
5. Benchmark: Latency p95 < 0.5s/item, candidate reduction ≥ 20×
