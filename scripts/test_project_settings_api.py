import asyncio
import httpx
from uuid import uuid4

BASE_URL = "http://localhost:8001"

async def test_project_settings():
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=10.0) as client:
        # 1. Create Project
        org_id = "test-org"
        project_id = f"test-proj-{uuid4().hex[:8]}"
        print(f"Creating project {project_id}...")
        
        resp = await client.post(f"/api/projects?org_id={org_id}&project_id={project_id}&display_name=Test Project")
        assert resp.status_code == 200, f"Create failed: {resp.text}"
        
        # Get the UUID from the list (since create doesn't return UUID)
        resp = await client.get("/api/projects/all")
        projects = resp.json()["projects"]
        project = next(p for p in projects if p["project_id"] == project_id)
        p_uuid = project["id"]
        print(f"Project UUID: {p_uuid}")
        
        # 2. Get Settings (Default)
        print(f"Fetching settings for {p_uuid}...")
        resp = await client.get(f"/api/projects/{p_uuid}/settings")
        if resp.status_code != 200:
            print(f"Failed to get settings: {resp.status_code} - {resp.text}")
        assert resp.status_code == 200
        settings = resp.json()
        print(f"Initial settings: {settings}")
        
        # 3. Update Settings
        print("Updating settings...")
        new_settings = {
            "blended_labor_rate": 75.50,
            "default_markup_percentage": 20.0,
            "currency": "USD"
        }
        resp = await client.patch(f"/api/projects/{p_uuid}/settings", json=new_settings)
        assert resp.status_code == 200
        updated = resp.json()["settings"]
        assert updated["blended_labor_rate"] == 75.50
        assert updated["currency"] == "USD"
        print("Settings updated successfully.")
        
        # 4. Labor Rate Overrides
        print("Adding labor rate override...")
        override_data = {"category": "Electrical", "rate": 120.00}
        resp = await client.post(f"/api/projects/{p_uuid}/labor-rates", json=override_data)
        assert resp.status_code == 200
        
        print("Verifying override...")
        resp = await client.get(f"/api/projects/{p_uuid}/labor-rates")
        overrides = resp.json()["overrides"]
        assert len(overrides) == 1
        assert overrides[0]["category"] == "Electrical"
        assert overrides[0]["rate"] == 120.00
        override_id = overrides[0]["id"]
        print("Override verified.")
        
        # 5. Delete Override
        print("Deleting override...")
        resp = await client.delete(f"/api/projects/{p_uuid}/labor-rates/{override_id}")
        assert resp.status_code == 200
        
        resp = await client.get(f"/api/projects/{p_uuid}/labor-rates")
        assert len(resp.json()["overrides"]) == 0
        print("Override deleted.")
        
        print("\n✅ All Project Settings API tests passed!")

if __name__ == "__main__":
    asyncio.run(test_project_settings())
