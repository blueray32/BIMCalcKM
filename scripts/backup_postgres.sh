#!/bin/bash
# BIMCalc PostgreSQL Database Backup Script (Docker)
# Usage: ./scripts/backup_postgres.sh [backup_dir]

set -e

# Configuration
BACKUP_DIR="${1:-./backups}"
CONTAINER_NAME="bimcalc-postgres"
DB_NAME="bimcalc"
DB_USER="bimcalc"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="${BACKUP_DIR}/bimcalc_postgres_backup_${TIMESTAMP}.sql"
COMPRESSED_FILE="${BACKUP_FILE}.gz"
RETENTION_DAYS=30

echo "========================================="
echo "BIMCalc PostgreSQL Backup (Docker)"
echo "========================================="
echo ""

# Check if Docker container is running
if ! docker ps --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
    echo "❌ ERROR: PostgreSQL container '${CONTAINER_NAME}' is not running"
    echo "   Start it with: docker start ${CONTAINER_NAME}"
    exit 1
fi

# Create backup directory if needed
mkdir -p "$BACKUP_DIR"

# Get database size
echo "📊 Checking database size..."
DB_SIZE=$(docker exec "$CONTAINER_NAME" psql -U "$DB_USER" -d "$DB_NAME" -t -c "SELECT pg_size_pretty(pg_database_size('$DB_NAME'));" | xargs)
echo "   Database size: $DB_SIZE"

# Count records
echo "📊 Counting records..."
PRICE_COUNT=$(docker exec "$CONTAINER_NAME" psql -U "$DB_USER" -d "$DB_NAME" -t -c "SELECT COUNT(*) FROM price_items;" | xargs)
SYNC_COUNT=$(docker exec "$CONTAINER_NAME" psql -U "$DB_USER" -d "$DB_NAME" -t -c "SELECT COUNT(*) FROM data_sync_log;" | xargs)
echo "   Price items: $PRICE_COUNT"
echo "   Pipeline runs: $SYNC_COUNT"

# Perform backup
echo ""
echo "🔄 Creating backup..."
docker exec "$CONTAINER_NAME" pg_dump -U "$DB_USER" "$DB_NAME" > "$BACKUP_FILE"

# Verify backup was created
if [ ! -f "$BACKUP_FILE" ]; then
    echo "❌ ERROR: Backup failed - file not created"
    exit 1
fi

BACKUP_SIZE=$(du -h "$BACKUP_FILE" | awk '{print $1}')
echo "✅ Backup created: $BACKUP_FILE ($BACKUP_SIZE)"

# Compress backup
echo "🗜️  Compressing backup..."
gzip "$BACKUP_FILE"

if [ -f "$COMPRESSED_FILE" ]; then
    COMPRESSED_SIZE=$(du -h "$COMPRESSED_FILE" | awk '{print $1}')
    echo "✅ Compressed: $COMPRESSED_FILE ($COMPRESSED_SIZE)"
else
    echo "⚠️  Warning: Compression failed, keeping uncompressed backup"
fi

# Verify backup integrity
echo ""
echo "🔍 Verifying backup integrity..."
if [ -f "$COMPRESSED_FILE" ]; then
    # Test gzip integrity
    if gzip -t "$COMPRESSED_FILE" 2>/dev/null; then
        echo "✅ Backup integrity verified (compressed)"
    else
        echo "❌ ERROR: Compressed backup is corrupted"
        exit 1
    fi
elif [ -f "$BACKUP_FILE" ]; then
    # Check if file contains SQL
    if head -n 1 "$BACKUP_FILE" | grep -q "PostgreSQL"; then
        echo "✅ Backup integrity verified (uncompressed)"
    else
        echo "❌ ERROR: Backup file is corrupted"
        exit 1
    fi
fi

# Clean old backups
echo ""
echo "🧹 Cleaning old backups (older than $RETENTION_DAYS days)..."
DELETED_SQL=$(find "$BACKUP_DIR" -name "bimcalc_postgres_backup_*.sql" -mtime +$RETENTION_DAYS -type f -delete -print | wc -l | xargs)
DELETED_GZ=$(find "$BACKUP_DIR" -name "bimcalc_postgres_backup_*.sql.gz" -mtime +$RETENTION_DAYS -type f -delete -print | wc -l | xargs)
TOTAL_DELETED=$((DELETED_SQL + DELETED_GZ))

if [ "$TOTAL_DELETED" -gt 0 ]; then
    echo "   Deleted $TOTAL_DELETED old backup(s)"
else
    echo "   No old backups to delete"
fi

# List current backups
echo ""
echo "📁 Current backups:"
BACKUP_COUNT=$(ls -1 "$BACKUP_DIR"/bimcalc_postgres_backup_*.{sql,sql.gz} 2>/dev/null | wc -l | xargs)
if [ "$BACKUP_COUNT" -gt 0 ]; then
    ls -lh "$BACKUP_DIR"/bimcalc_postgres_backup_*.{sql,sql.gz} 2>/dev/null | awk '{print "   " $9 " (" $5 ")"}'
    echo ""
    echo "   Total backups: $BACKUP_COUNT"
    TOTAL_SIZE=$(du -sh "$BACKUP_DIR" | awk '{print $1}')
    echo "   Total size: $TOTAL_SIZE"
else
    echo "   No backups found"
fi

echo ""
echo "========================================="
echo "✅ Backup Complete"
echo "========================================="
echo ""
echo "To restore this backup:"
echo "   1. Stop the application:"
echo "      docker stop bimcalckm-app-1"
echo ""
echo "   2. Restore the backup:"
if [ -f "$COMPRESSED_FILE" ]; then
    echo "      gunzip -c $COMPRESSED_FILE | docker exec -i $CONTAINER_NAME psql -U $DB_USER -d $DB_NAME"
else
    echo "      docker exec -i $CONTAINER_NAME psql -U $DB_USER -d $DB_NAME < $BACKUP_FILE"
fi
echo ""
echo "   3. Restart the application:"
echo "      docker start bimcalckm-app-1"
echo ""
