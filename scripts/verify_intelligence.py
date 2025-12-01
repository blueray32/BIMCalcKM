import asyncio
import os
import sys
from uuid import uuid4
from datetime import datetime

# Add project root to path
sys.path.append(os.getcwd())

from bimcalc.db.connection import get_session
from bimcalc.db.models import ItemModel, PriceItemModel, MatchResultModel, TrainingExampleModel
from bimcalc.review.models import ReviewRecord, ReviewItem, ReviewPrice, ReviewFlag
from bimcalc.review.service import approve_review_record

async def verify_intelligence():
    print("🧪 Verifying Intelligence Feedback Loop...")
    
    org_id = "test-org-intel"
    project_id = "test-proj-intel"
    
    # Cleanup
    async with get_session() as session:
        from sqlalchemy import text
        await session.execute(text(f"DELETE FROM training_examples WHERE org_id = '{org_id}'"))
        await session.execute(text(f"DELETE FROM match_results WHERE created_by = 'verify-script'"))
        await session.commit()

    # Create dummy data
    item_id = uuid4()
    price_id = uuid4()
    
    item = ItemModel(
        id=item_id,
        org_id=org_id,
        project_id=project_id,
        family="Basic Wall",
        type_name="Generic - 200mm",
        classification_code="2101", # Original class
        created_at=datetime.utcnow()
    )
    
    price = PriceItemModel(
        id=price_id,
        org_id=org_id,
        item_code="P1",
        region="EU",
        classification_code="2102", # Target class (Correction!)
        sku="SKU123",
        description="Concrete Block 200mm",
        unit="m2",
        unit_price=50.0,
        currency="EUR",
        source_name="TestVendor",
        source_currency="EUR",
        valid_from=datetime.utcnow(),
        is_current=True
    )
    
    # Construct ReviewRecord
    record = ReviewRecord(
        match_result_id=uuid4(),
        item=ReviewItem(
            id=item.id,
            org_id=org_id,
            project_id=project_id,
            canonical_key="hash123",
            family=item.family,
            type_name=item.type_name,
            category="Walls",
            system_type=None,
            classification_code=item.classification_code,
            quantity=10,
            unit="m2",
            width_mm=None,
            height_mm=None,
            dn_mm=None,
            angle_deg=None,
            material=None,
            source_file="test.rvt"
        ),
        price=ReviewPrice(
            id=price.id,
            vendor_id="vendor1",
            sku=price.sku,
            description=price.description,
            classification_code=price.classification_code,
            unit=price.unit,
            unit_price=price.unit_price,
            currency=price.currency,
            vat_rate=None,
            width_mm=None,
            height_mm=None,
            dn_mm=None,
            angle_deg=None,
            material=None,
            last_updated=datetime.utcnow(),
            vendor_note=None
        ),
        confidence_score=85.0,
        source="fuzzy_match",
        reason="Test match",
        created_by="system",
        timestamp=datetime.utcnow(),
        flags=[]
    )
    
    async with get_session() as session:
        # We don't need to insert Item/Price into DB for this unit test of the service function,
        # providing the service function doesn't query them again.
        # Checking service.py: it uses MappingMemory which writes to DB.
        # So we probably need Item/Price in DB to satisfy foreign keys if they exist?
        # MappingMemory writes to item_mapping table.
        # TrainingExample writes to training_examples table.
        # Neither strictly enforces FKs in SQLite usually unless enabled, but good to be safe.
        # Actually, TrainingExample has no FKs defined in the model I wrote (just UUID cols).
        
        await approve_review_record(session, record, created_by="verify-script", annotation="Correcting class")
        await session.commit()
        
        # Verify TrainingExample created
        from sqlalchemy import select
        stmt = select(TrainingExampleModel).where(TrainingExampleModel.org_id == org_id)
        result = (await session.execute(stmt)).scalars().first()
        
        if result:
            print(f"✅ Training Example Created: {result.id}")
            print(f"   Item: {result.item_description}")
            print(f"   Target Class: {result.target_classification_code}")
            print(f"   Feedback Type: {result.feedback_type}")
            
            assert result.feedback_type == "correction"
            assert result.target_classification_code == "2102"
        else:
            print("❌ No Training Example found!")
            exit(1)

if __name__ == "__main__":
    asyncio.run(verify_intelligence())
