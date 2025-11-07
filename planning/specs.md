# BIMCalc MVP — Specifications

**Version**: 1.0
**Date**: 2025-11-07
**Status**: Draft
**Purpose**: Clear policy specifications for core matching engine components

---

## 1. Classification Trust Hierarchy

### Purpose
Assign a `classification_code` to every BIM item and price item using a deterministic, ordered list of sources. Classification codes group similar items (e.g., all HVAC equipment, all pipe fittings) to enable efficient candidate filtering.

### Trust Order (Priority)
The classifier stops at the first successful match:

1. **Explicit Override** (Priority: 100)
   - Fields: `omniclass_code`, `uniformat_code`
   - User or system explicitly provides classification
   - **Action**: Use provided code directly

2. **Curated Manual List** (Priority: 90)
   - Source: `config/curated_classifications.csv`
   - Match on: `family` + `type_name` combinations
   - Manually maintained mappings for common families
   - **Action**: Lookup in CSV; if match found, use that code

3. **Revit Category + System Type** (Priority: 70)
   - Uses Revit's built-in `Category` (e.g., "Mechanical Equipment", "Pipes") + `System Type` (e.g., "HVAC", "Domestic Hot Water")
   - Pre-configured rules map combinations to classification codes
   - **Action**: Apply rule-based mapping (see YAML config)

4. **Fallback Heuristics** (Priority: 50)
   - Keyword pattern matching in `family` or `type_name`
   - Example: "duct" or "diffuser" → 2302 (HVAC distribution)
   - **Action**: Search family/type text for keywords; assign code on match

5. **Unknown** (Priority: 0)
   - No classification source succeeded
   - **Action**: Assign code 9999; flag for mandatory manual review

### Invariants
- Classification must run **before** matching
- Every item and price must have a `classification_code` (even if 9999)
- Unknown classification (9999) **blocks auto-accept** (forces manual review)
- Trust order never skips levels (must check priority 100 → 90 → 70 → 50 → 0)

### Configuration
All rules stored in `config/classification_hierarchy.yaml` (no hardcoded logic).

---

## 2. Auto-Routing Policy

### Purpose
Determine whether a matched item pair can be auto-accepted or requires manual review based on confidence score and business risk flags.

### Confidence Bands
- **High**: Score ≥ 85%
  - Strong textual similarity + numeric attributes align
  - Example: RapidFuzz score 92% + width/height match within tolerance

- **Medium**: Score 70–84%
  - Moderate similarity or partial attribute match
  - Example: RapidFuzz score 75% but missing material confirmation

- **Low**: Score < 70%
  - Weak similarity or significant attribute mismatches
  - Example: RapidFuzz score 65% or numeric attributes differ beyond tolerance

### Auto-Accept Rule
**Accept automatically ONLY if:**
```
Confidence = High (≥85%) AND Flags = None
```

**Reject auto-accept if:**
- Confidence is Medium or Low (any score < 85%), OR
- Any flag is present (Critical-Veto or Advisory)

### Manual Review Queue
All items failing auto-accept criteria enter review queue with:
- Match candidates ranked by confidence
- All detected flags displayed
- Reasons for rejection (low confidence, specific flags)
- Historical mapping suggestions (if canonical key exists)

### Audit Trail
Every decision must record:
- `item_id`, `price_item_id`, `confidence_score`
- `decision` (auto-accepted / manual-review / rejected)
- `flags` (list of flag types)
- `reason` (human or system rationale)
- `created_by` (user or "system")
- `timestamp`

### Invariants
- Zero auto-accepts with active flags
- Zero auto-accepts below 85% confidence
- All decisions logged (no silent failures)

---

## 3. Risk Flags Taxonomy

### Purpose
Detect business-critical mismatches (Critical-Veto) and advisory concerns before accepting matches. Flags enforce safety and data quality.

---

### Critical-Veto Flags
**Severity**: Blocks auto-accept; disables "Accept" button in UI

#### 3.1 Unit Conflict
- **Condition**: `item.unit ≠ price.unit`
- **Example**: Item measured in meters (`m`) matched to price in each (`ea`)
- **Impact**: Cost calculation error (€/m vs €/ea)
- **Message**: "Item unit 'm' does not match price unit 'ea'"

#### 3.2 Size Mismatch
- **Condition**: Width, height, or DN (diameter) differ by > 10mm
- **Example**: Item width 200mm matched to price width 250mm (50mm difference)
- **Impact**: Wrong product specified (undersized/oversized)
- **Tolerance**: 10mm configurable via `SIZE_TOLERANCE_MM` env var
- **Message**: "Item dimensions differ by >10mm"

