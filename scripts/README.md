# BIMCalc Operational Scripts

This directory contains helper scripts for day-to-day operations of the BIMCalc live pricing pipeline.

## Available Scripts

### 1. Dashboard (`dashboard.py`)

Quick visual overview of system health and statistics.

**Usage:**
```bash
python scripts/dashboard.py
```

**What it shows:**
- System overview (database size, item counts, mappings)
- Pipeline status (recent runs, failures)
- Price data (changes, regional breakdown, classifications)
- Most volatile items (frequent price changes)
- Health check (recent runs, failures, data freshness)
- Quick action commands

**Example Output:**
```
======================================================================
                    BIMCalc Pipeline Dashboard
======================================================================

📊 SYSTEM OVERVIEW
----------------------------------------------------------------------
  Database Size:        340.0 KB
  BIM Items:            246
  Price Items:          65 current / 1 historical
  Mappings:             2 active / 2 total

⚙️  PIPELINE STATUS
----------------------------------------------------------------------
  Total Runs:           9
  Runs (24h):           9
  Failures (7d):        3
  Last Run:             2025-11-13 22:43:58
    Source:             test_prices_local
    Status:             ✅ SUCCESS
    Records Processed:  1
    Duration:           0ms

✅ OVERALL STATUS: HEALTHY
```

---

### 2. Health Check (`health_check.sh`)

Automated health verification for monitoring systems.

**Usage:**
```bash
./scripts/health_check.sh
```

**What it checks:**
- Database file exists
- Database size
- Last pipeline run status
- Recent failures (last 5 runs)
- Data freshness per source
- Stale sources (no updates in 7+ days)

**Exit codes:**
- `0` - Health check passed
- `1` - Health check failed (for CI/CD integration)

**Integration:**
```bash
# Add to monitoring system
*/30 * * * * /path/to/BIMCalcKM/scripts/health_check.sh || echo "BIMCalc health check failed" | mail -s "Alert" ops@example.com

# Add to Nagios/Icinga
check_command = /usr/local/bin/health_check.sh
```

---

### 3. Backup Database (`backup_database.sh`)

Create timestamped database backups with automatic retention.

**Usage:**
```bash
# Default backup to ./backups
./scripts/backup_database.sh

# Custom backup directory
./scripts/backup_database.sh /mnt/backups/bimcalc
```

**Features:**
- Creates timestamped backup: `bimcalc_backup_YYYYMMDD_HHMMSS.db`
- Verifies backup integrity
- Automatic cleanup of backups older than 30 days
- Shows current backup inventory

**Automated backups:**
```bash
# Add to crontab - daily at 1 AM
0 1 * * * /path/to/BIMCalcKM/scripts/backup_database.sh /backups/bimcalc
```

**Recovery:**
```bash
# List available backups
ls -lh backups/bimcalc_backup_*.db

# Restore from backup
cp backups/bimcalc_backup_20251113_223541.db bimcalc.db

# Verify integrity
python -m bimcalc.cli pipeline-status --last 1
```

---

### 4. Validate Config (`validate_config.py`)

Pre-flight validation of pipeline configuration before running.

**Usage:**
```bash
python scripts/validate_config.py
```

**What it validates:**
- Configuration file exists and is valid YAML
- All sources have required fields (name, type, enabled, config)
- No duplicate source names
- CSV sources: file_path exists, region set, column_mapping present
- API sources: api_url present, API keys in environment, rate limits reasonable
- Required mapped fields present (item_code, description, unit_price)

**Exit codes:**
- `0` - Validation passed
- `1` - Validation failed (errors found)

**Example output:**
```
✅ Configuration validation PASSED
   Ready to run pipeline with 1 enabled source(s)
```

**Use before pipeline runs:**
```bash
# Validate before running pipeline
python scripts/validate_config.py && python -m bimcalc.cli sync-prices

# In CI/CD
- name: Validate config
  run: python scripts/validate_config.py
```

---

## Recommended Operational Workflows

### Daily Operations

**Morning Check:**
```bash
# Quick system overview
python scripts/dashboard.py

# Check last night's pipeline run
python -m bimcalc.cli pipeline-status --last 1
```

**Before manual pipeline run:**
```bash
# Validate configuration
python scripts/validate_config.py

# Run pipeline
python -m bimcalc.cli sync-prices

# Verify results
python scripts/dashboard.py
```

---

### Weekly Maintenance

```bash
# Review week's performance
python -m bimcalc.cli pipeline-status --last 7

# Check database size growth
python scripts/dashboard.py | grep "Database Size"

# Verify backups
ls -lh backups/

# Health check
./scripts/health_check.sh
```

---

### Monthly Operations

```bash
# Full system review
python scripts/dashboard.py

# Analyze price volatility
python scripts/dashboard.py | grep -A 10 "MOST VOLATILE"

# Review configuration for new sources
python scripts/validate_config.py

# Test configuration with dry-run
python -m bimcalc.cli sync-prices --dry-run

# Create manual backup before changes
./scripts/backup_database.sh backups/monthly
```

---

### Troubleshooting Workflow

**Pipeline failure detected:**

1. **Check dashboard**
   ```bash
   python scripts/dashboard.py
   ```

2. **View failure details**
   ```bash
   python -m bimcalc.cli pipeline-status --last 5
   ```

3. **Validate configuration**
   ```bash
   python scripts/validate_config.py
   ```

4. **Check specific source**
   ```bash
   python -m bimcalc.cli sync-prices --source problem_source --dry-run
   ```

