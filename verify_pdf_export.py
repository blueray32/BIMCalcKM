"""Verification script for PDF export functionality."""
import asyncio
from uuid import uuid4
from decimal import Decimal
from datetime import datetime

from bimcalc.reporting.pdf_export import generate_project_pdf_report
from bimcalc.db.connection import get_session
from bimcalc.db.models import ProjectModel, ItemModel, PriceItemModel, MatchResultModel

async def verify_pdf_export():
    print("🧪 Verifying PDF Export...")
    
    async with get_session() as session:
        # 1. Create test data
        org_id = "test-org-pdf"
        project_id = f"proj-{uuid4().hex[:8]}"
        
        print(f"   Creating test project: {project_id}")
        
        project = ProjectModel(
            id=uuid4(),
            org_id=org_id,
            project_id=project_id,
            display_name="PDF Export Test Project",
            status="active"
        )
        session.add(project)
        
        # Add price item
        price_item = PriceItemModel(
            id=uuid4(),
            org_id=org_id,
            item_code="TEST-PDF-001",
            description="Test PDF Item",
            unit_price=Decimal("150.00"),
            currency="EUR",
            source_name="Test Source",
            unit="ea",
            classification_code="123",
            sku="SKU-PDF",
            source_currency="EUR",
            region="EU"
        )
        session.add(price_item)
        
        # Add item
        item = ItemModel(
            id=uuid4(),
            org_id=org_id,
            project_id=project_id,
            category="Mechanical",
            family="Test Family",
            type_name="Test Type",
            quantity=Decimal("10.0")
        )
        session.add(item)
        
        # Add match result
        match = MatchResultModel(
            id=uuid4(),
            item_id=item.id,
            price_item_id=price_item.id,
            confidence_score=98.0,
            decision="auto-accepted",
            source="fuzzy_match",
            reason="High confidence match",
            created_by="system"
        )
        session.add(match)
        
        await session.commit()
        
        try:
            # 2. Generate PDF
            print("   Generating PDF report...")
            pdf_buffer = await generate_project_pdf_report(session, org_id, project_id)
            
            # 3. Verify PDF content (basic check)
            pdf_content = pdf_buffer.getvalue()
            
            if len(pdf_content) > 0 and pdf_content.startswith(b"%PDF"):
                print("   ✅ PDF generated successfully (valid header)")
                
                # Save for manual inspection
                filename = "verify_report.pdf"
                with open(filename, "wb") as f:
                    f.write(pdf_content)
                print(f"   💾 Saved test file to: {filename}")
                
            else:
                print("   ❌ PDF generation failed or invalid format")
                
        except Exception as e:
            print(f"   ❌ Error during PDF generation: {str(e)}")
            import traceback
            traceback.print_exc()
            
        finally:
            # Cleanup
            print("   Cleaning up test data...")
            await session.delete(match)
            await session.delete(item)
            await session.delete(price_item)
            await session.delete(project)
            await session.commit()

if __name__ == "__main__":
    asyncio.run(verify_pdf_export())
