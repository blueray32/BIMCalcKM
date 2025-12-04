import sys
import os

# Add current directory to path
sys.path.append(os.getcwd())

try:
    print("Attempting to import bimcalc.web.app_enhanced...")
    print("Successfully imported app_enhanced!")

    print("Attempting to import bimcalc.worker...")
    print("Successfully imported worker settings!")

except Exception as e:
    print(f"Startup verification failed: {e}")
    sys.exit(1)
