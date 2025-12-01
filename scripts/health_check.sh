#!/bin/bash
# BIMCalc System Health Check
# Monitors Docker containers, database, pipeline, and backups

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

# Exit codes for monitoring systems
EXIT_OK=0
EXIT_WARNING=1
EXIT_CRITICAL=2
EXIT_UNKNOWN=3

ISSUES=()
WARNINGS=()
STATUS=$EXIT_OK

echo "========================================="
echo "BIMCalc Health Check"
echo "========================================="
echo "$(date)"
echo ""

# 1. Check Docker Containers
echo "🐳 Docker Containers"
echo "-------------------"

if ! docker ps --format '{{.Names}}' | grep -q "bimcalc-app"; then
    ISSUES+=("❌ Application container (bimcalc-app) is not running")
    STATUS=$EXIT_CRITICAL
else
    echo "✅ Application container: Running"
fi

if ! docker ps --format '{{.Names}}' | grep -q "bimcalc-postgres"; then
    ISSUES+=("❌ PostgreSQL container (bimcalc-postgres) is not running")
    STATUS=$EXIT_CRITICAL
else
    echo "✅ PostgreSQL container: Running"
fi

echo ""

# 2. Check Database Connection
echo "💾 Database Health"
echo "------------------"

if docker exec bimcalc-postgres psql -U bimcalc -d bimcalc -c "SELECT 1;" > /dev/null 2>&1; then
    echo "✅ Database connection: OK"

    # Check database size
    DB_SIZE=$(docker exec bimcalc-postgres psql -U bimcalc -d bimcalc -t -c "SELECT pg_size_pretty(pg_database_size('bimcalc'));" | xargs)
    echo "   Size: $DB_SIZE"

    # Check record counts
    PRICE_COUNT=$(docker exec bimcalc-postgres psql -U bimcalc -d bimcalc -t -c "SELECT COUNT(*) FROM price_items WHERE is_current = true;" | xargs)
    echo "   Current prices: $PRICE_COUNT"

    if [ "$PRICE_COUNT" -eq 0 ]; then
        WARNINGS+=("⚠️  No current price items in database")
        [ "$STATUS" -eq "$EXIT_OK" ] && STATUS=$EXIT_WARNING
    fi
else
    ISSUES+=("❌ Database connection failed")
    STATUS=$EXIT_CRITICAL
fi

echo ""

# 3. Check Pipeline Status
echo "🔄 Pipeline Status"
echo "------------------"

if [ -f "$PROJECT_DIR/logs/pipeline.log" ]; then
    # Check when last run was
    LAST_RUN=$(grep "Pipeline Run Summary" "$PROJECT_DIR/logs/pipeline.log" | tail -1 | grep -o "Run timestamp: [^$]*" || echo "Never")
    echo "   Last run: $LAST_RUN"

    # Check for recent failures
    RECENT_FAILURES=$(grep "FAILED" "$PROJECT_DIR/logs/pipeline.log" 2>/dev/null | tail -10 | wc -l | xargs || echo "0")
    if [ "$RECENT_FAILURES" -gt 0 ]; then
        WARNINGS+=("⚠️  $RECENT_FAILURES recent pipeline failures detected in log")
        [ "$STATUS" -eq "$EXIT_OK" ] && STATUS=$EXIT_WARNING
    fi

    # Check if pipeline ran in last 25 hours (should run daily at 2 AM)
    if [ -f "$PROJECT_DIR/logs/pipeline.log" ]; then
        # Linux stat syntax
        LAST_RUN_TIME=$(stat -c %Y "$PROJECT_DIR/logs/pipeline.log" 2>/dev/null || echo "0")
        CURRENT_TIME=$(date +%s)
        HOURS_SINCE=$(( (CURRENT_TIME - LAST_RUN_TIME) / 3600 ))

        if [ "$HOURS_SINCE" -gt 25 ]; then
            ISSUES+=("❌ Pipeline hasn't run in $HOURS_SINCE hours (expected: 24)")
            STATUS=$EXIT_CRITICAL
        else
            echo "✅ Pipeline last ran $HOURS_SINCE hours ago"
        fi
    fi
else
    WARNINGS+=("⚠️  No pipeline log found")
    [ "$STATUS" -eq "$EXIT_OK" ] && STATUS=$EXIT_WARNING
fi

echo ""

# 4. Check Backup Status
echo "💾 Backup Status"
echo "----------------"

