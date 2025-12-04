import urllib.request
import urllib.error
import ssl
import sys

BASE_URL = "https://157.230.149.106.nip.io"

# Ignore SSL certificate errors (self-signed or staging)
ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE


def check_endpoint(path, expected_status=200):
    url = f"{BASE_URL}{path}"
    print(f"Checking {path}...")
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, context=ctx, timeout=10) as response:
            status = response.getcode()
            print(f"  Status: {status}")
            if status == expected_status or (
                expected_status == 200 and status in [200, 307]
            ):
                print("  ✅ PASS")
                return True
            else:
                print(f"  ❌ FAIL (Expected {expected_status})")
                return False
    except urllib.error.HTTPError as e:
        print(f"  Status: {e.code}")
        if e.code == expected_status:
            print("  ✅ PASS")
            return True
        else:
            print(f"  ❌ FAIL (Expected {expected_status}, got {e.code})")
            return False
    except Exception as e:
        print(f"  ❌ ERROR: {e}")
        return False


print(f"🚀 Starting Smoke Test for {BASE_URL}\n")

success = True
success &= check_endpoint("/")
success &= check_endpoint("/docs")  # FastAPI docs
success &= check_endpoint("/login")  # Login page might return 200

if success:
    print("\n✅ Smoke Test Passed! The server is up and responding.")
    sys.exit(0)
else:
    print("\n⚠️ Smoke Test Failed. Some endpoints are not responding as expected.")
    sys.exit(1)
