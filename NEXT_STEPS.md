# BIMCalc - Next Steps After Deployment

**System Status:** ✅ **Production Ready**
**Deployment Date:** November 13, 2024
**Last Updated:** November 13, 2024

---

## Current State

Your BIMCalc live pricing pipeline is successfully deployed and operational:

- ✅ SCD Type-2 price history working
- ✅ Data governance tracking in place
- ✅ Pipeline tested and verified
- ✅ Operational scripts ready
- ✅ Documentation complete
- ✅ Configuration validated

**Current Statistics:**
- 246 BIM items
- 65 price items (+ 1 historical record)
- 2 active mappings
- 1 enabled data source (test data)
- Database size: 340 KB

---

## Immediate Next Steps (Priority Order)

### 1. Set Up Automated Backups (5 minutes)

**Why:** Protect your data before enabling production sources

```bash
# Test backup script
./scripts/backup_database.sh

# Add to crontab for daily backups
crontab -e
# Add this line:
0 1 * * * cd /Users/ciarancox/BIMCalcKM && ./scripts/backup_database.sh
```

**Verification:**
```bash
ls -lh backups/
```

---

### 2. Schedule Automated Pipeline Runs (5 minutes)

**Why:** Ensure pricing data stays current

```bash
# Add to crontab for nightly runs at 2 AM
crontab -e
# Add this line:
0 2 * * * cd /Users/ciarancox/BIMCalcKM && python -m bimcalc.cli sync-prices >> /var/log/bimcalc_pipeline.log 2>&1
```

**Alternative (for development):**
```bash
# Run manually when needed
python -m bimcalc.cli sync-prices
```

---

### 3. Configure Production Data Sources (30-60 minutes)

**Current Status:** Only test data enabled

**Options:**

#### Option A: CSV File Sources (Easiest)

If you have manufacturer price lists as Excel/CSV files:

1. **Place files in accessible location:**
   ```bash
   mkdir -p /Users/ciarancox/BIMCalcKM/data/prices
   # Copy your price list files here
   ```

2. **Edit configuration:**
   ```bash
   # Copy example and edit
   cp config/pipeline_sources_examples.yaml config/my_sources.yaml

   # Edit to add your file source
   vim config/pipeline_sources.yaml
   ```

3. **Add source configuration:**
   ```yaml
   sources:
     - name: manufacturer_jan_2025
       type: csv
       enabled: true
       config:
         file_path: /Users/ciarancox/BIMCalcKM/data/prices/manufacturer_pricelist.xlsx
         region: UK  # or DE, NL, etc.
         vendor_id: MANUFACTURER_NAME
         column_mapping:
           "Item Code": "item_code"
           "Description": "description"
           "Category": "classification_code"
           "Price": "unit_price"
           "Currency": "currency"
           "Unit": "unit"
   ```

4. **Validate and test:**
   ```bash
   python scripts/validate_config.py
   python -m bimcalc.cli sync-prices --dry-run
   python -m bimcalc.cli sync-prices
   ```

#### Option B: API Sources (Requires API Keys)

If you have API access to distributors (RS Components, Farnell, etc.):

1. **Obtain API keys from vendors**

2. **Set environment variables:**
   ```bash
   # Add to ~/.bashrc or ~/.zshrc
   export RS_API_KEY="your_api_key_here"
   export FARNELL_API_KEY="your_api_key_here"
   ```

3. **Enable API source in config:**
   ```yaml
   sources:
     - name: rs_components_uk
       type: api
       enabled: true
       config:
         api_url: https://api.rs-online.com/v1/catalogue/products
         api_key_env: RS_API_KEY
         region: UK
         rate_limit: 5
   ```

4. **Test:**
   ```bash
   python scripts/validate_config.py
   python -m bimcalc.cli sync-prices --source rs_components_uk --dry-run
   ```

#### Option C: Manual Upload

For ad-hoc price updates:

1. **Create upload directory:**
   ```bash
   mkdir -p /Users/ciarancox/BIMCalcKM/data/uploads
   ```

2. **Drop price list files there**

3. **Configure manual source:**
   ```yaml
   sources:
     - name: manual_upload
       type: csv
       enabled: true
       config:
         file_path: /Users/ciarancox/BIMCalcKM/data/uploads/latest.csv
         region: UK
         vendor_id: MANUAL_UPLOAD
         column_mapping:
           "SKU": "item_code"
           "Description": "description"
           "Price": "unit_price"
           "Currency": "currency"
   ```

---

### 4. Set Up Monitoring Dashboard (10 minutes)

**Daily health checks:**

```bash
# Run dashboard to see current state
python scripts/dashboard.py

# Add to crontab for weekly reports
crontab -e
# Add this line:
0 9 * * 1 cd /Users/ciarancox/BIMCalcKM && python scripts/dashboard.py | mail -s "BIMCalc Weekly Report" your.email@example.com
```

