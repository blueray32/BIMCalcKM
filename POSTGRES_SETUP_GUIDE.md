# BIMCalc PostgreSQL Setup Guide

Complete guide to setting up PostgreSQL for local BIMCalc development using Docker Compose.

---

## Prerequisites

### Required Software

1. **Docker Desktop** (Mac/Windows) or **Docker Engine** (Linux)
   - Mac: [Download Docker Desktop](https://www.docker.com/products/docker-desktop/)
   - Windows: [Download Docker Desktop](https://www.docker.com/products/docker-desktop/)
   - Linux: Install Docker Engine + Docker Compose
     ```bash
     curl -fsSL https://get.docker.com | sh
     sudo usermod -aG docker $USER
     ```

2. **Verify Installation**
   ```bash
   docker --version  # Should show Docker version 20.10+
   docker compose version  # Should show Docker Compose version 2.0+
   ```

---

## Quick Start (5 Minutes)

### Step 1: Start PostgreSQL

```bash
cd /path/to/BIMCalcKM

# Start PostgreSQL container
docker compose up -d postgres

# Check it's running
docker compose ps

# View logs
docker compose logs -f postgres
```

**Expected Output**:
```
✔ Container bimcalc-postgres  Started
database system is ready to accept connections
```

### Step 2: Configure Environment

```bash
# Copy environment template
cp .env.example .env

# Edit .env (use your favorite editor)
nano .env
```

**Minimal Configuration**:
```bash
DATABASE_URL=postgresql+asyncpg://bimcalc:dev_password_change_in_production@localhost:5432/bimcalc
ORG_ID=acme-construction
PROJECT_ID=project-a
```

### Step 3: Initialize Database Schema

```bash
# Run Alembic migrations (creates all tables)
python -m bimcalc.cli init

# Or with drop existing tables
python -m bimcalc.cli init --drop
```

**Expected Output**:
```
Initializing database: postgresql+asyncpg://bimcalc:***@localhost:5432/bimcalc
Creating tables...
✓ Database initialized
```

### Step 4: Verify Setup

```bash
# Check database connection
docker exec -it bimcalc-postgres psql -U bimcalc -d bimcalc -c "\dt"

# Should show tables: items, price_items, match_results, item_mappings, etc.
```

---

## Docker Compose Commands

### Starting Services

```bash
# Start PostgreSQL only
docker compose up -d postgres

# Start PostgreSQL + pgAdmin (web UI)
docker compose --profile dev up -d

# View all running containers
docker compose ps
```

### Stopping Services

```bash
# Stop all services
docker compose down

# Stop and remove volumes (⚠️ DELETES ALL DATA)
docker compose down -v
```

### Logs & Debugging

```bash
# View logs (real-time)
docker compose logs -f postgres

# View last 100 lines
docker compose logs --tail=100 postgres

# Check container health
docker compose ps
```

### Accessing PostgreSQL

```bash
# Interactive psql shell
docker exec -it bimcalc-postgres psql -U bimcalc -d bimcalc

# Run SQL query directly
docker exec -it bimcalc-postgres psql -U bimcalc -d bimcalc -c "SELECT version();"

# Dump database to file
docker exec -t bimcalc-postgres pg_dump -U bimcalc bimcalc > backup.sql

# Restore database from file
docker exec -i bimcalc-postgres psql -U bimcalc -d bimcalc < backup.sql
```

---

## pgAdmin (Optional Web UI)

### Starting pgAdmin

```bash
# Start with pgAdmin included
docker compose --profile dev up -d

# Access at: http://localhost:5050
# Email: admin@bimcalc.local
# Password: admin
```

### Connecting to PostgreSQL in pgAdmin

1. Open http://localhost:5050
2. Right-click "Servers" → "Register" → "Server"
3. **General Tab**:
   - Name: `BIMCalc Local`
4. **Connection Tab**:
   - Host: `postgres` (container name)
   - Port: `5432`
   - Database: `bimcalc`
   - Username: `bimcalc`
   - Password: `dev_password_change_in_production`
5. Click "Save"

---

## Performance Tuning

### Default Configuration

The `init.sql` script applies these performance settings:

```sql
shared_buffers = 256MB        # Memory for caching
effective_cache_size = 1GB    # Estimate of OS cache
work_mem = 4MB                # Memory per query operation
maintenance_work_mem = 64MB   # Memory for VACUUM, CREATE INDEX
```

**Suitable for**:
- Development machines with 8GB+ RAM
- Small to medium datasets (<100K items)

### High-Performance Configuration

For production or large datasets, edit `scripts/postgres/init.sql`:

```sql
shared_buffers = '1GB'              # 25% of system RAM
effective_cache_size = '3GB'        # 75% of system RAM
work_mem = '16MB'                   # Higher for complex queries
maintenance_work_mem = '256MB'      # Faster index creation
max_connections = 100               # Concurrent connections
```

**Apply Changes**:
```bash
# Recreate container with new settings
docker compose down
docker compose up -d postgres
```

---

## Database Indexes (Critical for Performance)

### Automatic Indexes (via Alembic)

These are created by migrations:

```sql
-- Primary keys (automatic)
items.id, price_items.id, match_results.id, item_mappings.id

-- Foreign keys (automatic)
match_results.item_id, match_results.price_item_id
item_mappings.item_id, item_mappings.price_item_id
```

### Recommended Custom Indexes

Add these for better query performance:

```bash
# Connect to database
docker exec -it bimcalc-postgres psql -U bimcalc -d bimcalc

# Create indexes
CREATE INDEX CONCURRENTLY idx_items_canonical_key ON items(canonical_key);
CREATE INDEX CONCURRENTLY idx_items_classification_code ON items(classification_code);
CREATE INDEX CONCURRENTLY idx_items_org_project ON items(org_id, project_id);
CREATE INDEX CONCURRENTLY idx_price_items_classification ON price_items(classification_code);
CREATE INDEX CONCURRENTLY idx_mappings_active ON item_mappings(org_id, canonical_key) WHERE end_ts IS NULL;

# JSONB indexes (if using custom metadata)
CREATE INDEX CONCURRENTLY idx_items_metadata ON items USING gin(doc_metadata);
```

**Verify Indexes**:
```sql
SELECT tablename, indexname, indexdef
FROM pg_indexes
WHERE schemaname = 'public'
ORDER BY tablename, indexname;
```

---

## Troubleshooting

### Issue 1: Port 5432 Already in Use

**Symptom**:
```
Error: bind: address already in use
```

**Solution**:
```bash
# Check what's using port 5432
lsof -i :5432  # Mac/Linux
netstat -ano | findstr :5432  # Windows

# Option 1: Stop existing PostgreSQL
brew services stop postgresql  # Mac Homebrew
sudo service postgresql stop   # Linux

# Option 2: Use different port in docker-compose.yml
ports:
  - "5433:5432"  # Map to 5433 instead

# Update DATABASE_URL in .env
DATABASE_URL=postgresql+asyncpg://bimcalc:dev_password@localhost:5433/bimcalc
```

### Issue 2: Container Won't Start

**Check Logs**:
```bash
docker compose logs postgres
```

**Common Causes**:
1. **Corrupted volume** → `docker compose down -v` (⚠️ deletes data)
2. **Invalid init.sql** → Check syntax in `scripts/postgres/init.sql`
3. **Resource limits** → Increase Docker Desktop memory (Settings → Resources)

### Issue 3: Connection Refused

**Symptom**:
```
asyncpg.exceptions.ConnectionDoesNotExistError
```

**Checklist**:
1. Container running? `docker compose ps`
2. Health check passing? `docker inspect bimcalc-postgres | grep Health`
3. Network reachable? `docker exec bimcalc-postgres pg_isready`
4. DATABASE_URL correct in .env?

**Test Connection**:
```bash
# From host machine
psql postgresql://bimcalc:dev_password@localhost:5432/bimcalc -c "SELECT 1;"
```

### Issue 4: Slow Queries

**Enable Query Logging**:
```sql
-- In psql shell
ALTER SYSTEM SET log_min_duration_statement = 100;  -- Log queries > 100ms
SELECT pg_reload_conf();
```

**View Slow Queries**:
```bash
docker compose logs postgres | grep "duration:"
```

**Analyze Query Plan**:
```sql
EXPLAIN ANALYZE SELECT * FROM items WHERE canonical_key = 'some-key';
```

---

## Migrating from SQLite

### Automated Migration Script

```bash
# Run migration script
python scripts/migrate_sqlite_to_postgres.py \
  --sqlite-db bimcalc.db \
  --postgres-url postgresql+asyncpg://bimcalc:dev_password@localhost:5432/bimcalc

# Verify row counts match
python scripts/verify_migration.py
```

### Manual Migration

```bash
# 1. Export SQLite to CSV
sqlite3 bimcalc.db <<EOF
.mode csv
.output items.csv
SELECT * FROM items;
.output price_items.csv
SELECT * FROM price_items;
EOF

# 2. Import to PostgreSQL
docker exec -i bimcalc-postgres psql -U bimcalc -d bimcalc <<EOF
\COPY items FROM 'items.csv' CSV HEADER;
\COPY price_items FROM 'price_items.csv' CSV HEADER;
EOF

# 3. Verify counts
docker exec bimcalc-postgres psql -U bimcalc -d bimcalc -c "SELECT COUNT(*) FROM items;"
```

---

## Backup & Restore

### Daily Backups (Automated)

**Create Backup Script** (`scripts/backup_postgres.sh`):
```bash
#!/bin/bash
BACKUP_DIR="./backups"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
mkdir -p "$BACKUP_DIR"

docker exec -t bimcalc-postgres pg_dump -U bimcalc -Fc bimcalc > \
  "$BACKUP_DIR/bimcalc_$TIMESTAMP.dump"

# Keep only last 7 days
find "$BACKUP_DIR" -name "bimcalc_*.dump" -mtime +7 -delete

echo "Backup completed: $BACKUP_DIR/bimcalc_$TIMESTAMP.dump"
```

**Schedule Daily Backups**:
```bash
# Mac/Linux: Add to crontab
crontab -e

# Add line:
0 2 * * * /path/to/BIMCalcKM/scripts/backup_postgres.sh
```

### Manual Backup

```bash
# Create backup (custom format, compressed)
docker exec -t bimcalc-postgres pg_dump -U bimcalc -Fc bimcalc > backup.dump

# Or SQL format (human-readable)
docker exec -t bimcalc-postgres pg_dump -U bimcalc bimcalc > backup.sql
```

### Restore from Backup

```bash
# Restore from custom format
docker exec -i bimcalc-postgres pg_restore -U bimcalc -d bimcalc -c < backup.dump

# Restore from SQL
docker exec -i bimcalc-postgres psql -U bimcalc -d bimcalc < backup.sql
```

---

## Production Deployment

### Security Checklist

- [ ] Change default password in `docker-compose.yml`
- [ ] Use secrets management (Docker secrets, Vault, etc.)
- [ ] Enable SSL/TLS (`postgresql://...?sslmode=require`)
- [ ] Restrict network access (firewall rules)
- [ ] Create read-only user for reporting
- [ ] Enable audit logging (`log_statement = 'ddl'`)
- [ ] Set up automated backups (daily + weekly retention)
- [ ] Configure replication (if HA required)
- [ ] Monitor disk space (alerts at 80% full)
- [ ] Set up connection pooling (PgBouncer)

### Environment Variables

**Production .env**:
```bash
DATABASE_URL=postgresql+asyncpg://bimcalc:${DB_PASSWORD}@db.example.com:5432/bimcalc?sslmode=require
LOG_LEVEL=WARNING
DEBUG=false
```

### Connection Pooling

For production, add PgBouncer:

```yaml
# docker-compose.yml (add service)
pgbouncer:
  image: edoburu/pgbouncer:latest
  environment:
    DATABASE_URL: postgres://bimcalc:password@postgres:5432/bimcalc
    POOL_MODE: transaction
    MAX_CLIENT_CONN: 1000
    DEFAULT_POOL_SIZE: 20
  ports:
    - "6432:5432"
  depends_on:
    - postgres
```

**Update DATABASE_URL**:
```
postgresql+asyncpg://bimcalc:password@localhost:6432/bimcalc
```

---

## Next Steps

1. ✅ Start PostgreSQL: `docker compose up -d postgres`
2. ✅ Initialize database: `python -m bimcalc.cli init`
3. ✅ Ingest sample data: `python -m bimcalc.cli ingest-schedules ...`
4. ✅ Run matching: `python -m bimcalc.cli match`
5. ✅ Start Web UI: `python -m bimcalc.cli web serve --port 8002`

**Verify Everything Works**:
```bash
# Run full test suite
python -m pytest -v

# Check database has data
docker exec bimcalc-postgres psql -U bimcalc -d bimcalc -c "\
  SELECT
    (SELECT COUNT(*) FROM items) as items,
    (SELECT COUNT(*) FROM price_items) as prices,
    (SELECT COUNT(*) FROM match_results) as matches;
"
```

---

## Support & Resources

- **Documentation**: See `MVP_REVIEW_RESPONSE.md` for migration roadmap
- **Issues**: Check Docker logs first (`docker compose logs postgres`)
- **Performance**: Review query plans with `EXPLAIN ANALYZE`
- **Backup**: Automate with `scripts/backup_postgres.sh`

**PostgreSQL Resources**:
- [Official Docs](https://www.postgresql.org/docs/16/)
- [pgvector Extension](https://github.com/pgvector/pgvector)
- [Performance Tuning](https://wiki.postgresql.org/wiki/Tuning_Your_PostgreSQL_Server)
