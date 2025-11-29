#!/bin/bash
# Phase 10 Docker Deployment Script
# Run this on the staging server (157.230.149.106) after syncing code

set -e  # Exit on error

echo "=== Phase 10: Document Analysis Deployment (Docker) ==="
echo ""

# Navigate to application directory
cd /opt/bimcalc

echo "1. Installing pdfplumber in Docker container..."
docker exec bimcalc-app pip install -q pdfplumber

echo "2. Running database migrations..."
docker exec bimcalc-app alembic upgrade head

echo "3. Restarting application containers..."
docker-compose restart app worker

echo "4. Checking container status..."
sleep 3
docker ps | grep bimcalc-app

echo ""
echo "=== Deployment Complete ==="
echo "Access: https://bimcalc-staging.157.230.149.106.nip.io/"
echo ""
echo "Next steps:"
echo "  - Test document upload at Executive Dashboard -> Documents tab"
echo "  - Verify extraction results in modal"
echo "  - Run UAT checklist Section 8"