**Health monitoring:**

```bash
# Add health check to crontab
crontab -e
# Add this line:
0 */6 * * * cd /Users/ciarancox/BIMCalcKM && ./scripts/health_check.sh
```

---

## Recommended First Week Actions

### Day 1: Validate Deployment
- ✅ Already done! System deployed and tested

### Day 2: Configure First Production Source
- [ ] Choose 1 production data source (CSV file or API)
- [ ] Configure in `pipeline_sources.yaml`
- [ ] Validate configuration: `python scripts/validate_config.py`
- [ ] Test with dry-run: `python -m bimcalc.cli sync-prices --dry-run`
- [ ] Run production import: `python -m bimcalc.cli sync-prices`
- [ ] Verify in dashboard: `python scripts/dashboard.py`

### Day 3: Schedule Automation
- [ ] Set up daily backups (cron job)
- [ ] Set up nightly pipeline runs (cron job)
- [ ] Set up health check monitoring (cron job)
- [ ] Test cron jobs manually

### Day 4: Add More Sources
- [ ] Configure additional data sources
- [ ] Test each source individually
- [ ] Enable all working sources
- [ ] Monitor first automated run

### Day 5: Review and Optimize
- [ ] Review pipeline performance: `python -m bimcalc.cli pipeline-status --last 7`
- [ ] Check for failures or warnings
- [ ] Optimize slow sources
- [ ] Document any vendor-specific quirks

---

## Common Scenarios and Solutions

### Scenario 1: "I have manufacturer Excel files"

**Solution:**
1. Copy Excel files to `data/prices/` directory
2. Add CSV source to `config/pipeline_sources.yaml`
3. Map Excel columns to price fields
4. Test and enable

**Time:** 15 minutes per manufacturer

---

### Scenario 2: "I have API access to distributors"

**Solution:**
1. Get API credentials from vendor
2. Set API key as environment variable
3. Add API source to config
4. Test with rate limiting
5. Enable for production

**Time:** 30 minutes per API

---

### Scenario 3: "I want to use test data for now"

**Solution:**
- Already configured! The `test_prices_local` source is enabled
- Just run: `python -m bimcalc.cli sync-prices`
- Add your own test data to `tests/fixtures/sample_prices.csv`

**Time:** Already done

---

### Scenario 4: "I need to support multiple countries"

**Solution:**
1. Create one source per country/region
2. Set different `region` codes (UK, DE, NL, etc.)
3. All sources run in same pipeline
4. Regional prices tracked automatically

**Example:**
```yaml
sources:
  - name: rs_components_uk
    type: api
    enabled: true
    config:
      region: UK
      api_url: https://api.rs-online.com/uk/...

  - name: rs_components_de
    type: api
    enabled: true
    config:
      region: DE
      api_url: https://api.rs-online.com/de/...
```

---

## Quick Reference Commands

### Daily Operations
```bash
# Quick system check
python scripts/dashboard.py

# Run pipeline
python -m bimcalc.cli sync-prices

# Check last run
python -m bimcalc.cli pipeline-status --last 1

# Create backup
./scripts/backup_database.sh
```

### Configuration
```bash
# Validate config before running
python scripts/validate_config.py

# Edit sources
vim config/pipeline_sources.yaml

# View example configurations
cat config/pipeline_sources_examples.yaml
```

### Troubleshooting
```bash
# Health check
./scripts/health_check.sh

# View recent failures
python -m bimcalc.cli pipeline-status --last 10

# Test specific source
python -m bimcalc.cli sync-prices --source source_name --dry-run

# Check logs
tail -f /var/log/bimcalc_pipeline.log
```

---

## Available Resources

### Documentation
- **Production Operations Guide:** `docs/PRODUCTION_OPERATIONS_GUIDE.md`
  - Comprehensive operations manual
  - All operational scenarios covered
  - Integration examples

- **Scripts README:** `scripts/README.md`
  - Detailed script documentation
  - Automation examples
  - Monitoring integration

- **Configuration Examples:** `config/pipeline_sources_examples.yaml`
  - Example configurations for all source types
  - European vendor examples
  - Column mapping templates

- **Deployment Success:** `DEPLOYMENT_SUCCESS.md`
  - Deployment verification
  - Test results
  - Resolved issues

### Tools Available
- **Dashboard:** `scripts/dashboard.py` - System overview
- **Health Check:** `scripts/health_check.sh` - Automated monitoring
- **Backup:** `scripts/backup_database.sh` - Database backup
- **Validation:** `scripts/validate_config.py` - Config verification

### CLI Commands
```bash
python -m bimcalc.cli --help
python -m bimcalc.cli sync-prices --help
python -m bimcalc.cli pipeline-status --help
```

---

