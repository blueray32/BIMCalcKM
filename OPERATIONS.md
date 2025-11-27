# BIMCalc Operations Guide

This guide covers the essential operational tasks for maintaining the BIMCalc production environment.

## 1. Monitoring & Alerts

BIMCalc includes built-in alerting for critical events like ingestion failures and high-risk items.

### Configuration
Ensure the following environment variables are set in your `.env` file (or `production.env`):

**Email Alerts (SMTP)**
```bash
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your-email@gmail.com
SMTP_PASSWORD=your-app-password
SMTP_FROM=noreply@bimcalc.com
```

**Slack Alerts**
```bash
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/T00000000/B00000000/XXXXXXXXXXXXXXXXXXXXXXXX
```

### Alert Triggers
- **Ingestion Failure**: Triggered when a schedule or price book upload fails. Sent to Admin Email & Slack.
- **High Risk Item**: Triggered when an item's risk score exceeds the threshold. Sent to Slack.
- **Checklist Complete**: Triggered when a QA checklist is finished. Sent to Email.

### Logs
Application logs are available via Docker:
```bash
docker-compose logs -f web
```
Look for `ERROR` level logs for stack traces.

## 2. Database Backups

Regular backups are critical for disaster recovery. We provide scripts to automate this.

### Manual Backup
Run the backup script to create a timestamped dump of the database:
```bash
./backup.sh
```
Backups are stored in the `./backups` directory.

### Automated Backup (Cron)
Add a cron job to run the backup script daily (e.g., at 2 AM):
```bash
0 2 * * * /path/to/bimcalc/backup.sh >> /path/to/bimcalc/backups/backup.log 2>&1
```

### Restore
To restore from a backup file:
```bash
./restore.sh backups/bimcalc_backup_YYYYMMDD_HHMMSS.sql.gz
```
**WARNING**: This will overwrite the current database.

## 3. Troubleshooting

**Ingestion Fails Immediately**
- Check `upload_max_filesize` in Nginx/Python config.
- Verify file format (CSV/XLSX).
- Check logs for "Permission denied" errors on `/tmp`.

**No Alerts Received**
- Verify SMTP credentials.
- Check if `SLACK_WEBHOOK_URL` is valid.
- Check logs for "Failed to send email" or "Slack notification failed".

**Database Connection Error**
- Ensure `db` container is running: `docker-compose ps`.
- Check `DATABASE_URL` in `.env`.
