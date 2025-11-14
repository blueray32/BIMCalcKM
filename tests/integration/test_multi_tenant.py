"""Integration tests for multi-tenant price isolation.

Tests that org_id properly isolates price catalogs between organizations.
"""

from __future__ import annotations

from decimal import Decimal
from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from bimcalc.db.models import Base, ItemModel, PriceItemModel
from bimcalc.matching.candidate_generator import CandidateGenerator
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
async def test_candidate_generation_filters_by_org_id(db_session: AsyncSession):
    """Test that candidate generation only returns prices for the item's organization.

    Scenario:
    - Organization 'acme' has item and prices
    - Organization 'beta' has prices with same classification
    - Item from 'acme' should only match 'acme' prices
    """
    # Create item for org 'acme'
    item_acme = ItemModel(
        org_id="acme",
        project_id="acme-project",
        family="Cable Tray",
        type_name="Ladder Type 200x50",
        classification_code=66,
        canonical_key="66|cable_tray|ladder|w=200|h=50",
        unit="m",
        quantity=Decimal("10.0"),
        width_mm=200.0,
    )
    db_session.add(item_acme)
    await db_session.flush()

    # Create prices for org 'acme'
    price_acme = PriceItemModel(
        org_id="acme",
        item_code="CT-200-ACME",
        region="IE",
        vendor_id="acme-vendor",
        sku="CT-200-ACME",
        description="ACME Cable tray 200mm",
        classification_code=66,
        unit="m",
        unit_price=Decimal("25.0"),
        currency="EUR",
        source_name="acme_catalog",
        source_currency="EUR",
        width_mm=200.0,
    )

    # Create prices for org 'beta' (same classification!)
    price_beta = PriceItemModel(
        org_id="beta",
        item_code="CT-200-BETA",
        region="IE",
        vendor_id="beta-vendor",
        sku="CT-200-BETA",
        description="BETA Cable tray 200mm",
        classification_code=66,  # Same classification as acme item
        unit="m",
        unit_price=Decimal("20.0"),  # Different price
        currency="EUR",
        source_name="beta_catalog",
        source_currency="EUR",
        width_mm=200.0,
    )

    db_session.add_all([price_acme, price_beta])
    await db_session.commit()

    # Test candidate generation for acme item
    generator = CandidateGenerator(db_session)

    item_pydantic = Item(
        id=item_acme.id,
        org_id=item_acme.org_id,
        project_id=item_acme.project_id,
        family=item_acme.family,
        type_name=item_acme.type_name,
        classification_code=item_acme.classification_code,
        canonical_key=item_acme.canonical_key,
        unit=item_acme.unit,
        quantity=item_acme.quantity,
        width_mm=item_acme.width_mm,
    )

    candidates = await generator.generate(item_pydantic)

    # Assertions
    assert len(candidates) == 1, "Should only return prices from same org"
    assert candidates[0].sku == "CT-200-ACME", "Should return acme price, not beta"
    assert candidates[0].unit_price == Decimal("25.0"), "Should return acme price"

    # Explicitly verify beta price was NOT returned
    beta_skus = [c.sku for c in candidates if c.sku == "CT-200-BETA"]
    assert len(beta_skus) == 0, "Beta price should NOT be in candidates"


@pytest.mark.asyncio
async def test_no_cross_org_matching_even_with_perfect_match(db_session: AsyncSession):
    """Test that perfect matches from other orgs are excluded.

    Scenario:
    - Org 'acme' item with no acme prices
    - Org 'beta' has perfect match (same canonical key, classification, everything)
    - Should NOT match beta price, even though it's perfect
    """
    # Create item for org 'acme'
    item_acme = ItemModel(
        org_id="acme",
        project_id="acme-project",
        family="Cable Tray",
        type_name="Elbow 90",
        classification_code=66,
        canonical_key="66|cable_tray|elbow|w=200|h=50|a=90",
        unit="ea",
        quantity=Decimal("5.0"),
        width_mm=200.0,
        height_mm=50.0,
        angle_deg=90.0,
    )
    db_session.add(item_acme)
    await db_session.flush()

    # Create PERFECT match price for org 'beta' (but wrong org!)
    price_beta_perfect = PriceItemModel(
        org_id="beta",
        item_code="CT-ELBOW-90",
        region="IE",
        vendor_id="beta-vendor",
        sku="CT-ELBOW-90-BETA",
        description="Cable tray elbow 90° 200x50mm",
        classification_code=66,  # Same
        unit="ea",  # Same
        unit_price=Decimal("15.0"),
        currency="EUR",
        source_name="beta_catalog",
        source_currency="EUR",
        width_mm=200.0,  # Same
        height_mm=50.0,  # Same
        angle_deg=90.0,  # Same
    )

    db_session.add(price_beta_perfect)
    await db_session.commit()

    # Test candidate generation
    generator = CandidateGenerator(db_session)

    item_pydantic = Item(
        id=item_acme.id,
        org_id=item_acme.org_id,
        project_id=item_acme.project_id,
        family=item_acme.family,
        type_name=item_acme.type_name,
        classification_code=item_acme.classification_code,
        canonical_key=item_acme.canonical_key,
        unit=item_acme.unit,
        quantity=item_acme.quantity,
        width_mm=item_acme.width_mm,
        height_mm=item_acme.height_mm,
        angle_deg=item_acme.angle_deg,
    )

    candidates = await generator.generate(item_pydantic)

    # Assertions
    assert len(candidates) == 0, "Should not return any candidates from different org"


