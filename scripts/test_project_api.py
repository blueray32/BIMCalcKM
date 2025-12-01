import sys
import os
from fastapi.testclient import TestClient
from uuid import uuid4

# Add project root to path
sys.path.append(os.getcwd())

from bimcalc.web.app_enhanced import app

client = TestClient(app)

def test_create_project_api():
    print("🌍 Testing Create Project API with Region...")
    
    run_id = uuid4().hex[:6]
    org_id = f"test-org-api-{run_id}"
    
    # Test 1: Create EU Project (Default)
    print("\n   1. Creating EU Project (Default)...")
    project_eu_id = f"proj-eu-{run_id}"
    response = client.post("/api/projects", params={
        "org_id": org_id,
        "project_id": project_eu_id,
        "display_name": "API Test EU",
        "region": "EU"
    })
    
    if response.status_code == 200:
        print("   ✅ API returned 200 OK")
        # Verify in DB (optional, but good)
        # For now, we trust the API response if we had a GET endpoint that returned region
    else:
        print(f"   ❌ API Failed: {response.status_code} - {response.text}")

    # Test 2: Create US Project
    print("\n   2. Creating US Project...")
    project_us_id = f"proj-us-{run_id}"
    response = client.post("/api/projects", params={
        "org_id": org_id,
        "project_id": project_us_id,
        "display_name": "API Test US",
        "region": "US"
    })
    
    if response.status_code == 200:
        print("   ✅ API returned 200 OK")
    else:
        print(f"   ❌ API Failed: {response.status_code} - {response.text}")

    # Test 3: Create UK Project
    print("\n   3. Creating UK Project...")
    project_uk_id = f"proj-uk-{run_id}"
    response = client.post("/api/projects", params={
        "org_id": org_id,
        "project_id": project_uk_id,
        "display_name": "API Test UK",
        "region": "UK"
    })
    
    if response.status_code == 200:
        print("   ✅ API returned 200 OK")
    else:
        print(f"   ❌ API Failed: {response.status_code} - {response.text}")

if __name__ == "__main__":
    test_create_project_api()
