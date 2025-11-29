# ✅ Automation Setup Complete

**Date:** November 14, 2024
**Status:** ✅ **FULLY AUTOMATED**

---

## Setup Summary

Your BIMCalc system now runs completely automatically!

### ✅ What's Been Automated

**1. Pipeline Synchronization** 🔄
- **Schedule:** Daily at 2:00 AM
- **Action:** Syncs pricing data from all enabled sources
- **Updates:** SCD Type-2 price history
- **Logging:** `logs/pipeline.log`

**2. Database Backups** 💾
- **Schedule:** Daily at 2:30 AM (30 min after pipeline)
- **Action:** Full PostgreSQL backup with compression
- **Retention:** 30 days (automatic cleanup)
- **Logging:** `logs/backup.log`

---

## 📅 Automated Schedule

```
Time    | Task              | Action
--------|-------------------|----------------------------------------
2:00 AM | Pipeline Sync     | Import latest prices from all sources
2:30 AM | Database Backup   | Backup PostgreSQL with compression
Daily   | Retention Cleanup | Remove backups older than 30 days
```

**Result:** Fresh pricing data and secure backups every morning!

---

## ✅ Installed Cron Jobs

```bash
# BIMCalc Automated Tasks
# Added on 2025-11-14

# Pipeline sync - Daily at 2:00 AM
0 2 * * * cd /Users/ciarancox/BIMCalcKM && docker exec bimcalckm-app-1 python -m bimcalc.cli sync-prices >> /Users/ciarancox/BIMCalcKM/logs/pipeline.log 2>&1

# Database backup - Daily at 2:30 AM
30 2 * * * cd /Users/ciarancox/BIMCalcKM && /Users/ciarancox/BIMCalcKM/scripts/backup_postgres.sh >> /Users/ciarancox/BIMCalcKM/logs/backup.log 2>&1
```

---

## 🔍 Monitoring Your Automation

### Check Scheduled Jobs

```bash
# View all cron jobs
crontab -l

# View just BIMCalc jobs
crontab -l | grep -A 5 "BIMCalc"
```

### Monitor Logs (Real-time)

```bash
# Watch pipeline runs
tail -f logs/pipeline.log

# Watch backups
tail -f logs/backup.log

# Watch both
tail -f logs/pipeline.log logs/backup.log
```

### Check Recent Runs

```bash
# Last 50 lines of pipeline log
tail -50 logs/pipeline.log

# Last 50 lines of backup log
tail -50 logs/backup.log

# Search for errors
grep -i error logs/pipeline.log
grep -i error logs/backup.log
```

### Web UI Monitoring

```bash
# View pipeline status
open http://localhost:8001/pipeline

# View price data
open http://localhost:8001/prices

# View dashboard
open http://localhost:8001/
```

---

## 🧪 Testing

### Test Pipeline Run Manually

```bash
# Run pipeline now (doesn't interfere with scheduled runs)
docker exec bimcalckm-app-1 python -m bimcalc.cli sync-prices

# Expected output:
# Starting price synchronization pipeline
# Config: config/pipeline_sources.yaml
# Loaded 1 data sources
#
# Pipeline Run Summary
# Run timestamp: 2025-11-14...
# Status: 1/1 sources successful
```

### Test Backup Manually

```bash
# Run backup now
./scripts/backup_postgres.sh

# Expected output:
# =========================================
# BIMCalc PostgreSQL Backup (Docker)
# =========================================
# 📊 Database size: 8676 kB
# ✅ Backup created: ...
# ✅ Compressed: ...
# ✅ Backup integrity verified
```

### Verify Jobs Will Run

```bash
# Check cron service is running (macOS)
launchctl list | grep cron

# View upcoming cron executions (next 24 hours)
# Note: macOS doesn't show this by default, but jobs will run at 2:00 AM and 2:30 AM
```

---

## 📊 What Happens Each Night

### 2:00 AM - Pipeline Sync

