#!/bin/bash
# BIMCalc Backup Schedule Setup Script
# Usage: ./scripts/setup_backup_schedule.sh [method]
# Methods: cron, systemd, manual

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
BACKUP_SCRIPT="$SCRIPT_DIR/backup_postgres.sh"

METHOD="${1:-cron}"

echo "========================================="
echo "BIMCalc Backup Schedule Setup"
echo "========================================="
echo ""

# Check if backup script exists
if [ ! -f "$BACKUP_SCRIPT" ]; then
    echo "❌ ERROR: Backup script not found: $BACKUP_SCRIPT"
    exit 1
fi

case "$METHOD" in
    cron)
        echo "📅 Setting up Cron Job"
        echo ""
        echo "Recommended schedule: Daily at 2:00 AM"
        echo ""
        echo "Add this line to your crontab:"
        echo ""
        echo "0 2 * * * cd $PROJECT_DIR && $BACKUP_SCRIPT >> $PROJECT_DIR/logs/backup.log 2>&1"
        echo ""
        echo "To edit your crontab, run:"
        echo "   crontab -e"
        echo ""
        echo "Or to install it now, run:"
        echo "   (crontab -l 2>/dev/null; echo \"0 2 * * * cd $PROJECT_DIR && $BACKUP_SCRIPT >> $PROJECT_DIR/logs/backup.log 2>&1\") | crontab -"
        echo ""
        read -p "Install cron job now? (yes/no): " INSTALL
        if [ "$INSTALL" = "yes" ]; then
            mkdir -p "$PROJECT_DIR/logs"
            (crontab -l 2>/dev/null | grep -v "$BACKUP_SCRIPT"; echo "0 2 * * * cd $PROJECT_DIR && $BACKUP_SCRIPT >> $PROJECT_DIR/logs/backup.log 2>&1") | crontab -
            echo "✅ Cron job installed successfully!"
            echo ""
            echo "Current crontab:"
            crontab -l | grep -A 1 -B 1 "backup_postgres"
        else
            echo "ℹ️  Run the command above manually when ready"
        fi
        ;;

    systemd)
        echo "📅 Setting up Systemd Timer"
        echo ""

        SERVICE_FILE="/etc/systemd/system/bimcalc-backup.service"
        TIMER_FILE="/etc/systemd/system/bimcalc-backup.timer"

        echo "This will create two systemd files:"
        echo "   1. $SERVICE_FILE"
        echo "   2. $TIMER_FILE"
        echo ""

        cat <<EOF > /tmp/bimcalc-backup.service
[Unit]
Description=BIMCalc Database Backup
After=docker.service
Requires=docker.service

[Service]
Type=oneshot
User=$(whoami)
WorkingDirectory=$PROJECT_DIR
ExecStart=$BACKUP_SCRIPT
StandardOutput=append:$PROJECT_DIR/logs/backup.log
StandardError=append:$PROJECT_DIR/logs/backup.log

[Install]
WantedBy=multi-user.target
EOF

        cat <<EOF > /tmp/bimcalc-backup.timer
[Unit]
Description=BIMCalc Database Backup Timer
Requires=bimcalc-backup.service

[Timer]
OnCalendar=daily
OnCalendar=02:00
Persistent=true

[Install]
WantedBy=timers.target
EOF

        echo "Service file:"
        cat /tmp/bimcalc-backup.service
        echo ""
        echo "Timer file:"
        cat /tmp/bimcalc-backup.timer
        echo ""
        echo "To install (requires sudo):"
        echo "   sudo cp /tmp/bimcalc-backup.service $SERVICE_FILE"
        echo "   sudo cp /tmp/bimcalc-backup.timer $TIMER_FILE"
        echo "   sudo systemctl daemon-reload"
        echo "   sudo systemctl enable bimcalc-backup.timer"
        echo "   sudo systemctl start bimcalc-backup.timer"
        echo ""
        echo "To check status:"
        echo "   sudo systemctl status bimcalc-backup.timer"
        echo "   sudo systemctl list-timers bimcalc-backup.timer"
        echo ""
        ;;

    manual)
        echo "📋 Manual Backup Instructions"
        echo ""
        echo "To run a backup manually:"
        echo "   cd $PROJECT_DIR"
        echo "   $BACKUP_SCRIPT"
        echo ""
        echo "Recommended schedule:"
        echo "   - Daily: Best for active use"
        echo "   - Weekly: Acceptable for low-change systems"
        echo "   - Before major changes: Always!"
        echo ""
        echo "Create a reminder to run backups regularly."
        ;;

    *)
        echo "❌ ERROR: Unknown method '$METHOD'"
        echo ""
        echo "Usage: $0 [method]"
        echo "Methods:"
        echo "   cron     - Use cron for scheduling (default)"
        echo "   systemd  - Use systemd timer"
        echo "   manual   - Show manual backup instructions"
        exit 1
        ;;
esac

echo ""
echo "========================================="
echo "Additional Recommendations"
echo "========================================="
echo ""
echo "1. Test your backups regularly:"
echo "   $SCRIPT_DIR/restore_postgres.sh <backup_file>"
echo ""
echo "2. Monitor backup logs:"
echo "   tail -f $PROJECT_DIR/logs/backup.log"
echo ""
echo "3. Check disk space:"
echo "   du -sh $PROJECT_DIR/backups"
echo ""
echo "4. Consider off-site backups:"
echo "   - Copy to cloud storage (AWS S3, Azure Blob, Google Cloud)"
echo "   - Copy to network drive"
echo "   - Copy to external hard drive"
echo ""
echo "5. Document your restore procedure"
echo ""
