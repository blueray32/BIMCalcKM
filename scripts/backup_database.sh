#!/bin/bash
# BIMCalc Database Backup Script
# Usage: ./scripts/backup_database.sh [backup_dir]

set -e

# Configuration
BACKUP_DIR="${1:-./backups}"
DB_FILE="bimcalc.db"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="${BACKUP_DIR}/bimcalc_backup_${TIMESTAMP}.db"
RETENTION_DAYS=30

echo "========================================="
echo "BIMCalc Database Backup"
echo "========================================="
echo ""

# Check database exists
if [ ! -f "$DB_FILE" ]; then
    echo "❌ ERROR: Database file not found ($DB_FILE)"
    exit 1
fi

# Create backup directory if needed
mkdir -p "$BACKUP_DIR"

# Get database size
DB_SIZE=$(du -h "$DB_FILE" | awk '{print $1}')
echo "📊 Database size: $DB_SIZE"

# Perform backup
echo "🔄 Creating backup..."
cp "$DB_FILE" "$BACKUP_FILE"

# Verify backup
if [ -f "$BACKUP_FILE" ]; then
    BACKUP_SIZE=$(du -h "$BACKUP_FILE" | awk '{print $1}')
    echo "✅ Backup created: $BACKUP_FILE ($BACKUP_SIZE)"
else
    echo "❌ ERROR: Backup failed"
    exit 1
fi

# Clean old backups
echo ""
echo "🧹 Cleaning old backups (older than $RETENTION_DAYS days)..."
DELETED=$(find "$BACKUP_DIR" -name "bimcalc_backup_*.db" -mtime +$RETENTION_DAYS -type f -delete -print | wc -l)
if [ "$DELETED" -gt 0 ]; then
    echo "   Deleted $DELETED old backup(s)"
else
    echo "   No old backups to delete"
fi

# List current backups
echo ""
echo "📁 Current backups:"
ls -lh "$BACKUP_DIR"/bimcalc_backup_*.db | awk '{print "   " $9 " (" $5 ")"}'

echo ""
echo "========================================="
echo "Backup Complete"
echo "========================================="
