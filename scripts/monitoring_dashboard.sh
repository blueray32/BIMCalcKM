#!/bin/bash
# BIMCalc Monitoring Dashboard
# Real-time system status overview

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

# Colors for terminal output (optional)
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

clear

echo "========================================="
echo "   BIMCalc Monitoring Dashboard"
echo "========================================="
echo "   $(date '+%Y-%m-%d %H:%M:%S')"
echo "========================================="
echo ""

# 1. System Status
echo "🖥️  SYSTEM STATUS"
echo "─────────────────────────────────────────"

# Docker containers
if docker ps --format '{{.Names}}' | grep -q "^bimcalckm-app-1$"; then
    echo -e "${GREEN}✅${NC} Application:  Running"
else
    echo -e "${RED}❌${NC} Application:  Stopped"
fi

if docker ps --format '{{.Names}}' | grep -q "^bimcalc-postgres$"; then
    echo -e "${GREEN}✅${NC} Database:     Running"
else
    echo -e "${RED}❌${NC} Database:     Stopped"
fi

# Database connection
if docker exec bimcalc-postgres psql -U bimcalc -d bimcalc -c "SELECT 1;" > /dev/null 2>&1; then
    echo -e "${GREEN}✅${NC} DB Connection: OK"

    # Get DB size
    DB_SIZE=$(docker exec bimcalc-postgres psql -U bimcalc -d bimcalc -t -c "SELECT pg_size_pretty(pg_database_size('bimcalc'));" | xargs)
    echo "   Database Size: $DB_SIZE"
else
    echo -e "${RED}❌${NC} DB Connection: Failed"
fi

echo ""

# 2. Data Summary
echo "📊 DATA SUMMARY"
echo "─────────────────────────────────────────"

if docker exec bimcalc-postgres psql -U bimcalc -d bimcalc -c "SELECT 1;" > /dev/null 2>&1; then
    CURRENT_PRICES=$(docker exec bimcalc-postgres psql -U bimcalc -d bimcalc -t -c "SELECT COUNT(*) FROM price_items WHERE is_current = true;" | xargs)
    HISTORICAL_PRICES=$(docker exec bimcalc-postgres psql -U bimcalc -d bimcalc -t -c "SELECT COUNT(*) FROM price_items WHERE is_current = false;" | xargs)
    TOTAL_PRICES=$((CURRENT_PRICES + HISTORICAL_PRICES))

    echo "Current Prices:    $CURRENT_PRICES"
    echo "Historical Prices: $HISTORICAL_PRICES"
    echo "Total Records:     $TOTAL_PRICES"

    # Sources
    SOURCES=$(docker exec bimcalc-postgres psql -U bimcalc -d bimcalc -t -c "SELECT COUNT(DISTINCT source_name) FROM price_items;" | xargs)
    echo "Active Sources:    $SOURCES"
else
    echo "Database not accessible"
fi

echo ""

# 3. Pipeline Activity
echo "🔄 PIPELINE ACTIVITY"
echo "─────────────────────────────────────────"

if docker exec bimcalc-postgres psql -U bimcalc -d bimcalc -c "SELECT 1 FROM data_sync_log LIMIT 1;" > /dev/null 2>&1; then
    TOTAL_RUNS=$(docker exec bimcalc-postgres psql -U bimcalc -d bimcalc -t -c "SELECT COUNT(*) FROM data_sync_log;" | xargs)
    SUCCESSFUL=$(docker exec bimcalc-postgres psql -U bimcalc -d bimcalc -t -c "SELECT COUNT(*) FROM data_sync_log WHERE status = 'SUCCESS';" | xargs)
    FAILED=$(docker exec bimcalc-postgres psql -U bimcalc -d bimcalc -t -c "SELECT COUNT(*) FROM data_sync_log WHERE status = 'FAILED';" | xargs)

    echo "Total Runs:    $TOTAL_RUNS"
    echo -e "Successful:    ${GREEN}$SUCCESSFUL${NC}"
    if [ "$FAILED" -gt 0 ]; then
        echo -e "Failed:        ${RED}$FAILED${NC}"
    else
        echo -e "Failed:        ${GREEN}$FAILED${NC}"
    fi

    # Success rate
    if [ "$TOTAL_RUNS" -gt 0 ]; then
        SUCCESS_RATE=$((SUCCESSFUL * 100 / TOTAL_RUNS))
        echo "Success Rate:  ${SUCCESS_RATE}%"
    fi

    # Last run
    echo ""
    echo "Recent Runs:"
    docker exec bimcalc-postgres psql -U bimcalc -d bimcalc -c "
        SELECT
            TO_CHAR(run_timestamp, 'MM-DD HH24:MI') as time,
            RPAD(source_name, 18) as source,
            status,
            records_inserted as ins,
            records_updated as upd
        FROM data_sync_log
        ORDER BY run_timestamp DESC
        LIMIT 5;
    " | tail -n +3 | head -n -2
