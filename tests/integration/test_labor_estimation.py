import pytest
import os
import uuid
from decimal import Decimal
from datetime import datetime
from sqlalchemy import text, event
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from bimcalc.db.models import ItemModel, MatchResultModel
from bimcalc.ingestion.pricebooks import ingest_pricebook
from bimcalc.reporting.dashboard_metrics import compute_dashboard_metrics
from pathlib import Path

# Use the same DB URL as the app or a test one
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./bimcalc.db")

import pytest_asyncio


@pytest_asyncio.fixture
async def db_session():
    engine = create_async_engine(DATABASE_URL)

    # Register LEAST and now functions for SQLite
    @event.listens_for(engine.sync_engine, "connect")
    def connect(dbapi_connection, connection_record):
        try:
            dbapi_connection.create_function("LEAST", -1, min)
            dbapi_connection.create_function(
                "now", 0, lambda: datetime.utcnow().isoformat(" ")
            )
        except Exception:
            pass

    AsyncSessionLocal = sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )
    async with AsyncSessionLocal() as session:
        yield session
    await engine.dispose()


@pytest.mark.asyncio
async def test_labor_estimation_flow(db_session):
    session = db_session

    # 0. Cleanup Previous Test Data
    await session.execute(
        text("DELETE FROM price_items WHERE vendor_id = 'TEST_LABOR_INTEGRATION'")
    )
    await session.execute(
        text("DELETE FROM items WHERE org_id = 'test_org_integration'")
    )
    await session.execute(
        text("DELETE FROM match_results WHERE created_by = 'test_script_integration'")
    )
    await session.execute(
        text("DELETE FROM item_mapping WHERE created_by = 'test_script_integration'")
    )
    await session.commit()

    # 1. Ingest Test Data
    # Create a temporary CSV file
    csv_content = """SKU,Description,Unit,Unit Price,Labor Hours,Labor Code,Classification Code
LAB-INT-001,Test Elbow,ea,45.00,0.8,NECA-101,2215
"""
    csv_path = Path("test_data/labor_integration_test.csv")
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    csv_path.write_text(csv_content)

    try:
        success, errors = await ingest_pricebook(
            session=session,
            file_path=csv_path,
            vendor_id="TEST_LABOR_INTEGRATION",
            org_id="test_org_integration",
            region="IE",
        )
        assert success == 1
        assert len(errors) == 0

        # 2. Verify Database Records
        stmt = text(
            "SELECT labor_hours FROM price_items WHERE sku = 'LAB-INT-001' AND vendor_id = 'TEST_LABOR_INTEGRATION'"
        )
        result = await session.execute(stmt)
        labor_hours = result.scalar()
        assert labor_hours == 0.8

        # 3. Setup Dashboard Test Data
        # Create Item
        test_item = ItemModel(
            org_id="test_org_integration",
            project_id="test_proj_integration",
            family="Elbow",
            type_name="Steel",
            quantity=Decimal("10"),
            classification_code="2215",
            canonical_key="test_canonical_key_integration",
            created_at=datetime.utcnow(),
        )
        session.add(test_item)
        await session.flush()

        # Get Price Item
        stmt = text(
            "SELECT id FROM price_items WHERE sku = 'LAB-INT-001' AND vendor_id = 'TEST_LABOR_INTEGRATION'"
        )
        price_item_id_res = await session.execute(stmt)
        price_item_id_raw = price_item_id_res.scalar()

        # Convert to UUID object for Model
        if isinstance(price_item_id_raw, str):
            price_item_id_uuid = uuid.UUID(price_item_id_raw)
        else:
            price_item_id_uuid = price_item_id_raw

        # Create Match
        match = MatchResultModel(
            item_id=test_item.id,
            price_item_id=price_item_id_uuid,
            confidence_score=0.95,
            source="mapping_memory",
            decision="auto-accepted",
            reason="Test verification",
            created_by="test_script_integration",
            timestamp=datetime.utcnow(),
        )
        session.add(match)

        # Create Mapping (Raw SQL to avoid model import issues if any)
        # For SQLite raw insert, we likely need the hex string
        price_item_id_str = str(price_item_id_uuid).replace("-", "")

        await session.execute(
            text("""
            INSERT INTO item_mapping (id, org_id, canonical_key, price_item_id, reason, created_by, start_ts)
            VALUES (:id, :org_id, :canonical_key, :price_item_id, :reason, :created_by, :start_ts)
        """),
            {
                "id": "test_mapping_id_integration",
                "org_id": "test_org_integration",
                "canonical_key": "test_canonical_key_integration",
                "price_item_id": price_item_id_str,
                "reason": "Test verification",
                "created_by": "test_script_integration",
                "start_ts": datetime.utcnow(),
            },
        )
        await session.commit()

        # 4. Verify Dashboard Metrics
        metrics = await compute_dashboard_metrics(
            session, "test_org_integration", "test_proj_integration"
        )

        # Expected: 10 items * 0.8 hours = 8.0 hours
        # Cost: 8.0 hours * 50.0 rate = 400.0
        # Material: 10 * 45.00 = 450.0
        # Total: 850.0

        assert metrics.total_labor_hours == 8.0
        assert metrics.total_labor_cost == 400.0
        assert metrics.total_cost_net == 450.0
        assert metrics.total_installed_cost == 850.0

    finally:
        # Cleanup file
        if csv_path.exists():
            csv_path.unlink()
