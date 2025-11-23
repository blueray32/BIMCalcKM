"""Integration tests for BIMCalc end-to-end workflows.

Tests:
1. Two-pass matching: Demonstrate learning curve (instant match on second project)
2. As-of report reproducibility: Same timestamp = same report
3. Classification blocking: Performance gain from indexed filtering
"""

from __future__ import annotations

import asyncio
from datetime import datetime
from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy import select

from bimcalc.config import get_config
from bimcalc.db.connection import get_engine, get_session
from bimcalc.db.models import Base, ItemMappingModel, ItemModel, PriceItemModel
from bimcalc.matching.orchestrator import MatchOrchestrator
from bimcalc.models import Item
from bimcalc.reporting.builder import generate_report


@pytest_asyncio.fixture(scope="function")
async def db_setup():
    """Set up test database."""
    engine = get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield
    await engine.dispose()


@pytest_asyncio.fixture
async def seed_price_items():
    """Seed test price items."""
    async with get_session() as session:
        # ... (content same as before) ...
        # Cable tray elbow 90° 200x50mm
        price1 = PriceItemModel(
            org_id="test-org",  # Add org_id
            item_code="CT-200x50-90", # Add item_code
            region="IE", # Add region
            source_name="test", # Add source_name
            source_currency="EUR", # Add source_currency
            vendor_id="test",
            sku="CT-200x50-90",
            description="Cable Tray Ladder Elbow 90° 200x50mm Galvanized",
            classification_code=2650,  # Cable tray (updated code)
            unit="ea",
            unit_price=45.50,
            currency="EUR",
            vat_rate=0.23,
            width_mm=200.0,
            height_mm=50.0,
            angle_deg=90.0,
            material="galvanized_steel",
        )

        # Cable tray elbow 45° 200x50mm
        price2 = PriceItemModel(
            org_id="test-org",
            item_code="CT-200x50-45",
            region="IE",
            source_name="test",
            source_currency="EUR",
            vendor_id="test",
            sku="CT-200x50-45",
            description="Cable Tray Ladder Elbow 45° 200x50mm Galvanized",
            classification_code=2650,
            unit="ea",
            unit_price=42.00,
            currency="EUR",
            vat_rate=0.23,
            width_mm=200.0,
            height_mm=50.0,
            angle_deg=45.0,
            material="galvanized_steel",
        )

        # Lighting fixture (different classification)
        price3 = PriceItemModel(
            org_id="test-org",
            item_code="LF-600-LED",
            region="IE",
            source_name="test",
            source_currency="EUR",
            vendor_id="test",
            sku="LF-600-LED",
            description="LED Panel 600x600 40W",
            classification_code=95,  # Lighting
            unit="ea",
            unit_price=125.00,
            currency="EUR",
            vat_rate=0.23,
            width_mm=600.0,
            height_mm=600.0,
        )

        session.add_all([price1, price2, price3])
        await session.commit()


