import asyncio
from datetime import datetime
from decimal import Decimal
from uuid import uuid4

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from bimcalc.db.models import ItemModel, PriceItemModel, ProjectModel
from bimcalc.reporting.dashboard_metrics import compute_dashboard_metrics

# Database setup
DATABASE_URL = "sqlite+aiosqlite:///bimcalc.db"
engine = create_async_engine(DATABASE_URL)
AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def verify_labor_config():
    async with AsyncSessionLocal() as session:
        print("1. Setting up test data...")
        org_id = "test-org"
        project_id = f"test-proj-{uuid4().hex[:8]}"
        now = datetime.utcnow()

        # Create Project
        project = ProjectModel(
            org_id=org_id,
            project_id=project_id,
            display_name="Labor Config Test",
            status="active",
            created_at=now,
            updated_at=now,
        )
        session.add(project)

        # Create Price Item with labor
        unique_suffix = uuid4().hex[:6]
        price_item = PriceItemModel(
            org_id=org_id,
            item_code=f"TEST-{unique_suffix}",
            region="EU",
            classification_code="2601",
            sku="SKU-001",
            description="Test Item",
            unit="EA",
            unit_price=Decimal("100.00"),
            currency="EUR",
            labor_hours=Decimal("2.0"),  # 2 hours
            source_name="Manual",
            source_currency="EUR",
            valid_from=now,
            last_updated=now,
            created_at=now,
            is_current=True,
        )
        session.add(price_item)
        await session.flush()

        # Create Item
        item = ItemModel(
            org_id=org_id,
            project_id=project_id,
            classification_code="2601",
            family="Test Family",
            type_name="Test Type",
            quantity=Decimal("10.0"),  # 10 items
            price_item_id=price_item.id,
            created_at=now,
        )
        session.add(item)
        await session.flush()

        # Create Item Mapping (required for dashboard metrics query)
        from bimcalc.db.models import ItemMappingModel

        unique_key = f"2601-{unique_suffix}"
        mapping = ItemMappingModel(
            org_id=org_id,
            canonical_key=unique_key,
            price_item_id=price_item.id,
            start_ts=now,
            created_by="test",
            reason="test",
        )
        session.add(mapping)

        # Update item to have canonical key
        item.canonical_key = unique_key

        # Create Match Result (required for cost calculation)
        from bimcalc.db.models import MatchResultModel

        match_result = MatchResultModel(
            item_id=item.id,
            price_item_id=price_item.id,
            confidence_score=0.95,
            source="mapping_memory",
            decision="auto-accepted",
            reason="test",
            created_by="test",
            timestamp=now,
        )
        session.add(match_result)

        await session.commit()

        print(f"   Created project {project_id} with 10 items (2.0 labor hours each).")
        print("   Total Labor Hours = 20.0")

        # 2. Check Default Rate (50.0)
        print("\n2. Verifying Default Rate (€50/hr)...")
        metrics = await compute_dashboard_metrics(session, org_id, project_id)
        print(f"   Blended Labor Rate: €{metrics.blended_labor_rate}/hr")
        print(f"   Total Labor Cost: €{metrics.total_labor_cost}")

        expected_cost_default = 20.0 * 50.0  # 1000.0
        assert metrics.blended_labor_rate == 50.0, (
            f"Expected 50.0, got {metrics.blended_labor_rate}"
        )
        assert metrics.total_labor_cost == expected_cost_default, (
            f"Expected {expected_cost_default}, got {metrics.total_labor_cost}"
        )
        print("   ✅ Default rate verification passed.")

        # 3. Update Settings via DB (simulating API)
        print("\n3. Updating Labor Rate to €100/hr...")
        project.settings = {"blended_labor_rate": 100.0}
        session.add(project)
        await session.commit()

        # 4. Verify New Rate
        print("\n4. Verifying New Rate (€100/hr)...")
        metrics = await compute_dashboard_metrics(session, org_id, project_id)
        print(f"   Blended Labor Rate: €{metrics.blended_labor_rate}/hr")
        print(f"   Total Labor Cost: €{metrics.total_labor_cost}")

        expected_cost_new = 20.0 * 100.0  # 2000.0
        assert metrics.blended_labor_rate == 100.0, (
            f"Expected 100.0, got {metrics.blended_labor_rate}"
        )
        assert metrics.total_labor_cost == expected_cost_new, (
            f"Expected {expected_cost_new}, got {metrics.total_labor_cost}"
        )
        print("   ✅ New rate verification passed.")

        print("\n🎉 Verification Complete!")


if __name__ == "__main__":
    asyncio.run(verify_labor_config())
