# BIMCalc Staging Deployment Guide

**Version**: 1.0
**Date**: 2025-01-14
**Target**: Production-ready staging environment
**Database**: PostgreSQL 16 with pgvector

---

## 📋 Pre-Deployment Checklist

### Required Software
- [ ] Docker Engine 20.10+ installed
- [ ] Docker Compose 2.0+ installed
- [ ] Git installed
- [ ] 2GB+ RAM available
- [ ] 10GB+ disk space available

### Required Files
- [ ] `docker-compose.yml` present
- [ ] `Dockerfile` present
- [ ] `.env` file configured (see Configuration section)
- [ ] `config/vendors/` directory with vendor mappings

### Pre-Flight Checks
```bash
# Verify Docker is running
docker --version
docker compose version

# Check available resources
docker system df

# Test Docker connectivity
docker ps
```

---

## 🔧 Environment Configuration

### Step 1: Create `.env` File

Create a `.env` file in the project root:

```bash
# Database Configuration
POSTGRES_USER=bimcalc
POSTGRES_PASSWORD=CHANGE_ME_IN_PRODUCTION
POSTGRES_DB=bimcalc
DATABASE_URL=postgresql+asyncpg://bimcalc:CHANGE_ME_IN_PRODUCTION@db:5432/bimcalc

# Application Configuration
DEFAULT_ORG_ID=staging-org
DEFAULT_CURRENCY=EUR
VAT_INCLUDED=true
VAT_RATE=0.23

# CMM (Vendor Mapping) Configuration
USE_CMM=true
CMM_CONFIG_DIR=config/vendors

# Logging
LOG_LEVEL=INFO

# Optional: Enable Archon integration
# ARCHON_SERVER=https://archon.example.com
# ARCHON_TOKEN=your-token-here
```

### Step 2: Security Hardening

**CRITICAL**: Change default passwords before staging deployment!

```bash
# Generate secure password
openssl rand -base64 32

# Update .env file with generated password
sed -i 's/CHANGE_ME_IN_PRODUCTION/YOUR_GENERATED_PASSWORD/g' .env
```

### Step 3: Firewall Configuration (if needed)

```bash
# Allow PostgreSQL port (if accessing externally)
sudo ufw allow 5432/tcp

# Allow Web UI port
sudo ufw allow 8001/tcp

# Allow pgAdmin (optional, dev only)
sudo ufw allow 5050/tcp
```

---

## 🚀 Deployment Steps

### Step 1: Clone Repository (if not already done)

```bash
git clone https://github.com/your-org/bimcalc.git
cd bimcalc

# Checkout latest stable release
git checkout main
git pull origin main
```

### Step 2: Build Docker Images

```bash
# Build application image
docker compose build app

# Verify build success
docker images | grep bimcalc
```

**Expected output**:
```
bimcalc-app    latest    abc123def456    2 minutes ago    1.2GB
```

### Step 3: Start Database

```bash
# Start only the database first
docker compose up -d db

# Wait for database to be healthy (check logs)
docker compose logs -f db
```

**Wait for this message**:
```
PostgreSQL init process complete; ready for start up.
database system is ready to accept connections
```

**Verify database health**:
```bash
docker compose exec db pg_isready -U bimcalc -d bimcalc
# Expected: db:5432 - accepting connections
```

### Step 4: Run Database Migrations

**CRITICAL**: Run org_id migration if deploying fresh database

```bash
# Option A: Using Docker exec
docker compose exec app python -m bimcalc.migrations.add_org_id_to_prices_sqlite

# Option B: Using local Python (if installed)
python -m bimcalc.migrations.add_org_id_to_prices_sqlite
```

**Verify migration success**:
```bash
docker compose exec db psql -U bimcalc -d bimcalc -c "
SELECT column_name, data_type
FROM information_schema.columns
WHERE table_name = 'price_items' AND column_name = 'org_id';
"
```

**Expected output**:
```
 column_name | data_type
-------------+-----------
 org_id      | text
```

### Step 5: Start Application

```bash
# Start all services
docker compose up -d

# Check all services are running
docker compose ps
```

**Expected output**:
```
NAME                STATUS              PORTS
bimcalc-postgres    running (healthy)   0.0.0.0:5432->5432/tcp
bimcalc-app         running             0.0.0.0:8001->8001/tcp
```

