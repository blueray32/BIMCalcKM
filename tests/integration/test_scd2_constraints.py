"""Integration tests for SCD2 (Slowly Changing Dimension Type-2) invariants.

Tests that database enforces proper SCD2 constraints and temporal integrity.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from bimcalc.db.models import Base, ItemMappingModel, PriceItemModel


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
async def test_price_unique_constraint_prevents_duplicate_active_records(db_session: AsyncSession):
    """Test that database prevents multiple active prices for same (org_id, item_code, region).

    Per CLAUDE.md: "Enforce one active record per (org_id, item_code, region)"

    Scenario:
    - Create active price for (org='acme', item_code='CT-200', region='IE')
    - Attempt to create another active price with same key
    - Should raise IntegrityError due to unique index
    """
    # Create first active price
    price1 = PriceItemModel(
        org_id="acme",
        item_code="CT-200",
        region="IE",
        vendor_id="vendor",
        sku="CT-200-V1",
        description="Cable tray 200mm version 1",
        classification_code=66,
        unit="m",
        unit_price=Decimal("25.0"),
        currency="EUR",
        source_name="catalog",
        source_currency="EUR",
        is_current=True,  # Active
    )

    db_session.add(price1)
    await db_session.commit()

    # Attempt to create duplicate active price (same org, item_code, region)
    price2_duplicate = PriceItemModel(
        org_id="acme",
        item_code="CT-200",
        region="IE",
        vendor_id="vendor",
        sku="CT-200-V2",  # Different SKU
        description="Cable tray 200mm version 2",
        classification_code=66,
        unit="m",
        unit_price=Decimal("27.0"),  # Different price
        currency="EUR",
        source_name="catalog",
        source_currency="EUR",
        is_current=True,  # Also active - SHOULD FAIL
    )

    db_session.add(price2_duplicate)

    # Should raise IntegrityError
    with pytest.raises(IntegrityError, match="UNIQUE constraint failed|duplicate key"):
        await db_session.commit()


@pytest.mark.asyncio
async def test_price_allows_multiple_inactive_records(db_session: AsyncSession):
    """Test that multiple inactive (is_current=false) prices are allowed.

    Scenario:
    - Create inactive price for (org='acme', item_code='CT-200', region='IE')
    - Create another inactive price with same key
    - Should succeed (unique constraint only applies to active records)
    """
    # Create first inactive price
    price1 = PriceItemModel(
        org_id="acme",
        item_code="CT-200",
        region="IE",
        vendor_id="vendor",
        sku="CT-200-OLD1",
        description="Cable tray 200mm old version 1",
        classification_code=66,
        unit="m",
        unit_price=Decimal("23.0"),
        currency="EUR",
        source_name="catalog",
        source_currency="EUR",
        is_current=False,  # Inactive
        valid_to=datetime.utcnow() - timedelta(days=30),
    )

    # Create second inactive price (same key)
    price2 = PriceItemModel(
        org_id="acme",
        item_code="CT-200",
        region="IE",
        vendor_id="vendor",
        sku="CT-200-OLD2",
        description="Cable tray 200mm old version 2",
        classification_code=66,
        unit="m",
        unit_price=Decimal("24.0"),
        currency="EUR",
        source_name="catalog",
        source_currency="EUR",
        is_current=False,  # Also inactive
        valid_to=datetime.utcnow() - timedelta(days=15),
    )

    db_session.add_all([price1, price2])
    await db_session.commit()  # Should succeed

    # Verify both records exist
    result = await db_session.execute(
        select(PriceItemModel).where(
            PriceItemModel.org_id == "acme",
            PriceItemModel.item_code == "CT-200",
            PriceItemModel.region == "IE",
            PriceItemModel.is_current == False,
        )
    )
    inactive_prices = result.scalars().all()

    assert len(inactive_prices) == 2, "Should allow multiple inactive records"


@pytest.mark.asyncio
async def test_price_scd2_temporal_integrity_with_valid_period(db_session: AsyncSession):
    """Test SCD2 temporal integrity: valid_to > valid_from.

    Scenario:
    - Attempt to create price with valid_to <= valid_from
    - Should violate check constraint
    """
    now = datetime.utcnow()

    # Create price with invalid temporal period (valid_to before valid_from)
    price_invalid = PriceItemModel(
        org_id="acme",
        item_code="CT-200",
        region="IE",
        vendor_id="vendor",
        sku="CT-200",
        description="Cable tray 200mm",
        classification_code=66,
        unit="m",
        unit_price=Decimal("25.0"),
        currency="EUR",
        source_name="catalog",
        source_currency="EUR",
        is_current=False,
        valid_from=now,
        valid_to=now - timedelta(days=1),  # Before valid_from - INVALID
    )

    db_session.add(price_invalid)

    # Should raise IntegrityError due to check constraint
    with pytest.raises(IntegrityError, match="check_valid_period|CHECK constraint"):
        await db_session.commit()


@pytest.mark.asyncio
async def test_mapping_unique_constraint_prevents_duplicate_active_records(db_session: AsyncSession):
    """Test that database prevents multiple active mappings for same (org_id, canonical_key).

    Per CLAUDE.md: "One active row per (org_id, canonical_key)"

    Scenario:
    - Create active mapping for (org='acme', canonical_key='key-123')
    - Attempt to create another active mapping with same key
    - Should raise IntegrityError
    """
    # Create first active mapping
    mapping1 = ItemMappingModel(
        org_id="acme",
        canonical_key="key-123",
        price_item_id=UUID("00000000-0000-0000-0000-000000000001"),
        created_by="user1",
        reason="First mapping",
        start_ts=datetime.utcnow(),
        end_ts=None,  # Active
    )

    db_session.add(mapping1)
    await db_session.commit()

    # Attempt to create duplicate active mapping
    mapping2_duplicate = ItemMappingModel(
        org_id="acme",
        canonical_key="key-123",  # Same key
        price_item_id=UUID("00000000-0000-0000-0000-000000000002"),  # Different price
        created_by="user2",
        reason="Second mapping",
        start_ts=datetime.utcnow(),
        end_ts=None,  # Also active - SHOULD FAIL
    )

    db_session.add(mapping2_duplicate)

    # Should raise IntegrityError
    with pytest.raises(IntegrityError, match="UNIQUE constraint failed|duplicate key"):
        await db_session.commit()


@pytest.mark.asyncio
async def test_mapping_allows_multiple_inactive_records(db_session: AsyncSession):
    """Test that multiple inactive (end_ts is not None) mappings are allowed.

    Scenario:
    - Create inactive mapping for (org='acme', canonical_key='key-123')
    - Create another inactive mapping with same key
    - Should succeed (unique constraint only applies to active records)
    """
    now = datetime.utcnow()

    # Create first inactive mapping
    mapping1 = ItemMappingModel(
        org_id="acme",
        canonical_key="key-123",
        price_item_id=UUID("00000000-0000-0000-0000-000000000001"),
        created_by="user1",
        reason="First mapping",
        start_ts=now - timedelta(days=60),
        end_ts=now - timedelta(days=30),  # Inactive
    )

    # Create second inactive mapping (same key)
    mapping2 = ItemMappingModel(
        org_id="acme",
        canonical_key="key-123",
        price_item_id=UUID("00000000-0000-0000-0000-000000000002"),
        created_by="user2",
        reason="Second mapping",
        start_ts=now - timedelta(days=30),
        end_ts=now - timedelta(days=15),  # Also inactive
    )

    db_session.add_all([mapping1, mapping2])
    await db_session.commit()  # Should succeed

    # Verify both records exist
    result = await db_session.execute(
        select(ItemMappingModel).where(
            ItemMappingModel.org_id == "acme",
            ItemMappingModel.canonical_key == "key-123",
            ItemMappingModel.end_ts.isnot(None),
        )
    )
    inactive_mappings = result.scalars().all()

    assert len(inactive_mappings) == 2, "Should allow multiple inactive mappings"


@pytest.mark.asyncio
async def test_mapping_temporal_integrity_with_end_after_start(db_session: AsyncSession):
    """Test mapping temporal integrity: end_ts > start_ts.

    Scenario:
    - Attempt to create mapping with end_ts <= start_ts
    - Should violate check constraint
    """
    now = datetime.utcnow()

    # Create mapping with invalid temporal period (end before start)
    mapping_invalid = ItemMappingModel(
        org_id="acme",
        canonical_key="key-invalid",
        price_item_id=UUID("00000000-0000-0000-0000-000000000001"),
        created_by="user",
        reason="Invalid temporal period",
        start_ts=now,
        end_ts=now - timedelta(days=1),  # Before start_ts - INVALID
    )

    db_session.add(mapping_invalid)

    # Should raise IntegrityError due to check constraint
    with pytest.raises(IntegrityError, match="CHECK constraint"):
        await db_session.commit()


@pytest.mark.asyncio
async def test_different_orgs_can_have_same_canonical_key(db_session: AsyncSession):
    """Test that different orgs can have active mappings with same canonical_key.

    Scenario:
    - Org 'acme' has active mapping with canonical_key='key-123'
    - Org 'beta' has active mapping with canonical_key='key-123'
    - Should succeed (unique constraint is per-org)
    """
    # Create active mapping for org 'acme'
    mapping_acme = ItemMappingModel(
        org_id="acme",
        canonical_key="key-123",
        price_item_id=UUID("00000000-0000-0000-0000-000000000001"),
        created_by="acme-user",
        reason="ACME mapping",
        start_ts=datetime.utcnow(),
        end_ts=None,  # Active
    )

    # Create active mapping for org 'beta' (same canonical_key)
    mapping_beta = ItemMappingModel(
        org_id="beta",
        canonical_key="key-123",  # Same key, different org
        price_item_id=UUID("00000000-0000-0000-0000-000000000002"),
        created_by="beta-user",
        reason="BETA mapping",
        start_ts=datetime.utcnow(),
        end_ts=None,  # Also active
    )

    db_session.add_all([mapping_acme, mapping_beta])
    await db_session.commit()  # Should succeed

    # Verify both mappings exist and are active
    result = await db_session.execute(
        select(ItemMappingModel).where(
            ItemMappingModel.canonical_key == "key-123",
            ItemMappingModel.end_ts.is_(None),
        )
    )
    active_mappings = result.scalars().all()

    assert len(active_mappings) == 2, "Different orgs can have same canonical_key"
    org_ids = {m.org_id for m in active_mappings}
    assert org_ids == {"acme", "beta"}, "Should have mappings from both orgs"


@pytest.mark.asyncio
async def test_scd2_update_workflow_closes_old_opens_new(db_session: AsyncSession):
    """Test proper SCD2 update workflow: close old record, open new record.

    This tests the intended update pattern:
    1. Close existing active record (set end_ts)
    2. Create new active record
    3. Both records preserved in history

    Scenario:
    - Create active mapping v1
    - Update: close v1, create active v2
    - Verify both exist in database
    - Verify only v2 is active
    """
    now = datetime.utcnow()

    # Step 1: Create initial active mapping (v1)
    mapping_v1 = ItemMappingModel(
        org_id="acme",
        canonical_key="key-evolving",
        price_item_id=UUID("00000000-0000-0000-0000-000000000001"),
        created_by="user1",
        reason="Initial mapping",
        start_ts=now - timedelta(days=30),
        end_ts=None,  # Active
    )

    db_session.add(mapping_v1)
    await db_session.commit()

    # Step 2: Update - close v1 and create v2
    # Close v1
    mapping_v1.end_ts = now
    await db_session.flush()  # CRITICAL: Flush v1 update before creating v2

    # Create v2 (new active record)
    mapping_v2 = ItemMappingModel(
        org_id="acme",
        canonical_key="key-evolving",  # Same key
        price_item_id=UUID("00000000-0000-0000-0000-000000000002"),  # New price
        created_by="user2",
        reason="Updated mapping",
        start_ts=now,
        end_ts=None,  # Active
    )

    db_session.add(mapping_v2)
    await db_session.commit()

    # Step 3: Verify both records exist
    result = await db_session.execute(
        select(ItemMappingModel)
        .where(
            ItemMappingModel.org_id == "acme",
            ItemMappingModel.canonical_key == "key-evolving",
        )
        .order_by(ItemMappingModel.start_ts)
    )
    all_mappings = result.scalars().all()

    assert len(all_mappings) == 2, "Both v1 and v2 should exist (history preserved)"

    # Verify v1 is closed
    assert all_mappings[0].end_ts is not None, "V1 should be closed"
    assert all_mappings[0].price_item_id == "00000000-0000-0000-0000-000000000001"

    # Verify v2 is active
    assert all_mappings[1].end_ts is None, "V2 should be active"
    assert all_mappings[1].price_item_id == "00000000-0000-0000-0000-000000000002"

    # Verify only one active record
    active_result = await db_session.execute(
        select(ItemMappingModel).where(
            ItemMappingModel.org_id == "acme",
            ItemMappingModel.canonical_key == "key-evolving",
            ItemMappingModel.end_ts.is_(None),
        )
    )
    active_mappings = active_result.scalars().all()

    assert len(active_mappings) == 1, "Only one mapping should be active"
    assert active_mappings[0] == all_mappings[1], "V2 should be the active one"
