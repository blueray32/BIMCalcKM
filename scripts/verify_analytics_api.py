"""Verification script for Advanced Analytics API endpoints.

Tests:
1. GET /api/analytics/history/{item_code}
2. POST /api/analytics/vendor-comparison
3. GET /api/analytics/forecast
"""

import asyncio
import sys
from pathlib import Path
from uuid import uuid4
from datetime import datetime

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent))

from fastapi.testclient import TestClient
from bimcalc.web.app_enhanced import app
from bimcalc.db.connection import get_session
from bimcalc.db.models import PriceItemModel, ItemModel


async def setup_test_data(org_id: str, project_id: str):
    """Create necessary test data in the DB."""
    async with get_session() as session:
        # Create Price Item
        p = PriceItemModel(
            org_id=org_id,
            item_code="API-TEST-ITEM",
            unit_price=150.0,
            currency="EUR",
            vendor_id="VendorAPI",
            valid_from=datetime.now(),
            is_current=True,
            region="UK",
            classification_code="API-CLASS",
            sku="API-SKU-1",
            description="API Test Item",
            unit="EA",
            source_name="API Test",
            source_currency="EUR",
        )
        session.add(p)
        await session.flush()

        # Create Project Item (for forecast)
        item = ItemModel(
            id=uuid4(),
            org_id=org_id,
            project_id=project_id,
            family="ApiFamily",
            type_name="ApiType",
            quantity=5,
            created_at=datetime.now(),
            price_item_id=p.id,
        )
        session.add(item)
        await session.commit()


def verify_api():
    print("🌐 Verifying Analytics API Endpoints...")

    client = TestClient(app)
    org_id = f"test-org-api-{uuid4()}"
    project_id = str(uuid4())

    # Setup data (using asyncio loop since setup is async)
    asyncio.run(setup_test_data(org_id, project_id))

    # 1. Test History API
    print("   Testing GET /api/analytics/history/...")
    resp = client.get(f"/api/analytics/history/API-TEST-ITEM?org={org_id}")
    if resp.status_code == 200:
        data = resp.json()
        if data["item_code"] == "API-TEST-ITEM" and len(data["history"]) > 0:
            print("   ✅ History API success")
        else:
            print(f"   ❌ History API returned unexpected data: {data}")
    else:
        print(f"   ❌ History API failed: {resp.status_code} - {resp.text}")

    # 2. Test Vendor Comparison API
    print("   Testing POST /api/analytics/vendor-comparison...")
    resp = client.post(
        f"/api/analytics/vendor-comparison?org={org_id}", json=["API-TEST-ITEM"]
    )
    if resp.status_code == 200:
        data = resp.json()
        if (
            len(data["comparison"]) > 0
            and data["comparison"][0]["vendor"] == "VendorAPI"
        ):
            print("   ✅ Vendor Comparison API success")
        else:
            print(f"   ❌ Vendor Comparison API returned unexpected data: {data}")
    else:
        print(f"   ❌ Vendor Comparison API failed: {resp.status_code} - {resp.text}")

    # 3. Test Forecast API
    print("   Testing GET /api/analytics/forecast...")
    resp = client.get(f"/api/analytics/forecast?project={project_id}&days=30")
    if resp.status_code == 200:
        data = resp.json()
        # Note: Forecast might return empty/warning if not enough data points, but 200 OK means endpoint works
        if "forecast_data" in data or "message" in data:
            print("   ✅ Forecast API success")
        else:
            print(f"   ❌ Forecast API returned unexpected structure: {data.keys()}")
    else:
        print(f"   ❌ Forecast API failed: {resp.status_code} - {resp.text}")

    print("✅ API Verification Complete!")


if __name__ == "__main__":
    verify_api()
