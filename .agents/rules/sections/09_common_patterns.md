# Common Patterns

## BIMCalc-Specific Patterns

### 1. Classification-First Blocking

**Pattern**: Use classification to reduce candidate space before fuzzy matching.

```python
def get_candidates(item: dict) -> list[dict]:
    """Get matching candidates using classification-first blocking."""
    # Step 1: Classify item
    classification = classify_item(item)

    # Step 2: Block by classification (if trusted)
    if classification.trust_level in ["high", "medium"]:
        candidates = query_by_classification(classification.code)
    else:
        # Escape hatch: broader search
        candidates = query_by_category(item["category"])

    return candidates
```

**When to Use**: All matching operations.

---

### 2. Canonical Key Generation

**Pattern**: Generate normalized, deterministic keys for deduplication and matching.

```python
def canonical_key(item: dict) -> str:
    """Generate canonical key from item attributes.

    Handles:
    - Unicode normalization (× → x)
    - Size/angle/unit parsing
    - Case normalization
    - Material standardization
    """
    description = normalize_unicode(item["description"])
    size = parse_size(description)
    material = parse_material(description)

    components = [
        item.get("category", "unknown").lower(),
        size or "",
        material or "",
    ]

    return "-".join(c for c in components if c)
```

**When to Use**: Before storing mappings, before matching, for deduplication.

---

### 3. SCD Type-2 Mapping

**Pattern**: Store temporal history with one active row per key.

```python
def create_mapping(canonical_key: str, pricebook_id: int, effective_date: date) -> ItemMapping:
    """Create new mapping, closing any active previous mapping."""
    # Step 1: Close active row (if exists)
    active = get_active_mapping(canonical_key)
    if active:
        active.end_date = effective_date - timedelta(days=1)
        db.commit()

    # Step 2: Create new active row
    new_mapping = ItemMapping(
        canonical_key=canonical_key,
        pricebook_item_id=pricebook_id,
        effective_date=effective_date,
        end_date=None,  # NULL = active
    )
    db.add(new_mapping)
    db.commit()

    return new_mapping

def get_active_mapping(canonical_key: str) -> ItemMapping | None:
    """Get currently active mapping."""
    return db.query(ItemMapping).filter(
        ItemMapping.canonical_key == canonical_key,
        ItemMapping.end_date.is_(None)
    ).first()

def get_mapping_as_of(canonical_key: str, as_of_date: date) -> ItemMapping | None:
    """Get mapping as of a specific date (for historical reports)."""
    return db.query(ItemMapping).filter(
        ItemMapping.canonical_key == canonical_key,
        ItemMapping.effective_date <= as_of_date,
        (ItemMapping.end_date.is_(None) | (ItemMapping.end_date >= as_of_date))
    ).first()
```

**When to Use**: All mapping storage, historical reporting.

---

### 4. Risk Flag Engine

**Pattern**: Detect risks and classify as Critical-Veto vs Advisory.

```python
from enum import Enum

class FlagSeverity(str, Enum):
    CRITICAL_VETO = "critical-veto"  # Blocks auto-accept
    ADVISORY = "advisory"            # Warns only

class Flag(BaseModel):
    type: str
    severity: FlagSeverity
    message: str
    data: dict = {}

def compute_flags(match: Match) -> list[Flag]:
    """Compute risk flags for a match."""
    flags = []

    # Price variance check
    if abs(match.price_diff_pct) > 20:
        flags.append(Flag(
            type="price_outlier",
            severity=FlagSeverity.CRITICAL_VETO,
            message=f"Price variance {match.price_diff_pct:.1f}% exceeds threshold"
        ))

    # Low confidence
    if match.confidence < 0.8:
        flags.append(Flag(
            type="low_confidence",
            severity=FlagSeverity.ADVISORY,
            message=f"Confidence {match.confidence:.2f} below 0.8"
        ))

    return flags

def can_auto_accept(match: Match) -> bool:
    """Check if match can be auto-accepted."""
    if match.confidence < 0.95:
        return False

    # Critical-Veto flags block auto-accept
    has_critical = any(
        f.severity == FlagSeverity.CRITICAL_VETO
        for f in match.flags
    )

    return not has_critical
```

**When to Use**: After matching, before auto-accept, in review UI.

---

### 5. Trust Hierarchy

**Pattern**: Prioritize classification sources by trust level.

