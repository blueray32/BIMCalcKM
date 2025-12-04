import asyncio
import uuid
from bimcalc.db.connection import get_session
from bimcalc.db.models import ItemModel, PriceItemModel
from bimcalc.reporting.scenario import compute_vendor_scenario, get_available_vendors
from sqlalchemy import text


async def test_scenario():
    async with get_session() as session:
        org_id = "test-org-scenario"
        project_id = "test-proj-scenario"

        # 0. Cleanup
        print("Cleaning up previous test data...")
        await session.execute(
            text(f"DELETE FROM price_items WHERE org_id = '{org_id}'")
        )
        await session.execute(text(f"DELETE FROM items WHERE org_id = '{org_id}'"))
        await session.commit()

        # 1. Setup: Create items and price items
        print("Setting up test data...")

        # Items
        item1 = ItemModel(
            id=uuid.uuid4(),
            org_id=org_id,
            project_id=project_id,
            family="Wall",
            type_name="Type A",
            quantity=10,
            classification_code="2001",
        )
        item2 = ItemModel(
            id=uuid.uuid4(),
            org_id=org_id,
            project_id=project_id,
            family="Wall",
            type_name="Type B",
            quantity=5,
            classification_code="2002",
        )
        session.add_all([item1, item2])

        # Vendor A Prices (Full coverage)
        price_a1 = PriceItemModel(
            id=uuid.uuid4(),
            org_id=org_id,
            item_code="A1",
            region="EU",
            classification_code="2001",
            source_name="Vendor A",
            unit_price=100,
            sku="A1",
            description="A1",
            unit="m2",
            currency="EUR",
            source_currency="EUR",
        )
        price_a2 = PriceItemModel(
            id=uuid.uuid4(),
            org_id=org_id,
            item_code="A2",
            region="EU",
            classification_code="2002",
            source_name="Vendor A",
            unit_price=200,
            sku="A2",
            description="A2",
            unit="m2",
            currency="EUR",
            source_currency="EUR",
        )

        # Vendor B Prices (Partial coverage)
        price_b1 = PriceItemModel(
            id=uuid.uuid4(),
            org_id=org_id,
            item_code="B1",
            region="EU",
            classification_code="2001",
            source_name="Vendor B",
            unit_price=90,
            sku="B1",
            description="B1",
            unit="m2",
            currency="EUR",
            source_currency="EUR",
        )

        session.add_all([price_a1, price_a2, price_b1])
        await session.commit()

        # 2. Test Available Vendors
        print("\nTesting get_available_vendors...")
        vendors = await get_available_vendors(session, org_id)
        print(f"Vendors found: {vendors}")
        if "Vendor A" in vendors and "Vendor B" in vendors:
            print("PASS: Vendors found")
        else:
            print("FAIL: Vendors missing")

        # 3. Test Scenario Calculation (Vendor A)
        print("\nTesting Scenario Vendor A (Full Coverage)...")
        scenario_a = await compute_vendor_scenario(
            session, org_id, project_id, "Vendor A"
        )
        print(
            f"Vendor A: Cost={scenario_a.total_cost}, Coverage={scenario_a.coverage_percent}%"
        )

        # Expected: (10 * 100) + (5 * 200) = 1000 + 1000 = 2000
        if scenario_a.total_cost == 2000.0 and scenario_a.coverage_percent == 100.0:
            print("PASS: Vendor A calculation correct")
        else:
            print(
                f"FAIL: Vendor A calculation incorrect. Expected 2000/100%, got {scenario_a.total_cost}/{scenario_a.coverage_percent}%"
            )

        # 4. Test Scenario Calculation (Vendor B)
        print("\nTesting Scenario Vendor B (Partial Coverage)...")
        scenario_b = await compute_vendor_scenario(
            session, org_id, project_id, "Vendor B"
        )
        print(
            f"Vendor B: Cost={scenario_b.total_cost}, Coverage={scenario_b.coverage_percent}%"
        )

        # Expected: (10 * 90) + (0) = 900. Coverage: 1/2 items = 50%
        if scenario_b.total_cost == 900.0 and scenario_b.coverage_percent == 50.0:
            print("PASS: Vendor B calculation correct")
        else:
            print(
                f"FAIL: Vendor B calculation incorrect. Expected 900/50%, got {scenario_b.total_cost}/{scenario_b.coverage_percent}%"
            )


if __name__ == "__main__":
    asyncio.run(test_scenario())
