import asyncio
import httpx
from uuid import uuid4

BASE_URL = "http://localhost:8001"


async def verify_project_creation():
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=10.0) as client:
        # 1. Create Project with full details
        org_id = "test-org-create"
        project_id = f"proj-{uuid4().hex[:6]}"

        payload = {
            "org_id": org_id,
            "project_id": project_id,
            "display_name": "Full Detail Project",
            "region": "US",
            "description": "A project with description and dates",
            "start_date": "2025-01-01T00:00:00",
            "target_completion": "2025-12-31T00:00:00",
        }

        print(f"Creating project {project_id} with JSON payload...")
        resp = await client.post("/api/projects", json=payload)

        if resp.status_code != 200:
            print(f"Failed to create: {resp.status_code} - {resp.text}")
            return

        assert resp.status_code == 200
        print("Project created successfully.")

        # 2. Verify Data Persistence
        print("Verifying persistence...")
        resp = await client.get("/api/projects/all")
        projects = resp.json()["projects"]

        project = next((p for p in projects if p["project_id"] == project_id), None)
        assert project is not None, "Project not found in list"

        print(f"Found project: {project['display_name']}")
        assert project["description"] == "A project with description and dates"
        assert project["region"] == "US"
        # Note: Date format might vary slightly in response (ISO string)
        assert project["start_date"].startswith("2025-01-01")

        print("✅ Project creation verification passed!")


if __name__ == "__main__":
    asyncio.run(verify_project_creation())
