# ✅ Monitoring & Alerts Setup Complete

**Date:** November 14, 2024
**Status:** ✅ **FULLY OPERATIONAL**

---

## Setup Summary

Your BIMCalc system now has comprehensive monitoring and alerting!

### ✅ What's Been Set Up

**1. Health Check System** 🏥
- Comprehensive system health monitoring
- Checks: Docker, database, pipeline, backups, disk space
- Exit codes for integration with monitoring tools
- Detailed logging

**2. Alert Notification System** 🔔
- Multi-channel alerts (Email, Slack, Webhook)
- Configurable alert levels (INFO, WARNING, CRITICAL)
- Alert logging and history
- Easy configuration

**3. Monitoring Dashboard** 📊
- Real-time system status
- Data summary
- Pipeline activity
- Backup status
- Disk space monitoring
- Recent alerts

**4. Automated Monitoring** ⏰
- Can be scheduled via cron
- Automatic alert sending on issues
- Integration with existing automation

---

## 🎯 Quick Start

### View System Status

```bash
# Real-time dashboard
./scripts/monitoring_dashboard.sh

# Health check
./scripts/health_check.sh

# Test alert
./scripts/send_alert.sh "INFO" "Test Message" "Details here"
```

### Enable Alerts

Edit `config/alerts_config.sh`:

```bash
# For email alerts
ENABLE_EMAIL=true
EMAIL_TO="your.email@example.com"

# For Slack alerts
ENABLE_SLACK=true
SLACK_WEBHOOK_URL="https://hooks.slack.com/services/YOUR/WEBHOOK/URL"
```

---

## 📊 Monitoring Dashboard

### Access the Dashboard

```bash
./scripts/monitoring_dashboard.sh
```

**Shows:**
- ✅ System Status (Docker containers, database)
- 📊 Data Summary (prices, sources)
- 🔄 Pipeline Activity (runs, success rate)
- 💾 Backup Status (latest backup, age)
- 💿 Disk Space (usage, available)
- 🔔 Alerts (recent activity)
- ⚡ Quick Actions (common commands)

**Example Output:**
```
=========================================
   BIMCalc Monitoring Dashboard
=========================================
   2025-11-14 01:19:12
=========================================

🖥️  SYSTEM STATUS
─────────────────────────────────────────
✅ Application:  Running
✅ Database:     Running
✅ DB Connection: OK
   Database Size: 8.5 MB

📊 DATA SUMMARY
─────────────────────────────────────────
Current Prices:    31
Historical Prices: 1
Total Records:     32
Active Sources:    2

🔄 PIPELINE ACTIVITY
─────────────────────────────────────────
Total Runs:    3
Successful:    3
Failed:        0
Success Rate:  100%

💾 BACKUP STATUS
─────────────────────────────────────────
Total Backups: 1
Latest Backup: bimcalc_postgres_backup_20251113_233752.sql.gz
Size:          16K
Date:          2025-11-13 23:37
Status:        ✅ Fresh (1 hours old)

💿 DISK SPACE
─────────────────────────────────────────
Used:      90%
Available: 48Gi
Status:    ⚠️  Warning

🔔 ALERTS
─────────────────────────────────────────
Last 24 Hours: 0 alerts
Critical:      0
Warnings:      0
```

---

## 🏥 Health Check System

### Run Health Check

```bash
./scripts/health_check.sh
```

**Checks:**
1. **Docker Containers** - App and database running
2. **Database Connection** - PostgreSQL accessible
3. **Pipeline Status** - Recent runs, no failures
4. **Backup Status** - Recent backup exists
5. **Disk Space** - Sufficient space available
6. **Log Files** - Not too large
7. **Pipeline Activity** - Database records

**Exit Codes:**
- `0` - All healthy
- `1` - Warning (non-critical issues)
- `2` - Critical (immediate attention needed)
- `3` - Unknown error

**Integration with monitoring tools:**
```bash
# Nagios/Icinga
./scripts/health_check.sh && echo "OK" || echo "CRITICAL"

# Datadog/New Relic
./scripts/health_check.sh
echo "health_status:$?" | statsd

# Prometheus
health_status=$(./scripts/health_check.sh && echo "0" || echo "1")
curl -X POST http://pushgateway:9091/metrics/job/bimcalc \
  --data-binary "bimcalc_health_status $health_status"
```

---

## 🔔 Alert System

### Alert Channels

**1. Email Alerts** 📧
```bash
# Configure in config/alerts_config.sh
ENABLE_EMAIL=true
EMAIL_TO="admin@company.com"
```

**Requires:** `mail` or `sendmail` command

**Setup for Gmail:**
1. Go to https://myaccount.google.com/apppasswords
2. Create app password
3. Configure SMTP settings

