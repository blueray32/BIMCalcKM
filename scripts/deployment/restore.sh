#!/bin/bash

# BIMCalc Database Restore Script
# Usage: ./restore.sh <backup_file.sql.gz>

set -e

BACKUP_FILE="$1"
CONTAINER_NAME="db"
DB_USER="postgres"
DB_NAME="bimcalc"

if [ -z "$BACKUP_FILE" ]; then
    echo "Usage: ./restore.sh <backup_file.sql.gz>"
    exit 1
fi

if [ ! -f "$BACKUP_FILE" ]; then
    echo "Error: File '$BACKUP_FILE' not found."
    exit 1
fi

echo "⚠️  WARNING: This will OVERWRITE the current database '$DB_NAME'."
read -p "Are you sure you want to continue? (y/N) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Aborted."
    exit 1
fi

echo "📦 Restoring database from $BACKUP_FILE..."

# Drop and recreate database to ensure clean state
echo "   Recreating database..."
docker-compose exec -T "$CONTAINER_NAME" psql -U "$DB_USER" -c "DROP DATABASE IF EXISTS $DB_NAME;"
docker-compose exec -T "$CONTAINER_NAME" psql -U "$DB_USER" -c "CREATE DATABASE $DB_NAME;"

# Restore
echo "   Importing data..."
gunzip -c "$BACKUP_FILE" | docker-compose exec -T "$CONTAINER_NAME" psql -U "$DB_USER" -d "$DB_NAME"

echo "✅ Restore complete."
