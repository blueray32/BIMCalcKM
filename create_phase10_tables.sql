-- Phase 10 Database Tables for Staging
-- Create project_documents and extracted_items tables

CREATE TABLE IF NOT EXISTS project_documents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id TEXT NOT NULL,
    project_id TEXT NOT NULL,
    filename TEXT NOT NULL,
    file_path TEXT NOT NULL,
    file_type TEXT NOT NULL,
    file_size_bytes INTEGER NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    error_message TEXT,
    uploaded_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    processed_at TIMESTAMP WITH TIME ZONE
);

CREATE INDEX IF NOT EXISTS ix_project_documents_org_id ON project_documents (org_id);
CREATE INDEX IF NOT EXISTS ix_project_documents_project_id ON project_documents (project_id);

CREATE TABLE IF NOT EXISTS extracted_items (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id UUID NOT NULL REFERENCES project_documents(id) ON DELETE CASCADE,
    raw_text TEXT NOT NULL,
    page_number INTEGER NOT NULL,
    description TEXT,
    quantity NUMERIC(12, 2),
    unit TEXT,
    unit_price NUMERIC(12, 2),
    total_price NUMERIC(12, 2),
    confidence_score NUMERIC(5, 2) DEFAULT 0.0,
    is_converted BOOLEAN DEFAULT FALSE,
    converted_item_id UUID
);

CREATE INDEX IF NOT EXISTS ix_extracted_items_document_id ON extracted_items (document_id);
