#!/bin/bash

# BIMCalc Database Backup Script
# Usage: ./backup.sh

set -e

# Configuration
BACKUP_DIR="./backups"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
FILENAME="bimcalc_backup_${TIMESTAMP}.sql.gz"
CONTAINER_NAME="db"  # Adjust if your docker-compose service name differs
DB_USER="postgres"

# Create backup directory
mkdir -p "$BACKUP_DIR"

echo "📦 Starting backup of BIMCalc database..."

# Run pg_dump inside the container and pipe to gzip
if docker-compose exec -T "$CONTAINER_NAME" pg_dump -U "$DB_USER" bimcalc | gzip > "${BACKUP_DIR}/${FILENAME}"; then
    echo "✅ Backup successful: ${BACKUP_DIR}/${FILENAME}"
    
    # Optional: Keep only last 7 days of backups
    # find "$BACKUP_DIR" -name "bimcalc_backup_*.sql.gz" -mtime +7 -delete
else
    echo "❌ Backup failed!"
    exit 1
fi
