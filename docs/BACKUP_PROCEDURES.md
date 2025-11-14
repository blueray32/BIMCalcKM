# BIMCalc Backup & Restore Procedures

**Version:** 1.0
**Last Updated:** November 13, 2024
**Status:** Production Ready

---

## Table of Contents

1. [Overview](#overview)
2. [Quick Start](#quick-start)
3. [Backup Procedures](#backup-procedures)
4. [Restore Procedures](#restore-procedures)
5. [Automated Backups](#automated-backups)
6. [Retention Policy](#retention-policy)
7. [Off-Site Backups](#off-site-backups)
8. [Monitoring](#monitoring)
9. [Testing](#testing)
10. [Troubleshooting](#troubleshooting)

---

## Overview

BIMCalc uses PostgreSQL in Docker for production data storage. This document covers:
- Automated and manual backup procedures
- Point-in-time restore procedures
- Retention and archival policies
- Disaster recovery planning

### Backup Strategy

**3-2-1 Rule:**
- **3** copies of your data
- **2** different storage media
- **1** copy off-site

**Our Implementation:**
- Primary: PostgreSQL in Docker (live data)
- Secondary: Local compressed backups (./backups/)
- Tertiary: Off-site backups (cloud/network - optional)

---

## Quick Start

### Run a Manual Backup

```bash
./scripts/backup_postgres.sh
```

Output shows:
- Database size
- Record counts
- Backup file location
- Compression status
- Integrity verification

### Restore from Backup

```bash
./scripts/restore_postgres.sh ./backups/bimcalc_postgres_backup_YYYYMMDD_HHMMSS.sql.gz
```

⚠️ **Warning:** This replaces the current database!

---

## Backup Procedures

### 1. Manual Backup

**Command:**
```bash
cd /Users/ciarancox/BIMCalcKM
./scripts/backup_postgres.sh
```

**What it does:**
1. Checks PostgreSQL container is running
2. Collects database statistics
3. Creates SQL dump using `pg_dump`
4. Compresses with gzip (saves ~75% space)
5. Verifies backup integrity
6. Cleans old backups (>30 days)
7. Lists current backups

**Output Example:**
```
=========================================
BIMCalc PostgreSQL Backup (Docker)
=========================================

📊 Checking database size...
   Database size: 8676 kB
📊 Counting records...
   Price items: 32
   Pipeline runs: 1

🔄 Creating backup...
✅ Backup created: ./backups/bimcalc_postgres_backup_20251113_233752.sql (72K)
🗜️  Compressing backup...
✅ Compressed: ./backups/bimcalc_postgres_backup_20251113_233752.sql.gz (16K)

🔍 Verifying backup integrity...
✅ Backup integrity verified (compressed)

📁 Current backups:
   ./backups/bimcalc_postgres_backup_20251113_233752.sql.gz (14K)
   Total backups: 1
   Total size: 16K

✅ Backup Complete
```

### 2. Custom Backup Location

```bash
./scripts/backup_postgres.sh /path/to/custom/backups
```

### 3. Before Major Changes

**Always backup before:**
- Upgrading BIMCalc
- Migrating schemas
- Bulk data operations
- Major configuration changes

```bash
# Pre-upgrade backup
./scripts/backup_postgres.sh ./backups/pre-upgrade
```

---

## Restore Procedures

### Full Restore

**Command:**
```bash
./scripts/restore_postgres.sh <backup_file>
```

**Process:**
1. Shows current database statistics
2. Asks for confirmation (type "yes")
3. Stops application container
4. Drops existing database
5. Creates fresh database
6. Restores from backup
7. Verifies restoration
8. Restarts application
9. Checks web UI is responding

**Example:**
```bash
./scripts/restore_postgres.sh ./backups/bimcalc_postgres_backup_20251113_233752.sql.gz
```

**Output:**
```
=========================================
BIMCalc PostgreSQL Restore (Docker)
=========================================

📊 Current database stats:
   Price items: 32
   Pipeline runs: 1

⚠️  WARNING: This will REPLACE the current database!
   Backup file: ./backups/bimcalc_postgres_backup_20251113_233752.sql.gz

Are you sure you want to continue? (yes/no): yes

🛑 Stopping application...
🗑️  Dropping existing database...
🆕 Creating fresh database...
📥 Restoring backup...
🔍 Verifying restoration...
   Price items: 32
   Pipeline runs: 1

🚀 Starting application...
⏳ Waiting for application to be ready...
✅ Application is responding

✅ Restore Complete

Web UI: http://localhost:8001
```

### Point-in-Time Restore

To restore to a specific date:

```bash
# List backups
ls -lh ./backups/

# Choose backup from desired date
./scripts/restore_postgres.sh ./backups/bimcalc_postgres_backup_20251110_020000.sql.gz
```

### Partial Restore (Table-Level)

To restore specific tables only:

```bash
# Extract specific table from backup
gunzip -c ./backups/bimcalc_postgres_backup_20251113_233752.sql.gz | \
  grep -A 1000 "CREATE TABLE price_items" > price_items_only.sql

# Restore just that table
docker exec -i bimcalc-postgres psql -U bimcalc -d bimcalc < price_items_only.sql
```

---

## Automated Backups

### Option 1: Cron Job (Recommended)

**Setup:**
```bash
./scripts/setup_backup_schedule.sh cron
```

**Or manually edit crontab:**
```bash
crontab -e
```

**Add this line:**
```cron
# BIMCalc daily backup at 2:00 AM
0 2 * * * cd /Users/ciarancox/BIMCalcKM && /Users/ciarancox/BIMCalcKM/scripts/backup_postgres.sh >> /Users/ciarancox/BIMCalcKM/logs/backup.log 2>&1
```

**Verify cron job:**
```bash
crontab -l | grep backup
```

**Common Schedules:**
```cron
# Daily at 2 AM
0 2 * * * ...

# Every 12 hours
0 */12 * * * ...

# Weekly (Sunday at 3 AM)
0 3 * * 0 ...

# Monthly (1st day at 4 AM)
0 4 1 * * ...
```

### Option 2: Systemd Timer

**Setup:**
```bash
./scripts/setup_backup_schedule.sh systemd
```

**Install (requires sudo):**
```bash
sudo cp /tmp/bimcalc-backup.service /etc/systemd/system/
sudo cp /tmp/bimcalc-backup.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable bimcalc-backup.timer
sudo systemctl start bimcalc-backup.timer
```

**Check status:**
```bash
sudo systemctl status bimcalc-backup.timer
sudo systemctl list-timers bimcalc-backup.timer
```

**View logs:**
```bash
journalctl -u bimcalc-backup.service -f
```

---

## Retention Policy

### Default Configuration

**Current Setting:** 30 days

Configured in:
- `scripts/backup_postgres.sh` (RETENTION_DAYS=30)
- `config/backup_config.sh`

### Customize Retention

Edit `config/backup_config.sh`:
```bash
# Change retention period
export BACKUP_RETENTION_DAYS=90  # 90 days
```

### Recommended Retention Periods

| Use Case | Retention | Reason |
|----------|-----------|--------|
| Development | 7 days | Frequent changes, less critical |
| Production | 30 days | Balance of safety and storage |
| Compliance | 90 days | Regulatory requirements |
| Archival | 365 days | Long-term audit trail |

### Manual Cleanup

**Remove all backups older than 60 days:**
```bash
find ./backups -name "bimcalc_postgres_backup_*.sql.gz" -mtime +60 -delete
```

**Remove backups by size (keep only latest 10):**
```bash
ls -t ./backups/bimcalc_postgres_backup_*.sql.gz | tail -n +11 | xargs rm -f
```

### Check Storage Usage

```bash
# Total backup size
du -sh ./backups

# Individual backup sizes
ls -lh ./backups/

# Largest backups
du -h ./backups/* | sort -hr | head -10
```

---

## Off-Site Backups

### Why Off-Site?

Protects against:
- Hardware failure
- Ransomware
- Physical disasters (fire, flood)
- Accidental deletion
- Site-wide outages

### Option 1: AWS S3

**Setup AWS CLI:**
```bash
brew install awscli
aws configure
```

**Manual sync:**
```bash
aws s3 sync ./backups s3://my-bimcalc-backups/backups/ --storage-class STANDARD_IA
```

**Automated (add to cron):**
```bash
# After backup, sync to S3
0 3 * * * cd /Users/ciarancox/BIMCalcKM && aws s3 sync ./backups s3://my-bimcalc-backups/backups/ >> logs/backup.log 2>&1
```

**Cost estimate:** ~$0.0125/GB/month (Standard-IA)

### Option 2: Network Drive

**Mount network drive:**
```bash
# Create mount point
mkdir -p /mnt/backup-drive

# Mount (example for NFS)
sudo mount -t nfs 192.168.1.100:/backups /mnt/backup-drive
```

**Automated sync:**
```bash
# After backup, copy to network drive
rsync -av --delete ./backups/ /mnt/backup-drive/bimcalc/
```

### Option 3: Cloud Storage (General)

**Rclone (supports many providers):**
```bash
# Install rclone
brew install rclone

# Configure remote
rclone config

# Sync backups
rclone sync ./backups remote:bimcalc-backups
```

Supports:
- Google Drive
- Dropbox
- OneDrive
- Azure Blob
- Backblaze B2
- Many others

---

## Monitoring

### Check Backup Status

**View backup log:**
```bash
tail -f logs/backup.log
```

**Check latest backup:**
```bash
ls -lht ./backups/ | head -5
```

**Verify backup is recent:**
```bash
find ./backups -name "*.sql.gz" -mtime -1  # Backups within 24 hours
```

### Backup Health Check

**Create monitoring script:**
```bash
#!/bin/bash
# Check if backup is less than 25 hours old

LATEST_BACKUP=$(find ./backups -name "*.sql.gz" -mtime -1 | head -1)

if [ -z "$LATEST_BACKUP" ]; then
    echo "❌ ALERT: No backup found within 24 hours!"
    # Send alert (email, Slack, etc.)
    exit 1
else
    echo "✅ Recent backup found: $LATEST_BACKUP"
    exit 0
fi
```

### Automated Alerts

**Email on backup failure (using mail):**
```bash
# In cron job
0 2 * * * cd /path && ./scripts/backup_postgres.sh || echo "Backup failed" | mail -s "BIMCalc Backup Failed" admin@example.com
```

**Slack webhook notification:**
```bash
# After backup
curl -X POST -H 'Content-type: application/json' \
  --data '{"text":"✅ BIMCalc backup completed successfully"}' \
  https://hooks.slack.com/services/YOUR/WEBHOOK/URL
```

---

## Testing

### Test Backup Integrity

**Verify compressed backup:**
```bash
gzip -t ./backups/bimcalc_postgres_backup_*.sql.gz
```

**Check SQL syntax:**
```bash
gunzip -c backup.sql.gz | head -100
```

### Test Restore Procedure

**Best Practice:** Test restore quarterly

**Create test database:**
```bash
# 1. Create test database
docker exec bimcalc-postgres psql -U bimcalc -d postgres \
  -c "CREATE DATABASE bimcalc_test OWNER bimcalc;"

# 2. Restore to test database
gunzip -c ./backups/latest_backup.sql.gz | \
  docker exec -i bimcalc-postgres psql -U bimcalc -d bimcalc_test

# 3. Verify data
docker exec bimcalc-postgres psql -U bimcalc -d bimcalc_test \
  -c "SELECT COUNT(*) FROM price_items;"

# 4. Clean up
docker exec bimcalc-postgres psql -U bimcalc -d postgres \
  -c "DROP DATABASE bimcalc_test;"
```

### Disaster Recovery Drill

**Schedule:** Annually

**Procedure:**
1. Take fresh backup
2. Simulate total data loss (drop database)
3. Restore from backup
4. Verify all data intact
5. Test application functionality
6. Document time to recovery (RTO)
7. Document data loss (RPO)

---

## Troubleshooting

### Issue: Backup Script Fails

**Error:** "PostgreSQL container is not running"

**Solution:**
```bash
docker ps | grep postgres
docker start bimcalc-postgres
```

### Issue: Insufficient Disk Space

**Check disk usage:**
```bash
df -h
du -sh ./backups
```

**Solutions:**
1. Reduce retention period
2. Move backups to larger drive
3. Clean old backups manually
4. Enable compression (already default)

### Issue: Restore Fails

**Error:** "DROP DATABASE cannot run inside a transaction block"

**Solution:** Use restore script, not manual psql commands

### Issue: Backup Takes Too Long

**Current database is large**

**Solutions:**
1. **Parallel dump:**
```bash
docker exec bimcalc-postgres pg_dump -U bimcalc -d bimcalc -Fd -j 4 -f /tmp/backup
```

2. **Exclude large tables:**
```bash
docker exec bimcalc-postgres pg_dump -U bimcalc -d bimcalc --exclude-table=logs > backup.sql
```

3. **Schedule during low-traffic:**
   - Run backups at night
   - Use read replicas if available

### Issue: Backup File Corrupted

**Verify:**
```bash
gzip -t backup.sql.gz  # Test compression
gunzip -c backup.sql.gz | head  # Check contents
```

**Prevention:**
- Enable integrity verification (already in script)
- Keep multiple backup copies
- Test restores regularly

---

## Best Practices

### DO ✅

1. **Test restores regularly** - Untested backups are useless
2. **Automate backups** - Humans forget
3. **Keep multiple copies** - Follow 3-2-1 rule
4. **Monitor backup status** - Set up alerts
5. **Document procedures** - Others need to restore too
6. **Backup before changes** - Always!
7. **Verify backup integrity** - Automated in script
8. **Secure backups** - Encrypt if storing off-site

### DON'T ❌

1. **Don't store only one backup** - Redundancy is critical
2. **Don't skip testing restores** - Assume nothing
3. **Don't ignore backup failures** - Fix immediately
4. **Don't backup to same disk** - Defeats the purpose
5. **Don't forget to backup config** - Scripts need config too
6. **Don't leave backups unencrypted** - Security matters
7. **Don't wait until disaster** - Test procedures now

---

## Recovery Time Objectives

### Target RTOs

| Scenario | Target RTO | Actual RTO |
|----------|------------|------------|
| Full restore | < 5 minutes | ~3 minutes |
| Table-level restore | < 2 minutes | ~1 minute |
| Point-in-time restore | < 10 minutes | ~5 minutes |

### Recovery Point Objectives

| Backup Frequency | RPO | Data Loss |
|------------------|-----|-----------|
| Continuous (WAL) | < 1 minute | Minimal |
| Hourly | 1 hour | Acceptable |
| Daily | 24 hours | Standard |

**Current RPO:** 24 hours (daily backups)

**To improve RPO:**
- Increase backup frequency
- Enable PostgreSQL WAL archiving
- Use streaming replication

---

## Compliance & Auditing

### Backup Audit Log

**Track:**
- Backup timestamp
- Backup size
- Records backed up
- Success/failure status
- Who initiated backup

**Log file:** `logs/backup.log`

**Parse log:**
```bash
grep "Backup Complete" logs/backup.log | tail -10
```

### Compliance Requirements

**For GDPR/SOC2/ISO27001:**
1. ✅ Regular backups (daily)
2. ✅ Backup integrity verification
3. ✅ Off-site storage (configure)
4. ✅ Access controls (file permissions)
5. ✅ Audit logging (backup.log)
6. ✅ Tested restore procedures
7. ⚠️ Encryption (add if needed)
8. ⚠️ Retention policy (documented)

---

## Quick Reference

### Essential Commands

```bash
# Manual backup
./scripts/backup_postgres.sh

# Restore from backup
./scripts/restore_postgres.sh <backup_file>

# List backups
ls -lh ./backups/

# Check backup age
find ./backups -name "*.sql.gz" -mtime -1

# Test backup integrity
gzip -t ./backups/*.sql.gz

# View backup log
tail -f logs/backup.log

# Setup automated backups
./scripts/setup_backup_schedule.sh cron

# Check disk usage
du -sh ./backups

# Clean old backups (>60 days)
find ./backups -name "*.sql.gz" -mtime +60 -delete
```

---

## Support

### Getting Help

**Issue:** Backup problems
**Contact:** Check logs first, then admin

**Documentation:**
- This file: `docs/BACKUP_PROCEDURES.md`
- Scripts: `scripts/backup_postgres.sh`
- Config: `config/backup_config.sh`

### Emergency Contacts

**Database Administrator:** [Your contact]
**System Administrator:** [Your contact]
**After-hours support:** [Your contact]

---

**Document Version:** 1.0
**Last Review:** November 13, 2024
**Next Review:** February 13, 2025 (quarterly)
**Owner:** BIMCalc Operations Team

---

## Appendix: Configuration Files

### A. Backup Script Location
```
/Users/ciarancox/BIMCalcKM/scripts/backup_postgres.sh
```

### B. Restore Script Location
```
/Users/ciarancox/BIMCalcKM/scripts/restore_postgres.sh
```

### C. Setup Script Location
```
/Users/ciarancox/BIMCalcKM/scripts/setup_backup_schedule.sh
```

### D. Configuration Location
```
/Users/ciarancox/BIMCalcKM/config/backup_config.sh
```

### E. Backup Storage Location
```
/Users/ciarancox/BIMCalcKM/backups/
```

### F. Log File Location
```
/Users/ciarancox/BIMCalcKM/logs/backup.log
```

---

**END OF DOCUMENT**