## Decision Matrix: What Should I Do First?

### If you have manufacturer price files NOW:
→ **Go to Step 3: Configure Production Data Sources (Option A)**

### If you have API access NOW:
→ **Go to Step 3: Configure Production Data Sources (Option B)**

### If you want to test with existing data first:
→ **Go to Step 2: Schedule Automated Pipeline Runs**
   (test_prices_local is already enabled and working)

### If you want to set up monitoring first:
→ **Go to Step 4: Set Up Monitoring Dashboard**

### If you're not sure what data sources you'll use yet:
→ **Go to Step 1: Set Up Automated Backups**
→ **Go to Step 2: Schedule Automated Pipeline Runs**
→ Explore `config/pipeline_sources_examples.yaml` for ideas

---

## Success Metrics

### Week 1 Goals
- [ ] 1+ production data source configured
- [ ] Automated backups running
- [ ] Nightly pipeline scheduled
- [ ] Health monitoring in place

### Month 1 Goals
- [ ] 3+ production data sources
- [ ] Zero pipeline failures
- [ ] Price history accumulating
- [ ] Dashboard reviewed weekly

### Quarter 1 Goals
- [ ] All regional sources integrated
- [ ] Historical price analysis
- [ ] Cost trend reporting
- [ ] Integration with BIM matching workflow

---

## Support and Troubleshooting

### Common Issues

**"Pipeline not running automatically"**
- Check crontab: `crontab -l`
- Check logs: `tail -f /var/log/bimcalc_pipeline.log`
- Verify working directory in cron job

**"API source failing"**
- Verify API key: `echo $RS_API_KEY`
- Check rate limits in source config
- Test with dry-run first

**"Column mapping not working"**
- Check exact column names (case-sensitive)
- Use `head -1 your_file.csv` to see headers
- Update mapping in config to match exactly

**"Database locked error"**
- Check for other processes: `lsof bimcalc.db`
- Ensure only one pipeline runs at a time
- Add locking to cron jobs if needed

---

## Getting Help

### Before Asking for Help

1. Run diagnostics:
   ```bash
   python scripts/dashboard.py > diagnostics.txt
   python -m bimcalc.cli pipeline-status --last 10 >> diagnostics.txt
   python scripts/validate_config.py >> diagnostics.txt
   ```

2. Check logs:
   ```bash
   tail -n 100 /var/log/bimcalc_pipeline.log >> diagnostics.txt
   ```

3. Include in your report:
   - What you were trying to do
   - What happened instead
   - Error messages
   - Output of diagnostics commands

### Documentation to Check
1. `docs/PRODUCTION_OPERATIONS_GUIDE.md` - Comprehensive operations manual
2. `scripts/README.md` - Script documentation
3. `DEPLOYMENT_SUCCESS.md` - Deployment verification
4. `config/pipeline_sources_examples.yaml` - Configuration examples

---

## What's Next After This?

Once you have the pipeline running smoothly:

### Phase 2: Integration (Month 2-3)
- Integrate pricing with BIM matching workflow
- Use `get_current_price()` in matching calculations
- Enable automatic cost estimates in reports

### Phase 3: Analytics (Month 3-6)
- Historical price trend analysis
- Vendor comparison reports
- Cost escalation forecasting
- Budget variance tracking

### Phase 4: Advanced Features (Month 6+)
- Multi-currency runtime conversion
- Predictive cost modeling
- Procurement system integration
- Automated vendor negotiations

---

## Current Codebase Status

**✅ Completed and Production Ready:**
- SCD Type-2 implementation
- Multi-source pipeline orchestration
- Data governance tracking
- Operational monitoring
- Complete documentation
- Helper scripts and tools

**🔄 Ready to Configure:**
- Production data sources (your specific vendors)
- Automated scheduling (cron jobs)
- Monitoring and alerting (email/Slack)
- Regional pricing sources

**🚀 Future Enhancements (Optional):**
- Web dashboard UI
- Email/Slack alerts
- Parallel source processing
- Advanced analytics
- API for external integrations

---

## Conclusion

Your BIMCalc live pricing pipeline is **production ready**. The core infrastructure is solid, tested, and documented.

**Your next decision:** Which data source to configure first?

Choose based on:
- **Availability:** What data do you have access to now?
- **Importance:** Which vendor/region is most critical?
- **Ease:** Start with CSV files before APIs

**Recommended first step:** Configure one CSV file source from your most important manufacturer, test it, then add more sources incrementally.

---

**Questions?** Review the comprehensive documentation in:
- `docs/PRODUCTION_OPERATIONS_GUIDE.md`
- `scripts/README.md`
- `config/pipeline_sources_examples.yaml`

**Ready to start?** Pick your scenario above and begin! 🚀

---

**Status:** Production Ready
**Last Updated:** November 13, 2024
**Version:** 1.0
