#!/bin/bash

# BIMCalc Cron Setup Script
# Adds operational tasks to the user's crontab

PROJECT_DIR="$(pwd)"
LOG_DIR="/var/log/bimcalc"

# Ensure log directory exists (might need sudo, or use local dir)
if [ ! -d "$LOG_DIR" ]; then
    echo "Creating log directory at $PROJECT_DIR/logs..."
    mkdir -p "$PROJECT_DIR/logs"
    LOG_DIR="$PROJECT_DIR/logs"
fi

echo "Setting up cron jobs for BIMCalc in $PROJECT_DIR..."

# Define cron jobs
BACKUP_JOB="0 1 * * * cd $PROJECT_DIR && ./scripts/backup_database.sh >> $LOG_DIR/backup.log 2>&1"
PIPELINE_JOB="0 2 * * * cd $PROJECT_DIR && python -m bimcalc.cli sync-prices >> $LOG_DIR/pipeline.log 2>&1"
HEALTH_JOB="0 */4 * * * cd $PROJECT_DIR && ./scripts/health_check.sh >> $LOG_DIR/health.log 2>&1"

# Function to add job if not exists
add_job() {
    local job="$1"
    (crontab -l 2>/dev/null | grep -F "$job") || (crontab -l 2>/dev/null; echo "$job") | crontab -
}

add_job "$BACKUP_JOB"
add_job "$PIPELINE_JOB"
add_job "$HEALTH_JOB"

echo "✅ Cron jobs added successfully!"
crontab -l
