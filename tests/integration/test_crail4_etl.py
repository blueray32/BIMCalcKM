"""Integration tests for Crail4 ETL pipeline."""

from __future__ import annotations

from decimal import Decimal

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from bimcalc.db.models import Base, ClassificationMappingModel
from bimcalc.integration.classification_mapper import ClassificationMapper
from bimcalc.integration.crail4_transformer import Crail4Transformer


@pytest_asyncio.fixture
async def session(tmp_path) -> AsyncSession:
    """Provide isolated SQLite database with seeded mappings."""

    db_path = tmp_path / "crail4_etl.db"
    engine = create_async_engine(f"sqlite+aiosqlite:///{db_path}")
    sessionmaker = async_sessionmaker(engine, expire_on_commit=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with sessionmaker() as session_obj:
        await _seed_classification_mappings(session_obj)
        yield session_obj

    await engine.dispose()


async def _seed_classification_mappings(session: AsyncSession) -> None:
    """Insert OmniClass → UniClass seed rows for tests."""

    mappings = [
        ("23-17 11 23", "66"),
        ("23-17 13 11", "62"),
        ("23-17 15 11", "64"),
        ("23-17 21 11", "68"),
        ("23-17 31 11", "67"),
    ]

    for source_code, target_code in mappings:
        session.add(
            ClassificationMappingModel(
                id=f"test-{source_code}",
                org_id="acme-construction",
                source_scheme="OmniClass",
                source_code=source_code,
                target_scheme="UniClass2015",
                target_code=target_code,
            )
        )

    await session.commit()


@pytest.mark.asyncio
async def test_classification_mapper_translate(session: AsyncSession):
    """Test that OmniClass codes translate to UniClass."""
    mapper = ClassificationMapper(session, "acme-construction")
    result = await mapper.translate(
        source_code="23-17 11 23",
        source_scheme="OmniClass",
        target_scheme="UniClass2015",
    )
    assert result == "66", f"Expected '66', got '{result}'"


@pytest.mark.asyncio
async def test_transformer_valid_item(session: AsyncSession):
    """Test transformer handles valid Crail4 item."""
    mapper = ClassificationMapper(session, "acme-construction")
    transformer = Crail4Transformer(mapper, "UniClass2015")

    raw_item = {
        "id": "test-001",
        "classification_code": "23-17 11 23",
        "classification_scheme": "OmniClass",
        "name": "Cable Tray Elbow 90° 200x50mm",
        "unit": "ea",
        "unit_price": 45.50,
        "currency": "EUR",
        "vat_rate": 0.23,
        "vendor_code": "CTL-ELB-90-200X50",
    }

    result = await transformer.transform_item(raw_item)

    assert result is not None, "Valid item should not be rejected"
    assert result["classification_code"] == "66"
    assert result["unit"] == "ea"
    assert result["unit_price"] == Decimal("45.50")
    assert result["currency"] == "EUR"
    assert result["canonical_key"] is not None


@pytest.mark.asyncio
async def test_transformer_missing_fields(session: AsyncSession):
    """Test transformer rejects item with missing mandatory fields."""
    mapper = ClassificationMapper(session, "acme-construction")
    transformer = Crail4Transformer(mapper, "UniClass2015")

    raw_item = {
        "classification_code": "23-17 11 23",
        "classification_scheme": "OmniClass",
        "name": "Cable Tray Elbow",
        "unit": "ea",
    }

    result = await transformer.transform_item(raw_item)
    assert result is None


@pytest.mark.asyncio
async def test_transformer_batch_statistics(session: AsyncSession):
    """Test batch transformer returns rejection statistics."""
    mapper = ClassificationMapper(session, "acme-construction")
    transformer = Crail4Transformer(mapper, "UniClass2015")

    raw_items = [
        {
            "classification_code": "23-17 11 23",
            "classification_scheme": "OmniClass",
            "name": "Cable Tray",
            "unit": "ea",
            "unit_price": 45.50,
        },
        {
            "classification_code": "23-17 11 23",
            "classification_scheme": "OmniClass",
            "name": "Cable Tray",
            "unit": "ea",
        },
        {
            "classification_code": "99-99 99 99",
            "classification_scheme": "OmniClass",
            "name": "Unknown Item",
            "unit": "ea",
            "unit_price": 10.00,
        },
    ]

    valid, rejections = await transformer.transform_batch(raw_items)

    assert len(valid) == 1
    assert rejections["missing_fields"] >= 1
    assert rejections["no_classification_mapping"] >= 1


@pytest.mark.asyncio
async def test_unit_standardization(session: AsyncSession):
    """Test that units are normalized correctly."""
    mapper = ClassificationMapper(session, "acme-construction")
    transformer = Crail4Transformer(mapper, "UniClass2015")

    test_cases = [
        ("sq.m", "m²"),
        ("sqm", "m²"),
        ("square meter", "m²"),
        ("piece", "ea"),
        ("each", "ea"),
        ("meter", "m"),
    ]

    for input_unit, expected_unit in test_cases:
        assert transformer._standardize_unit(input_unit) == expected_unit