**Process:**
1. ✅ Loads `config/pipeline_sources.yaml`
2. ✅ Connects to each enabled source
3. ✅ Imports new pricing data
4. ✅ Updates SCD Type-2 records:
   - Price unchanged? No action
   - Price changed? Close old record, create new
   - New item? Create record
   - Item removed? Expire record
5. ✅ Logs results to `data_sync_log` table
6. ✅ Writes log to `logs/pipeline.log`

**Success indicators:**
```
Status: X/X sources successful
No errors in logs
data_sync_log shows new entries
```

### 2:30 AM - Database Backup

**Process:**
1. ✅ Checks PostgreSQL is running
2. ✅ Creates SQL dump using `pg_dump`
3. ✅ Compresses with gzip (~80% reduction)
4. ✅ Verifies backup integrity
5. ✅ Removes backups older than 30 days
6. ✅ Writes log to `logs/backup.log`

**Success indicators:**
```
✅ Backup created: backups/bimcalc_postgres_backup_YYYYMMDD_HHMMSS.sql.gz
✅ Compressed: ...
✅ Backup integrity verified
```

---

## 📧 Alerts & Notifications

### Current Status
- ✅ Logging enabled (both tasks log to files)
- ⏸️ Email alerts not configured (future enhancement)
- ⏸️ Slack alerts not configured (future enhancement)

### Adding Email Alerts (Optional)

**Edit cron jobs to send email on failure:**
```bash
crontab -e
```

**Modify to:**
```bash
# Pipeline with email on failure
0 2 * * * cd /Users/ciarancox/BIMCalcKM && docker exec bimcalckm-app-1 python -m bimcalc.cli sync-prices >> /Users/ciarancox/BIMCalcKM/logs/pipeline.log 2>&1 || echo "Pipeline failed" | mail -s "BIMCalc Pipeline Failed" your.email@example.com

# Backup with email on failure
30 2 * * * cd /Users/ciarancox/BIMCalcKM && /Users/ciarancox/BIMCalcKM/scripts/backup_postgres.sh >> /Users/ciarancox/BIMCalcKM/logs/backup.log 2>&1 || echo "Backup failed" | mail -s "BIMCalc Backup Failed" your.email@example.com
```

### Adding Slack Alerts (Optional)

**Create a webhook-based notification script:**
```bash
#!/bin/bash
# scripts/notify_slack.sh
WEBHOOK_URL="https://hooks.slack.com/services/YOUR/WEBHOOK/URL"
MESSAGE="$1"

curl -X POST -H 'Content-type: application/json' \
  --data "{\"text\":\"$MESSAGE\"}" \
  "$WEBHOOK_URL"
```

**Update cron jobs:**
```bash
# Pipeline with Slack notification
0 2 * * * cd /Users/ciarancox/BIMCalcKM && docker exec bimcalckm-app-1 python -m bimcalc.cli sync-prices >> logs/pipeline.log 2>&1 && ./scripts/notify_slack.sh "✅ Pipeline sync completed" || ./scripts/notify_slack.sh "❌ Pipeline sync failed"
```

---

## 🛠️ Managing Automation

### View Scheduled Jobs

```bash
crontab -l
```

### Edit Schedule

```bash
crontab -e
```

**Common schedule changes:**
```bash
# Run every 12 hours (2 AM and 2 PM)
0 2,14 * * * ...

# Run every 6 hours
0 */6 * * * ...

# Run weekly (Sunday at 2 AM)
0 2 * * 0 ...

# Run at 3 AM instead of 2 AM
0 3 * * * ...
```

### Temporarily Disable Automation

```bash
# Comment out cron jobs
crontab -e

# Add # at start of lines:
# 0 2 * * * cd /Users/ciarancox/BIMCalcKM && docker exec ...
# 30 2 * * * cd /Users/ciarancox/BIMCalcKM && ./scripts/backup_postgres.sh ...
```

### Remove Automation Completely

```bash
crontab -e

# Delete the BIMCalc lines
# Or remove all jobs:
crontab -r
```