@pytest.mark.asyncio
async def test_escape_hatch_respects_org_isolation(db_session: AsyncSession):
    """Test that escape-hatch also respects org_id isolation.

    Scenario:
    - Org 'acme' item with no in-class prices for acme
    - Org 'beta' has out-of-class prices
    - Escape-hatch should NOT return beta prices
    """
    # Create item for org 'acme' with classification 66
    item_acme = ItemModel(
        org_id="acme",
        project_id="acme-project",
        family="Cable Tray",
        type_name="Ladder Type 200x50",
        classification_code=66,
        unit="m",
        quantity=Decimal("10.0"),
        width_mm=200.0,
    )
    db_session.add(item_acme)
    await db_session.flush()

    # Create out-of-class prices for org 'beta' (classification 22)
    price_beta = PriceItemModel(
        org_id="beta",
        item_code="PIPE-200",
        region="IE",
        vendor_id="beta-vendor",
        sku="PIPE-200-BETA",
        description="Beta pipe 200mm",
        classification_code=22,  # Out-of-class
        unit="m",
        unit_price=Decimal("15.0"),
        currency="EUR",
        source_name="beta_catalog",
        source_currency="EUR",
        width_mm=200.0,
    )

    db_session.add(price_beta)
    await db_session.commit()

    # Test escape-hatch
    generator = CandidateGenerator(db_session)

    item_pydantic = Item(
        id=item_acme.id,
        org_id=item_acme.org_id,
        project_id=item_acme.project_id,
        family=item_acme.family,
        type_name=item_acme.type_name,
        classification_code=item_acme.classification_code,
        unit=item_acme.unit,
        quantity=item_acme.quantity,
        width_mm=item_acme.width_mm,
    )

    candidates, used_escape_hatch = await generator.generate_with_escape_hatch(item_pydantic)

    # Assertions
    # Escape-hatch should be attempted but find nothing (org isolation)
    assert len(candidates) == 0, "Should not return candidates from different org, even with escape-hatch"


@pytest.mark.asyncio
async def test_multiple_orgs_with_same_item_codes(db_session: AsyncSession):
    """Test that different orgs can have same item_codes without conflicts.

    Scenario:
    - Org 'acme' has price with item_code='CT-200'
    - Org 'beta' has price with item_code='CT-200' (same code)
    - Both are active (is_current=true)
    - No unique constraint violations should occur
    - Candidate generation should return correct org's price
    """
    # Create prices with SAME item_code for different orgs
    price_acme = PriceItemModel(
        org_id="acme",
        item_code="CT-200",  # Same code
        region="IE",
        vendor_id="acme-vendor",
        sku="SKU-ACME",
        description="ACME Cable tray 200mm",
        classification_code=66,
        unit="m",
        unit_price=Decimal("25.0"),
        currency="EUR",
        source_name="acme_catalog",
        source_currency="EUR",
    )

    price_beta = PriceItemModel(
        org_id="beta",
        item_code="CT-200",  # Same code (should not conflict)
        region="IE",
        vendor_id="beta-vendor",
        sku="SKU-BETA",
        description="BETA Cable tray 200mm",
        classification_code=66,
        unit="m",
        unit_price=Decimal("30.0"),
        currency="EUR",
        source_name="beta_catalog",
        source_currency="EUR",
    )

    db_session.add_all([price_acme, price_beta])
    await db_session.commit()  # Should not raise unique constraint error

    # Create item for acme
    item_acme = ItemModel(
        org_id="acme",
        project_id="acme-project",
        family="Cable Tray",
        type_name="Standard 200mm",
        classification_code=66,
        unit="m",
        quantity=Decimal("10.0"),
    )
    db_session.add(item_acme)
    await db_session.flush()

    # Test candidate generation returns correct org's price
    generator = CandidateGenerator(db_session)

    item_pydantic = Item(
        id=item_acme.id,
        org_id=item_acme.org_id,
        project_id=item_acme.project_id,
        family=item_acme.family,
        type_name=item_acme.type_name,
        classification_code=item_acme.classification_code,
        unit=item_acme.unit,
        quantity=item_acme.quantity,
    )

    candidates = await generator.generate(item_pydantic)

    # Assertions
    assert len(candidates) == 1, "Should return exactly one candidate"
    assert candidates[0].sku == "SKU-ACME", "Should return acme's price"
    assert candidates[0].unit_price == Decimal("25.0"), "Should return acme's unit price"


@pytest.mark.asyncio
async def test_org_id_required_for_candidate_generation(db_session: AsyncSession):
    """Test that candidate generation raises error if org_id is None.

    Per audit fix: org_id is required for multi-tenant filtering.
    """
    # Create item without org_id
    item_no_org = Item(
        id=uuid4(),
        org_id=None,  # Missing org_id
        project_id="test-project",
        family="Cable Tray",
        type_name="Test",
        classification_code=66,
    )

    generator = CandidateGenerator(db_session)

    # Should raise ValueError
    with pytest.raises(ValueError, match="org_id is required"):
        await generator.generate(item_no_org)
