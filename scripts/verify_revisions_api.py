import asyncio
import os
import sys
from uuid import uuid4
from datetime import datetime

# Add project root to path
sys.path.append(os.getcwd())

# Disable auth for testing
os.environ["BIMCALC_AUTH_DISABLED"] = "true"

from fastapi.testclient import TestClient
from bimcalc.web.app_enhanced import app
from bimcalc.db.connection import get_session
from bimcalc.db.models import ItemModel, ItemRevisionModel

client = TestClient(app)


async def verify_revisions_api():
    print("🧪 Verifying Revisions API...")

    org_id = f"API-TEST-ORG-{uuid4().hex[:8]}"
    project_id = "API-TEST-PROJ"

    # 1. Setup Test Data
    print("   Setting up test data...")
    async with get_session() as session:
        # Create an item
        item = ItemModel(
            org_id=org_id,
            project_id=project_id,
            family="TestFamily",
            type_name="TestType",
            category="Walls",
            attributes={"width": "100mm"},
        )
        session.add(item)
        await session.flush()

        # Create revisions
        rev1 = ItemRevisionModel(
            item_id=item.id,
            org_id=org_id,
            project_id=project_id,
            ingest_timestamp=datetime.utcnow(),
            source_filename="import1.xlsx",
            field_name="width",
            old_value="100mm",
            new_value="150mm",
            change_type="modified",
        )
        session.add(rev1)

        rev2 = ItemRevisionModel(
            item_id=item.id,
            org_id=org_id,
            project_id=project_id,
            ingest_timestamp=datetime.utcnow(),
            source_filename="import2.xlsx",
            field_name="material",
            old_value=None,
            new_value="Concrete",
            change_type="added",
        )
        session.add(rev2)

        await session.commit()
        item_id = str(item.id)

    # 2. Test API
    print("   Testing GET /api/revisions...")
    resp = client.get(f"/api/revisions?org={org_id}&project={project_id}")

    if resp.status_code != 200:
        print(f"❌ Failed to get revisions: {resp.status_code} - {resp.text}")
        return False

    data = resp.json()
    if data["count"] != 2:
        print(f"❌ Expected 2 revisions, got {data['count']}")
        return False

    print(f"   ✅ Retrieved {data['count']} revisions")

    # Verify content
    revs = data["revisions"]
    if revs[0]["field_name"] == "material" and revs[0]["change_type"] == "added":
        print("   ✅ Revision 1 content correct")
    else:
        print(f"❌ Revision 1 content mismatch: {revs[0]}")

    if revs[1]["field_name"] == "width" and revs[1]["change_type"] == "modified":
        print("   ✅ Revision 2 content correct")
    else:
        print(f"❌ Revision 2 content mismatch: {revs[1]}")

    print("✅ Revisions API Verification Complete!")
    return True


if __name__ == "__main__":
    success = asyncio.run(verify_revisions_api())
    sys.exit(0 if success else 1)
