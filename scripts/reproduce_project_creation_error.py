import asyncio
import httpx
from uuid import uuid4

BASE_URL = "http://localhost:8001"


async def reproduce_error():
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=10.0) as client:
        project_id = f"proj-{uuid4().hex[:6]}"

        # Simulate form submission where empty dates are sent as empty strings
        payload = {
            "org_id": "test-org",
            "project_id": project_id,
            "display_name": "Test Project",
            "region": "EU",
            "description": "",
            "start_date": "",  # This is likely causing the issue
            "target_completion": "",  # This too
        }

        print(f"Sending payload with empty strings for dates: {payload}")
        resp = await client.post("/api/projects", json=payload)

        print(f"Response Status: {resp.status_code}")
        print(f"Response Body: {resp.text}")


if __name__ == "__main__":
    asyncio.run(reproduce_error())
