"""Verification script for Compliance API endpoints.

Tests:
1. Upload Spec (Mock text)
2. Get Rules
3. Run Check
4. Get Results
"""

import sys
from pathlib import Path
from fastapi.testclient import TestClient

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent))

# Disable auth for testing
import os

os.environ["BIMCALC_AUTH_DISABLED"] = "true"

from bimcalc.web.app_enhanced import app

client = TestClient(app)


def verify_api():
    print("🧪 Verifying Compliance API...")

    org_id = "test-org-api"
    project_id = "test-proj-api"

    # 1. Upload Spec
    print("   Testing Upload...")
    spec_content = "All fire doors must have a fire rating of at least 30 minutes."
    files = {"file": ("spec.txt", spec_content, "text/plain")}
    data = {"org_id": org_id, "project_id": project_id}

    response = client.post("/api/compliance/upload", files=files, data=data)
    if response.status_code != 200:
        print(f"❌ Upload failed: {response.text}")
        return

    rule_count = response.json().get("rule_count")
    print(f"   Upload success. Extracted {rule_count} rules.")

    # 2. Get Rules
    print("   Testing Get Rules...")
    response = client.get(f"/api/compliance/rules?org={org_id}&project={project_id}")
    rules = response.json().get("rules")
    if not rules or len(rules) == 0:
        print("❌ No rules returned.")
        return
    print(f"   Got {len(rules)} rules.")

    # 3. Run Check
    print("   Testing Run Check...")
    # Note: This might not find items if we haven't created them for this project ID in the DB.
    # But checking that the endpoint runs without error is the main goal here.
    response = client.post(f"/api/compliance/check?org={org_id}&project={project_id}")
    if response.status_code != 200:
        print(f"❌ Check failed: {response.text}")
        return
    stats = response.json().get("stats")
    print(f"   Check success. Stats: {stats}")

    # 4. Get Results
    print("   Testing Get Results...")
    response = client.get(f"/api/compliance/results?org={org_id}&project={project_id}")
    results = response.json().get("results")
    print(f"   Got {len(results)} results.")

    print("✅ API Verification Complete!")


if __name__ == "__main__":
    verify_api()