### Step 6: View Logs

```bash
# Follow all logs
docker compose logs -f

# Follow only app logs
docker compose logs -f app

# Check for startup validation messages
docker compose logs app | grep "startup validations"
```

**Look for**:
```
INFO     bimcalc.startup_validation:startup_validation.py:XX Running startup validations...
INFO     bimcalc.startup_validation:startup_validation.py:XX ✓ All startup validations passed
```

---

## ✅ Post-Deployment Validation

### Step 1: Health Checks

```bash
# Check web UI is accessible
curl http://localhost:8001/

# Check database connectivity
docker compose exec app python -c "
from bimcalc.db import get_session
import asyncio
async def test():
    async with get_session() as session:
        print('✓ Database connection successful')
asyncio.run(test())
"
```

### Step 2: Startup Validation

The application automatically runs startup validation. Check logs for:

```bash
docker compose logs app | grep -A 10 "startup validations"
```

**Expected checks**:
- ✓ Classification config loaded
- ✓ Database connection verified
- ✓ VAT/currency config validated
- ✓ Classification distribution checked (if prices exist)

### Step 3: Web UI Accessibility

**Navigate to**: http://localhost:8001

**Verify pages load**:
- [ ] Dashboard (`/`)
- [ ] Items (`/items`)
- [ ] Prices (`/prices`)
- [ ] Review (`/review?org=staging-org&project=test`)
- [ ] Reports (`/reports`)

### Step 4: Test Price Ingestion

```bash
# Create sample price file
cat > sample_prices.csv << EOF
item_code,sku,description,classification_code,unit,unit_price,currency,vendor_id,region
CT-200,CT-200-V1,Cable tray 200mm,66,m,25.00,EUR,vendor1,IE
PIPE-200,PIPE-200-V1,Steel pipe 200mm,22,m,15.00,EUR,vendor1,IE
EOF

# Ingest via CLI
docker compose exec app python -m bimcalc.cli ingest \
  --org staging-org \
  --vendor vendor1 \
  --region IE \
  sample_prices.csv

# Verify ingestion
docker compose exec app python -m bimcalc.cli prices \
  --org staging-org \
  --limit 10
```

### Step 5: Test Matching Workflow

```bash
# Create sample item file
cat > sample_items.csv << EOF
family,type_name,classification_code,unit,quantity,width_mm,height_mm
Cable Tray,Elbow 90,66,ea,10,200,50
EOF

# Ingest items
docker compose exec app python -m bimcalc.cli ingest \
  --org staging-org \
  --project test \
  sample_items.csv

# Run matching
docker compose exec app python -m bimcalc.cli match \
  --org staging-org \
  --project test \
  --limit 5
```

### Step 6: Verify Escape-Hatch UI

1. Navigate to Review page: http://localhost:8001/review?org=staging-org&project=test
2. Check for:
   - [ ] Classification codes displayed
   - [ ] "⚠ Out-of-Class" badge (if escape-hatch was used)
   - [ ] "Classification Mismatch" in filter dropdown
   - [ ] Flags display correctly

---

## 🔍 Monitoring & Troubleshooting

### View Real-Time Logs

```bash
# All services
docker compose logs -f

# Only errors
docker compose logs -f | grep ERROR

# Only warnings and errors
docker compose logs -f | grep -E 'ERROR|WARNING'
```

### Database Access

```bash
# psql shell
docker compose exec db psql -U bimcalc -d bimcalc

# Quick queries
docker compose exec db psql -U bimcalc -d bimcalc -c "
SELECT COUNT(*) as total_prices FROM price_items WHERE is_current = true;
"

docker compose exec db psql -U bimcalc -d bimcalc -c "
SELECT org_id, COUNT(*) as count
FROM price_items
WHERE is_current = true
GROUP BY org_id;
"
```

### pgAdmin (Optional)

Start pgAdmin for visual database management:

```bash
# Start with dev profile
docker compose --profile dev up -d pgadmin

# Access at: http://localhost:5050
# Email: admin@bimcalc.local
# Password: admin
```

**Add Server in pgAdmin**:
- Host: db
- Port: 5432
- Username: bimcalc
- Password: (from .env file)

