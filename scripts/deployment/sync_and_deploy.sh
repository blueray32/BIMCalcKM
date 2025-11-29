#!/bin/bash
# Local script to sync code to staging server and deploy Phase 10

set -e

echo "=== Syncing Code to Staging Server ==="
echo ""

# Sync code (excluding unnecessary files)
echo "1. Syncing code via rsync..."
rsync -avz \
  --exclude '.venv' \
  --exclude '__pycache__' \
  --exclude '*.pyc' \
  --exclude '.git' \
  --exclude 'node_modules' \
  --exclude 'bimcalc.db' \
  --exclude '*.log' \
  ./ root@157.230.149.106:/opt/bimcalc/

echo ""
echo "2. Code sync complete!"
echo ""
echo "3. Now run deployment on server:"
echo "   ssh root@157.230.149.106"
echo "   cd /opt/bimcalc"
echo "   bash deploy_phase10.sh"
echo ""
echo "Or run directly:"
echo "   ssh root@157.230.149.106 'cd /opt/bimcalc && bash deploy_phase10.sh'"
