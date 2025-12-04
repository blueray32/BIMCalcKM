"""Tests for review repository/service."""

from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from bimcalc.db.models import (
    Base,
    ItemMappingModel,
    ItemModel,
    MatchFlagModel,
    MatchResultModel,
    PriceItemModel,
)
from bimcalc.models import FlagSeverity
from bimcalc.review.models import ReviewFlag, ReviewItem, ReviewPrice, ReviewRecord
from bimcalc.review.repository import fetch_pending_reviews
from bimcalc.review.service import approve_review_record


@pytest_asyncio.fixture()
async def db_session() -> AsyncSession:
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
async def test_fetch_pending_reviews_returns_latest_manual_entry(
    db_session: AsyncSession,
):
    item = ItemModel(
        org_id="acme",
        project_id="proj-a",
        family="Cable Tray",
        type_name="Elbow 90",
        classification_code=66,
        canonical_key="key-123",
    )
    price = PriceItemModel(
        org_id="acme",
        item_code="CT-90-ELBOW",
        region="IE",
        vendor_id="vendor",
        sku="CT-90",
        description="Cable tray elbow 90",
        classification_code=66,
        unit="ea",
        unit_price=Decimal("25.0"),
        currency="EUR",
        source_name="test_catalog",
        source_currency="EUR",
    )
    db_session.add_all([item, price])
    await db_session.flush()

    older_result = MatchResultModel(
        item_id=item.id,
        price_item_id=price.id,
        confidence_score=50.0,
        source="fuzzy_match",
        decision="manual-review",
        reason="Initial run",
        created_by="matcher",
        timestamp=datetime.utcnow() - timedelta(hours=1),
    )
    latest_result = MatchResultModel(
        item_id=item.id,
        price_item_id=price.id,
        confidence_score=55.0,
        source="fuzzy_match",
        decision="manual-review",
        reason="Needs review",
        created_by="matcher",
        timestamp=datetime.utcnow(),
    )
    db_session.add_all([older_result, latest_result])
    await db_session.flush()

    db_session.add(
        MatchFlagModel(
            match_result_id=latest_result.id,
            item_id=item.id,
            price_item_id=price.id,
            flag_type="Unit Conflict",
            severity="Critical-Veto",
            message="Unit mismatch",
        )
    )
    await db_session.commit()

    records = await fetch_pending_reviews(db_session, "acme", "proj-a")
    assert len(records) == 1
    record = records[0]
    assert record.item.id == item.id
    assert record.price and record.price.id == price.id
    assert record.has_critical_flags
    assert "Unit Conflict" in record.flag_types


@pytest.mark.asyncio
async def test_approve_review_record_writes_mapping_and_audit(db_session: AsyncSession):
    item = ItemModel(
        org_id="acme",
        project_id="proj-a",
        family="Cable Tray",
        type_name="Elbow 90",
        classification_code=66,
        canonical_key="key-789",
    )
    price = PriceItemModel(
        org_id="acme",
        item_code="CT-90-ELBOW",
        region="IE",
        vendor_id="vendor",
        sku="CT-90",
        description="Cable tray elbow 90",
        classification_code=66,
        unit="ea",
        unit_price=Decimal("25.0"),
        currency="EUR",
        source_name="test_catalog",
        source_currency="EUR",
    )
    db_session.add_all([item, price])
    await db_session.commit()

    review_record = ReviewRecord(
        match_result_id=uuid4(),
        item=ReviewItem(
            id=item.id,
            org_id=item.org_id,
            project_id=item.project_id,
            canonical_key=item.canonical_key,
            family=item.family,
            type_name=item.type_name,
            category=item.category,
            system_type=item.system_type,
            classification_code=item.classification_code,
            quantity=None,
            unit=None,
            width_mm=None,
            height_mm=None,
            dn_mm=None,
            angle_deg=None,
            material=None,
            source_file=None,
        ),
        price=ReviewPrice(
            id=price.id,
            vendor_id=price.vendor_id,
            sku=price.sku,
            description=price.description,
            classification_code=price.classification_code,
            unit=price.unit,
            unit_price=price.unit_price,
            currency=price.currency,
            vat_rate=price.vat_rate,
            width_mm=price.width_mm,
            height_mm=price.height_mm,
            dn_mm=price.dn_mm,
            angle_deg=price.angle_deg,
            material=price.material,
            last_updated=price.last_updated,
            vendor_note=price.vendor_note,
        ),
        confidence_score=92.0,
        source="fuzzy_match",
        reason="Manual review",
        created_by="matcher",
        timestamp=datetime.utcnow(),
        flags=[
            ReviewFlag(type="StalePrice", severity=FlagSeverity.ADVISORY, message="old")
        ],
    )

    await approve_review_record(
        db_session,
        review_record,
        created_by="reviewer@acme",
        annotation="Confirmed dimensions",
    )

    mapping_rows = await db_session.execute(select(ItemMappingModel))
    mapping = mapping_rows.scalar_one()
    assert mapping.org_id == "acme"
    assert mapping.canonical_key == "key-789"
    assert mapping.price_item_id == price.id

    result_rows = await db_session.execute(select(MatchResultModel))
    stored_result = result_rows.scalar_one()
    assert stored_result.source == "review_ui"
    assert stored_result.decision == "auto-accepted"
    assert stored_result.created_by == "reviewer@acme"

    flag_rows = await db_session.execute(select(MatchFlagModel))
    stored_flag = flag_rows.scalar_one()
    assert stored_flag.flag_type == "StalePrice"
    assert stored_flag.severity == "Advisory"