else
    echo "No pipeline runs recorded yet"
fi

echo ""

# 4. Backup Status
echo "💾 BACKUP STATUS"
echo "─────────────────────────────────────────"

if [ -d "$PROJECT_DIR/backups" ]; then
    BACKUP_COUNT=$(ls -1 "$PROJECT_DIR/backups"/*.sql.gz 2>/dev/null | wc -l | xargs)
    echo "Total Backups: $BACKUP_COUNT"

    if [ "$BACKUP_COUNT" -gt 0 ]; then
        LATEST_BACKUP=$(ls -t "$PROJECT_DIR/backups"/*.sql.gz 2>/dev/null | head -1)
        BACKUP_NAME=$(basename "$LATEST_BACKUP")
        BACKUP_SIZE=$(du -h "$LATEST_BACKUP" | awk '{print $1}')
        BACKUP_DATE=$(stat -f "%Sm" -t "%Y-%m-%d %H:%M" "$LATEST_BACKUP" 2>/dev/null || stat -c "%y" "$LATEST_BACKUP" 2>/dev/null | cut -d' ' -f1-2)

        echo "Latest Backup: $BACKUP_NAME"
        echo "Size:          $BACKUP_SIZE"
        echo "Date:          $BACKUP_DATE"

        # Backup age
        BACKUP_AGE_SEC=$(($(date +%s) - $(stat -f "%m" "$LATEST_BACKUP" 2>/dev/null || stat -c "%Y" "$LATEST_BACKUP" 2>/dev/null)))
        BACKUP_AGE_HOURS=$((BACKUP_AGE_SEC / 3600))

        if [ "$BACKUP_AGE_HOURS" -lt 25 ]; then
            echo -e "Status:        ${GREEN}✅ Fresh${NC} ($BACKUP_AGE_HOURS hours old)"
        else
            echo -e "Status:        ${YELLOW}⚠️  Old${NC} ($BACKUP_AGE_HOURS hours old)"
        fi
    fi
else
    echo "Backup directory not found"
fi

echo ""

# 5. Disk Space
echo "💿 DISK SPACE"
echo "─────────────────────────────────────────"

DISK_USAGE=$(df -h "$PROJECT_DIR" | awk 'NR==2 {print $5}' | sed 's/%//')
DISK_AVAIL=$(df -h "$PROJECT_DIR" | awk 'NR==2 {print $4}')

echo "Used:      ${DISK_USAGE}%"
echo "Available: $DISK_AVAIL"

if [ "$DISK_USAGE" -gt 90 ]; then
    echo -e "Status:    ${RED}❌ Critical${NC}"
elif [ "$DISK_USAGE" -gt 80 ]; then
    echo -e "Status:    ${YELLOW}⚠️  Warning${NC}"
else
    echo -e "Status:    ${GREEN}✅ OK${NC}"
fi

echo ""

# 6. Alert Summary
echo "🔔 ALERTS"
echo "─────────────────────────────────────────"

if [ -f "$PROJECT_DIR/logs/alerts.log" ]; then
    ALERTS_24H=$(grep -c "\[$(date '+%Y-%m-%d')\]" "$PROJECT_DIR/logs/alerts.log" 2>/dev/null || echo "0")
    CRITICAL=$(grep -c "\[CRITICAL\]" "$PROJECT_DIR/logs/alerts.log" 2>/dev/null || echo "0")
    WARNINGS=$(grep -c "\[WARNING\]" "$PROJECT_DIR/logs/alerts.log" 2>/dev/null || echo "0")

    echo "Last 24 Hours: $ALERTS_24H alerts"
    if [ "$CRITICAL" -gt 0 ]; then
        echo -e "Critical:      ${RED}$CRITICAL${NC}"
    else
        echo "Critical:      0"
    fi
    if [ "$WARNINGS" -gt 0 ]; then
        echo -e "Warnings:      ${YELLOW}$WARNINGS${NC}"
    else
        echo "Warnings:      0"
    fi

    # Latest alert
    LATEST_ALERT=$(tail -1 "$PROJECT_DIR/logs/alerts.log" 2>/dev/null)
    if [ -n "$LATEST_ALERT" ]; then
        echo ""
        echo "Latest Alert:"
        echo "$LATEST_ALERT"
    fi
else
    echo "No alerts logged yet"
fi

echo ""

# 7. Quick Actions
echo "========================================="
echo "QUICK ACTIONS"
echo "========================================="
echo ""
echo "Health Check:    ./scripts/health_check.sh"
echo "Run Pipeline:    docker exec bimcalckm-app-1 python -m bimcalc.cli sync-prices"
echo "Create Backup:   ./scripts/backup_postgres.sh"
echo "View Web UI:     http://localhost:8001"
echo "View Logs:       tail -f logs/pipeline.log"
echo ""
echo "Refresh dashboard: $0"
echo ""