### Common Issues

#### Issue: Database connection refused

**Symptoms**:
```
sqlalchemy.exc.OperationalError: could not connect to server
```

**Solution**:
```bash
# Check database is running
docker compose ps db

# Check database health
docker compose exec db pg_isready -U bimcalc

# Restart database
docker compose restart db

# Check logs
docker compose logs db
```

#### Issue: Migration fails

**Symptoms**:
```
UNIQUE constraint failed
```

**Solution**:
```bash
# Backup database first
docker compose exec db pg_dump -U bimcalc bimcalc > backup.sql

# Drop and recreate (CAUTION: loses all data)
docker compose down -v
docker compose up -d db

# Wait for health check
docker compose logs -f db

# Re-run migration
docker compose exec app python -m bimcalc.migrations.add_org_id_to_prices_sqlite
```

#### Issue: Web UI not loading

**Symptoms**:
Browser shows "Unable to connect"

**Solution**:
```bash
# Check app is running
docker compose ps app

# Check app logs
docker compose logs app | tail -50

# Restart app
docker compose restart app

# Verify port binding
docker compose ps | grep 8001
netstat -tulpn | grep 8001
```

#### Issue: Startup validation fails

**Symptoms**:
```
✗ Startup validation failed
```

**Solution**:
```bash
# Check specific validation error
docker compose logs app | grep "validation"

# Common fixes:
# 1. Classification config missing
#    → Ensure config/classification_hierarchy.yaml exists

# 2. Database not accessible
#    → Check DATABASE_URL in .env

# 3. VAT config invalid
#    → Check VAT_RATE and VAT_INCLUDED in .env
```

---

## 🔄 Updating to New Version

### Step 1: Backup Data

```bash
# Backup database
docker compose exec db pg_dump -U bimcalc bimcalc > backup_$(date +%Y%m%d_%H%M%S).sql

# Backup volumes (alternative)
docker compose stop
sudo tar -czf bimcalc_volumes_backup.tar.gz /var/lib/docker/volumes/bimcalc*
```

### Step 2: Pull Latest Code

```bash
git fetch origin
git checkout main
git pull origin main

# Or checkout specific version
git checkout v1.2.3
```

### Step 3: Rebuild and Redeploy

```bash
# Rebuild image
docker compose build app

# Stop services
docker compose down

# Start services
docker compose up -d

# Run any new migrations
docker compose exec app python -m bimcalc.migrations.run_all

# Verify health
docker compose ps
docker compose logs -f
```

---

## 🛑 Rollback Procedure

### Emergency Rollback

If deployment fails critically:

```bash
# Step 1: Stop services
docker compose down

# Step 2: Restore database backup
docker compose up -d db
docker compose exec -T db psql -U bimcalc -d bimcalc < backup_YYYYMMDD_HHMMSS.sql

# Step 3: Checkout previous version
git log --oneline -n 10  # Find previous commit
git checkout <previous-commit-hash>

# Step 4: Rebuild and restart
docker compose build app
docker compose up -d

# Step 5: Verify
docker compose ps
docker compose logs -f app
```

---

## 🔒 Security Checklist

### Before Staging Deployment

- [ ] Change default database password in `.env`
- [ ] Disable pgAdmin in production (use `--profile dev` only)
- [ ] Review firewall rules
- [ ] Enable HTTPS (use reverse proxy like Nginx/Traefik)
- [ ] Set up database backups (cron job)
- [ ] Configure log rotation
- [ ] Review CORS settings if exposing API
- [ ] Set up monitoring (Prometheus/Grafana)

### Recommended: Reverse Proxy Setup

```nginx
# /etc/nginx/sites-available/bimcalc-staging
server {
    listen 80;
    server_name staging.bimcalc.example.com;

    location / {
        proxy_pass http://localhost:8001;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

---

## 📊 Performance Monitoring

### Key Metrics to Monitor

```bash
# Database connections
docker compose exec db psql -U bimcalc -d bimcalc -c "
SELECT count(*) as active_connections
FROM pg_stat_activity
WHERE state = 'active';
"

# Database size
docker compose exec db psql -U bimcalc -d bimcalc -c "
SELECT pg_size_pretty(pg_database_size('bimcalc')) as database_size;
"