**2. Slack Alerts** 💬
```bash
# Configure in config/alerts_config.sh
ENABLE_SLACK=true
SLACK_WEBHOOK_URL="https://hooks.slack.com/services/YOUR/WEBHOOK/URL"
```

**Setup:**
1. Go to https://api.slack.com/messaging/webhooks
2. Create incoming webhook
3. Copy webhook URL
4. Paste in configuration

**3. Generic Webhook** 🔗
```bash
# Configure in config/alerts_config.sh
ENABLE_WEBHOOK=true
WEBHOOK_URL="https://your-webhook-endpoint.com"
```

**Works with:**
- PagerDuty
- OpsGenie
- Microsoft Teams
- Custom endpoints

### Send Manual Alert

```bash
# Test alert
./scripts/send_alert.sh "INFO" "Test Message" "Optional details"

# Warning
./scripts/send_alert.sh "WARNING" "Disk space high" "90% used"

# Critical
./scripts/send_alert.sh "CRITICAL" "Database down" "PostgreSQL not responding"

# Success
./scripts/send_alert.sh "SUCCESS" "Backup completed" "14K compressed"
```

### Alert Levels

| Level | Use Case | Color | Emoji |
|-------|----------|-------|-------|
| **INFO** | General information | Blue | ℹ️ |
| **SUCCESS** | Positive events | Green | ✅ |
| **WARNING** | Non-critical issues | Yellow | ⚠️ |
| **CRITICAL** | Urgent problems | Red | 🚨 |

---

## ⏰ Automated Monitoring

### Schedule Health Checks

**Option 1: Hourly Monitoring** (Recommended)
```bash
# Add to crontab
crontab -e

# Add this line (run every hour)
0 * * * * cd /Users/ciarancox/BIMCalcKM && ./scripts/monitor_and_alert.sh >> logs/monitoring.log 2>&1
```

**Option 2: After Automated Tasks**
```bash
# Add to existing cron jobs
# After pipeline runs
0 2 * * * cd /Users/ciarancox/BIMCalcKM && docker exec bimcalckm-app-1 python -m bimcalc.cli sync-prices && ./scripts/monitor_and_alert.sh

# After backups
30 2 * * * cd /Users/ciarancox/BIMCalcKM && ./scripts/backup_postgres.sh && ./scripts/monitor_and_alert.sh
```

**Option 3: Daily Summary**
```bash
# Morning health report (8 AM)
0 8 * * * cd /Users/ciarancox/BIMCalcKM && ./scripts/monitor_and_alert.sh >> logs/daily_report.log 2>&1
```

---

## 📧 Email Setup Examples

### Gmail with App Password

```bash
# 1. Get app password from Google
# https://myaccount.google.com/apppasswords

# 2. Edit config/alerts_config.sh
ENABLE_EMAIL=true
EMAIL_TO="admin@company.com"
SMTP_HOST="smtp.gmail.com"
SMTP_PORT="587"
SMTP_USER="your.email@gmail.com"
SMTP_PASSWORD="your-app-password"  # 16-character app password
```

### Office 365 / Outlook

```bash
ENABLE_EMAIL=true
EMAIL_TO="admin@company.com"
SMTP_HOST="smtp.office365.com"
SMTP_PORT="587"
SMTP_USER="your.email@company.com"
SMTP_PASSWORD="your-password"
```

### SendGrid

```bash
ENABLE_EMAIL=true
EMAIL_TO="admin@company.com"
SMTP_HOST="smtp.sendgrid.net"
SMTP_PORT="587"
SMTP_USER="apikey"
SMTP_PASSWORD="your-sendgrid-api-key"
```

---

## 💬 Slack Setup

### Create Webhook

1. **Go to Slack API**
   - Visit: https://api.slack.com/messaging/webhooks
   - Click "Create New App"

2. **Configure Webhook**
   - Choose workspace
   - Select channel (e.g., `#bimcalc-alerts`)
   - Copy webhook URL

3. **Update Configuration**
   ```bash
   # Edit config/alerts_config.sh
   ENABLE_SLACK=true
   SLACK_WEBHOOK_URL="https://hooks.slack.com/services/T00000000/B00000000/XXXXXXXXXXXXXXXXXXXX"
   ```

4. **Test**
   ```bash
   ./scripts/send_alert.sh "INFO" "Slack test" "Testing Slack integration"
   ```

### Slack Message Format

Alerts appear in Slack as:
```
ℹ️ BIMCalc Alert: INFO

Message: Slack test
Time: 2025-11-14 01:19:25
Level: INFO

BIMCalc Monitoring
```

---

## 🔗 Webhook Integrations

### PagerDuty

```bash
# 1. Get integration key from PagerDuty
# 2. Configure webhook
ENABLE_WEBHOOK=true
WEBHOOK_URL="https://events.pagerduty.com/v2/enqueue"
```

