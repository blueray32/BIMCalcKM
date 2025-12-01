"""Verification script for Phase 5: AI Compliance Checker.

Tests:
1. Creating a Compliance Rule.
2. Running Compliance Check on sample items.
3. Verifying Pass/Fail results.
"""

import asyncio
import sys
from pathlib import Path

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent))

from sqlalchemy import select, delete
from bimcalc.db.connection import get_session
from bimcalc.db.models import ItemModel
from bimcalc.db.models_intelligence import ComplianceRuleModel, ComplianceResultModel
from bimcalc.intelligence.compliance import run_compliance_check, extract_rules_from_text

async def verify_compliance():
    print("🧪 Verifying AI Compliance Checker...")
    
    async with get_session() as session:
        org_id = "test-org"
        project_id = "test-proj-compliance"
        
        # 1. Setup Data
        print("   Cleaning up old test data...")
        await session.execute(delete(ComplianceResultModel))
        await session.execute(delete(ComplianceRuleModel).where(ComplianceRuleModel.project_id == project_id))
        await session.execute(delete(ItemModel).where(ItemModel.project_id == project_id))
        
        # Create Sample Items
        print("   Creating sample items...")
        item_pass = ItemModel(
            org_id=org_id, project_id=project_id,
            family="Fire Door", type_name="FD60",
            category="Doors",
            attributes={"fire_rating": 60}
        )
        item_fail = ItemModel(
            org_id=org_id, project_id=project_id,
            family="Fire Door", type_name="FD20",
            category="Doors",
            attributes={"fire_rating": 20}
        )
        item_ignore = ItemModel(
            org_id=org_id, project_id=project_id,
            family="Window", type_name="Standard",
            category="Windows",
            attributes={"fire_rating": 0}
        )
        session.add_all([item_pass, item_fail, item_ignore])
        await session.commit()
        
        # 2. Extract Rules (Mock)
        print("   Extracting rules from text...")
        spec_text = "All fire doors must have a fire rating of at least 30 minutes."
        extracted_rules = await extract_rules_from_text(spec_text)
        
        if not extracted_rules:
            print("❌ Failed to extract rules")
            return
            
        print(f"   Extracted {len(extracted_rules)} rules.")
        
        # Save Rule
        rule_def = extracted_rules[0]
        rule = ComplianceRuleModel(
            org_id=org_id,
            project_id=project_id,
            name=rule_def["name"],
            description=rule_def["description"],
            rule_logic=rule_def["rule_logic"]
        )
        session.add(rule)
        await session.commit()
        
        # 3. Run Check
        print("   Running compliance check...")
        stats = await run_compliance_check(session, org_id, project_id)
        print(f"   Results: {stats}")
        
        # 4. Verify Results
        results = (await session.execute(select(ComplianceResultModel))).scalars().all()
        
        pass_count = sum(1 for r in results if r.status == 'pass')
        fail_count = sum(1 for r in results if r.status == 'fail')
        
        # We expect:
        # item_pass -> Pass (60 >= 30)
        # item_fail -> Fail (20 < 30)
        # item_ignore -> Pass (Not applicable, returns pass with message) OR Warning?
        # Logic says: if not applicable, returns "pass" with message "Rule not applicable..."
        
        if pass_count >= 2 and fail_count == 1:
            print("✅ Compliance Logic Verified!")
        else:
            print(f"❌ Verification Failed. Expected 2 Pass, 1 Fail. Got {pass_count} Pass, {fail_count} Fail.")
            for r in results:
                print(f"   - Item {r.item_id}: {r.status} ({r.message})")

if __name__ == "__main__":
    asyncio.run(verify_compliance())
