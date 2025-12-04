"""Verification script for Advanced Analytics logic.

Tests:
1. Item Price History
2. Vendor Comparison
3. Cost Forecasting
"""

import asyncio
import sys
from pathlib import Path
from datetime import datetime, timedelta
from uuid import uuid4

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent))

from bimcalc.db.connection import get_session
from bimcalc.db.models import ItemModel, PriceItemModel
from bimcalc.reporting.analytics import AnalyticsEngine


async def verify_analytics():
    print("🧪 Verifying Advanced Analytics...")

    org_id = f"test-org-{uuid4()}"
    project_id = str(uuid4())
    item_code = "TEST-ITEM-001"

    async with get_session() as session:
        # 1. Setup Test Data
        print("   Setting up test data...")

        # Create Price History (SCD2)
        # Only the last one should be current
        dates = [
            (datetime.now() - timedelta(days=60), 100.0, False),
            (datetime.now() - timedelta(days=30), 110.0, False),
            (datetime.now(), 120.0, True),
        ]

        for i, (dt, price, is_curr) in enumerate(dates):
            p = PriceItemModel(
                org_id=org_id,
                item_code=item_code,
                unit_price=price,
                currency="EUR",
                vendor_id="VendorA",
                valid_from=dt,
                valid_to=None,  # Simplified
                is_current=is_curr,  # Correct SCD2 logic
                region="UK",  # Required field
                classification_code="TEST-CLASS",  # Required field
                sku=f"SKU-A-{i}",  # Required field
                description="Test Item Description",  # Required field
                unit="EA",  # Required field
                source_name="Manual Test",  # Required field
                source_currency="EUR",  # Required field
            )
            session.add(p)

        # Create Vendor B price (Must use different item_code due to unique constraint)
        item_code_b = "TEST-ITEM-002"
        p_b = PriceItemModel(
            org_id=org_id,
            item_code=item_code_b,
            unit_price=115.0,
            currency="EUR",
            vendor_id="VendorB",
            valid_from=datetime.now(),
            is_current=True,
            region="UK",  # Required field
            classification_code="TEST-CLASS",  # Required field
            sku="SKU-B-1",  # Required field
            description="Test Item Description",  # Required field
            unit="EA",  # Required field
            source_name="Manual Test",  # Required field
            source_currency="EUR",  # Required field
        )
        session.add(p_b)
        await session.flush()  # Ensure ID is generated

        # Create Items for Project (for forecasting)
        # Create items created over time
        for i in range(5):
            item = ItemModel(
                id=uuid4(),
                org_id=org_id,
                project_id=project_id,
                family="TestFamily",
                type_name="TestType",
                quantity=10,
                created_at=datetime.now() - timedelta(days=5 - i),
                price_item_id=p_b.id,  # Link to price
            )
            session.add(item)

        await session.commit()

        engine = AnalyticsEngine(session)

        # 2. Test Price History
        print("   Testing Price History...")
        history = await engine.get_item_price_history(item_code, org_id)
        if len(history["history"]) >= 3:
            print(f"   ✅ History retrieved: {len(history['history'])} records.")
        else:
            print(f"   ❌ History failed: {len(history['history'])} records found.")

        # 3. Test Vendor Comparison
        print("   Testing Vendor Comparison...")
        comparison = await engine.compare_vendors([item_code, item_code_b], org_id)
        vendors = [c["vendor"] for c in comparison["comparison"]]
        if "VendorA" in vendors and "VendorB" in vendors:
            print(f"   ✅ Vendor comparison successful: {vendors}")
        else:
            print(f"   ❌ Vendor comparison failed: {vendors}")

        # 4. Test Forecasting
        print("   Testing Forecasting...")
        forecast = await engine.forecast_cost_trends(project_id, days=10)
        if forecast.get("forecast_data"):
            print(f"   ✅ Forecast generated: {len(forecast['forecast_data'])} days.")
            print(f"   Slope: {forecast.get('trend_slope')}")
        else:
            print(f"   ⚠️ Forecast warning: {forecast.get('message')}")

    print("✅ Analytics Verification Complete!")


if __name__ == "__main__":
    asyncio.run(verify_analytics())
