import asyncio
import httpx
from uuid import uuid4

BASE_URL = "http://localhost:8003"

async def verify_lifecycle():
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=10.0) as client:
        # 1. Create
        project_id = f"proj-{uuid4().hex[:6]}"
        payload = {
            "org_id": "test-lifecycle",
            "project_id": project_id,
            "display_name": "Lifecycle Test",
            "region": "EU"
        }
        
        print(f"1. Creating project {project_id}...")
        resp = await client.post("/api/projects", json=payload)
        assert resp.status_code == 200, f"Create failed: {resp.text}"
        
        # Get UUID
        resp = await client.get("/api/projects/all")
        projects = resp.json()["projects"]
        project = next((p for p in projects if p["project_id"] == project_id), None)
        assert project is not None
        uuid = project["id"]
        
        # 2. Get (New Endpoint)
        print(f"2. Testing GET /api/projects/{uuid}...")
        resp = await client.get(f"/api/projects/{uuid}")
        assert resp.status_code == 200, f"Get failed: {resp.status_code}"
        data = resp.json()
        assert data["project_id"] == project_id
        print("   GET endpoint working.")
        
        # 3. Delete
        print(f"3. Deleting project {uuid}...")
        resp = await client.delete(f"/api/projects/{uuid}")
        assert resp.status_code == 200, f"Delete failed: {resp.status_code}"
        
        # 4. Verify Deletion
        print("4. Verifying deletion...")
        resp = await client.get(f"/api/projects/{uuid}")
        assert resp.status_code == 404, f"Project still exists (got {resp.status_code})"
        
        print("\n✅ Project lifecycle verification passed!")

if __name__ == "__main__":
    asyncio.run(verify_lifecycle())