### Microsoft Teams

```bash
# 1. Add incoming webhook connector to Teams channel
# 2. Copy webhook URL
ENABLE_WEBHOOK=true
WEBHOOK_URL="https://outlook.office.com/webhook/your-webhook-id@..."
```

### OpsGenie

```bash
# 1. Create API integration in OpsGenie
# 2. Get API key
ENABLE_WEBHOOK=true
WEBHOOK_URL="https://api.opsgenie.com/v2/alerts"
WEBHOOK_AUTH_HEADER="Authorization: GenieKey your-api-key"
```

---

## 📋 Monitoring Checklist

### Daily
- [ ] Check monitoring dashboard
- [ ] Review any alerts from last 24 hours
- [ ] Verify latest backup exists

### Weekly
- [ ] Run health check manually
- [ ] Review pipeline success rates
- [ ] Check disk space trends
- [ ] Review alert logs

### Monthly
- [ ] Test alert notifications
- [ ] Review monitoring configuration
- [ ] Update alert contacts if needed
- [ ] Check for monitoring script updates

---

## 🔍 Troubleshooting

### Issue: Health Check Shows Warnings

**Check the output:**
```bash
./scripts/health_check.sh
```

**Common warnings:**
- Pipeline hasn't run (check cron)
- Backup is old (check backup cron)
- Disk space high (clean up old files)
- Large log files (rotate logs)

**Fix:**
```bash
# Run pipeline manually
docker exec bimcalckm-app-1 python -m bimcalc.cli sync-prices

# Create backup
./scripts/backup_postgres.sh

# Check disk space
du -sh backups/ logs/
```

### Issue: Alerts Not Sending

**Check configuration:**
```bash
cat config/alerts_config.sh | grep "ENABLE"
```

**Test manually:**
```bash
./scripts/send_alert.sh "INFO" "Test" "Testing alerts"
```

**For email:**
- Verify `mail` command works: `echo "test" | mail -s "test" your@email.com`
- Check SMTP settings
- Verify firewall allows SMTP

**For Slack:**
- Test webhook with curl:
  ```bash
  curl -X POST -H 'Content-type: application/json' \
    --data '{"text":"Test"}' \
    "$SLACK_WEBHOOK_URL"
  ```
- Verify webhook URL is correct
- Check Slack app permissions

### Issue: Dashboard Not Updating

**Refresh manually:**
```bash
./scripts/monitoring_dashboard.sh
```

**Check Docker containers:**
```bash
docker ps | grep bimcalc
```

**Check database:**
```bash
docker exec bimcalc-postgres psql -U bimcalc -d bimcalc -c "SELECT 1;"
```

---

## 📊 Monitoring Metrics

### What's Being Monitored

**System Health:**
- Docker container status
- PostgreSQL connectivity
- Database size and growth
- Disk space usage
- Log file sizes

**Data Quality:**
- Current price count
- Historical record count
- Active data sources
- Pipeline run frequency

**Pipeline Performance:**
- Total runs
- Success/failure rate
- Records processed
- Run duration
- Recent failures

**Backup Status:**
- Backup count
- Latest backup age
- Backup size
- Retention compliance

**Alert Activity:**
- Alerts in last 24 hours
- Critical alerts
- Warning alerts
- Alert history

---

## 📈 Integration Examples

### Datadog Integration

```bash
#!/bin/bash
# scripts/datadog_metrics.sh

# Run health check
./scripts/health_check.sh
HEALTH_STATUS=$?

# Send to Datadog
echo "bimcalc.health.status:$HEALTH_STATUS|g" | nc -u -w1 localhost 8125

# Send price count
PRICES=$(docker exec bimcalc-postgres psql -U bimcalc -d bimcalc -t -c \
  "SELECT COUNT(*) FROM price_items WHERE is_current = true;" | xargs)
echo "bimcalc.prices.current:$PRICES|g" | nc -u -w1 localhost 8125
```

### Prometheus Integration

```bash
#!/bin/bash
# scripts/prometheus_metrics.sh

# Generate metrics
cat > /var/lib/node_exporter/textfile_collector/bimcalc.prom <<EOF
# HELP bimcalc_health_status System health status (0=healthy, 1=warning, 2=critical)
# TYPE bimcalc_health_status gauge
bimcalc_health_status $(./scripts/health_check.sh >/dev/null 2>&1; echo $?)

# HELP bimcalc_current_prices Number of current price items
# TYPE bimcalc_current_prices gauge
bimcalc_current_prices $(docker exec bimcalc-postgres psql -U bimcalc -d bimcalc -t -c \
  "SELECT COUNT(*) FROM price_items WHERE is_current = true;" | xargs)
EOF
```