#### 3.3 Angle Mismatch
- **Condition**: Angle differs by > 5° (common for elbows: 45°, 90°)
- **Example**: 90° elbow matched to 45° elbow price
- **Impact**: Wrong fitting geometry
- **Tolerance**: 5° configurable via `ANGLE_TOLERANCE_DEG` env var
- **Message**: "Angle differs by >5°"

#### 3.4 Material Conflict
- **Condition**: Materials differ (after normalization: "steel" vs "copper", "galvanized" vs "stainless")
- **Example**: Steel pipe matched to copper pipe price
- **Impact**: Wrong material spec (corrosion, code compliance)
- **Note**: Uses slug normalization to handle "SS" = "Stainless Steel"
- **Message**: "Material mismatch: steel vs copper"

#### 3.5 Class Mismatch
- **Condition**: `item.classification_code ≠ price.classification_code`
- **Example**: Pipe fitting (2215) matched to HVAC equipment (2301)
- **Impact**: Fundamentally wrong product category
- **Message**: "Classification codes differ"
- **Note**: This should rarely occur due to classification blocking, but enforced as safety net

---

### Advisory Flags
**Severity**: Warns but allows accept with mandatory annotation

#### 3.6 Stale Price
- **Condition**: `price.last_updated` > 1 year old
- **Example**: Price last updated 2023-01-15, current date 2025-01-20
- **Impact**: Price may be outdated (inflation, vendor changes)
- **Action**: Accept requires annotation justifying use of old price
- **Message**: "Price is over 1 year old (last updated: 2023-01-15)"

#### 3.7 Currency/VAT Ambiguity
- **Condition**: `price.currency ≠ 'EUR'` OR `price.vat_rate IS NULL`
- **Example**: Price in GBP or VAT status unclear
- **Impact**: Manual conversion needed; cost calculation uncertainty
- **Action**: Accept requires explicit conversion rate or VAT assumption
- **Message**: "Non-EUR pricing (GBP) requires manual conversion" or "VAT rate not specified"

#### 3.8 Vendor Note
- **Condition**: Price has non-empty `vendor_note` field (e.g., "Discontinued", "Lead time 12 weeks")
- **Impact**: Procurement concerns (availability, delays)
- **Action**: Accept requires acknowledgment of note
- **Message**: "Vendor note: {note_content}"

---

### Flag Enforcement (UI Rules)

#### Critical-Veto Items:
- **"Accept" button**: Disabled (greyed out)
- **Required action**: Fix underlying issue (choose different candidate) OR override with supervisor approval (post-MVP)
- **No auto-accept**: System never auto-accepts items with Critical-Veto flags

#### Advisory Items:
- **"Accept" button**: Enabled but requires annotation field
- **Required action**: Provide written justification before accept
- **Auto-accept**: Blocked (any flag presence blocks auto-routing, even Advisory)

---

### Flag Configuration
All flag rules stored in `config/flags.yaml` with:
- `severity` (Critical-Veto / Advisory)
- `condition` (evaluable expression)
- `message` (template with variable substitution)

### Invariants
- Flags evaluated on **every** match candidate (before auto-routing)
- Multiple flags can coexist (e.g., Size + Material + Stale Price)
- Flag evaluation deterministic (same inputs → same flags)
- Critical-Veto **always** blocks accept (no exceptions in MVP)

---

## Implementation Notes

### Technology Stack
- **Language**: Python 3.11+
- **Framework**: Pydantic for data validation
- **Config**: YAML for classification rules and flags
- **Storage**: PostgreSQL with SCD Type-2 for mapping memory
- **CLI**: Typer for command interface

### Testing Requirements
- Unit tests for each trust level (classifier)
- Unit tests for confidence band thresholds
- Unit tests for each flag condition (Critical-Veto + Advisory)
- Integration test: two-pass learning curve demo
- Integration test: flag blocking auto-accept

### Performance Targets
- Classification: < 10ms per item (priority-ordered early exit)
- Flag evaluation: < 5ms per match pair (simple conditional logic)
- Auto-routing decision: < 1ms (boolean logic)

---

## References
- **Full PRP**: `/Users/ciarancox/BIMCalcKM/PRPs/PRP-001-BIMCALC-MVP.md`
- **Global Rules**: `/Users/ciarancox/BIMCalcKM/CLAUDE.md`
- **Config Templates**: See Appendix B in PRP (YAML examples)
