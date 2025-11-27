"""Verification script for Export Filtering."""
import asyncio
from uuid import uuid4
from decimal import Decimal
from fastapi.testclient import TestClient

from bimcalc.web.app_enhanced import app
from bimcalc.db.connection import get_session
from bimcalc.db.models import ProjectModel, ItemModel, PriceItemModel, MatchResultModel

async def verify_export_filters():
    print("🧪 Verifying Export Filtering...")
    
    async with get_session() as session:
        # 1. Create test data
        org_id = "test-org-export"
        project_id = uuid4()
        project_str = str(project_id)
        
        print(f"   Creating test project: {project_str}")
        
        project = ProjectModel(
            id=project_id,
            org_id=org_id,
            project_id=f"proj-{project_str[:8]}",
            display_name="Export Test Project",
            status="active"
        )
        session.add(project)
        
        # Create Items (Cat A and Cat B)
        item_a = ItemModel(
            id=uuid4(), org_id=org_id, project_id=project.project_id,
            category="Cat A", family="Family A", type_name="Type A",
            quantity=Decimal("10.0")
        )
        item_b = ItemModel(
            id=uuid4(), org_id=org_id, project_id=project.project_id,
            category="Cat B", family="Family B", type_name="Type B",
            quantity=Decimal("5.0")
        )
        session.add(item_a)
        session.add(item_b)
        
        # Create Price Items (Vendor X and Vendor Y)
        price_x = PriceItemModel(
            id=uuid4(), org_id=org_id, classification_code="Cat A",
            item_code="X1", description="Item X", unit_price=Decimal("100.0"),
            source_name="Vendor X", region="IE", sku="SKU-X1", unit="EA",
            source_currency="EUR"
        )
        price_y = PriceItemModel(
            id=uuid4(), org_id=org_id, classification_code="Cat B",
            item_code="Y1", description="Item Y", unit_price=Decimal("50.0"),
            source_name="Vendor Y", region="IE", sku="SKU-Y1", unit="EA",
            source_currency="EUR"
        )
        session.add(price_x)
        session.add(price_y)
        
        # Create Matches (High conf and Low conf)
        match_high = MatchResultModel(
            id=uuid4(), item_id=item_a.id, price_item_id=price_x.id,
            confidence_score=95.0, source="fuzzy_match", decision="auto-accepted",
            reason="Good match", created_by="system"
        )
        match_low = MatchResultModel(
            id=uuid4(), item_id=item_b.id, price_item_id=price_y.id,
            confidence_score=40.0, source="fuzzy_match", decision="manual-review",
            reason="Bad match", created_by="system"
        )
        session.add(match_high)
        session.add(match_low)
        
        await session.commit()
        
        try:
            client = TestClient(app)
            
            # 2. Test Items Filter (Category)
            print("   Testing Items Export (Filter: Cat A)...")
            response = client.get(f"/api/projects/{project_str}/export/csv/items?category=Cat A")
            assert response.status_code == 200
            content = response.text
            print(f"DEBUG: Response content: {content}")
            assert "Cat A" in content
            assert "Cat B" not in content
            print("   ✅ Items filtered correctly")
            
            # 3. Test Prices Filter (Vendor)
            print("   Testing Prices Export (Filter: Vendor X)...")
            response = client.get(f"/api/projects/{project_str}/export/csv/prices?vendor=Vendor X")
            assert response.status_code == 200
            content = response.text
            assert "Vendor X" in content
            assert "Vendor Y" not in content
            print("   ✅ Prices filtered correctly")
            
            # 4. Test Matches Filter (Confidence)
            print("   Testing Matches Export (Filter: Confidence >= 90)...")
            response = client.get(f"/api/projects/{project_str}/export/csv/matches?min_confidence=90")
            assert response.status_code == 200
            content = response.text
            assert "95.00" in content
            assert "40.00" not in content
            print("   ✅ Matches filtered correctly")
            
        finally:
            # Cleanup
            print("   Cleaning up test data...")
            await session.delete(match_high)
            await session.delete(match_low)
            await session.delete(price_x)
            await session.delete(price_y)
            await session.delete(item_a)
            await session.delete(item_b)
            await session.delete(project)
            await session.commit()

if __name__ == "__main__":
    asyncio.run(verify_export_filters())