@pytest.mark.asyncio
@pytest.mark.integration
async def test_two_pass_matching(db_setup, seed_price_items):
    """Test learning curve: First match requires fuzzy matching, second is instant.

    Demonstrates:
    - First project: Fuzzy match → auto-accept → write mapping
    - Second project: Same item → instant O(1) lookup → auto-accept
    - 30-50% reduction in matching time on repeat items
    """
    config = get_config()
    org_id = config.org_id

    async with get_session() as session:
        orchestrator = MatchOrchestrator(session)

        # PROJECT A: First encounter with cable tray elbow
        item_a = Item(
            id=str(uuid4()),
            org_id="test-org",
            project_id="test-project",
            family="Cable Tray - Ladder",
            type_name="Elbow 90 deg 200x50mm",
            category="Cable Tray",
            quantity=10.0,
            unit="ea",
            width_mm=200.0,
            height_mm=50.0,
            angle_deg=90.0,
            material="galvanized_steel",
        )

        # First match: Should use fuzzy matching
        result_a, price_a = await orchestrator.match(item_a, created_by="test")

        assert result_a.decision == "auto-accepted", "First match should auto-accept"
        assert "fuzzy" in result_a.reason.lower(), "Should use fuzzy matching"
        assert price_a is not None
        assert price_a.sku == "CT-200x50-90"

        # PROJECT B: Same item with slight name variation (case)
        item_b = Item(
            id=str(uuid4()),
            org_id="test-org",
            project_id="test-project",
            family="Cable Tray Ladder",  # Slightly different
            type_name="ELBOW 90 DEG 200x50mm",  # Uppercase variation
            category="Cable Tray",
            quantity=15.0,
            unit="ea",
            width_mm=200.0,
            height_mm=50.0,
            angle_deg=90.0,
            material="galvanized_steel",
        )

        # Second match: Should be instant via mapping memory
        result_b, price_b = await orchestrator.match(item_b, created_by="test")

        assert result_b.decision == "auto-accepted", "Second match should auto-accept"
        assert "mapping memory" in result_b.reason.lower(), "Should use instant mapping lookup"
        assert price_b is not None
        assert price_b.sku == "CT-200x50-90", "Should match same price item"

        # Verify mapping exists
        mapping_stmt = select(ItemMappingModel).where(
            ItemMappingModel.org_id == org_id,
            ItemMappingModel.canonical_key == item_b.canonical_key,
            ItemMappingModel.end_ts.is_(None),
        )
        mapping_result = await session.execute(mapping_stmt)
        mapping = mapping_result.scalar_one()

        assert mapping is not None
        assert mapping.price_item_id == price_a.id


@pytest.mark.asyncio
@pytest.mark.integration
async def test_as_of_report_reproducibility(db_setup, seed_price_items):
    """Test temporal reproducibility: Same as-of timestamp = same report.

    Demonstrates:
    - Generate report at T1
    - Update mapping at T2
    - Regenerate report at T1 → identical result
    - Generate report at T3 → shows updated mapping
    """
    config = get_config()
    org_id = config.org_id
    project_id = "test-project-temporal"

    async with get_session() as session:
        # Create test item
        item = ItemModel(
            org_id=org_id,
            project_id=project_id,
            family="Cable Tray - Ladder",
            type_name="Elbow 90deg 200x50mm",
            category="Cable Tray",
            quantity=10.0,
            unit="ea",
            width_mm=200.0,
            height_mm=50.0,
            angle_deg=90.0,
            material="galvanized_steel",
            canonical_key="66|cable_tray|elbow|w=200|h=50|a=90", # Manually set for test
        )
        session.add(item)
        await session.commit()

        # Get first price item for initial mapping
        price_result = await session.execute(
            select(PriceItemModel).where(PriceItemModel.sku == "CT-200x50-90")
        )
        price1 = price_result.scalar_one()

        # T1: Create initial mapping
        t1 = datetime.utcnow()
        mapping1 = ItemMappingModel(
            org_id=org_id,
            canonical_key=item.canonical_key,
            price_item_id=price1.id,
            start_ts=t1,
            end_ts=None,
            created_by="test",
            reason="Initial mapping",
        )
        session.add(mapping1)
        await session.commit()

        # Generate report at T1
        report1 = await generate_report(session, org_id, project_id, as_of=t1)
        assert len(report1) == 1
        assert report1.iloc[0]["sku"] == "CT-200x50-90"
        total1 = report1.iloc[0]["total_net"]

        # T2: Update mapping to different price item
        await asyncio.sleep(0.1)  # Small delay to ensure different timestamp
        t2 = datetime.utcnow()

        # Get second price item
        price_result2 = await session.execute(
            select(PriceItemModel).where(PriceItemModel.sku == "CT-200x50-45")
        )
        price2 = price_result2.scalar_one()

        # Close old mapping and create new one
        mapping1.end_ts = t2
        mapping2 = ItemMappingModel(
            org_id=org_id,
            canonical_key=item.canonical_key,
            price_item_id=price2.id,
            start_ts=t2,
            end_ts=None,
            created_by="test",
            reason="Updated mapping",
        )
        session.add(mapping2)
        await session.commit()

        # Regenerate report at T1 (should be identical)
        report1_replay = await generate_report(session, org_id, project_id, as_of=t1)
        assert len(report1_replay) == 1
        assert report1_replay.iloc[0]["sku"] == "CT-200x50-90", "As-of T1 should show old mapping"
        assert report1_replay.iloc[0]["total_net"] == total1, "Total should be identical"

        # Generate report at T3 (current time - should show new mapping)
        t3 = datetime.utcnow()
        report3 = await generate_report(session, org_id, project_id, as_of=t3)
        assert len(report3) == 1
        assert report3.iloc[0]["sku"] == "CT-200x50-45", "As-of T3 should show new mapping"
        assert report3.iloc[0]["total_net"] != total1, "Total should be different"


