-- BIMCalc PostgreSQL Initialization Script
-- This runs once when the container is first created

-- Enable pgvector extension for semantic search (future use)
CREATE EXTENSION IF NOT EXISTS vector;

-- Enable UUID generation functions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Create indexes for common query patterns (Alembic will also create these)
-- These are commented out because Alembic migrations handle schema creation
-- Uncomment if you want faster first-time setup without migrations

-- CREATE INDEX IF NOT EXISTS idx_items_canonical_key ON items(canonical_key);
-- CREATE INDEX IF NOT EXISTS idx_items_classification_code ON items(classification_code);
-- CREATE INDEX IF NOT EXISTS idx_items_org_project ON items(org_id, project_id);

-- Create read-only user for reporting (optional)
-- CREATE USER bimcalc_readonly WITH PASSWORD 'readonly_password';
-- GRANT CONNECT ON DATABASE bimcalc TO bimcalc_readonly;
-- GRANT USAGE ON SCHEMA public TO bimcalc_readonly;
-- GRANT SELECT ON ALL TABLES IN SCHEMA public TO bimcalc_readonly;

-- Set default privileges for future tables
-- ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO bimcalc_readonly;

-- Performance tuning for development
ALTER SYSTEM SET shared_buffers = '256MB';
ALTER SYSTEM SET effective_cache_size = '1GB';
ALTER SYSTEM SET maintenance_work_mem = '64MB';
ALTER SYSTEM SET checkpoint_completion_target = 0.9;
ALTER SYSTEM SET wal_buffers = '16MB';
ALTER SYSTEM SET default_statistics_target = 100;
ALTER SYSTEM SET random_page_cost = 1.1;
ALTER SYSTEM SET effective_io_concurrency = 200;
ALTER SYSTEM SET work_mem = '4MB';
ALTER SYSTEM SET min_wal_size = '1GB';
ALTER SYSTEM SET max_wal_size = '4GB';

-- Log configuration for debugging
ALTER SYSTEM SET log_statement = 'all';
ALTER SYSTEM SET log_duration = 'on';
ALTER SYSTEM SET log_min_duration_statement = 1000;  -- Log queries > 1s

SELECT pg_reload_conf();
