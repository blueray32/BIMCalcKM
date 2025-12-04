import asyncio
import httpx
from uuid import uuid4

BASE_URL = "http://localhost:8003"


async def verify_deletion():
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=10.0) as client:
        # 1. Create a project to delete
        project_id = f"proj-{uuid4().hex[:6]}"
        payload = {
            "org_id": "test-org-del",
            "project_id": project_id,
            "display_name": "To Be Deleted",
            "region": "EU",
        }

        print(f"Creating project {project_id}...")
        resp = await client.post("/api/projects", json=payload)
        assert resp.status_code == 200

        # Get the UUID from the list (since create returns org/proj IDs but delete needs UUID)
        resp = await client.get("/api/projects/all")
        projects = resp.json()["projects"]
        project = next((p for p in projects if p["project_id"] == project_id), None)
        assert project is not None
        uuid = project["id"]

        print(f"Deleting project UUID: {uuid}")

        # 2. Delete the project
        resp = await client.delete(f"/api/projects/{uuid}")

        if resp.status_code != 200:
            print(f"Failed to delete: {resp.status_code} - {resp.text}")
            return

        assert resp.status_code == 200
        print("Project deleted successfully.")

        # 3. Verify it's gone
        resp = await client.get("/api/projects/all")
        projects = resp.json()["projects"]
        project = next((p for p in projects if p["project_id"] == project_id), None)
        assert project is None, "Project still exists in list"

        print("✅ Project deletion verification passed!")


if __name__ == "__main__":
    asyncio.run(verify_deletion())