@pytest.mark.asyncio
async def test_approve_review_record_blocks_critical_veto_flags(
    db_session: AsyncSession,
):
    """Backend MUST reject approval when Critical-Veto flags exist."""
    item = ItemModel(
        org_id="acme",
        project_id="proj-a",
        family="Cable Tray",
        type_name="Elbow 90",
        classification_code=66,
        canonical_key="key-critical",
    )
    price = PriceItemModel(
        org_id="acme",
        item_code="CT-90-ELBOW",
        region="IE",
        vendor_id="vendor",
        sku="CT-90",
        description="Cable tray elbow 90",
        classification_code=66,
        unit="m",  # Different from item unit
        unit_price=Decimal("25.0"),
        currency="EUR",
        source_name="test_catalog",
        source_currency="EUR",
    )
    db_session.add_all([item, price])
    await db_session.commit()

    review_record = ReviewRecord(
        match_result_id=uuid4(),
        item=ReviewItem(
            id=item.id,
            org_id=item.org_id,
            project_id=item.project_id,
            canonical_key=item.canonical_key,
            family=item.family,
            type_name=item.type_name,
            category=item.category,
            system_type=item.system_type,
            classification_code=item.classification_code,
            quantity=None,
            unit="ea",  # Item has 'ea', price has 'm' -> Unit Conflict
            width_mm=None,
            height_mm=None,
            dn_mm=None,
            angle_deg=None,
            material=None,
            source_file=None,
        ),
        price=ReviewPrice(
            id=price.id,
            vendor_id=price.vendor_id,
            sku=price.sku,
            description=price.description,
            classification_code=price.classification_code,
            unit=price.unit,
            unit_price=price.unit_price,
            currency=price.currency,
            vat_rate=price.vat_rate,
            width_mm=price.width_mm,
            height_mm=price.height_mm,
            dn_mm=price.dn_mm,
            angle_deg=price.angle_deg,
            material=price.material,
            last_updated=price.last_updated,
            vendor_note=price.vendor_note,
        ),
        confidence_score=75.0,
        source="fuzzy_match",
        reason="Manual review needed",
        created_by="matcher",
        timestamp=datetime.utcnow(),
        flags=[
            ReviewFlag(
                type="Unit Conflict",
                severity=FlagSeverity.CRITICAL_VETO,
                message="Unit mismatch: ea != m",
            )
        ],
    )

    # Attempt to approve should raise ValueError
    with pytest.raises(
        ValueError, match="Cannot approve item with Critical-Veto flags"
    ):
        await approve_review_record(
            db_session,
            review_record,
            created_by="reviewer@acme",
            annotation="Trying to force approval",
        )

    # Verify no mapping was created
    mapping_rows = await db_session.execute(select(ItemMappingModel))
    assert mapping_rows.scalar_one_or_none() is None

    # Verify no match result was stored
    result_rows = await db_session.execute(
        select(MatchResultModel).where(MatchResultModel.item_id == item.id)
    )
    assert result_rows.scalar_one_or_none() is None
