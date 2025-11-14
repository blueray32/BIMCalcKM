# BIMCalc Production Operations Guide

## Overview

This guide covers day-to-day operations of the BIMCalc live pricing pipeline in production. The system is now deployed and ready for operational use.

**Current Status:** ✅ Production Ready (Deployed: November 13, 2024)

---

## Daily Operations

### Monitoring Pipeline Health

```bash
# Check last 5 pipeline runs
python -m bimcalc.cli pipeline-status --last 5

# Check specific source performance
python -m bimcalc.cli pipeline-status --source test_prices_local

# View detailed logs
tail -f /var/log/bimcalc_pipeline.log
```

### Manual Pipeline Execution

```bash
# Dry run (test without committing)
python -m bimcalc.cli sync-prices --dry-run

# Full production run
python -m bimcalc.cli sync-prices

# Run specific source only
python -m bimcalc.cli sync-prices --source obo_q4_2024
```

### Querying Current Prices

```python
from bimcalc.db.connection import get_session
from bimcalc.db.price_queries import get_current_price, get_price_history

# Get current active price
async with get_session() as session:
    price = await get_current_price(session, "ELBOW-001", "UK")
    print(f"Current price: €{price.unit_price}")

# Get full price history
async with get_session() as session:
    history = await get_price_history(session, "ELBOW-001", "UK")
    for record in history:
        status = "CURRENT" if record.is_current else "EXPIRED"
        print(f"{status}: €{record.unit_price} from {record.valid_from} to {record.valid_to}")
```

### Historical Price Queries (Audit Support)

```python
from datetime import datetime
from bimcalc.db.price_queries import get_historical_price

# "What was the price on this date?"
as_of_date = datetime(2025, 11, 13, 22, 42, 0)
async with get_session() as session:
    price = await get_historical_price(session, "ELBOW-001", "UK", as_of_date)
    print(f"Price on {as_of_date}: €{price.unit_price}")
```

---

## Configuration Management

### Adding New Data Sources

1. **Edit `config/pipeline_sources.yaml`**

```yaml
sources:
  # Example: CSV file from manufacturer
  - name: obo_q1_2025
    type: csv
    enabled: true
    config:
      file_path: /data/prices/obo/OBO_Q1_2025_Pricelist.csv
      region: DE
      vendor_id: OBO_BETTERMANN
      column_mapping:
        "Artikel-Nr": "item_code"
        "Bezeichnung": "description"
        "Warengruppe": "classification_code"
        "Preis": "unit_price"
        "Währung": "currency"
        "Einheit": "unit"
        "Breite": "width_mm"
        "Höhe": "height_mm"
        "Material": "material"

  # Example: API source
  - name: rs_components_uk
    type: api
    enabled: true
    config:
      api_url: https://api.rs-online.com/v1/catalogue/products
      api_key_env: RS_API_KEY  # Set in environment
      region: UK
      vendor_id: RS_COMPONENTS
      rate_limit: 10  # requests per second
      pagination:
        page_size: 100
        max_pages: 500
```

2. **Test new source**

```bash
# Test with dry-run first
python -m bimcalc.cli sync-prices --source obo_q1_2025 --dry-run

# Check for errors
python -m bimcalc.cli pipeline-status --source obo_q1_2025
```

3. **Enable in production**

Once tested, the source will run automatically in scheduled pipeline executions.

---

## Automated Scheduling

### Option 1: Cron (Linux/macOS)

```bash
# Edit crontab
crontab -e

# Add nightly run at 2 AM
0 2 * * * cd /Users/ciarancox/BIMCalcKM && python -m bimcalc.cli sync-prices >> /var/log/bimcalc_pipeline.log 2>&1

# Add weekly health check at 9 AM Monday
0 9 * * 1 cd /Users/ciarancox/BIMCalcKM && python -m bimcalc.cli pipeline-status --last 7
```

