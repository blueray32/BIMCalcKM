#!/bin/bash
# BIMCalc PostgreSQL Restore Script (Docker)
# Usage: ./scripts/restore_postgres.sh <backup_file>

set -e

# Configuration
CONTAINER_NAME="bimcalc-postgres"
APP_CONTAINER="bimcalckm-app-1"
DB_NAME="bimcalc"
DB_USER="bimcalc"

# Check arguments
if [ $# -eq 0 ]; then
    echo "========================================="
    echo "BIMCalc PostgreSQL Restore (Docker)"
    echo "========================================="
    echo ""
    echo "Usage: $0 <backup_file>"
    echo ""
    echo "Available backups:"
    ls -lh ./backups/bimcalc_postgres_backup_*.sql.gz 2>/dev/null | awk '{print "   " $9 " (" $5 ")"}'
    echo ""
    exit 1
fi

BACKUP_FILE="$1"

echo "========================================="
echo "BIMCalc PostgreSQL Restore (Docker)"
echo "========================================="
echo ""

# Check if backup file exists
if [ ! -f "$BACKUP_FILE" ]; then
    echo "❌ ERROR: Backup file not found: $BACKUP_FILE"
    exit 1
fi

# Check if Docker container is running
if ! docker ps --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
    echo "❌ ERROR: PostgreSQL container '${CONTAINER_NAME}' is not running"
    echo "   Start it with: docker start ${CONTAINER_NAME}"
    exit 1
fi

# Get current database stats for comparison
echo "📊 Current database stats:"
CURRENT_PRICES=$(docker exec "$CONTAINER_NAME" psql -U "$DB_USER" -d "$DB_NAME" -t -c "SELECT COUNT(*) FROM price_items;" 2>/dev/null | xargs || echo "0")
CURRENT_SYNC=$(docker exec "$CONTAINER_NAME" psql -U "$DB_USER" -d "$DB_NAME" -t -c "SELECT COUNT(*) FROM data_sync_log;" 2>/dev/null | xargs || echo "0")
echo "   Price items: $CURRENT_PRICES"
echo "   Pipeline runs: $CURRENT_SYNC"
echo ""

# Warning
echo "⚠️  WARNING: This will REPLACE the current database!"
echo "   Backup file: $BACKUP_FILE"
echo ""
read -p "Are you sure you want to continue? (yes/no): " CONFIRM

if [ "$CONFIRM" != "yes" ]; then
    echo "❌ Restore cancelled"
    exit 0
fi

# Stop the application
echo ""
echo "🛑 Stopping application..."
docker stop "$APP_CONTAINER" > /dev/null 2>&1 || echo "   Application already stopped"

# Drop and recreate database
echo "🗑️  Dropping existing database..."
docker exec "$CONTAINER_NAME" psql -U "$DB_USER" -d postgres -c "DROP DATABASE IF EXISTS $DB_NAME;" > /dev/null

echo "🆕 Creating fresh database..."
docker exec "$CONTAINER_NAME" psql -U "$DB_USER" -d postgres -c "CREATE DATABASE $DB_NAME OWNER $DB_USER;" > /dev/null

# Restore backup
echo "📥 Restoring backup..."
if [[ "$BACKUP_FILE" == *.gz ]]; then
    # Compressed backup
    gunzip -c "$BACKUP_FILE" | docker exec -i "$CONTAINER_NAME" psql -U "$DB_USER" -d "$DB_NAME" > /dev/null 2>&1
else
    # Uncompressed backup
    docker exec -i "$CONTAINER_NAME" psql -U "$DB_USER" -d "$DB_NAME" < "$BACKUP_FILE" > /dev/null 2>&1
fi

# Verify restoration
echo "🔍 Verifying restoration..."
RESTORED_PRICES=$(docker exec "$CONTAINER_NAME" psql -U "$DB_USER" -d "$DB_NAME" -t -c "SELECT COUNT(*) FROM price_items;" | xargs)
RESTORED_SYNC=$(docker exec "$CONTAINER_NAME" psql -U "$DB_USER" -d "$DB_NAME" -t -c "SELECT COUNT(*) FROM data_sync_log;" | xargs)
echo "   Price items: $RESTORED_PRICES"
echo "   Pipeline runs: $RESTORED_SYNC"

# Restart application
echo ""
echo "🚀 Starting application..."
docker start "$APP_CONTAINER" > /dev/null 2>&1

# Wait for app to be ready
echo "⏳ Waiting for application to be ready..."
sleep 5

# Check if app is responding
if curl -s -o /dev/null -w "%{http_code}" http://localhost:8001/ | grep -q "200"; then
    echo "✅ Application is responding"
else
    echo "⚠️  Warning: Application may not be ready yet"
fi

echo ""
echo "========================================="
echo "✅ Restore Complete"
echo "========================================="
echo ""
echo "Comparison:"
echo "   Before: $CURRENT_PRICES price items, $CURRENT_SYNC pipeline runs"
echo "   After:  $RESTORED_PRICES price items, $RESTORED_SYNC pipeline runs"
echo ""
echo "Web UI: http://localhost:8001"
echo ""