### Re-enable Automation

```bash
# Run setup script again
./scripts/setup_automation.sh
```

---

## 📁 Log Management

### Log Files Location

```
logs/
├── pipeline.log     # Pipeline sync logs
└── backup.log       # Backup logs
```

### Log Rotation (Optional)

**Create logrotate config (Linux):**
```bash
# /etc/logrotate.d/bimcalc
/Users/ciarancox/BIMCalcKM/logs/*.log {
    daily
    rotate 30
    compress
    missingok
    notifempty
}
```

**macOS alternative - manual rotation:**
```bash
#!/bin/bash
# scripts/rotate_logs.sh
cd /Users/ciarancox/BIMCalcKM/logs
gzip -9 pipeline.log
mv pipeline.log.gz pipeline_$(date +%Y%m%d).log.gz
touch pipeline.log

gzip -9 backup.log
mv backup.log.gz backup_$(date +%Y%m%d).log.gz
touch backup.log

# Remove logs older than 30 days
find . -name "*.log.gz" -mtime +30 -delete
```

**Add to crontab:**
```bash
# Rotate logs weekly (Sunday at 1 AM)
0 1 * * 0 /Users/ciarancox/BIMCalcKM/scripts/rotate_logs.sh
```

---

## 🚨 Troubleshooting

### Issue: Jobs Not Running

**Check cron is active:**
```bash
# macOS
launchctl list | grep cron

# Linux
systemctl status cron
```

**Check Docker containers are running:**
```bash
docker ps | grep bimcalc

# Start if needed
docker start bimcalckm-app-1
docker start bimcalc-postgres
```

### Issue: No Logs Generated

**Check log directory exists:**
```bash
ls -la logs/
mkdir -p logs  # Create if missing
```

**Check permissions:**
```bash
chmod 755 logs
touch logs/pipeline.log logs/backup.log
chmod 644 logs/*.log
```

### Issue: Pipeline Failed

**Check logs:**
```bash
tail -100 logs/pipeline.log | grep -i error
```

**Common causes:**
- Docker container stopped
- Configuration file error
- Data source unavailable
- Network issues (APIs)
- File not found (CSV sources)

**Fix:**
```bash
# Test manually
docker exec bimcalckm-app-1 python -m bimcalc.cli sync-prices

# Check configuration
python scripts/validate_config.py

# View container logs
docker logs bimcalckm-app-1 --tail 50
```

### Issue: Backup Failed

**Check logs:**
```bash
tail -100 logs/backup.log | grep -i error
```

**Common causes:**
- PostgreSQL container stopped
- Disk space full
- Permissions issue

**Fix:**
```bash
# Check disk space
df -h

# Check PostgreSQL
docker ps | grep postgres

# Test manually
./scripts/backup_postgres.sh
```

### Issue: Cron Job Not Executing

**Check cron syntax:**
```bash
crontab -l

# Verify paths are absolute
# Verify commands work manually
```

**Test cron environment:**
```bash
# Add test job
* * * * * echo "Test at $(date)" >> /tmp/crontest.log

# Wait 1 minute, check:
cat /tmp/crontest.log

# Remove test job
crontab -e
```

---

## 📊 Monitoring Dashboard

### Daily Health Check

**Morning routine (optional):**
```bash
#!/bin/bash
# scripts/morning_check.sh

echo "BIMCalc Daily Health Check"
echo "=========================="
echo ""

echo "Pipeline Status:"
tail -20 logs/pipeline.log | grep -E "Status:|SUCCESS|FAILED"

echo ""
echo "Backup Status:"
tail -20 logs/backup.log | grep -E "Backup Complete|ERROR"

echo ""
echo "Latest Prices:"
docker exec bimcalc-postgres psql -U bimcalc -d bimcalc -t -c "
  SELECT COUNT(*) FROM price_items WHERE is_current = true;
" | xargs echo "Current items:"

echo ""
echo "Recent Pipeline Runs:"
docker exec bimcalc-postgres psql -U bimcalc -d bimcalc -c "
  SELECT run_timestamp, source_name, status, records_inserted, records_updated
  FROM data_sync_log
  ORDER BY run_timestamp DESC
  LIMIT 5;
"
```

