"""Verification script for Compliance UI API."""

import asyncio
from uuid import uuid4
from decimal import Decimal
from fastapi.testclient import TestClient

from bimcalc.web.app_enhanced import app
from bimcalc.db.connection import get_session
from bimcalc.db.models import ProjectModel, ItemModel
from bimcalc.db.models_intelligence import ComplianceRuleModel


async def verify_compliance_ui():
    print("🧪 Verifying Compliance UI API...")

    async with get_session() as session:
        # 1. Create test data
        org_id = "test-org-comp-ui"
        project_id = uuid4()
        project_str = str(project_id)

        print(f"   Creating test project: {project_str}")

        project = ProjectModel(
            id=project_id,
            org_id=org_id,
            project_id=f"proj-{project_str[:8]}",
            display_name="Comp UI Test Project",
            status="active",
        )
        session.add(project)

        # 2. Create Rules (API should seed if empty, but we want controlled test)
        rule_class = ComplianceRuleModel(
            id=uuid4(),
            org_id=org_id,
            name="Class Required",
            description="Must have class",
            rule_type="classification_required",
            severity="high",
            is_active=True,
        )
        session.add(rule_class)

        # 3. Create Items
        # Non-Compliant (Missing Class)
        item_bad = ItemModel(
            id=uuid4(),
            org_id=org_id,
            project_id=project_str,
            classification_code=None,
            quantity=Decimal("10.0"),
            family="Bad Item",
            type_name="Type X",
        )
        session.add(item_bad)

        # Compliant
        item_good = ItemModel(
            id=uuid4(),
            org_id=org_id,
            project_id=project_str,
            classification_code="123",
            quantity=Decimal("10.0"),
            family="Good Item",
            type_name="Type Y",
        )
        session.add(item_good)

        await session.commit()

        try:
            # 4. Call API
            print("   Calling API endpoint...")
            client = TestClient(app)
            response = client.get(
                f"/api/projects/{project_str}/intelligence/compliance"
            )

            if response.status_code == 200:
                data = response.json()
                summary = data.get("summary", {})
                failures = data.get("failures", [])

                print(f"   Summary: {summary}")
                print(f"   Failures: {len(failures)}")

                if summary.get("score") == 50.0:
                    print("   ✅ Score is 50% (1 passed, 1 failed)")
                else:
                    print(f"   ❌ Expected score 50%, got {summary.get('score')}")

                if len(failures) == 1:
                    print("   ✅ Correct failure count")
                    if failures[0]["family"] == "Bad Item":
                        print("   ✅ Correct item failed")
                    else:
                        print(f"   ❌ Wrong item failed: {failures[0]['family']}")
                else:
                    print(f"   ❌ Expected 1 failure, got {len(failures)}")

            else:
                print(
                    f"   ❌ API call failed: {response.status_code} - {response.text}"
                )

        finally:
            # Cleanup
            print("   Cleaning up test data...")
            await session.delete(item_bad)
            await session.delete(item_good)
            await session.delete(rule_class)
            await session.delete(project)
            await session.commit()


if __name__ == "__main__":
    asyncio.run(verify_compliance_ui())
