"""Verification script for CSV export functionality."""

import asyncio
import csv
from io import StringIO
from uuid import uuid4
from decimal import Decimal

from bimcalc.reporting.csv_export import (
    export_items_csv,
    export_prices_csv,
    export_matches_csv,
)
from bimcalc.db.connection import get_session
from bimcalc.db.models import ProjectModel, ItemModel, PriceItemModel, MatchResultModel


async def verify_csv_export():
    print("🧪 Verifying CSV Export...")

    async with get_session() as session:
        # 1. Create test data
        org_id = "test-org-csv"
        project_id = f"proj-{uuid4().hex[:8]}"

        print(f"   Creating test project: {project_id}")

        project = ProjectModel(
            id=uuid4(),
            org_id=org_id,
            project_id=project_id,
            display_name="CSV Export Test Project",
            status="active",
        )
        session.add(project)

        # Add price item
        price_item = PriceItemModel(
            id=uuid4(),
            org_id=org_id,
            item_code="TEST-001",
            region="EU",
            description="Test Description",
            unit_price=Decimal("100.00"),
            currency="EUR",
            unit="ea",
            classification_code="123",
            sku="SKU-123",
            source_name="Test Source",
            source_currency="EUR",
        )
        session.add(price_item)

        # Add item
        item = ItemModel(
            id=uuid4(),
            org_id=org_id,
            project_id=project_id,
            category="Electrical",
            family="Test Family",
            type_name="Test Type",
            quantity=Decimal("5.0"),
        )
        session.add(item)

        # Add match result
        match = MatchResultModel(
            id=uuid4(),
            item_id=item.id,
            price_item_id=price_item.id,
            confidence_score=95.0,
            decision="auto-accepted",
            source="fuzzy_match",
            reason="High confidence match",
            created_by="system",
        )
        session.add(match)

        await session.commit()

        try:
            # 2. Verify Items CSV
            print("   Verifying Items CSV...")
            items_csv_content = ""
            async for chunk in export_items_csv(session, org_id, project_id):
                items_csv_content += chunk

            reader = csv.DictReader(StringIO(items_csv_content))
            rows = list(reader)

            if len(rows) == 1 and rows[0]["Family"] == "Test Family":
                print("   ✅ Items CSV content verified")
            else:
                print(f"   ❌ Items CSV content incorrect: {rows}")

            # 3. Verify Prices CSV
            print("   Verifying Prices CSV...")
            prices_csv_content = ""
            async for chunk in export_prices_csv(session, org_id):
                prices_csv_content += chunk

            reader = csv.DictReader(StringIO(prices_csv_content))
            rows = list(reader)

            found_price = False
            for row in rows:
                if row["Item Code"] == "TEST-001":
                    found_price = True
                    break

            if found_price:
                print("   ✅ Prices CSV content verified")
            else:
                print("   ❌ Prices CSV content incorrect")

            # 4. Verify Matches CSV
            print("   Verifying Matches CSV...")
            matches_csv_content = ""
            async for chunk in export_matches_csv(session, org_id, project_id):
                matches_csv_content += chunk

            reader = csv.DictReader(StringIO(matches_csv_content))
            rows = list(reader)

            if len(rows) == 1 and rows[0]["Decision"] == "auto-accepted":
                print("   ✅ Matches CSV content verified")
            else:
                print(f"   ❌ Matches CSV content incorrect: {rows}")

        finally:
            # Cleanup
            print("   Cleaning up test data...")
            await session.delete(match)
            await session.delete(item)
            await session.delete(price_item)
            await session.delete(project)
            await session.commit()


if __name__ == "__main__":
    asyncio.run(verify_csv_export())
