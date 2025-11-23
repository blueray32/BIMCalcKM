# Crail4 Integration - Production Deployment Checklist

## Pre-Deployment

- [ ] Database backup created
- [ ] Environment variables set in production .env
- [ ] API key validated with Crail4
- [ ] Classification mappings reviewed and approved
- [ ] Test sync completed successfully in staging

## Deployment Steps

1. [ ] Run database migration
   ```bash
   sqlite3 /path/to/prod/bimcalc.db < bimcalc/db/migrations/add_crail4_support.sql
   ```

2. [ ] Seed classification mappings
   ```bash
   python -m bimcalc.integration.seed_classification_mappings
   ```

3. [ ] Copy systemd units
   ```bash
   sudo cp deployment/crail4-sync.* /etc/systemd/system/
   sudo systemctl daemon-reload
   ```

4. [ ] Enable and start timer
   ```bash
   sudo systemctl enable crail4-sync.timer
   sudo systemctl start crail4-sync.timer
   ```

5. [ ] Verify timer is active
   ```bash
   sudo systemctl status crail4-sync.timer
   ```

## Post-Deployment Verification

- [ ] Manual sync test: `bimcalc sync-crail4 --org <prod-org> --classifications 66`
- [ ] Check import run created: Query `price_import_runs` table
- [ ] Verify price items imported: Query `price_items` WHERE `import_run_id` IS NOT NULL
- [ ] Test API endpoint: POST to `/api/price-items/bulk-import`
- [ ] Check systemd logs: `sudo journalctl -u crail4-sync.service -n 50`
