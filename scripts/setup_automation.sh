#!/bin/bash
# BIMCalc Automation Setup
# Sets up automated pipeline runs and backups

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

echo "========================================="
echo "BIMCalc Automation Setup"
echo "========================================="
echo ""

# Check if Docker containers are running
echo "🔍 Checking Docker containers..."
if ! docker ps | grep -q "bimcalckm-app-1"; then
    echo "⚠️  Warning: bimcalckm-app-1 container is not running"
    echo "   Start it with: docker start bimcalckm-app-1"
fi

if ! docker ps | grep -q "bimcalc-postgres"; then
    echo "⚠️  Warning: bimcalc-postgres container is not running"
    echo "   Start it with: docker start bimcalc-postgres"
fi

echo ""
echo "📅 This will schedule:"
echo "   1. Pipeline sync - Daily at 2:00 AM"
echo "   2. Database backup - Daily at 2:30 AM"
echo ""
echo "Logs will be stored in: $PROJECT_DIR/logs/"
echo ""

read -p "Continue with automation setup? (yes/no): " CONFIRM

if [ "$CONFIRM" != "yes" ]; then
    echo "❌ Setup cancelled"
    exit 0
fi

# Create logs directory
mkdir -p "$PROJECT_DIR/logs"

echo ""
echo "🔧 Installing cron jobs..."

# Get existing crontab (excluding any old BIMCalc jobs)
TEMP_CRON=$(mktemp)
crontab -l 2>/dev/null | grep -v "bimcalc\|BIMCalc" > "$TEMP_CRON" || true

# Add new cron jobs
cat >> "$TEMP_CRON" <<EOF

# BIMCalc Automated Tasks
# Added on $(date +%Y-%m-%d)

# Pipeline sync - Daily at 2:00 AM
0 2 * * * cd $PROJECT_DIR && docker exec bimcalckm-app-1 python -m bimcalc.cli sync-prices >> $PROJECT_DIR/logs/pipeline.log 2>&1

# Database backup - Daily at 2:30 AM
30 2 * * * cd $PROJECT_DIR && $SCRIPT_DIR/backup_postgres.sh >> $PROJECT_DIR/logs/backup.log 2>&1

EOF

# Install new crontab
crontab "$TEMP_CRON"
rm "$TEMP_CRON"

echo "✅ Cron jobs installed successfully!"
echo ""

echo "📋 Installed schedule:"
echo ""
crontab -l | grep -A 5 "BIMCalc Automated Tasks"
echo ""

echo "========================================="
echo "✅ Automation Setup Complete"
echo "========================================="
echo ""
echo "Next runs:"
echo "   Pipeline: Daily at 2:00 AM"
echo "   Backup:   Daily at 2:30 AM"
echo ""
echo "Monitor logs:"
echo "   tail -f $PROJECT_DIR/logs/pipeline.log"
echo "   tail -f $PROJECT_DIR/logs/backup.log"
echo ""
echo "View scheduled jobs:"
echo "   crontab -l"
echo ""
echo "Remove automation (if needed):"
echo "   crontab -e  # Then delete BIMCalc lines"
echo ""
echo "Test manually:"
echo "   docker exec bimcalckm-app-1 python -m bimcalc.cli sync-prices"
echo "   $SCRIPT_DIR/backup_postgres.sh"
echo ""
