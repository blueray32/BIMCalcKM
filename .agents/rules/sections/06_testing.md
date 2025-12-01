# Testing

## Testing Strategy

### Test Structure

```
tests/
├── unit/              # Unit tests (isolated, fast)
│   ├── test_classifier.py
│   ├── test_canonical.py
│   ├── test_flags.py
│   └── test_mapping.py
├── integration/       # Integration tests (database, external services)
│   ├── test_matching_integration.py
│   └── test_reporting.py
├── fixtures/          # Test data
│   ├── sample_schedules.csv
│   └── sample_pricebook.csv
└── conftest.py        # Shared fixtures
```

### Test Categories

#### Unit Tests
- Test single functions/classes in isolation
- Mock external dependencies
- Fast (<1s per test)
- High coverage (>80%)

```python
def test_canonical_key_normalization():
    """Test canonical key handles Unicode normalization."""
    item = {"description": "Cable × 2.5mm²"}
    key = canonical_key(item)
    assert "x" in key  # × normalized to x
    assert "2.5mm" in key
```

#### Integration Tests
- Test multiple components together
- Use test database
- Test actual queries and transactions
- Slower but realistic

```python
@pytest.mark.integration
def test_matching_pipeline_end_to_end(db_session):
    """Test complete matching workflow."""
    # Ingest schedule
    schedule_items = ingest_schedule("fixtures/sample_schedules.csv")

    # Run matching
    matches = run_matching_pipeline(schedule_items)

    # Verify results
    assert len(matches) > 0
    assert all(m.confidence >= 0.7 for m in matches)
```

### Fixtures

Use pytest fixtures for common setup:

```python
# conftest.py
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

@pytest.fixture
def db_session():
    """Provide test database session."""
    engine = create_engine("postgresql://test_db")
    session = Session(engine)
    yield session
    session.rollback()
    session.close()

@pytest.fixture
def sample_item():
    """Provide sample item for testing."""
    return {
        "description": "Cable 2.5mm² Red",
        "category": "Cables",
        "unit": "m",
    }
```

### BIMCalc-Specific Tests

#### Classification Tests
```python
def test_classification_trust_hierarchy():
    """Test trust hierarchy precedence."""
    # Omni classification should win over category
    result = classify_item(
        description="Cable",
        omni_class="12-34-56",
        category_hint="Electrical"
    )
    assert result.source == "omniclass"
    assert result.trust_level == "high"
```

#### SCD2 Tests
```python
def test_mapping_scd2_one_active_row(db_session):
    """Verify only one active row per canonical key."""
    key = "cable-2.5mm-red"

    # Create initial mapping
    create_mapping(key, pricebook_id=1)

    # Update mapping (should close old, create new)
    create_mapping(key, pricebook_id=2)

    # Verify only one active
    active = db_session.query(ItemMapping).filter(
        ItemMapping.canonical_key == key,
        ItemMapping.end_date.is_(None)
    ).all()

    assert len(active) == 1
    assert active[0].pricebook_id == 2
```

#### Flag Tests
```python
def test_critical_veto_flag_blocks_auto_accept():
    """Critical-Veto flags prevent auto-acceptance."""
    match = Match(
        confidence=0.95,
        flags=[Flag(type="price_outlier", severity="critical-veto")]
    )

    assert not match.can_auto_accept()
    assert match.requires_review()
```

#### Two-Pass Demo Test
```python
def test_two_pass_matching_determinism():
    """Second pass should auto-match via canonical key."""
    # First pass: manual mapping
    first_pass = run_matching(items)
    manually_accept_match(first_pass[0])

    # Second pass: same items
    second_pass = run_matching(items)

    # Should auto-match using stored canonical key
    assert second_pass[0].confidence == 1.0
    assert second_pass[0].source == "canonical_key"
```

### Running Tests

```bash
# All tests
pytest

# Unit tests only
pytest tests/unit

# Integration tests
pytest tests/integration -m integration

# With coverage
pytest --cov=bimcalc --cov-report=html

# Specific test
pytest tests/unit/test_classifier.py::test_classification_trust_hierarchy

# Verbose
pytest -v

# Stop on first failure
pytest -x
```

### Coverage Requirements

- **Minimum**: 80% overall coverage
- **Critical paths**: 95%+ coverage
  - Classification engine
  - Canonical key generation
  - SCD2 mapping operations
  - Flag engine
  - Matching pipeline

---

**CI/CD**: Tests run automatically on pull requests. Must pass before merge.