5. **Fix configuration and retry**
   ```bash
   # Edit config/pipeline_sources.yaml
   vim config/pipeline_sources.yaml

   # Validate
   python scripts/validate_config.py

   # Test
   python -m bimcalc.cli sync-prices --source problem_source
   ```

---

## Automation Examples

### Cron Jobs

**Complete automation setup:**

```bash
# Edit crontab
crontab -e

# Add these lines:

# 1. Backup database daily at 1 AM
0 1 * * * cd /path/to/BIMCalcKM && ./scripts/backup_database.sh /backups/bimcalc

# 2. Run pipeline daily at 2 AM
0 2 * * * cd /path/to/BIMCalcKM && python -m bimcalc.cli sync-prices >> /var/log/bimcalc_pipeline.log 2>&1

# 3. Health check every 6 hours
0 */6 * * * cd /path/to/BIMCalcKM && ./scripts/health_check.sh || echo "BIMCalc health check failed" | mail -s "Alert" ops@example.com

# 4. Weekly dashboard report (Monday 9 AM)
0 9 * * 1 cd /path/to/BIMCalcKM && python scripts/dashboard.py | mail -s "BIMCalc Weekly Report" team@example.com
```

---

### systemd Service (Linux)

**Pipeline Service:**

`/etc/systemd/system/bimcalc-sync.service`:
```ini
[Unit]
Description=BIMCalc Price Sync
After=network.target

[Service]
Type=oneshot
User=bimcalc
WorkingDirectory=/opt/bimcalc
ExecStartPre=/opt/bimcalc/scripts/validate_config.py
ExecStart=/opt/bimcalc/venv/bin/python -m bimcalc.cli sync-prices
StandardOutput=append:/var/log/bimcalc_pipeline.log
StandardError=append:/var/log/bimcalc_pipeline.log
```

**Pipeline Timer:**

`/etc/systemd/system/bimcalc-sync.timer`:
```ini
[Unit]
Description=BIMCalc nightly price sync

[Timer]
OnCalendar=daily
OnCalendar=02:00
Persistent=true

[Install]
WantedBy=timers.target
```

**Enable:**
```bash
systemctl enable bimcalc-sync.timer
systemctl start bimcalc-sync.timer
systemctl status bimcalc-sync.timer
```

---

### Monitoring Integration

**Prometheus Metrics:**

```bash
# Add to Prometheus config
scrape_configs:
  - job_name: 'bimcalc'
    static_configs:
      - targets: ['localhost:9090']
    metrics_path: '/metrics'
```

**Grafana Dashboard:**

Key metrics to monitor:
- Pipeline run frequency
- Success/failure rate
- Records processed per run
- Duration per run
- Database size growth
- Price change frequency

---

### Alert Rules

**Email alerts on failure:**

```bash
# Add to health_check.sh
if [ "$LAST_STATUS" != "SUCCESS" ]; then
    # Send email
    echo "BIMCalc pipeline failed. Check logs: python -m bimcalc.cli pipeline-status --last 1" | \
        mail -s "BIMCalc Pipeline Alert" ops@example.com
fi
```

**Slack alerts:**

```bash
# Add webhook notification
SLACK_WEBHOOK="https://hooks.slack.com/services/YOUR/WEBHOOK/URL"

if [ "$LAST_STATUS" != "SUCCESS" ]; then
    curl -X POST $SLACK_WEBHOOK \
        -H 'Content-Type: application/json' \
        -d '{"text":"🚨 BIMCalc pipeline failed. Check dashboard."}'
fi
```

---

## Script Permissions

All scripts should be executable:

```bash
chmod +x scripts/*.sh
chmod +x scripts/*.py
```

---

## Environment Requirements

**Python scripts require:**
- Python 3.11+
- Dependencies from `requirements.txt`
- Access to `bimcalc.db`
- Access to `config/pipeline_sources.yaml`

**Shell scripts require:**
- Bash 4.0+
- Standard Unix tools (sqlite3, du, find, awk)

---

## Directory Structure

```
scripts/
├── README.md                 # This file
├── dashboard.py              # System overview dashboard
├── health_check.sh           # Health verification
├── backup_database.sh        # Database backup tool
└── validate_config.py        # Configuration validator

backups/                      # Created by backup script
├── bimcalc_backup_20251113_223541.db
└── bimcalc_backup_20251114_010000.db
```

---

## Support and Documentation

**Related documentation:**
- `/docs/PRODUCTION_OPERATIONS_GUIDE.md` - Comprehensive operations manual
- `/DEPLOYMENT_SUCCESS.md` - Initial deployment verification
- `/PIPELINE_UPGRADE_GUIDE.md` - Migration and upgrade procedures

**CLI commands:**
```bash
# Pipeline operations
python -m bimcalc.cli sync-prices       # Run pipeline
python -m bimcalc.cli sync-prices --dry-run  # Test without committing
python -m bimcalc.cli pipeline-status   # View run history
python -m bimcalc.cli pipeline-status --last 10  # Last 10 runs

# Database operations
python -m bimcalc.cli init              # Initialize database
python -m bimcalc.cli migrate --execute # Run migration
```

**Logs location:**
- Pipeline logs: `/var/log/bimcalc_pipeline.log` (or as configured)
- Health check logs: stdout (capture in monitoring system)

---

**Last Updated:** November 13, 2024
**Version:** 1.0
**Status:** Production Ready
