-- BIMCalc PostgreSQL Schema with pgvector Extension
-- Requires PostgreSQL 15+ with pgvector extension
--
-- Core principles:
-- 1. SCD Type-2 for mapping memory (immutable audit trail)
-- 2. Classification-first blocking (indexed for performance)
-- 3. Canonical keys for deterministic matching
-- 4. EU locale defaults (EUR currency, VAT explicit)

-- Enable pgvector extension for RAG agent
CREATE EXTENSION IF NOT EXISTS vector;

-- ============================================================================
-- Core Tables
-- ============================================================================

CREATE TABLE items (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id TEXT NOT NULL,
    project_id TEXT NOT NULL,

    -- Classification
    classification_code INTEGER,
    canonical_key TEXT,

    -- Revit metadata
    category TEXT,
    family TEXT NOT NULL,
    type_name TEXT NOT NULL,
    system_type TEXT,

    -- Explicit classification overrides (highest trust)
    omniclass_code INTEGER,
    uniformat_code INTEGER,

    -- Quantities
    quantity NUMERIC(12, 2),
    unit TEXT,

    -- Physical attributes (for canonical key and matching)
    width_mm REAL,
    height_mm REAL,
    dn_mm REAL,  -- Pipe diameter
    angle_deg REAL,
    material TEXT,

    -- Audit
    source_file TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_items_org ON items(org_id);
CREATE INDEX idx_items_project ON items(project_id);
CREATE INDEX idx_items_class ON items(classification_code);  -- CRITICAL for blocking
CREATE INDEX idx_items_canonical ON items(canonical_key);    -- CRITICAL for O(1) lookup

COMMENT ON TABLE items IS 'BIM items from Revit schedules or other sources';
COMMENT ON COLUMN items.classification_code IS 'Uniformat/Omniclass code from trust hierarchy';
COMMENT ON COLUMN items.canonical_key IS 'Deterministic 16-char hash for mapping memory';


CREATE TABLE price_items (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    classification_code INTEGER NOT NULL,  -- Required for classification blocking
    vendor_id TEXT,
    sku TEXT NOT NULL,
    description TEXT NOT NULL,

    -- Unit pricing (EU defaults)
    unit TEXT NOT NULL,
    unit_price NUMERIC(12, 2) NOT NULL CHECK (unit_price >= 0),
    currency TEXT DEFAULT 'EUR' NOT NULL,
    vat_rate NUMERIC(5, 2),  -- 0.23 for Irish/EU standard rate

    -- Physical attributes (for matching and flags)
    width_mm REAL,
    height_mm REAL,
    dn_mm REAL,
    angle_deg REAL,
    material TEXT,

    -- Audit & metadata
    last_updated DATE,
    vendor_note TEXT,  -- "Discontinued", "12-week lead time", etc.
    attributes JSONB DEFAULT '{}'::JSONB,  -- Additional structured data

    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_price_class ON price_items(classification_code);  -- CRITICAL for blocking
CREATE INDEX idx_price_vendor ON price_items(vendor_id);
CREATE INDEX idx_price_sku ON price_items(sku);
CREATE INDEX idx_price_attributes ON price_items USING GIN(attributes);  -- JSONB search

COMMENT ON TABLE price_items IS 'Vendor price catalog items';
COMMENT ON COLUMN price_items.classification_code IS 'Required for classification-first blocking (20× reduction)';
COMMENT ON COLUMN price_items.vat_rate IS 'VAT rate (e.g., 0.23 for 23%). NULL if VAT status unclear';


-- ============================================================================
-- SCD Type-2 Mapping Memory (Immutable Audit Trail)
-- ============================================================================

CREATE TABLE item_mapping (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id TEXT NOT NULL,
    canonical_key TEXT NOT NULL,
    price_item_id UUID REFERENCES price_items(id),

    -- SCD2 temporal fields
    start_ts TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    end_ts TIMESTAMP WITH TIME ZONE,  -- NULL = active row

    -- Audit trail
    created_by TEXT NOT NULL,  -- User email or "system"
    reason TEXT NOT NULL,      -- "manual match", "auto-accept", "correction", etc.

    -- Constraints
    UNIQUE(org_id, canonical_key, start_ts),
    CHECK (end_ts IS NULL OR end_ts > start_ts)
);

-- At most one active row per (org_id, canonical_key)
CREATE UNIQUE INDEX idx_mapping_active
    ON item_mapping(org_id, canonical_key)
    WHERE end_ts IS NULL;

-- Temporal queries (as-of)
CREATE INDEX idx_mapping_temporal
    ON item_mapping(org_id, canonical_key, start_ts, end_ts);

-- Foreign key index
CREATE INDEX idx_mapping_price ON item_mapping(price_item_id);

COMMENT ON TABLE item_mapping IS 'SCD Type-2 mapping memory for learning curve (30-50% instant auto-match on repeat projects)';
COMMENT ON COLUMN item_mapping.start_ts IS 'Validity start timestamp';
COMMENT ON COLUMN item_mapping.end_ts IS 'Validity end timestamp (NULL = currently active)';
COMMENT ON INDEX idx_mapping_active IS 'Enforces at-most-one active row per (org_id, canonical_key)';


CREATE TABLE match_results (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    item_id UUID NOT NULL REFERENCES items(id),
    price_item_id UUID REFERENCES price_items(id),

    -- Match metadata
    confidence_score REAL NOT NULL CHECK (confidence_score >= 0 AND confidence_score <= 100),
    source TEXT NOT NULL CHECK (source IN ('mapping_memory', 'fuzzy_match', 'review_ui')),
    decision TEXT NOT NULL CHECK (decision IN ('auto-accepted', 'manual-review', 'rejected')),
    reason TEXT NOT NULL,

    -- Audit
    created_by TEXT NOT NULL,
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_match_results_item ON match_results(item_id);
CREATE INDEX idx_match_results_price ON match_results(price_item_id);
CREATE INDEX idx_match_results_decision ON match_results(decision);

COMMENT ON TABLE match_results IS 'Audit trail of all matching decisions';


CREATE TABLE match_flags (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    match_result_id UUID NOT NULL REFERENCES match_results(id) ON DELETE CASCADE,
    item_id UUID NOT NULL REFERENCES items(id),
    price_item_id UUID NOT NULL REFERENCES price_items(id),

    -- Flag details
    flag_type TEXT NOT NULL,  -- "UnitConflict", "SizeMismatch", etc.
    severity TEXT NOT NULL CHECK (severity IN ('Critical-Veto', 'Advisory')),
    message TEXT NOT NULL,

    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_flags_item ON match_flags(item_id);
CREATE INDEX idx_flags_price ON match_flags(price_item_id);
CREATE INDEX idx_flags_match_result ON match_flags(match_result_id);
CREATE INDEX idx_flags_severity ON match_flags(severity);

COMMENT ON TABLE match_flags IS 'Business risk flags detected during matching';
COMMENT ON COLUMN match_flags.severity IS 'Critical-Veto blocks auto-accept; Advisory warns but allows with annotation';


-- ============================================================================
-- RAG Agent: Documents with pgvector Embeddings
-- ============================================================================

CREATE TABLE documents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    title TEXT NOT NULL,
    content TEXT NOT NULL,
    embedding VECTOR(1536),  -- OpenAI text-embedding-3-large dimension

    -- Metadata
    metadata JSONB DEFAULT '{}'::JSONB,
    doc_type TEXT,  -- "ADR", "PRP", "Guide", "PriceBook", etc.
    source_file TEXT,

    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Vector similarity search (ivfflat)
CREATE INDEX idx_documents_embedding
    ON documents
    USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 100);  -- Tune for dataset size (100 for ~10K docs, 1000 for ~1M docs)

-- Full-text search (hybrid with vector)
CREATE INDEX idx_documents_fts
    ON documents
    USING gin(to_tsvector('english', content));

-- Metadata search
CREATE INDEX idx_documents_metadata ON documents USING GIN(metadata);
CREATE INDEX idx_documents_type ON documents(doc_type);

COMMENT ON TABLE documents IS 'RAG knowledge base with pgvector embeddings for semantic search';
COMMENT ON COLUMN documents.embedding IS 'OpenAI text-embedding-3-large (1536 dimensions)';
COMMENT ON INDEX idx_documents_embedding IS 'ivfflat vector index for cosine similarity (tune lists parameter for dataset size)';


-- ============================================================================
-- Helper Functions
-- ============================================================================

-- Function to close current mapping and insert new active row (SCD2 write)
CREATE OR REPLACE FUNCTION upsert_mapping(
    p_org_id TEXT,
    p_canonical_key TEXT,
    p_price_item_id UUID,
    p_created_by TEXT,
    p_reason TEXT
) RETURNS UUID AS $$
DECLARE
    v_new_id UUID;
BEGIN
    -- Close current active row (if exists)
    UPDATE item_mapping
    SET end_ts = NOW()
    WHERE org_id = p_org_id
      AND canonical_key = p_canonical_key
      AND end_ts IS NULL;

    -- Insert new active row
    INSERT INTO item_mapping (
        org_id,
        canonical_key,
        price_item_id,
        start_ts,
        end_ts,
        created_by,
        reason
    ) VALUES (
        p_org_id,
        p_canonical_key,
        p_price_item_id,
        NOW(),
        NULL,
        p_created_by,
        p_reason
    ) RETURNING id INTO v_new_id;

    RETURN v_new_id;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION upsert_mapping IS 'Atomic SCD2 write: close current mapping and insert new active row';


-- Function for as-of temporal queries
CREATE OR REPLACE FUNCTION get_mapping_as_of(
    p_org_id TEXT,
    p_canonical_key TEXT,
    p_as_of TIMESTAMP WITH TIME ZONE DEFAULT NOW()
) RETURNS UUID AS $$
DECLARE
    v_price_item_id UUID;
BEGIN
    SELECT price_item_id INTO v_price_item_id
    FROM item_mapping
    WHERE org_id = p_org_id
      AND canonical_key = p_canonical_key
      AND start_ts <= p_as_of
      AND (end_ts IS NULL OR end_ts > p_as_of)
    LIMIT 1;

    RETURN v_price_item_id;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION get_mapping_as_of IS 'Retrieve mapping valid at specific timestamp (reproducible reports)';


-- ============================================================================
-- Sample Data & Testing
-- ============================================================================

-- Insert sample classification codes (for reference)
CREATE TABLE IF NOT EXISTS classification_codes (
    code INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT
);

INSERT INTO classification_codes (code, name, description) VALUES
    (2211, 'Plumbing Fixtures', 'Sinks, toilets, urinals, showers, faucets'),
    (2212, 'Sanitary Waste', 'Sanitary drainage systems'),
    (2215, 'Pipe Fittings & Valves', 'Elbows, tees, reducers, valves'),
    (2301, 'HVAC Equipment', 'Boilers, chillers, AHUs, pumps'),
    (2302, 'HVAC Distribution', 'Ducts, air terminals, diffusers, grilles'),
    (2601, 'Electrical Power Distribution', 'Panels, switchboards, receptacles'),
    (2603, 'Lighting & Branch Wiring', 'Light fixtures, lamps, switches'),
    (2650, 'Cable Management', 'Cable trays, conduit, containment'),
    (2701, 'Communications & Data', 'Data devices, communication systems'),
    (2801, 'Fire Detection & Alarm', 'Smoke detectors, fire alarm panels'),
    (9999, 'Unknown', 'Requires manual classification')
ON CONFLICT (code) DO NOTHING;

COMMENT ON TABLE classification_codes IS 'Reference table for Uniformat Level 3 classification codes';


-- ============================================================================
-- Database Maintenance
-- ============================================================================

-- Auto-update timestamps
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER documents_updated_at
    BEFORE UPDATE ON documents
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at();


-- ============================================================================
-- Permissions & Security (production recommendations)
-- ============================================================================

-- Create application user with limited privileges
-- CREATE USER bimcalc_app WITH PASSWORD 'changeme';
-- GRANT CONNECT ON DATABASE bimcalc TO bimcalc_app;
-- GRANT USAGE ON SCHEMA public TO bimcalc_app;
-- GRANT SELECT, INSERT, UPDATE ON ALL TABLES IN SCHEMA public TO bimcalc_app;
-- GRANT USAGE ON ALL SEQUENCES IN SCHEMA public TO bimcalc_app;
-- GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA public TO bimcalc_app;

-- Prevent DELETE on mapping memory (immutability)
-- REVOKE DELETE ON item_mapping FROM bimcalc_app;

COMMENT ON DATABASE bimcalc IS 'BIMCalc MVP: Classification-first cost matching engine with SCD2 mapping memory';