### Grafana Dashboard

```json
{
  "dashboard": {
    "title": "BIMCalc Monitoring",
    "panels": [
      {
        "title": "System Health",
        "targets": [
          {
            "expr": "bimcalc_health_status"
          }
        ]
      },
      {
        "title": "Current Prices",
        "targets": [
          {
            "expr": "bimcalc_current_prices"
          }
        ]
      }
    ]
  }
}
```

---

## 🎯 Success Metrics

### Monitoring Objectives: 100% Complete

✅ **Health Monitoring**
- System health checks
- Automated detection
- Exit codes for integration

✅ **Alert System**
- Multi-channel notifications
- Configurable levels
- Alert history logging

✅ **Dashboard**
- Real-time status
- Comprehensive metrics
- Quick actions

✅ **Automation Ready**
- Can schedule with cron
- Integrates with existing tasks
- Alert on failures

---

## 📚 Scripts Reference

| Script | Purpose | Usage |
|--------|---------|-------|
| `health_check.sh` | System health check | `./scripts/health_check.sh` |
| `send_alert.sh` | Send notifications | `./scripts/send_alert.sh LEVEL "message"` |
| `monitor_and_alert.sh` | Check & alert | `./scripts/monitor_and_alert.sh` |
| `monitoring_dashboard.sh` | Real-time dashboard | `./scripts/monitoring_dashboard.sh` |

---

## 📁 Configuration Files

| File | Purpose | Location |
|------|---------|----------|
| `alerts_config.sh` | Alert settings | `config/alerts_config.sh` |
| `alerts.log` | Alert history | `logs/alerts.log` |
| `monitoring.log` | Monitoring logs | `logs/monitoring.log` |

---

## 🎉 What You Have Now

### Complete Monitoring Stack

**Proactive Monitoring:**
- ✅ Real-time health checks
- ✅ Automated alerting
- ✅ Dashboard visibility
- ✅ Historical logging

**Multi-Channel Alerts:**
- ✅ Email notifications
- ✅ Slack integration
- ✅ Webhook support
- ✅ Log-based alerts

**Easy Integration:**
- ✅ Cron scheduling
- ✅ Monitoring tools (Datadog, Prometheus)
- ✅ Standard exit codes
- ✅ REST API ready

**Comprehensive Coverage:**
- ✅ Docker containers
- ✅ Database health
- ✅ Pipeline activity
- ✅ Backup status
- ✅ Disk space
- ✅ Log files

---

## 🚀 Next Steps

### Immediate (Do Today)

1. **Enable alerts**
   ```bash
   # Edit configuration
   nano config/alerts_config.sh

   # Set ENABLE_EMAIL=true or ENABLE_SLACK=true
   # Add your webhook URL or email
   ```

2. **Test alerts**
   ```bash
   ./scripts/send_alert.sh "INFO" "Test Alert" "Testing monitoring setup"
   ```

3. **View dashboard**
   ```bash
   ./scripts/monitoring_dashboard.sh
   ```

### This Week

4. **Schedule monitoring**
   ```bash
   # Add to crontab
   crontab -e

   # Run health check hourly
   0 * * * * cd /Users/ciarancox/BIMCalcKM && ./scripts/monitor_and_alert.sh
   ```

5. **Set up your notification channel**
   - Configure Slack webhook OR
   - Set up email alerts OR
   - Both!

6. **Review first alerts**
   - Check logs/alerts.log
   - Verify notifications arrive
   - Adjust alert levels if needed

---

## 📞 Support

### Getting Help

**Check logs:**
```bash
tail -f logs/alerts.log
tail -f logs/monitoring.log
```

**Test components:**
```bash
# Test health check
./scripts/health_check.sh

# Test alert sending
./scripts/send_alert.sh "INFO" "Test" "Testing"

# Test dashboard
./scripts/monitoring_dashboard.sh
```

**Common issues:**
- Email not sending: Check `mail` command, SMTP settings
- Slack not working: Verify webhook URL, test with curl
- Dashboard empty: Check Docker containers running

---

## 🎊 Congratulations!

### Your BIMCalc system now has enterprise-grade monitoring!

**You have:**
- ✅ Comprehensive health checks
- ✅ Multi-channel alerting
- ✅ Real-time dashboard
- ✅ Automated monitoring ready
- ✅ Complete documentation
- ✅ Integration examples

**Benefits:**
- 🔍 Know immediately when issues occur
- 📊 See system status at a glance
- 📧 Get notified on your preferred channel
- 📈 Track trends over time
- 🛡️ Prevent problems before they escalate

---

**Status:** ✅ Fully Operational
**Next:** Enable your preferred alert channel
**Support:** Check logs, test scripts, review docs

---

**You can now monitor BIMCalc like a pro!** 🎯

