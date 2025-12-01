"""Verification script for Staging Compliance API.

Tests the deployed instance at 157.230.149.106.
"""

import requests
import urllib3

# Suppress insecure request warnings for self-signed certs
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

BASE_URL = "https://157.230.149.106"
ORG_ID = "staging-test-org"
PROJECT_ID = "staging-test-proj"

def verify_staging():
    print(f"🧪 Verifying Staging Compliance API at {BASE_URL}...")
    
    # 1. Check Dashboard Page Load
    print("   1. Checking Dashboard HTML...")
    try:
        resp = requests.get(f"{BASE_URL}/compliance", verify=False, timeout=10)
        if resp.status_code == 200 and "Compliance Checker" in resp.text:
            print("   ✅ Dashboard loaded successfully.")
        else:
            print(f"   ❌ Dashboard load failed: {resp.status_code}")
            return
    except Exception as e:
        print(f"   ❌ Connection failed: {e}")
        return

    # 2. Upload Spec
    print("   2. Testing Spec Upload...")
    spec_content = "All fire doors must have a fire rating of at least 30 minutes."
    files = {'file': ('staging_spec.txt', spec_content, 'text/plain')}
    data = {'org_id': ORG_ID, 'project_id': PROJECT_ID}
    
    try:
        resp = requests.post(
            f"{BASE_URL}/api/compliance/upload", 
            files=files, 
            data=data, 
            verify=False,
            timeout=10
        )
        if resp.status_code == 200:
            data = resp.json()
            print(f"   ✅ Upload success. Rules extracted: {data.get('rule_count')}")
        else:
            print(f"   ❌ Upload failed: {resp.status_code} - {resp.text}")
            return
    except Exception as e:
        print(f"   ❌ Upload error: {e}")
        return

    # 3. Get Rules
    print("   3. Fetching Rules...")
    try:
        resp = requests.get(
            f"{BASE_URL}/api/compliance/rules", 
            params={'org': ORG_ID, 'project': PROJECT_ID}, 
            verify=False,
            timeout=10
        )
        if resp.status_code == 200:
            rules = resp.json().get('rules', [])
            print(f"   ✅ Retrieved {len(rules)} rules.")
        else:
            print(f"   ❌ Get Rules failed: {resp.status_code}")
    except Exception as e:
        print(f"   ❌ Get Rules error: {e}")

    # 4. Run Check (Even if no items, should return stats)
    print("   4. Running Compliance Check...")
    try:
        resp = requests.post(
            f"{BASE_URL}/api/compliance/check", 
            params={'org': ORG_ID, 'project': PROJECT_ID}, 
            verify=False,
            timeout=10
        )
        if resp.status_code == 200:
            stats = resp.json().get('stats')
            print(f"   ✅ Check run successfully. Stats: {stats}")
        else:
            print(f"   ❌ Check run failed: {resp.status_code} - {resp.text}")
    except Exception as e:
        print(f"   ❌ Check run error: {e}")

    print("✅ Staging Verification Complete!")

if __name__ == "__main__":
    verify_staging()
