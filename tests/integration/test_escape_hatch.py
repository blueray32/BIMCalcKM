"""Integration tests for escape-hatch candidate generation.

Tests the out-of-class fallback mechanism per CLAUDE.md requirements.
"""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from bimcalc.db.models import Base, ItemModel, PriceItemModel
from bimcalc.matching.candidate_generator import CandidateGenerator
from bimcalc.matching.orchestrator import MatchOrchestrator
from bimcalc.models import Item


@pytest_asyncio.fixture()
async def db_session() -> AsyncSession:
    """Create in-memory database for testing."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    SessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    session = SessionLocal()
    try:
        yield session
    finally:
        await session.close()
        await engine.dispose()


@pytest.mark.asyncio
async def test_escape_hatch_engages_when_no_in_class_candidates(db_session: AsyncSession):
    """Test that escape-hatch engages when no in-class candidates exist.

    Scenario:
    - Item has classification_code=66 (Cable Tray)
    - No prices exist with classification_code=66
    - Prices exist with classification_code=22 (Piping)
    - Escape-hatch should engage and return out-of-class candidates
    """
    # Create item with classification 66
    item = ItemModel(
        org_id="acme",
        project_id="test-project",
        family="Cable Tray",
        type_name="Ladder Type 200x50",
        classification_code=66,
        canonical_key="66|cable_tray|ladder|w=200|h=50",
        unit="m",
        quantity=Decimal("10.0"),
        width_mm=200.0,
        height_mm=50.0,
    )
    db_session.add(item)
    await db_session.flush()

    # Create prices with DIFFERENT classification (22 instead of 66)
    price1 = PriceItemModel(
        org_id="acme",
        item_code="PIPE-200",
        region="IE",
        vendor_id="vendor",
        sku="PIPE-200",
        description="Steel pipe 200mm",
        classification_code=22,  # Out-of-class
        unit="m",
        unit_price=Decimal("15.0"),
        currency="EUR",
        source_name="test_catalog",
        source_currency="EUR",
        width_mm=200.0,
        last_updated=datetime.now(timezone.utc),
    )

    price2 = PriceItemModel(
        org_id="acme",
        item_code="PIPE-250",
        region="IE",
        vendor_id="vendor",
        sku="PIPE-250",
        description="Steel pipe 250mm",
        classification_code=22,  # Out-of-class
        unit="m",
        unit_price=Decimal("18.0"),
        currency="EUR",
        source_name="test_catalog",
        source_currency="EUR",
        width_mm=250.0,
        last_updated=datetime.now(timezone.utc),
    )

    db_session.add_all([price1, price2])
    await db_session.commit()

    # Test candidate generation with escape-hatch
    generator = CandidateGenerator(db_session)

    item_pydantic = Item(
        id=item.id,
        org_id=item.org_id,
        project_id=item.project_id,
        family=item.family,
        type_name=item.type_name,
        classification_code=item.classification_code,
        canonical_key=item.canonical_key,
        unit=item.unit,
        quantity=item.quantity,
        width_mm=item.width_mm,
        height_mm=item.height_mm,
    )

    candidates, used_escape_hatch = await generator.generate_with_escape_hatch(item_pydantic)

    # Assertions
    assert used_escape_hatch is True, "Escape-hatch should have been used"
    assert len(candidates) > 0, "Should have found out-of-class candidates"
    assert len(candidates) <= 2, "Should limit to max 2 escape-hatch candidates"

    # Verify candidate is out-of-class
    for candidate in candidates:
        assert candidate.classification_code == 22, "Candidate should be from different class"
        assert candidate.classification_code != item.classification_code


@pytest.mark.asyncio
async def test_escape_hatch_not_used_when_in_class_candidates_exist(db_session: AsyncSession):
    """Test that escape-hatch is NOT used when in-class candidates exist.

    Scenario:
    - Item has classification_code=66
    - Prices exist with classification_code=66
    - Escape-hatch should NOT engage
    - Should return in-class candidates only
    """
    # Create item with classification 66
    item = ItemModel(
        org_id="acme",
        project_id="test-project",
        family="Cable Tray",
        type_name="Ladder Type 200x50",
        classification_code=66,
        canonical_key="66|cable_tray|ladder|w=200|h=50",
        unit="m",
        quantity=Decimal("10.0"),
        width_mm=200.0,
        height_mm=50.0,
    )
    db_session.add(item)
    await db_session.flush()

    # Create prices with SAME classification (66)
    price1 = PriceItemModel(
        org_id="acme",
        item_code="CT-200",
        region="IE",
        vendor_id="vendor",
        sku="CT-200",
        description="Cable tray 200mm",
        classification_code=66,  # In-class
        unit="m",
        unit_price=Decimal("25.0"),
        currency="EUR",
        source_name="test_catalog",
        source_currency="EUR",
        width_mm=200.0,
        last_updated=datetime.now(timezone.utc),
    )

    db_session.add(price1)
    await db_session.commit()

    # Test candidate generation with escape-hatch
    generator = CandidateGenerator(db_session)

    item_pydantic = Item(
        id=item.id,
        org_id=item.org_id,
        project_id=item.project_id,
        family=item.family,
        type_name=item.type_name,
        classification_code=item.classification_code,
        canonical_key=item.canonical_key,
        unit=item.unit,
        quantity=item.quantity,
        width_mm=item.width_mm,
        height_mm=item.height_mm,
    )

    candidates, used_escape_hatch = await generator.generate_with_escape_hatch(item_pydantic)

    # Assertions
    assert used_escape_hatch is False, "Escape-hatch should NOT have been used"
    assert len(candidates) > 0, "Should have found in-class candidates"

    # Verify all candidates are in-class
    for candidate in candidates:
        assert candidate.classification_code == 66, "All candidates should be in-class"


@pytest.mark.asyncio
async def test_orchestrator_adds_classification_mismatch_flag_for_escape_hatch(db_session: AsyncSession):
    """Test that orchestrator adds Classification Mismatch flag when escape-hatch is used.

    Scenario:
    - Item with classification 66, no in-class prices
    - Escape-hatch finds out-of-class price (classification 22)
    - Orchestrator should add CRITICAL_VETO "Classification Mismatch" flag
    - Match should require manual review (not auto-accepted)
    """
    # Create item with classification 66
    item = ItemModel(
        org_id="acme",
        project_id="test-project",
        family="Cable Tray",
        type_name="Ladder Type 200x50",
        classification_code=66,
        canonical_key="66|cable_tray|ladder|w=200|h=50",
        unit="m",
        quantity=Decimal("10.0"),
        width_mm=200.0,
        height_mm=50.0,
    )
    db_session.add(item)
    await db_session.flush()

    # Create out-of-class price
    price = PriceItemModel(
        org_id="acme",
        item_code="PIPE-200",
        region="IE",
        vendor_id="vendor",
        sku="PIPE-200",
        description="Cable Tray Ladder Type 200x50 (Misclassified)",
        classification_code=22,  # Out-of-class
        unit="m",
        unit_price=Decimal("15.0"),
        currency="EUR",
        source_name="test_catalog",
        source_currency="EUR",
        width_mm=200.0,
        height_mm=50.0,
    )
    db_session.add(price)
    await db_session.commit()

    # Run orchestrator
    orchestrator = MatchOrchestrator(db_session)

    item_pydantic = Item(
        id=item.id,
        org_id=item.org_id,
        project_id=item.project_id,
        family=item.family,
        type_name=item.type_name,
        classification_code=item.classification_code,
        canonical_key=item.canonical_key,
        unit=item.unit,
        quantity=item.quantity,
        width_mm=item.width_mm,
        height_mm=item.height_mm,
    )

    result, matched_price = await orchestrator.match(item_pydantic, created_by="test")

    # Assertions
    assert result.decision == "manual-review", "Escape-hatch matches should require manual review"
    assert matched_price is not None, "Should have found a match via escape-hatch"

    # Check for Classification Mismatch flag
    flag_types = [f.type for f in result.flags]
    assert "Classification Mismatch" in flag_types, "Should have Classification Mismatch flag"

    # Verify flag is CRITICAL_VETO
    classification_flag = next(f for f in result.flags if f.type == "Classification Mismatch")
    assert classification_flag.severity == "Critical-Veto", "Classification Mismatch must be Critical-Veto"
    assert "escape-hatch" in classification_flag.message.lower(), "Flag should mention escape-hatch"


@pytest.mark.asyncio
async def test_escape_hatch_respects_numeric_filters(db_session: AsyncSession):
    """Test that escape-hatch still applies numeric pre-filters.

    Scenario:
    - Item has width=200mm
    - Out-of-class prices exist with width=200mm and width=500mm
    - Escape-hatch should only return prices within tolerance (200mm ± tolerance)
    """
    # Create item with width=200mm
    item = ItemModel(
        org_id="acme",
        project_id="test-project",
        family="Cable Tray",
        type_name="Ladder Type 200x50",
        classification_code=66,
        unit="m",
        quantity=Decimal("10.0"),
        width_mm=200.0,
        height_mm=50.0,
    )
    db_session.add(item)
    await db_session.flush()

    # Create out-of-class prices with different widths
    price_close = PriceItemModel(
        org_id="acme",
        item_code="PIPE-200",
        region="IE",
        vendor_id="vendor",
        sku="PIPE-200",
        description="Pipe 200mm",
        classification_code=22,
        unit="m",
        unit_price=Decimal("15.0"),
        currency="EUR",
        source_name="test_catalog",
        source_currency="EUR",
        width_mm=200.0,  # Close match
        last_updated=datetime.now(timezone.utc),
    )

    price_far = PriceItemModel(
        org_id="acme",
        item_code="PIPE-500",
        region="IE",
        vendor_id="vendor",
        sku="PIPE-500",
        description="Pipe 500mm",
        classification_code=22,
        unit="m",
        unit_price=Decimal("35.0"),
        currency="EUR",
        source_name="test_catalog",
        source_currency="EUR",
        width_mm=500.0,  # Too different
        last_updated=datetime.now(timezone.utc),
    )

    db_session.add_all([price_close, price_far])
    await db_session.commit()

    # Test escape-hatch
    generator = CandidateGenerator(db_session)

    item_pydantic = Item(
        id=item.id,
        org_id=item.org_id,
        project_id=item.project_id,
        family=item.family,
        type_name=item.type_name,
        classification_code=item.classification_code,
        unit=item.unit,
        quantity=item.quantity,
        width_mm=item.width_mm,
        height_mm=item.height_mm,
    )

    candidates, used_escape_hatch = await generator.generate_with_escape_hatch(item_pydantic)

    # Assertions
    assert used_escape_hatch is True, "Escape-hatch should be used"
    assert len(candidates) == 1, "Should only return price within tolerance"
    assert candidates[0].sku == "PIPE-200", "Should return the 200mm pipe, not 500mm"
    assert candidates[0].width_mm == 200.0, "Width should match within tolerance"
