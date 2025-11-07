#!/bin/bash
# BIMCalc Quick Start Example
# Demonstrates end-to-end workflow: ingest → match → report

set -e  # Exit on error

echo "===================================="
echo "BIMCalc Quick Start Example"
echo "===================================="
echo ""

# Step 1: Initialize database
echo "Step 1: Initialize database..."
python -m bimcalc.cli init --drop
echo "✓ Database initialized"
echo ""

# Step 2: Ingest vendor price books
echo "Step 2: Ingest vendor price books..."
python -m bimcalc.cli ingest-prices examples/pricebooks/sample_pricebook.csv --vendor "acme"
echo "✓ Price books ingested"
echo ""

# Step 3: Ingest Revit schedules
echo "Step 3: Ingest Revit schedules..."
python -m bimcalc.cli ingest-schedules examples/schedules/project_a.csv --org "default" --project "project-a"
echo "✓ Schedules ingested"
echo ""

# Step 4: Show project statistics
echo "Step 4: Show project statistics..."
python -m bimcalc.cli stats --org "default" --project "project-a"
echo ""

# Step 5: Run matching pipeline
echo "Step 5: Run matching pipeline..."
python -m bimcalc.cli match --org "default" --project "project-a" --by "demo-user"
echo "✓ Matching completed"
echo ""

# Step 6: Generate cost report
echo "Step 6: Generate cost report..."
python -m bimcalc.cli report --org "default" --project "project-a" --out "examples/reports/project_a_report.csv"
echo "✓ Report generated"
echo ""

# Step 7: Second project (demonstrate learning curve)
echo "===================================="
echo "Demonstrating Learning Curve"
echo "===================================="
echo ""

echo "Step 7: Ingest second project with similar items..."
python -m bimcalc.cli ingest-schedules examples/schedules/project_b.csv --org "default" --project "project-b"
echo "✓ Project B ingested"
echo ""

echo "Step 8: Run matching on Project B (should have instant matches)..."
python -m bimcalc.cli match --org "default" --project "project-b" --by "demo-user"
echo "✓ Notice the 'instant' matches for items seen in Project A!"
echo ""

echo "Step 9: Generate temporal report (as-of example)..."
AS_OF=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
python -m bimcalc.cli report --org "default" --project "project-b" --as-of "$AS_OF" --out "examples/reports/project_b_report.csv"
echo "✓ As-of report generated (timestamp: $AS_OF)"
echo ""

echo "===================================="
echo "Quick Start Complete!"
echo "===================================="
echo ""
echo "Next steps:"
echo "  1. Review reports in examples/reports/"
echo "  2. Try running integration tests: pytest tests/integration/ -v -m integration"
echo "  3. Experiment with different as-of timestamps for reproducible reports"
echo ""
