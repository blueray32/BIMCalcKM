"""Verification script for Rule Configuration CRUD API."""
import asyncio
from uuid import uuid4
from fastapi.testclient import TestClient

from bimcalc.web.app_enhanced import app
from bimcalc.db.connection import get_session
from bimcalc.db.models import ProjectModel
from bimcalc.db.models_intelligence import ComplianceRuleModel

async def verify_rule_crud():
    print("🧪 Verifying Rule Configuration CRUD API...")
    
    async with get_session() as session:
        # 1. Create test project
        org_id = "test-org-rules"
        project_id = uuid4()
        project_str = str(project_id)
        
        print(f"   Creating test project: {project_str}")
        
        project = ProjectModel(
            id=project_id,
            org_id=org_id,
            project_id=f"proj-{project_str[:8]}",
            display_name="Rule Test Project",
            status="active"
        )
        session.add(project)
        await session.commit()
        
        try:
            client = TestClient(app)
            
            # 2. Get Rules (Should seed defaults)
            print("   GET /rules (Seeding defaults)...")
            # First call to compliance endpoint triggers seeding
            client.get(f"/api/projects/{project_str}/intelligence/compliance")
            
            response = client.get(f"/api/projects/{project_str}/intelligence/rules")
            assert response.status_code == 200
            data = response.json()
            rules = data["rules"]
            print(f"   Found {len(rules)} rules")
            assert len(rules) >= 2 # Classification + Vendor
            
            # 3. Create Rule
            print("   POST /rules (Create new)...")
            new_rule_payload = {
                "name": "Test Rule",
                "description": "A test rule",
                "rule_type": "custom",
                "severity": "low",
                "is_active": True,
                "configuration": {"foo": "bar"}
            }
            response = client.post(f"/api/projects/{project_str}/intelligence/rules", json=new_rule_payload)
            assert response.status_code == 200
            new_rule_id = response.json()["id"]
            print(f"   Created rule: {new_rule_id}")
            
            # 4. Update Rule
            print("   PUT /rules/{id} (Update)...")
            update_payload = {
                "is_active": False,
                "configuration": {"foo": "baz", "vendors": ["A", "B"]}
            }
            response = client.put(f"/api/projects/{project_str}/intelligence/rules/{new_rule_id}", json=update_payload)
            assert response.status_code == 200
            
            # Verify Update
            response = client.get(f"/api/projects/{project_str}/intelligence/rules")
            rules = response.json()["rules"]
            updated_rule = next(r for r in rules if r["id"] == new_rule_id)
            assert updated_rule["is_active"] == False
            assert updated_rule["configuration"]["vendors"] == ["A", "B"]
            print("   ✅ Rule updated successfully")
            
            # 5. Delete Rule
            print("   DELETE /rules/{id} (Delete)...")
            response = client.delete(f"/api/projects/{project_str}/intelligence/rules/{new_rule_id}")
            assert response.status_code == 200
            
            # Verify Delete
            response = client.get(f"/api/projects/{project_str}/intelligence/rules")
            rules = response.json()["rules"]
            assert not any(r["id"] == new_rule_id for r in rules)
            print("   ✅ Rule deleted successfully")
            
        except Exception as e:
            print(f"   ❌ Verification failed: {e}")
            raise
            
        finally:
            # Cleanup
            print("   Cleaning up test data...")
            from sqlalchemy import text
            # Delete all rules for this org
            await session.execute(
                text("DELETE FROM compliance_rules WHERE org_id = :org_id"), 
                {"org_id": org_id}
            )
            await session.delete(project)
            await session.commit()

if __name__ == "__main__":
    asyncio.run(verify_rule_crud())