### Option 2: systemd Timer (Linux)

Create `/etc/systemd/system/bimcalc-sync.service`:

```ini
[Unit]
Description=BIMCalc Price Sync
After=network.target

[Service]
Type=oneshot
User=bimcalc
WorkingDirectory=/opt/bimcalc
ExecStart=/opt/bimcalc/venv/bin/python -m bimcalc.cli sync-prices
StandardOutput=append:/var/log/bimcalc_pipeline.log
StandardError=append:/var/log/bimcalc_pipeline.log
```

Create `/etc/systemd/system/bimcalc-sync.timer`:

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

Enable:

```bash
systemctl enable bimcalc-sync.timer
systemctl start bimcalc-sync.timer
systemctl status bimcalc-sync.timer
```

### Option 3: Task Scheduler (Windows)

```powershell
# Create scheduled task
$action = New-ScheduledTaskAction -Execute "python" -Argument "-m bimcalc.cli sync-prices" -WorkingDirectory "C:\BIMCalcKM"
$trigger = New-ScheduledTaskTrigger -Daily -At 2am
Register-ScheduledTask -Action $action -Trigger $trigger -TaskName "BIMCalc Price Sync" -Description "Nightly price data synchronization"
```

---

## Data Source Integration Patterns

### Pattern 1: Manufacturer Direct Files (OBO, Philips, etc.)

**Characteristics:**
- Quarterly or monthly Excel/CSV files
- Delivered via FTP, email, or portal download
- Fixed format per manufacturer
- Usually 5,000-50,000 items

**Setup:**
```yaml
- name: manufacturer_q4_2024
  type: csv
  enabled: true
  config:
    file_path: /data/manufacturers/philips/2024_Q4_Pricelist.xlsx
    region: DE
    vendor_id: PHILIPS_LIGHTING
    column_mapping:
      "SKU": "item_code"
      "Product Description": "description"
      "Category Code": "classification_code"
      "List Price": "unit_price"
      "Currency": "currency"
```

**Operations:**
1. Download new file to configured path
2. Update `file_path` in config if needed
3. Run pipeline
4. Old file can be archived

---

### Pattern 2: Distributor APIs (RS, Farnell, Trimble)

**Characteristics:**
- Real-time API access
- Rate-limited (10-100 req/s)
- Paginated responses
- Dynamic pricing

**Setup:**
```yaml
- name: rs_components_uk
  type: api
  enabled: true
  config:
    api_url: https://api.rs-online.com/v1/products
    api_key_env: RS_API_KEY
    region: UK
    vendor_id: RS_COMPONENTS
    rate_limit: 10
    headers:
      Accept: "application/json"
    pagination:
      page_size: 100
```

**Required Environment Variables:**
```bash
export RS_API_KEY="your_api_key_here"
export FARNELL_API_KEY="your_api_key_here"
```

---

### Pattern 3: Data Pools (ITEC, 2BA)

**Characteristics:**
- Industry-wide databases
- Subscription-based access
- Standardized schemas
- Daily or weekly updates

**Setup:**
```yaml
- name: itec_data_pool_de
  type: api
  enabled: true
  config:
    api_url: https://api.itec-standard.de/v2/prices
    api_key_env: ITEC_API_KEY
    region: DE
    vendor_id: ITEC_POOL
    standard: ITEC_7_0
```

---

## Performance Tuning

### Database Optimization

```sql
-- Verify indexes are being used
EXPLAIN QUERY PLAN
SELECT * FROM price_items
WHERE item_code = 'ELBOW-001'
  AND region = 'UK'
  AND is_current = 1;

-- Rebuild indexes if needed
REINDEX;

-- Vacuum database to reclaim space
VACUUM;

-- Check database size
SELECT page_count * page_size / 1024.0 / 1024.0 as size_mb
FROM pragma_page_count(), pragma_page_size();
```

### Pipeline Performance