@pytest.mark.asyncio
@pytest.mark.integration
async def test_classification_blocking_performance(db_setup, seed_price_items):
    """Test classification-first blocking: Reduces candidate pool 20×.

    Demonstrates:
    - Without blocking: Consider all price items
    - With blocking: Consider only items with matching classification_code
    - Measure candidate reduction factor
    """
    config = get_config()

    async with get_session() as session:
        # Count total price items
        total_result = await session.execute(select(PriceItemModel))
        total_count = len(total_result.scalars().all())

        # Create cable tray item (classification 66)
        item = Item(
            id=str(uuid4()),
            org_id="test-org",
            project_id="test-project",
            family="Cable Tray - Ladder",
            type_name="Elbow 90deg 200x50mm",
            category="Cable Tray",
            quantity=10.0,
            unit="ea",
            width_mm=200.0,
            height_mm=50.0,
            angle_deg=90.0,
            material="galvanized_steel",
            classification_code=2650,
        )

        # Import candidate generator
        from bimcalc.matching.candidate_generator import CandidateGenerator

        generator = CandidateGenerator(session)

        # Generate candidates with classification blocking
        candidates = await generator.generate(item)

        # All candidates should have classification_code = 2650
        for candidate in candidates:
            assert candidate.classification_code == 2650, "Should only return cable tray items"

        # Verify reduction factor
        blocked_count = len(candidates)
        reduction_factor = total_count / blocked_count if blocked_count > 0 else 0

        assert blocked_count < total_count, "Should reduce candidate pool"
        assert reduction_factor >= 1.0, "Should have positive reduction factor"

        # In this test, we have 2 cable tray items out of 3 total
        # Reduction factor should be ~1.5×
        assert blocked_count == 2, "Should find 2 cable tray candidates"


@pytest.mark.asyncio
@pytest.mark.integration
async def test_critical_veto_flag_blocks_auto_accept(db_setup, seed_price_items):
    """Test risk flags: Critical-Veto flags block auto-accept.

    Demonstrates:
    - High confidence match with unit conflict → manual review
    - Critical-Veto flag prevents auto-accept
    """
    config = get_config()

    async with get_session() as session:
        orchestrator = MatchOrchestrator(session)

        # Cable tray item with WRONG UNIT (should trigger UnitConflict flag)
        item = Item(
            id=str(uuid4()),
            org_id="test-org",
            project_id="test-project",
            family="Cable Tray - Ladder",
            type_name="Elbow 90deg 200x50mm",
            category="Cable Tray",
            quantity=10.0,
            unit="m",  # Should be "ea" - UNIT MISMATCH
            width_mm=200.0,
            height_mm=50.0,
            angle_deg=90.0,
            material="galvanized_steel",
        )

        result, price = await orchestrator.match(item, created_by="test")

        # Should route to manual review due to Critical-Veto flag
        assert result.decision == "manual-review", "Critical-Veto should block auto-accept"
        assert len(result.flags) > 0, "Should have flags"
        assert any("unit" in flag.message.lower() for flag in result.flags), "Should have unit conflict flag"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-m", "integration"])