# Active prices by org
docker compose exec db psql -U bimcalc -d bimcalc -c "
SELECT org_id, COUNT(*) as active_prices
FROM price_items
WHERE is_current = true
GROUP BY org_id;
"

# Pending reviews
docker compose exec db psql -U bimcalc -d bimcalc -c "
SELECT decision, COUNT(*)
FROM match_results
GROUP BY decision;
"
```

### Container Resource Usage

```bash
# CPU and memory usage
docker stats --no-stream

# Disk usage
docker system df

# Specific container stats
docker stats bimcalc-app bimcalc-postgres
```

---

## 📝 Validation Checklist

### Complete Deployment Validation

After deployment, verify:

**System Health**:
- [ ] All Docker containers running
- [ ] Database health check passing
- [ ] Web UI accessible at http://localhost:8001
- [ ] Startup validation passes (check logs)

**Data Layer**:
- [ ] `price_items` table has `org_id` column
- [ ] Indexes created successfully
- [ ] Can query prices by org_id
- [ ] SCD2 constraints enforced

**Application Layer**:
- [ ] Price ingestion works
- [ ] Item ingestion works
- [ ] Matching workflow completes
- [ ] Review page loads
- [ ] Reports generate

**UI Features**:
- [ ] Classification codes display
- [ ] Escape-hatch badge shows for out-of-class matches
- [ ] "Classification Mismatch" filter works
- [ ] Flags display correctly
- [ ] Critical flags block approval

**Integration**:
- [ ] CMM vendor mappings load
- [ ] Classification hierarchy loads
- [ ] VAT calculations correct
- [ ] Multi-tenant isolation working

---

## 🎓 User Acceptance Testing (UAT)

### Test Scenarios for Staging

#### Scenario 1: Standard Matching Workflow
1. Ingest price catalog with org_id
2. Ingest items with same org_id
3. Run matching
4. Review suggested matches
5. Approve matches
6. Generate report

**Expected**: All steps complete successfully, report includes source_file

#### Scenario 2: Multi-Tenant Isolation
1. Ingest prices for org_id="org-a"
2. Ingest prices for org_id="org-b"
3. Ingest items for org_id="org-a"
4. Run matching for org-a
5. Verify no matches from org-b

**Expected**: Only org-a prices considered

#### Scenario 3: Escape-Hatch Detection
1. Ingest items with classification_code=66
2. Ingest prices with classification_code=22 (no class-66 prices)
3. Run matching
4. Open review page

**Expected**:
- Matches show "⚠ Out-of-Class" badge
- Classification codes displayed (66 vs 22)
- "Classification Mismatch" flag present

#### Scenario 4: Critical Flag Enforcement
1. Create match with Unit Conflict flag
2. Navigate to review page
3. Attempt to approve

**Expected**: Approve button disabled, cannot approve

---

## 📞 Support & Escalation

### Getting Help

**Documentation**:
- Main README: `/README.md`
- Critical Fixes: `/CRITICAL_FIXES_COMPLETE.md`
- Integration Tests: `/INTEGRATION_TESTS_STATUS.md`
- UI Changes: `/WEB_UI_ENHANCEMENTS_COMPLETE.md`

**Logs Location**:
- Application: `docker compose logs app`
- Database: `docker compose logs db`
- All: `docker compose logs`

**Common Commands**:
```bash
# Full status
docker compose ps

# Restart everything
docker compose restart

# Stop everything
docker compose down

# Stop and remove volumes (DESTRUCTIVE)
docker compose down -v

# View resource usage
docker stats
```

### Escalation Path

1. **Check logs**: `docker compose logs -f`
2. **Review documentation**: See files listed above
3. **Check GitHub issues**: Known issues and solutions
4. **Contact support**: Include logs and error messages

---

## ✅ Staging Deployment Complete

Once all validation checks pass, staging deployment is complete!

**Next Steps**:
1. Conduct User Acceptance Testing (UAT)
2. Gather stakeholder feedback
3. Run performance benchmarks
4. Plan production deployment

**Status**: 🟢 **Staging Environment Ready**

---

**Version**: 1.0
**Last Updated**: 2025-01-14
**Maintainer**: BIMCalc Team
