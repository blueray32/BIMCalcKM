#!/bin/bash
# Phase 10 Deployment Script
# Run this on the staging server (157.230.149.106) after syncing code

set -e  # Exit on error

echo "=== Phase 10: Document Analysis Deployment ==="
echo ""

# Navigate to application directory
cd /opt/bimcalc

echo "1. Pulling latest code..."
# If using git on server, uncomment:
# git pull origin main

echo "2. Installing dependencies..."
source .venv/bin/activate
pip install -q pdfplumber

echo "3. Running database migrations..."
.venv/bin/alembic upgrade head

echo "4. Restarting application..."
systemctl restart bimcalc

echo "5. Checking service status..."
sleep 2
systemctl status bimcalc --no-pager

echo ""
echo "=== Deployment Complete ==="
echo "Access: https://bimcalc-staging.157.230.149.106.nip.io/"
echo ""
echo "Next steps:"
echo "  - Test document upload at Executive Dashboard -> Documents tab"
echo "  - Verify extraction results in modal"
echo "  - Run UAT checklist Section 8"
