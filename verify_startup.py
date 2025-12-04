import sys
import os

# Add current directory to path
sys.path.append(os.getcwd())

try:
    print("Attempting to import bimcalc.web.app_enhanced...")
    from bimcalc.web.app_enhanced import app
    print("Successfully imported app_enhanced!")
    
    print("Attempting to import bimcalc.worker...")
    from bimcalc.worker import WorkerSettings
    print("Successfully imported worker settings!")
    
except Exception as e:
    print(f"Startup verification failed: {e}")
    sys.exit(1)
