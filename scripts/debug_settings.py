import asyncio
import httpx
from uuid import uuid4

BASE_URL = "http://localhost:8003"


async def debug_settings():
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=10.0) as client:
        # 1. Create Project
        project_id = f"proj-{uuid4().hex[:6]}"
        payload = {
            "org_id": "test-settings",
            "project_id": project_id,
            "display_name": "Settings Debug",
            "region": "EU",
        }
        print(f"Creating project {project_id}...")
        resp = await client.post("/api/projects", json=payload)
        assert resp.status_code == 200

        # Get UUID
        resp = await client.get("/api/projects/all")
        projects = resp.json()["projects"]
        project = next(p for p in projects if p["project_id"] == project_id)
        uuid = project["id"]

        # 2. Get Settings
        print(f"Fetching settings for {uuid}...")
        resp = await client.get(f"/api/projects/{uuid}/settings")
        print(f"Status: {resp.status_code}")
        print(f"Body: {resp.text}")

        settings = resp.json()
        if settings is None:
            print("⚠️  Settings is NULL!")
        else:
            print(f"Settings type: {type(settings)}")
            print(f"Settings content: {settings}")


if __name__ == "__main__":
    asyncio.run(debug_settings())
