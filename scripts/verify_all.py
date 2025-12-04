#!/usr/bin/env python3
"""
Master Verification Script for BIMCalc Web Refactoring.
Runs all key verification scripts and reports overall status.
"""

import subprocess
import sys
import time
from pathlib import Path

# Define the scripts to run
SCRIPTS = [
    "scripts/verify_app_startup.py",
    "scripts/verify_multi_region.py",
    "scripts/test_project_api.py",
    "scripts/verify_revisions_api.py",
    "scripts/verify_compliance_api.py",
]


def run_script(script_path):
    """Run a single script and return success status."""
    print(f"\n{'=' * 60}")
    print(f"Running: {script_path}")
    print(f"{'=' * 60}\n")

    start_time = time.time()
    try:
        # Run with auth disabled for testing
        result = subprocess.run(
            [sys.executable, script_path],
            env={"BIMCALC_AUTH_DISABLED": "true", "PYTHONPATH": "."},
            capture_output=True,
            text=True,
        )

        duration = time.time() - start_time

        # Print output
        print(result.stdout)
        if result.stderr:
            print("STDERR:", result.stderr)

        if result.returncode == 0:
            print(f"\n✅ PASS ({duration:.2f}s)")
            return True
        else:
            print(f"\n❌ FAIL (Exit Code: {result.returncode})")
            return False

    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        return False


def main():
    """Run all scripts and summarize."""
    print("🚀 Starting BIMCalc Web Refactoring Verification Suite")
    print(f"Found {len(SCRIPTS)} verification scripts to run.")

    results = {}

    for script in SCRIPTS:
        if not Path(script).exists():
            print(f"⚠️  Script not found: {script}")
            results[script] = "MISSING"
            continue

        success = run_script(script)
        results[script] = "PASS" if success else "FAIL"

    # Summary
    print(f"\n{'=' * 60}")
    print("VERIFICATION SUMMARY")
    print(f"{'=' * 60}")

    all_passed = True
    for script, status in results.items():
        icon = "✅" if status == "PASS" else "❌"
        print(f"{icon} {script}: {status}")
        if status != "PASS":
            all_passed = False

    print(f"{'=' * 60}")

    if all_passed:
        print("\n🎉 ALL CHECKS PASSED! The refactoring is verified.")
        sys.exit(0)
    else:
        print("\n⚠️  SOME CHECKS FAILED. Please review the logs.")
        sys.exit(1)


if __name__ == "__main__":
    main()