```bash
# Monitor run times
python -m bimcalc.cli pipeline-status --last 30 | grep "Duration"

# Profile slow sources
python -m cProfile -m bimcalc.cli sync-prices --source slow_source
```

---

## Troubleshooting

### Issue: Pipeline Run Fails

**Check logs:**
```bash
python -m bimcalc.cli pipeline-status --last 1
```

**Common causes:**
1. **File not found** → Check file_path in config
2. **API authentication** → Verify API keys in environment
3. **Network timeout** → Check connectivity, increase timeout
4. **Column mapping error** → Verify CSV headers match mapping

**Resolution:**
```bash
# Test specific source
python -m bimcalc.cli sync-prices --source problem_source --dry-run

# Check configuration
cat config/pipeline_sources.yaml | grep -A 20 "problem_source"
```

---

### Issue: Price Not Updating

**Diagnostic query:**
```sql
-- Check if price record exists
SELECT * FROM price_items
WHERE item_code = 'ITEM-CODE'
  AND region = 'UK'
  AND is_current = 1;

-- Check last sync for source
SELECT * FROM data_sync_log
WHERE source_name = 'source_name'
ORDER BY run_timestamp DESC
LIMIT 1;
```

**Common causes:**
1. **Source disabled** → Check `enabled: true` in config
2. **Item code mismatch** → Verify column mapping
3. **Classification mismatch** → Check classification_code
4. **Price unchanged** → SCD2 correctly detected no change

---

### Issue: Duplicate Prices

**Should never happen** due to unique constraint. If it does:

```sql
-- Find duplicates (should return 0 rows)
SELECT item_code, region, COUNT(*)
FROM price_items
WHERE is_current = 1
GROUP BY item_code, region
HAVING COUNT(*) > 1;
```

**If duplicates found:**
```bash
# Database corruption - restore from backup
cp bimcalc_backup_YYYYMMDD_HHMMSS.db bimcalc.db
python -m bimcalc.cli sync-prices
```

---

## Backup and Recovery

### Automated Backups

```bash
# Add to crontab - daily backup at 1 AM
0 1 * * * cp /Users/ciarancox/BIMCalcKM/bimcalc.db /backups/bimcalc_$(date +\%Y\%m\%d).db

# Keep last 30 days
0 3 * * * find /backups -name "bimcalc_*.db" -mtime +30 -delete
```

### Manual Backup

```bash
# Before major changes
cp bimcalc.db bimcalc_backup_$(date +%Y%m%d_%H%M%S).db
```

### Recovery

```bash
# Restore from backup
cp bimcalc_backup_20251113.db bimcalc.db

# Verify integrity
python -m bimcalc.cli pipeline-status --last 1
```

---

## Security Considerations

### API Keys

**Never commit API keys to git:**

```bash
# Store in environment
export RS_API_KEY="sk_live_..."
export FARNELL_API_KEY="pk_prod_..."

# Or use .env file (add to .gitignore)
echo "RS_API_KEY=sk_live_..." >> .env
echo "FARNELL_API_KEY=pk_prod_..." >> .env
```

### File Permissions

```bash
# Restrict database access
chmod 600 bimcalc.db

# Restrict config file
chmod 600 config/pipeline_sources.yaml

# Restrict log files
chmod 640 /var/log/bimcalc_pipeline.log
```

---

## Monitoring and Alerts

### Health Check Script

Create `scripts/health_check.sh`:

```bash
#!/bin/bash
# Check if last pipeline run was successful

LAST_STATUS=$(python -m bimcalc.cli pipeline-status --last 1 | grep "Status:" | awk '{print $2}')

if [ "$LAST_STATUS" != "SUCCESS" ]; then
    echo "Pipeline failure detected!"
    # Send alert (email, Slack, etc.)
    # curl -X POST $SLACK_WEBHOOK -d '{"text":"BIMCalc pipeline failed"}'
    exit 1
fi

echo "Pipeline healthy"
exit 0
```