```python
TRUST_HIERARCHY = [
    ("omniclass", "high"),
    ("uniclass", "high"),
    ("curated_map", "high"),
    ("category_system", "medium"),
    ("heuristic", "low"),
    ("unknown", "none"),
]

def classify_item(
    description: str,
    omniclass: str | None = None,
    uniclass: str | None = None,
    category: str | None = None,
) -> Classification:
    """Classify using trust hierarchy."""
    # Check sources in order of trust
    if omniclass:
        return Classification(code=omniclass, source="omniclass", trust_level="high")

    if uniclass:
        return Classification(code=uniclass, source="uniclass", trust_level="high")

    # Check curated mapping
    curated = lookup_curated_map(description)
    if curated:
        return Classification(code=curated, source="curated_map", trust_level="high")

    # Category-based
    if category:
        return Classification(code=category, source="category_system", trust_level="medium")

    # Heuristic
    heuristic = apply_heuristics(description)
    if heuristic:
        return Classification(code=heuristic, source="heuristic", trust_level="low")

    # Unknown (escape hatch)
    return Classification(code="UNKNOWN", source="unknown", trust_level="none")
```

**When to Use**: All classification operations.

---

### 6. Two-Pass Matching

**Pattern**: First pass creates mappings, second pass uses them for instant matching.

```python
def match_item(item: dict) -> Match:
    """Match item using two-pass strategy."""
    canonical = canonical_key(item)

    # Check if we've seen this before (Pass 2)
    existing_mapping = get_active_mapping(canonical)
    if existing_mapping:
        return Match(
            pricebook_id=existing_mapping.pricebook_item_id,
            confidence=1.0,
            source="canonical_key",
            flags=[]
        )

    # First time seeing this item (Pass 1)
    candidates = get_candidates(item)
    best_match = rank_candidates(item, candidates)

    # Don't auto-create mapping - require review
    return best_match
```

**When to Use**: Matching pipeline.

---

### 7. Repository Pattern

**Pattern**: Separate data access from business logic.

```python
# Repository
class ItemMappingRepository:
    """Data access for ItemMapping."""

    def __init__(self, db: Session):
        self.db = db

    def get_active(self, canonical_key: str) -> ItemMapping | None:
        return self.db.query(ItemMapping).filter(...).first()

    def create(self, mapping: ItemMapping) -> ItemMapping:
        self.db.add(mapping)
        self.db.commit()
        return mapping

# Service (business logic)
class MappingService:
    """Business logic for mappings."""

    def __init__(self, repo: ItemMappingRepository):
        self.repo = repo

    def create_mapping_with_scd2(
        self,
        canonical_key: str,
        pricebook_id: int
    ) -> ItemMapping:
        # Business logic: close old, create new
        active = self.repo.get_active(canonical_key)
        if active:
            active.end_date = date.today()
            self.repo.update(active)

        new_mapping = ItemMapping(canonical_key=canonical_key, ...)
        return self.repo.create(new_mapping)
```

**When to Use**: All database operations.

---

### 8. Configuration Management

**Pattern**: Centralized, environment-based configuration.

```python
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    """Application settings."""

    # Database
    database_url: str

    # Matching
    min_confidence: float = 0.7
    auto_accept_threshold: float = 0.95

    # External services
    crail4_api_key: str | None = None
    openai_api_key: str | None = None

    class Config:
        env_file = ".env"

settings = Settings()
```

**When to Use**: All configuration access.

---

## Anti-Patterns to Avoid

### 1. Multiple Active Rows (SCD2 Violation)
```python
# BAD: Creates duplicate active rows
new_mapping = ItemMapping(canonical_key=key, end_date=None)
db.add(new_mapping)  # Didn't close old active row!

# GOOD: Always close old before creating new
close_active_mapping(key)
new_mapping = ItemMapping(canonical_key=key, end_date=None)
db.add(new_mapping)
```

### 2. Ignoring Classification Trust
```python
# BAD: Uses heuristic when Omniclass available
classification = apply_heuristics(description)

# GOOD: Respect trust hierarchy
classification = classify_item(description, omniclass=omniclass)
```

### 3. Auto-Accepting Critical-Veto Matches
```python
# BAD: Auto-accepts despite critical flag
if match.confidence > 0.95:
    accept_match(match)

# GOOD: Check flags first
if can_auto_accept(match):
    accept_match(match)
```

---

**Note**: These patterns are battle-tested in BIMCalc. Deviate with caution and document why.