if [ -d "$PROJECT_DIR/backups" ]; then
    BACKUP_COUNT=$(ls -1 "$PROJECT_DIR/backups"/*.sql.gz 2>/dev/null | wc -l | xargs)
    echo "   Total backups: $BACKUP_COUNT"

    if [ "$BACKUP_COUNT" -eq 0 ]; then
        ISSUES+=("❌ No backups found in backups/ directory")
        STATUS=$EXIT_CRITICAL
    else
        # Check age of latest backup
        LATEST_BACKUP=$(ls -t "$PROJECT_DIR/backups"/*.sql.gz 2>/dev/null | head -1)
        if [ -n "$LATEST_BACKUP" ]; then
            # Linux stat syntax
            BACKUP_TIME=$(stat -c %Y "$LATEST_BACKUP" 2>/dev/null)
            BACKUP_AGE_SECONDS=$((CURRENT_TIME - BACKUP_TIME))
            BACKUP_AGE_HOURS=$((BACKUP_AGE_SECONDS / 3600))

            echo "   Latest backup: $(basename "$LATEST_BACKUP")"
            echo "   Age: $BACKUP_AGE_HOURS hours"

            if [ "$BACKUP_AGE_HOURS" -gt 25 ]; then
                ISSUES+=("❌ Latest backup is $BACKUP_AGE_HOURS hours old (expected: <25)")
                STATUS=$EXIT_CRITICAL
            else
                echo "✅ Recent backup exists"
            fi

            # Check backup size
            BACKUP_SIZE=$(du -h "$LATEST_BACKUP" | awk '{print $1}')
            echo "   Size: $BACKUP_SIZE"
        fi
    fi
else
    ISSUES+=("❌ Backups directory not found")
    STATUS=$EXIT_CRITICAL
fi

echo ""

# 5. Check Disk Space
echo "💿 Disk Space"
echo "-------------"

DISK_USAGE=$(df -h "$PROJECT_DIR" | awk 'NR==2 {print $5}' | sed 's/%//')
DISK_AVAIL=$(df -h "$PROJECT_DIR" | awk 'NR==2 {print $4}')

echo "   Used: ${DISK_USAGE}%"
echo "   Available: $DISK_AVAIL"

if [ "$DISK_USAGE" -gt 90 ]; then
    ISSUES+=("❌ Disk usage critical: ${DISK_USAGE}%")
    STATUS=$EXIT_CRITICAL
elif [ "$DISK_USAGE" -gt 80 ]; then
    WARNINGS+=("⚠️  Disk usage high: ${DISK_USAGE}%")
    [ "$STATUS" -eq "$EXIT_OK" ] && STATUS=$EXIT_WARNING
else
    echo "✅ Disk space OK"
fi

echo ""

# 6. Check Log File Sizes
echo "📄 Log Files"
echo "------------"

if [ -d "$PROJECT_DIR/logs" ]; then
    TOTAL_LOG_SIZE=$(du -sh "$PROJECT_DIR/logs" 2>/dev/null | awk '{print $1}')
    echo "   Total size: $TOTAL_LOG_SIZE"

    # Check individual log sizes
    for logfile in "$PROJECT_DIR/logs"/*.log; do
        if [ -f "$logfile" ]; then
            SIZE=$(du -h "$logfile" | awk '{print $1}')
            echo "   $(basename "$logfile"): $SIZE"

            # Warn if log file is very large (>100MB)
            SIZE_BYTES=$(du -k "$logfile" | awk '{print $1}')
            if [ "$SIZE_BYTES" -gt 102400 ]; then
                WARNINGS+=("⚠️  Large log file: $(basename "$logfile") ($SIZE)")
                [ "$STATUS" -eq "$EXIT_OK" ] && STATUS=$EXIT_WARNING
            fi
        fi
    done
else
    WARNINGS+=("⚠️  Logs directory not found")
    [ "$STATUS" -eq "$EXIT_OK" ] && STATUS=$EXIT_WARNING
fi

echo ""

# 7. Check Recent Pipeline Runs (from database)
echo "📊 Recent Pipeline Activity"
echo "---------------------------"

if docker exec bimcalc-postgres psql -U bimcalc -d bimcalc -c "SELECT 1 FROM data_sync_log LIMIT 1;" > /dev/null 2>&1; then
    RECENT_RUNS=$(docker exec bimcalc-postgres psql -U bimcalc -d bimcalc -t -c "
        SELECT
            TO_CHAR(run_timestamp, 'YYYY-MM-DD HH24:MI') as time,
            source_name,
            status,
            records_inserted,
            records_updated
        FROM data_sync_log
        ORDER BY run_timestamp DESC
        LIMIT 5;
    ")

    if [ -n "$RECENT_RUNS" ]; then
        echo "$RECENT_RUNS"
    else
        echo "   No pipeline runs recorded yet"
    fi

    # Check for recent failures
    FAILURE_COUNT=$(docker exec bimcalc-postgres psql -U bimcalc -d bimcalc -t -c "
        SELECT COUNT(*) FROM data_sync_log
        WHERE status = 'FAILED'
        AND run_timestamp > NOW() - INTERVAL '7 days';
    " | xargs)

    if [ "$FAILURE_COUNT" -gt 0 ]; then
        WARNINGS+=("⚠️  $FAILURE_COUNT pipeline failures in last 7 days")
        [ "$STATUS" -eq "$EXIT_OK" ] && STATUS=$EXIT_WARNING
    fi
fi

echo ""

# Summary
echo "========================================="
echo "Health Check Summary"
echo "========================================="
echo ""

if [ ${#ISSUES[@]} -eq 0 ] && [ ${#WARNINGS[@]} -eq 0 ]; then
    echo "✅ All systems healthy!"
    echo ""
    echo "Status: HEALTHY"
    exit $EXIT_OK
fi

if [ ${#ISSUES[@]} -gt 0 ]; then
    echo "❌ Critical Issues:"
    for issue in "${ISSUES[@]}"; do
        echo "   $issue"
    done
    echo ""
fi

if [ ${#WARNINGS[@]} -gt 0 ]; then
    echo "⚠️  Warnings:"
    for warning in "${WARNINGS[@]}"; do
        echo "   $warning"
    done
    echo ""
fi

if [ "$STATUS" -eq "$EXIT_CRITICAL" ]; then
    echo "Status: CRITICAL"
elif [ "$STATUS" -eq "$EXIT_WARNING" ]; then
    echo "Status: WARNING"
else
    echo "Status: UNKNOWN"
fi

echo ""
echo "Run 'docker logs bimcalckm-app-1' for application logs"
echo "Run 'tail -f logs/pipeline.log' for pipeline details"
echo ""

exit $STATUS
