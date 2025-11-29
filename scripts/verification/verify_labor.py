import asyncio
import os
from pathlib import Path
from decimal import Decimal
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select, text, event

from bimcalc.db.models import Base, PriceItemModel, ItemModel, MatchResultModel
from bimcalc.ingestion.pricebooks import ingest_pricebook
from bimcalc.reporting.dashboard_metrics import compute_dashboard_metrics

# Setup DB
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./bimcalc.db")
engine = create_async_engine(DATABASE_URL)

# Register LEAST function for SQLite
@event.listens_for(engine.sync_engine, "connect")
def connect(dbapi_connection, connection_record):
    try:
        dbapi_connection.create_function("LEAST", -1, min)
    except Exception as e:
        print(f"Failed to register LEAST function: {e}")

AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

async def verify():
    async with AsyncSessionLocal() as session:
        # 0. Cleanup Previous Test Data
        print("--- Cleaning up previous test data ---")
        await session.execute(text("DELETE FROM price_items WHERE vendor_id = 'TEST_LABOR'"))
        await session.execute(text("DELETE FROM items WHERE org_id = 'test_org'"))
        await session.execute(text("DELETE FROM match_results WHERE created_by = 'test_script'"))
        await session.execute(text("DELETE FROM item_mapping WHERE created_by = 'test_script'"))
        await session.commit()

        # 1. Ingest Test Data
        print("--- Ingesting Labor Test Data ---")
        csv_path = Path("test_data/labor_test.csv")
        success, errors = await ingest_pricebook(
            session=session,
            file_path=csv_path,
            vendor_id="TEST_LABOR",
            org_id="test_org",
            region="IE"
        )
        print(f"Ingestion Result: {success} success, {len(errors)} errors")
        if errors:
            print("Errors:", errors)

        # 2. Verify Database Records
        print("\n--- Verifying Database Records ---")
        stmt = select(PriceItemModel).where(PriceItemModel.vendor_id == "TEST_LABOR")
        result = await session.execute(stmt)
        items = result.scalars().all()
        
        labor_found = False
        for item in items:
            print(f"Item: {item.sku}, Price: {item.unit_price}, Labor Hours: {item.labor_hours}")
            if item.sku == "LAB-001" and item.labor_hours == Decimal("0.80"):
                labor_found = True
        
        if labor_found:
            print("✅ SUCCESS: Labor hours correctly stored in DB.")
        else:
            print("❌ FAILURE: Labor hours not found or incorrect.")

        # 3. Create Dummy Project Items & Matches for Dashboard Test
        print("\n--- Setting up Dashboard Test Data ---")
        # Create an item that matches our labor item
        test_item = ItemModel(
            org_id="test_org",
            project_id="test_proj",
            family="Elbow",
            type_name="Steel",
            quantity=Decimal("10"), # 10 elbows
            classification_code="2215"
        )
        session.add(test_item)
        await session.flush()

        # Find the price item we just ingested
        price_item = next(i for i in items if i.sku == "LAB-001")
        
        # Create a match result linking them
        match = MatchResultModel(
            item_id=test_item.id,
            price_item_id=price_item.id,
            confidence_score=0.95,
            source="review_ui",
            decision="auto-accepted",
            reason="Test verification",
            created_by="test_script"
        )
        session.add(match)

        # Create Item Mapping (required for dashboard metrics)
        # The dashboard query joins on active_mappings via canonical_key
        test_item.canonical_key = "test_canonical_key"
        
        # We need to insert into item_mapping table directly or use a model if available
        # Let's use raw SQL for simplicity as ItemMappingModel might not be imported
        await session.execute(text("""
            INSERT INTO item_mapping (id, org_id, canonical_key, price_item_id, source, confidence_score, reason, created_by)
            VALUES (:id, :org_id, :canonical_key, :price_item_id, :source, :confidence_score, :reason, :created_by)
        """), {
            "id": "test_mapping_id",
            "org_id": "test_org",
            "canonical_key": "test_canonical_key",
            "price_item_id": price_item.id.hex,
            "source": "manual",
            "confidence_score": 0.95,
            "reason": "Test verification",
            "created_by": "test_script"
        })

        await session.commit()

        # Debug: Check DB Content
        print("\n--- Debugging DB Content ---")
        
        # Check Item
        item_res = await session.execute(text("SELECT id, canonical_key, org_id FROM items WHERE org_id = 'test_org'"))
        item_row = item_res.first()
        print(f"Item: {item_row}")

        # Check Price Item
        pi_res = await session.execute(text("SELECT id, labor_hours FROM price_items WHERE vendor_id = 'TEST_LABOR'"))
        pi_row = pi_res.first()
        print(f"Price Item ID (Raw): {pi_row[0]!r}, Type: {type(pi_row[0])}")
        
        # Check Mapping
        map_res = await session.execute(text("SELECT price_item_id, canonical_key FROM item_mapping WHERE org_id = 'test_org'"))
        map_row = map_res.first()
        print(f"Mapping Price Item ID (Raw): {map_row[0]!r}, Type: {type(map_row[0])}")

        # Check Match
        match_res = await session.execute(text("SELECT item_id, decision, price_item_id FROM match_results WHERE created_by = 'test_script'"))
        match_row = match_res.first()
        print(f"Match: {match_row}")

        # 4. Verify Dashboard Metrics
        print("\n--- Verifying Dashboard Metrics ---")
        metrics = await compute_dashboard_metrics(session, "test_org", "test_proj")
        
        print(f"Total Material Cost: {metrics.total_cost_net}")
        print(f"Total Labor Hours: {metrics.total_labor_hours}")
        print(f"Total Labor Cost: {metrics.total_labor_cost}")
        print(f"Total Installed Cost: {metrics.total_installed_cost}")

        # Expected: 10 items * 0.8 hours = 8.0 hours
        # Cost: 8.0 hours * 50.0 rate = 400.0
        if metrics.total_labor_hours == 8.0 and metrics.total_labor_cost == 400.0:
            print("✅ SUCCESS: Dashboard metrics correctly calculated labor costs.")
        else:
            print("❌ FAILURE: Dashboard metrics calculation incorrect.")

if __name__ == "__main__":
    asyncio.run(verify())