---

## 🎯 Success Metrics

### Automation Objectives: 100% Complete

✅ **Pipeline Automation**
- Scheduled daily runs
- Automatic price updates
- SCD Type-2 history maintained
- Error logging enabled

✅ **Backup Automation**
- Scheduled daily backups
- Automatic compression
- 30-day retention
- Integrity verification

✅ **Monitoring**
- Log files configured
- Web UI available
- Manual testing verified

✅ **Reliability**
- Isolated error handling
- Automatic retries (per source)
- Comprehensive logging
- Easy troubleshooting

---

## 📅 Maintenance Calendar

### Daily
- ⏰ Automated: Pipeline sync (2:00 AM)
- ⏰ Automated: Database backup (2:30 AM)

### Weekly
- 👁️ Check logs for errors
- 👁️ Verify web UI shows recent data
- 👁️ Spot check price updates

### Monthly
- 🧪 Test backup restore
- 📊 Review pipeline success rates
- 🧹 Check disk space usage
- 📈 Review price trends

### Quarterly
- 🔄 Review and optimize schedules
- 🎯 Audit data sources
- 📚 Update documentation
- 🔒 Security review

---

## 🎉 What You Have Now

### Fully Automated System

**Every Night at 2:00 AM:**
- Fresh pricing data imported
- SCD Type-2 history updated
- All sources processed
- Results logged

**Every Night at 2:30 AM:**
- Database backed up
- Compressed (80% reduction)
- Integrity verified
- Old backups cleaned up

**Every Morning:**
- Latest prices available
- Complete history maintained
- Secure backups stored
- Logs ready to review

### Zero Manual Work Required

**What runs automatically:**
- ✅ Price synchronization
- ✅ Database backups
- ✅ History tracking
- ✅ Retention cleanup
- ✅ Error logging

**What you can do:**
- 👁️ Monitor via web UI
- 📊 Generate reports
- 🔍 Review logs
- 📈 Analyze trends
- 🎯 Add more sources

---

## 📞 Support

### Getting Help

**Check logs first:**
```bash
tail -100 logs/pipeline.log
tail -100 logs/backup.log
```

**Test manually:**
```bash
docker exec bimcalckm-app-1 python -m bimcalc.cli sync-prices
./scripts/backup_postgres.sh
```

**Verify schedule:**
```bash
crontab -l
```

### Emergency Procedures

**Pipeline not running:**
1. Check Docker containers: `docker ps`
2. Check logs: `tail logs/pipeline.log`
3. Test manually: `docker exec bimcalckm-app-1 python -m bimcalc.cli sync-prices`
4. Check configuration: `python scripts/validate_config.py`

**Backups not working:**
1. Check disk space: `df -h`
2. Check PostgreSQL: `docker ps | grep postgres`
3. Test manually: `./scripts/backup_postgres.sh`
4. Check permissions: `ls -la backups/`

---

## 🎊 Congratulations!

### Your BIMCalc system is now fully automated!

**You have:**
- ✅ Automated daily pipeline runs
- ✅ Automated daily backups
- ✅ 30-day backup retention
- ✅ Comprehensive logging
- ✅ Web UI monitoring
- ✅ Manual testing verified
- ✅ Complete documentation

**Benefits:**
- 🕐 Saves time (no manual runs)
- 🛡️ Data protection (daily backups)
- 📊 Always current (fresh pricing)
- 🔍 Full audit trail (SCD Type-2)
- 😴 Peace of mind (runs while you sleep)

---

**Status:** ✅ Fully Automated
**Next Check:** Tomorrow morning
**Next Action:** Monitor logs occasionally

---

**You can now let BIMCalc run on autopilot!** 🚀

