"""Verification script for Recommendation System."""

import asyncio
from uuid import uuid4
from decimal import Decimal
from fastapi.testclient import TestClient

from bimcalc.web.app_enhanced import app
from bimcalc.db.connection import get_session
from bimcalc.db.models import ProjectModel, ItemModel, MatchResultModel, PriceItemModel


async def verify_recommendations():
    print("🧪 Verifying Recommendation System...")

    async with get_session() as session:
        # 1. Create test data
        org_id = "test-org-rec"
        project_id = uuid4()
        project_str = str(project_id)

        print(f"   Creating test project: {project_str}")

        project = ProjectModel(
            id=project_id,
            org_id=org_id,
            project_id=f"proj-{project_str[:8]}",
            display_name="Rec Test Project",
            status="active",
        )
        session.add(project)

        # Scenario 1: Missing Classification (Data Quality)
        item_no_class = ItemModel(
            id=uuid4(),
            org_id=org_id,
            project_id=project_str,
            classification_code=None,
            quantity=Decimal("10.0"),
            family="Unclassified Item",
            type_name="Type A",
        )
        session.add(item_no_class)

        # Scenario 2: Low Confidence Match (Better Match)
        item_low_conf = ItemModel(
            id=uuid4(),
            org_id=org_id,
            project_id=project_str,
            classification_code="123",
            quantity=Decimal("10.0"),
            family="Low Conf Item",
            type_name="Type B",
        )
        session.add(item_low_conf)

        match_low_conf = MatchResultModel(
            id=uuid4(),
            item_id=item_low_conf.id,
            price_item_id=None,
            confidence_score=60.0,
            decision="manual-review",
            source="fuzzy_match",
            reason="weak",
            created_by="system",
        )
        session.add(match_low_conf)

        # Scenario 3: High Cost (Cost Saving)
        item_high_cost = ItemModel(
            id=uuid4(),
            org_id=org_id,
            project_id=project_str,
            classification_code="123",
            quantity=Decimal("1.0"),
            family="Expensive Item",
            type_name="Type C",
        )
        session.add(item_high_cost)

        price_high = PriceItemModel(
            id=uuid4(),
            org_id=org_id,
            item_code="P_HIGH",
            region="EU",
            unit_price=Decimal("1000.00"),
            currency="EUR",
            source_name="Vendor A",
            description="Expensive",
            unit="ea",
            sku="SKU1",
            classification_code="123",
            source_currency="EUR",
        )
        session.add(price_high)

        match_high_cost = MatchResultModel(
            id=uuid4(),
            item_id=item_high_cost.id,
            price_item_id=price_high.id,
            confidence_score=95.0,
            decision="auto-accepted",
            source="fuzzy_match",
            reason="good",
            created_by="system",
        )
        session.add(match_high_cost)

        await session.commit()

        try:
            # 2. Call API
            print("   Calling API endpoint...")
            client = TestClient(app)
            response = client.get(
                f"/api/projects/{project_str}/intelligence/recommendations"
            )

            if response.status_code == 200:
                data = response.json()
                recs = data.get("recommendations", [])
                print(f"   Received {len(recs)} recommendations")

                # Verify types
                types = [r["type"] for r in recs]
                print(f"   Types found: {types}")

                if "data_quality" in types:
                    print("   ✅ Data Quality recommendation found")
                else:
                    print("   ❌ Missing Data Quality recommendation")

                if "better_match" in types:
                    print("   ✅ Better Match recommendation found")
                else:
                    print("   ❌ Missing Better Match recommendation")

                if "cost_saving" in types:
                    print("   ✅ Cost Saving recommendation found")
                else:
                    print("   ❌ Missing Cost Saving recommendation")

            else:
                print(
                    f"   ❌ API call failed: {response.status_code} - {response.text}"
                )

        finally:
            # Cleanup
            print("   Cleaning up test data...")
            await session.delete(match_high_cost)
            await session.delete(match_low_conf)
            await session.delete(price_high)
            await session.delete(item_high_cost)
            await session.delete(item_low_conf)
            await session.delete(item_no_class)
            await session.delete(project)
            await session.commit()


if __name__ == "__main__":
    asyncio.run(verify_recommendations())
