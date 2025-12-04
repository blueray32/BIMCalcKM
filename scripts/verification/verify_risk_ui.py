"""Verification script for Risk UI API."""

import asyncio
from uuid import uuid4
from decimal import Decimal
from fastapi.testclient import TestClient

from bimcalc.web.app_enhanced import app
from bimcalc.db.connection import get_session
from bimcalc.db.models import ProjectModel, ItemModel, MatchResultModel


async def verify_risk_api():
    print("🧪 Verifying Risk UI API...")

    async with get_session() as session:
        # 1. Create test data
        org_id = "test-org-ui"
        project_id = uuid4()
        project_str = str(project_id)

        print(f"   Creating test project: {project_str}")

        project = ProjectModel(
            id=project_id,
            org_id=org_id,
            project_id=f"proj-{project_str[:8]}",
            display_name="Risk UI Test Project",
            status="active",
        )
        session.add(project)

        # High Risk Item
        item_high = ItemModel(
            id=uuid4(),
            org_id=org_id,
            project_id=project_str,
            classification_code=None,
            quantity=Decimal("0.0"),
            family="High Risk Family",
            type_name="Type A",
        )
        session.add(item_high)

        match_high = MatchResultModel(
            id=uuid4(),
            item_id=item_high.id,
            price_item_id=None,
            confidence_score=50.0,
            decision="manual-review",
            source="fuzzy_match",
            reason="weak",
            created_by="system",
        )
        session.add(match_high)

        # Low Risk Item
        item_low = ItemModel(
            id=uuid4(),
            org_id=org_id,
            project_id=project_str,
            classification_code="123",
            quantity=Decimal("10.0"),
            family="Low Risk Family",
            type_name="Type B",
        )
        session.add(item_low)

        match_low = MatchResultModel(
            id=uuid4(),
            item_id=item_low.id,
            price_item_id=None,  # No price but high conf
            confidence_score=95.0,
            decision="auto-accepted",
            source="fuzzy_match",
            reason="good",
            created_by="system",
        )
        session.add(match_low)

        await session.commit()

        try:
            # 2. Call API
            print("   Calling API endpoint...")
            client = TestClient(app)
            response = client.get(f"/api/projects/{project_str}/intelligence/risk")

            if response.status_code == 200:
                data = response.json()
                print("   ✅ API call successful")

                # 3. Verify Response Structure
                summary = data.get("summary", {})
                high_risk_items = data.get("high_risk_items", [])

                print(f"   Summary: {summary}")
                print(f"   High Risk Items: {len(high_risk_items)}")

                if summary.get("high") >= 1:
                    print("   ✅ High risk count correct")
                else:
                    print(f"   ❌ Expected high risk >= 1, got {summary.get('high')}")

                found_item = next(
                    (i for i in high_risk_items if i["family"] == "High Risk Family"),
                    None,
                )
                if found_item:
                    print(
                        f"   ✅ Found high risk item: {found_item['family']} (Score: {found_item['score']})"
                    )
                    if found_item["score"] >= 80:
                        print("   ✅ Score is high risk")
                    else:
                        print(f"   ❌ Score too low: {found_item['score']}")
                else:
                    print("   ❌ High risk item not found in response")

            else:
                print(
                    f"   ❌ API call failed: {response.status_code} - {response.text}"
                )

        finally:
            # Cleanup
            print("   Cleaning up test data...")
            await session.delete(match_high)
            await session.delete(match_low)
            await session.delete(item_high)
            await session.delete(item_low)
            await session.delete(project)
            await session.commit()


if __name__ == "__main__":
    asyncio.run(verify_risk_api())