### Integration with Monitoring Tools

```python
# Example: Prometheus metrics export
from prometheus_client import Counter, Histogram, start_http_server

pipeline_runs = Counter('bimcalc_pipeline_runs_total', 'Total pipeline runs', ['status'])
pipeline_duration = Histogram('bimcalc_pipeline_duration_seconds', 'Pipeline duration')
records_processed = Counter('bimcalc_records_processed_total', 'Records processed', ['operation'])

# In orchestrator.py
pipeline_runs.labels(status='success').inc()
records_processed.labels(operation='inserted').inc(stats['inserted'])
```

---

## Reporting and Analytics

### Price Change Analysis

```sql
-- Items with most price changes
SELECT item_code, region, COUNT(*) as change_count
FROM price_items
GROUP BY item_code, region
HAVING COUNT(*) > 1
ORDER BY change_count DESC
LIMIT 20;

-- Average price volatility by classification
SELECT classification_code,
       AVG(price_changes) as avg_changes,
       COUNT(*) as item_count
FROM (
    SELECT classification_code, item_code, COUNT(*) - 1 as price_changes
    FROM price_items
    GROUP BY classification_code, item_code
)
GROUP BY classification_code
ORDER BY avg_changes DESC;
```

### Cost Trend Reports

```sql
-- Price trend for specific item
SELECT valid_from, unit_price, currency,
       CASE WHEN is_current = 1 THEN 'CURRENT' ELSE 'EXPIRED' END as status
FROM price_items
WHERE item_code = 'ELBOW-001' AND region = 'UK'
ORDER BY valid_from DESC;

-- Price increase detection (last 30 days)
SELECT p1.item_code, p1.region,
       p2.unit_price as old_price,
       p1.unit_price as new_price,
       ROUND((p1.unit_price - p2.unit_price) / p2.unit_price * 100, 2) as pct_change
FROM price_items p1
JOIN price_items p2 ON p1.item_code = p2.item_code
                   AND p1.region = p2.region
WHERE p1.is_current = 1
  AND p2.valid_to = p1.valid_from
  AND p1.valid_from >= datetime('now', '-30 days')
  AND p1.unit_price > p2.unit_price
ORDER BY pct_change DESC;
```

---

## Maintenance Calendar

### Daily
- Monitor pipeline execution
- Check for failures in logs

### Weekly
- Review pipeline-status for trends
- Check database size growth
- Verify backup retention

### Monthly
- Update manufacturer price files
- Review and update column mappings
- Analyze price volatility
- Performance optimization review

### Quarterly
- Major version updates
- Security audit
- Capacity planning
- Archive old historical data (optional)

---

## Support and Escalation

### Log Collection for Support

```bash
# Gather diagnostic info
python -m bimcalc.cli pipeline-status --last 10 > diagnostics.txt
sqlite3 bimcalc.db ".schema" >> diagnostics.txt
tail -n 1000 /var/log/bimcalc_pipeline.log >> diagnostics.txt
```

### Emergency Contacts

- **System Owner:** [Your team contact]
- **Database Admin:** [DBA contact]
- **Data Source Providers:** [Vendor contacts]

---

## Next Steps for Production Deployment

1. **Configure Production Data Sources**
   - Obtain API credentials from vendors
   - Set up file drop locations for manufacturers
   - Configure column mappings for each source

2. **Set Up Automation**
   - Implement cron job or systemd timer
   - Configure backup schedule
   - Set up monitoring/alerting

3. **Integration Testing**
   - Test each production source individually
   - Verify SCD Type-2 behavior with real data
   - Validate matching and reporting workflows

4. **Go Live**
   - Enable production sources
   - Monitor first few runs closely
   - Validate data quality with stakeholders

---

**Document Version:** 1.0
**Last Updated:** November 13, 2024
**Status:** Production Ready
