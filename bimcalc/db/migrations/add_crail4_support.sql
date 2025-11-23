-- Crail4 AI integration schema extensions

-- Track ETL job runs for auditability
CREATE TABLE IF NOT EXISTS price_import_runs (
    id TEXT PRIMARY KEY,  -- UUID
    org_id TEXT NOT NULL,
    source TEXT NOT NULL,  -- 'crail4_api', 'manual', etc.
    started_at TIMESTAMP NOT NULL,
    completed_at TIMESTAMP,
    status TEXT NOT NULL,  -- 'running', 'completed', 'failed'
    items_fetched INTEGER DEFAULT 0,
    items_loaded INTEGER DEFAULT 0,
    items_rejected INTEGER DEFAULT 0,
    rejection_reasons JSON,  -- {"missing_classification": 45, "invalid_unit": 12}
    error_message TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Classification code mapping for taxonomy translation
CREATE TABLE IF NOT EXISTS classification_mappings (
    id TEXT PRIMARY KEY,  -- UUID
    org_id TEXT NOT NULL,
    source_scheme TEXT NOT NULL,  -- 'OmniClass', 'UniClass2015', etc.
    source_code TEXT NOT NULL,
    target_scheme TEXT NOT NULL,
    target_code TEXT NOT NULL,
    confidence REAL DEFAULT 1.0,  -- 0.0-1.0, for fuzzy mappings
    mapping_source TEXT,  -- 'csi_crosswalk', 'manual', 'vendor'
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_by TEXT,
    UNIQUE(org_id, source_scheme, source_code, target_scheme)
);

-- Add vendor tracking to price_items
ALTER TABLE price_items ADD COLUMN IF NOT EXISTS vendor_code TEXT;
ALTER TABLE price_items ADD COLUMN IF NOT EXISTS last_updated TIMESTAMP;
ALTER TABLE price_items ADD COLUMN IF NOT EXISTS region TEXT;
ALTER TABLE price_items ADD COLUMN IF NOT EXISTS import_run_id TEXT REFERENCES price_import_runs(id);
