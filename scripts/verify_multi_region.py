import asyncio
import os
import sys
import logging
from uuid import uuid4
from decimal import Decimal

# Add project root to path
sys.path.append(os.getcwd())

from bimcalc.db.connection import get_session
from bimcalc.db.models import ProjectModel, PriceItemModel
from bimcalc.models import Item
from bimcalc.matching.orchestrator import match_item, MatchOrchestrator

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def verify_multi_region():
    print("🌍 Verifying Multi-Region Support...")
    
    async with get_session() as session:
        # 1. Setup Data
        run_id = uuid4().hex[:6]
        org_id = f"test-org-{run_id}"
        sku = f"TEST-PIPE-{run_id}"
        
        # Create Projects
        eu_project_id = f"proj-eu-{run_id}"
        us_project_id = f"proj-us-{run_id}"
        
        print(f"   Creating EU Project: {eu_project_id}")
        session.add(ProjectModel(
            org_id=org_id,
            project_id=eu_project_id,
            display_name="EU Tower",
            region="EU",
            status="active"
        ))
        
        print(f"   Creating US Project: {us_project_id}")
        session.add(ProjectModel(
            org_id=org_id,
            project_id=us_project_id,
            display_name="US Tower",
            region="US",
            status="active"
        ))
        
        # Create Price Items (Same item, different regions/prices)
        class_code = 2215
        
        print(f"   Creating EU Price: €100.00")
        session.add(PriceItemModel(
            org_id=org_id,
            item_code=sku,
            region="EU",
            vendor_id="vendor-eu",
            sku=sku,
            description="Pipe Steel DN100",
            classification_code=class_code,
            unit="m",
            unit_price=Decimal("100.00"),
            currency="EUR",
            width_mm=100.0,
            source_name="test",
            source_currency="EUR"
        ))
        
        print(f"   Creating US Price: $120.00")
        session.add(PriceItemModel(
            org_id=org_id,
            item_code=sku,
            region="US",
            vendor_id="vendor-us",
            sku=sku,
            description="Pipe Steel DN100",
            classification_code=class_code,
            unit="m",
            unit_price=Decimal("120.00"),
            currency="USD",
            width_mm=100.0,
            source_name="test",
            source_currency="USD"
        ))
        
        await session.commit()
        
        # 2. Verify EU Matching
        print("\n   🧪 Testing EU Matching...")
        eu_item = Item(
            org_id=org_id,
            project_id=eu_project_id,
            family="Pipe",
            type_name="Steel DN100",
            classification_code=class_code,
            width_mm=100.0,
            unit="m",
            quantity=Decimal("10")
        )
        
        result_eu, price_eu = await match_item(session, eu_item)
        
        if price_eu and price_eu.currency == "EUR" and price_eu.unit_price == 100.00:
            print(f"   ✅ EU Match Success: Found {price_eu.currency} {price_eu.unit_price}")
        else:
            print(f"   ❌ EU Match Failed: Got {price_eu.currency if price_eu else 'None'} {price_eu.unit_price if price_eu else ''}")
            
        # 3. Verify US Matching
        print("\n   🧪 Testing US Matching...")
        us_item = Item(
            org_id=org_id,
            project_id=us_project_id,
            family="Pipe",
            type_name="Steel DN100",
            classification_code=class_code,
            width_mm=100.0,
            unit="m",
            quantity=Decimal("10")
        )
        
        result_us, price_us = await match_item(session, us_item)
        
        if price_us and price_us.currency == "USD" and price_us.unit_price == 120.00:
            print(f"   ✅ US Match Success: Found {price_us.currency} {price_us.unit_price}")
        else:
            print(f"   ❌ US Match Failed: Got {price_us.currency if price_us else 'None'} {price_us.unit_price if price_us else ''}")

if __name__ == "__main__":
    asyncio.run(verify_multi_region())
