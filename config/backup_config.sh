#!/bin/bash
# BIMCalc Backup Configuration
# Source this file in backup scripts: source config/backup_config.sh

# Backup Retention Policy
export BACKUP_RETENTION_DAYS=30  # Keep backups for 30 days (default)

# Backup Schedule
# Uncomment and modify to override default schedule
# export BACKUP_SCHEDULE="0 2 * * *"  # Daily at 2:00 AM

# Backup Directory
export BACKUP_DIR="./backups"

# Compression
export BACKUP_COMPRESS=true  # Compress backups with gzip

# Database Configuration
export POSTGRES_CONTAINER="bimcalc-postgres"
export POSTGRES_DB="bimcalc"
export POSTGRES_USER="bimcalc"

# Application Container
export APP_CONTAINER="bimcalckm-app-1"

# Off-site Backup Configuration (optional)
# Uncomment and configure for cloud backups

# AWS S3
# export OFFSITE_BACKUP_ENABLED=true
# export OFFSITE_BACKUP_TYPE="s3"
# export AWS_S3_BUCKET="my-bimcalc-backups"
# export AWS_S3_PREFIX="bimcalc/"
# export AWS_REGION="us-east-1"

# Azure Blob Storage
# export OFFSITE_BACKUP_ENABLED=true
# export OFFSITE_BACKUP_TYPE="azure"
# export AZURE_STORAGE_ACCOUNT="mybimcalcbackups"
# export AZURE_STORAGE_CONTAINER="backups"

# Google Cloud Storage
# export OFFSITE_BACKUP_ENABLED=true
# export OFFSITE_BACKUP_TYPE="gcs"
# export GCS_BUCKET="my-bimcalc-backups"
# export GCS_PREFIX="bimcalc/"

# Network Drive
# export OFFSITE_BACKUP_ENABLED=true
# export OFFSITE_BACKUP_TYPE="network"
# export NETWORK_BACKUP_PATH="/mnt/backups/bimcalc"

# Notification Configuration (optional)
# Uncomment to enable email notifications

# Email Notifications
# export BACKUP_NOTIFY_EMAIL=true
# export BACKUP_NOTIFY_TO="admin@example.com"
# export BACKUP_NOTIFY_FROM="backups@example.com"
# export BACKUP_NOTIFY_SMTP="smtp.gmail.com:587"

# Slack Notifications
# export BACKUP_NOTIFY_SLACK=true
# export SLACK_WEBHOOK_URL="https://hooks.slack.com/services/YOUR/WEBHOOK/URL"

# Retention Policy Options:
# - 7 days: For testing/development
# - 30 days: Standard (recommended)
# - 90 days: Compliance/auditing
# - 365 days: Long-term archival

# Backup Types:
# - FULL: Complete database dump (default)
# - INCREMENTAL: Not yet supported
# - DIFFERENTIAL: Not yet supported

echo "✅ BIMCalc backup configuration loaded"
echo "   Retention: $BACKUP_RETENTION_DAYS days"
echo "   Directory: $BACKUP_DIR"
echo "   Compression: $BACKUP_COMPRESS"
