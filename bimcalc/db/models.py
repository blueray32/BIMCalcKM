"""SQLAlchemy async database models for BIMCalc.

Maps to PostgreSQL schema with SCD Type-2 support for mapping memory.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import (
    JSON,
    TIMESTAMP,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    text,
)
from pgvector.sqlalchemy import Vector

from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.sql import func


class Base(DeclarativeBase):
    """Base class for all models."""

    pass


class ItemModel(Base):
    """BIM item from Revit schedule or other source."""

    __tablename__ = "items"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    org_id: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    project_id: Mapped[str] = mapped_column(Text, nullable=False, index=True)

    # Classification
    classification_code: Mapped[str | None] = mapped_column(Text, index=True)
    canonical_key: Mapped[str | None] = mapped_column(Text, index=True)
    
    # Link to Price Item (Foreign Key)
    price_item_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), index=True)

    # Revit metadata
    category: Mapped[str | None] = mapped_column(Text)
    family: Mapped[str] = mapped_column(Text, nullable=False)
    type_name: Mapped[str] = mapped_column(Text, nullable=False)
    system_type: Mapped[str | None] = mapped_column(Text)
    element_id: Mapped[str | None] = mapped_column(Text)  # Revit Element ID

    # Explicit classification overrides
    omniclass_code: Mapped[int | None] = mapped_column(Integer)
    uniformat_code: Mapped[int | None] = mapped_column(Integer)

    # Quantities
    quantity: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    unit: Mapped[str | None] = mapped_column(Text)

    # Physical attributes
    width_mm: Mapped[float | None] = mapped_column()
    height_mm: Mapped[float | None] = mapped_column()
    dn_mm: Mapped[float | None] = mapped_column()
    angle_deg: Mapped[float | None] = mapped_column()
    material: Mapped[str | None] = mapped_column(Text)

    # Audit
    source_file: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    
    # Flexible attributes for domain-specific data
    attributes: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)

    __table_args__ = (
        Index("idx_items_class", "classification_code"),  # CRITICAL for blocking
        Index("idx_items_canonical", "canonical_key"),  # CRITICAL for O(1) lookup
        Index("idx_items_org_project_created", "org_id", "project_id", "created_at"),  # Items list performance
    )


class PriceItemModel(Base):
    """Vendor price catalog item with SCD Type-2 history tracking.

    Implements full Slowly Changing Dimension Type-2 for auditable price history.
    Each price change creates a new record, preserving complete timeline.
    """

    __tablename__ = "price_items"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)

    # Multi-tenant scoping (CRITICAL for org isolation)
    org_id: Mapped[str] = mapped_column(Text, nullable=False, index=True)

    # Composite business key (org_id + item_code + region)
    item_code: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    region: Mapped[str] = mapped_column(Text, nullable=False, index=True)

    classification_code: Mapped[str] = mapped_column(
        Text, nullable=False, index=True
    )  # Required for blocking
    vendor_id: Mapped[str | None] = mapped_column(Text, index=True)
    vendor_code: Mapped[str | None] = mapped_column(Text, index=True)
    sku: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    description: Mapped[str] = mapped_column(Text, nullable=False)

    # Unit pricing (EU defaults)
    unit: Mapped[str] = mapped_column(Text, nullable=False)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="EUR")
    vat_rate: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))

    # Labor Estimation
    labor_hours: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    labor_code: Mapped[str | None] = mapped_column(Text, index=True)

    # Physical attributes
    width_mm: Mapped[float | None] = mapped_column()
    height_mm: Mapped[float | None] = mapped_column()
    dn_mm: Mapped[float | None] = mapped_column()
    angle_deg: Mapped[float | None] = mapped_column()
    material: Mapped[str | None] = mapped_column(Text)

    # Governance fields (data provenance & integrity)
    source_name: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    source_currency: Mapped[str] = mapped_column(String(3), nullable=False)
    original_effective_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # SCD Type-2 temporal fields
    valid_from: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    valid_to: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    is_current: Mapped[bool] = mapped_column(nullable=False, default=True, index=True)

    # Audit & metadata
    last_updated: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
    vendor_note: Mapped[str | None] = mapped_column(Text)
    attributes: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    import_run_id: Mapped[str | None] = mapped_column(
        Text, ForeignKey("price_import_runs.id", ondelete="SET NULL"), index=True
    )

    __table_args__ = (
        CheckConstraint("unit_price >= 0", name="check_unit_price_non_negative"),
        CheckConstraint("valid_to IS NULL OR valid_to > valid_from", name="check_valid_period"),

        # CRITICAL for blocking by classification
        Index("idx_price_class", "classification_code"),

        # SCD Type-2: Enforce one active record per (org_id, item_code, region)
        Index(
            "idx_price_active_unique",
            "org_id",
            "item_code",
            "region",
            unique=True,
            postgresql_where=text("is_current = true"),
            sqlite_where=text("is_current = 1"),
        ),

        # Temporal queries (as-of lookups)
        Index("idx_price_temporal", "org_id", "item_code", "region", "valid_from", "valid_to"),

        # Current price lookups (most common query)
        Index("idx_price_current", "org_id", "item_code", "region", "is_current"),

        # Source tracking for operational monitoring
        Index("idx_price_source", "source_name", "last_updated"),
    )


class PriceImportRunModel(Base):
    """Audit log for external price imports (e.g., Crail4)."""

    __tablename__ = "price_import_runs"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    org_id: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    source: Mapped[str] = mapped_column(Text, nullable=False)
    started_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))
    status: Mapped[str] = mapped_column(Text, nullable=False)
    items_fetched: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    items_loaded: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    items_rejected: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    rejection_reasons: Mapped[dict | None] = mapped_column(JSON)
    error_message: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class PriceSourceModel(Base):
    """Configuration for supplier price data sources.

    Supports multi-source price intelligence by storing URLs and scraping
    configuration for each supplier. Used by MultiSourceOrchestrator for
    parallel price fetching and comparison.
    """

    __tablename__ = "price_sources"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    org_id: Mapped[str] = mapped_column(Text, nullable=False, index=True)

    # Source identification
    name: Mapped[str] = mapped_column(Text, nullable=False)  # "TLC Direct", "Rexel UK"
    url: Mapped[str] = mapped_column(Text, nullable=False)  # Base catalog URL
    domain: Mapped[str] = mapped_column(Text, nullable=False, index=True)  # For rate limiting

    # Configuration
    enabled: Mapped[bool] = mapped_column(nullable=False, default=True, index=True)
    cache_ttl_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=86400)  # 24hrs
    rate_limit_seconds: Mapped[float] = mapped_column(Float, nullable=False, default=2.0)

    # Operational metadata
    last_sync_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_sync_status: Mapped[str | None] = mapped_column(Text)  # "success", "failed", "partial"
    last_sync_items_count: Mapped[int | None] = mapped_column(Integer)
    last_sync_error: Mapped[str | None] = mapped_column(Text)

    # Audit
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
    created_by: Mapped[str | None] = mapped_column(Text)

    # Additional metadata
    notes: Mapped[str | None] = mapped_column(Text)
    tags: Mapped[list[str] | None] = mapped_column(JSON)  # JSON for cross-DB compatibility

    __table_args__ = (
        # Prevent duplicate sources per org
        UniqueConstraint("org_id", "domain", name="uq_price_source_domain"),

        # Index for enabled sources (most common query)
        Index("idx_price_sources_enabled", "org_id", "enabled"),

        # Index for last sync tracking
        Index("idx_price_sources_last_sync", "org_id", "last_sync_at"),
    )


class ClassificationMappingModel(Base):
    """Crosswalk table for translating classification schemes."""

    __tablename__ = "classification_mappings"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    org_id: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    source_scheme: Mapped[str] = mapped_column(Text, nullable=False)
    source_code: Mapped[str] = mapped_column(Text, nullable=False)
    target_scheme: Mapped[str] = mapped_column(Text, nullable=False)
    target_code: Mapped[str] = mapped_column(Text, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    mapping_source: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    created_by: Mapped[str | None] = mapped_column(Text)

    __table_args__ = (
        UniqueConstraint("org_id", "source_scheme", "source_code", "target_scheme"),
    )


class ItemMappingModel(Base):
    """SCD Type-2 mapping memory for learning curve."""

    __tablename__ = "item_mapping"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    org_id: Mapped[str] = mapped_column(Text, nullable=False)
    canonical_key: Mapped[str] = mapped_column(Text, nullable=False)
    price_item_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)

    # SCD2 temporal fields
    start_ts: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )
    end_ts: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))

    # Audit trail
    created_by: Mapped[str] = mapped_column(Text, nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)

    __table_args__ = (
        UniqueConstraint("org_id", "canonical_key", "start_ts", name="uq_mapping_start"),
        CheckConstraint("end_ts IS NULL OR end_ts > start_ts", name="check_valid_period"),
        # At most one active row per (org_id, canonical_key)
        Index(
            "idx_mapping_active",
            "org_id",
            "canonical_key",
            unique=True,
            postgresql_where=text("end_ts IS NULL"),
            sqlite_where=text("end_ts IS NULL"),
        ),
        # Temporal queries (as-of)
        Index("idx_mapping_temporal", "org_id", "canonical_key", "start_ts", "end_ts"),
    )


class MatchFlagModel(Base):
    """Business risk flag detected during matching."""

    __tablename__ = "match_flags"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    match_result_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("match_results.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    item_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False, index=True)
    price_item_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False, index=True)

    # Flag details
    flag_type: Mapped[str] = mapped_column(Text, nullable=False)
    severity: Mapped[str] = mapped_column(Text, nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        CheckConstraint(
            "severity IN ('Critical-Veto', 'Advisory')", name="check_severity_valid"
        ),
        Index("idx_flags_severity", "severity"),
        Index("idx_flags_item", "item_id"),
        Index("idx_flags_price", "price_item_id"),
        Index("idx_flags_match_result", "match_result_id"),
    )


class MatchResultModel(Base):
    """Audit trail of all matching decisions."""

    __tablename__ = "match_results"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    item_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False, index=True)
    price_item_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True), index=True
    )

    # Match metadata
    confidence_score: Mapped[float] = mapped_column(nullable=False)
    source: Mapped[str] = mapped_column(Text, nullable=False)
    decision: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    reason: Mapped[str] = mapped_column(Text, nullable=False)

    # Audit
    created_by: Mapped[str] = mapped_column(Text, nullable=False)
    timestamp: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        CheckConstraint(
            "confidence_score >= 0 AND confidence_score <= 100", name="check_confidence_range"
        ),
        CheckConstraint(
            "source IN ('mapping_memory', 'fuzzy_match', 'review_ui')",
            name="check_source_valid",
        ),
        CheckConstraint(
            "decision IN ('auto-accepted', 'manual-review', 'rejected')",
            name="check_decision_valid",
        ),
    )


class ProjectClassificationMappingModel(Base):
    """Project-specific classification code mappings.
    
    Allows projects to define their own local classification codes
    (e.g., "61" from Tritex) and map them to standard BIMCalc codes
    (e.g., "2601" for Electrical Distribution).
    """

    __tablename__ = "project_classification_mappings"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    org_id: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    project_id: Mapped[str] = mapped_column(Text, nullable=False, index=True)

    # The project-specific code (e.g., "61" from Tritex)
    local_code: Mapped[str] = mapped_column(String(50), nullable=False)

    # The standard BIMCalc code it maps to (e.g., "2601")
    standard_code: Mapped[str] = mapped_column(String(50), nullable=False)

    # Optional metadata
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)
    created_by: Mapped[str] = mapped_column(String(255), default="system", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (
        # Unique constraint: one project can't have duplicate local codes
        UniqueConstraint('org_id', 'project_id', 'local_code', name='uq_project_local_code'),
        Index('idx_project_classification_lookup', 'org_id', 'project_id', 'local_code'),
    )


# Type alias for consistency
DateTimeColumn = Text  # Stored as ISO8601 string


class DataSyncLogModel(Base):
    """Granular logging for automated price data synchronization pipeline.

    Provides per-source operational monitoring and diagnostics.
    Critical for resilience: isolates failures to individual sources.
    """

    __tablename__ = "data_sync_log"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)

    # Pipeline execution tracking
    run_timestamp: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, index=True
    )
    source_name: Mapped[str] = mapped_column(Text, nullable=False, index=True)

    # Execution outcome
    status: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    records_updated: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    records_inserted: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    records_failed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # Detailed diagnostics
    message: Mapped[str | None] = mapped_column(Text)
    error_details: Mapped[dict | None] = mapped_column(JSON)

    # Execution metrics
    duration_seconds: Mapped[float | None] = mapped_column()

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        CheckConstraint(
            "status IN ('SUCCESS', 'FAILED', 'PARTIAL_SUCCESS', 'SKIPPED')",
            name="check_sync_status_valid",
        ),
        CheckConstraint("records_updated >= 0", name="check_records_updated_non_negative"),
        CheckConstraint("records_inserted >= 0", name="check_records_inserted_non_negative"),
        CheckConstraint("records_failed >= 0", name="check_records_failed_non_negative"),

        # Query by run for full pipeline status
        Index("idx_sync_run", "run_timestamp", "source_name"),

        # Alert queries (find failures)
        Index("idx_sync_failures", "status", "run_timestamp"),

        # Source health monitoring
        Index("idx_sync_source_health", "source_name", "status", "run_timestamp"),
    )


class DocumentModel(Base):
    """RAG knowledge base document with pgvector embeddings."""

    __tablename__ = "documents"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    embedding: Mapped[Vector] = mapped_column(Vector(1536))  # Requires pgvector type

    # Document metadata (renamed to avoid SQLAlchemy conflict)
    doc_metadata: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    tags: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    doc_type: Mapped[str | None] = mapped_column(Text, index=True)
    source_file: Mapped[str | None] = mapped_column(Text)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        # HNSW Index for fast approximate nearest neighbor search
        Index(
            "idx_documents_embedding",
            "embedding",
            postgresql_using="hnsw",
            postgresql_with={"m": 16, "ef_construction": 64},
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
    )


class DocumentLinkModel(Base):
    """Link between an Item and a Document (Many-to-Many)."""

    __tablename__ = "document_links"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    item_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("items.id", ondelete="CASCADE"), nullable=False, index=True
    )
    document_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True
    )
    
    # Link metadata
    link_type: Mapped[str] = mapped_column(Text, nullable=False) # e.g., "commissioning_cert", "manual", "contract"
    confidence: Mapped[float] = mapped_column(Float, default=1.0)
    created_by: Mapped[str] = mapped_column(Text, default="system")
    
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        UniqueConstraint("item_id", "document_id", name="uq_item_document_link"),
    )


class QAChecklistModel(Base):
    """Auto-generated QA testing checklist for items."""
    
    __tablename__ = "qa_checklists"
    
    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    item_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("items.id", ondelete="CASCADE"), nullable=False, unique=True, index=True
    )
    org_id: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    project_id: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    
    # Checklist data (stored as JSON)
    checklist_items: Mapped[dict] = mapped_column(JSON, nullable=False)  # {"items": [...]}
    source_documents: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)  # {"docs": [...]}
    
    # Generation metadata
    auto_generated: Mapped[bool] = mapped_column(default=True, nullable=False)
    generated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), nullable=False
    )
    
    # Completion tracking
    completed_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))
    completion_percent: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    
    # Audit
    created_by: Mapped[str] = mapped_column(Text, default="system", nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
    
    __table_args__ = (
        CheckConstraint("completion_percent >= 0 AND completion_percent <= 100", name="check_completion_range"),
        Index("idx_qa_checklists_org_project", "org_id", "project_id"),
    )


class ChecklistTemplateModel(Base):
    """Reusable checklist templates for common item types."""
    
    __tablename__ = "checklist_templates"
    
    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    
    # Template metadata
    name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    
    # Applicability
    classification_codes: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    category: Mapped[str | None] = mapped_column(Text)  # Optional: Electrical, HVAC, etc.
    
    # Template content (same structure as checklist_items)
    template_items: Mapped[dict] = mapped_column(JSON, nullable=False)
    
    # Template metadata
    is_builtin: Mapped[bool] = mapped_column(default=False, nullable=False)
    created_by: Mapped[str] = mapped_column(Text, default="system", nullable=False)
    
    # Usage tracking
    usage_count: Mapped[int] = mapped_column(default=0, nullable=False)
    
    # Audit
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
    
    __table_args__ = (
        Index("idx_checklist_templates_codes", "classification_codes"),
        Index("idx_checklist_templates_builtin", "is_builtin"),
    )


class ProjectModel(Base):
    """Project metadata and configuration."""
    
    __tablename__ = "projects"
    
    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    
    # Project identification
    org_id: Mapped[str] = mapped_column(Text, nullable=False)
    project_id: Mapped[str] = mapped_column(Text, nullable=False)
    region: Mapped[str] = mapped_column(Text, nullable=False, default="EU")  # EU, UK, US
    
    # Metadata
    display_name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    settings: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    
    # Status
    status: Mapped[str] = mapped_column(Text, default="active", nullable=False)  # active, archived, completed
    
    # Dates
    start_date: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))
    target_completion: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))
    
    # Audit
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    created_by: Mapped[str] = mapped_column(Text, default="system", nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
    
    __table_args__ = (
        UniqueConstraint("org_id", "project_id", name="uq_projects_org_project"),
        Index("idx_projects_org", "org_id"),
        Index("idx_projects_status", "status"),
    )


class LaborRateOverride(Base):
    """Category-specific labor rate overrides for a project.
    
    Allows different labor rates per category (e.g., Electrical, Mechanical).
    When calculating labor costs, category-specific rates take precedence
    over the project's base blended_labor_rate.
    """
    __tablename__ = "labor_rate_overrides"
    
    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    project_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey('projects.id', ondelete='CASCADE'),
        nullable=False,
        index=True
    )
    category: Mapped[str] = mapped_column(Text, nullable=False)
    rate: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), onupdate=func.now()
    )
    
    __table_args__ = (
        UniqueConstraint('project_id', 'category', name='uq_project_category_rate'),
        Index('idx_labor_rate_project', 'project_id'),
    )


class ItemRevisionModel(Base):
    """Track field-level changes across Revit schedule imports.

    Enables:
    - Revision delta reports
    - Change detection between imports
    - Audit trail for item modifications
    - Answering "what changed?" queries
    """

    __tablename__ = "item_revisions"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)

    # Links to the item and import
    item_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), nullable=False, index=True
    )
    org_id: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    project_id: Mapped[str] = mapped_column(Text, nullable=False, index=True)

    # Ingest metadata
    ingest_timestamp: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, index=True
    )
    source_filename: Mapped[str | None] = mapped_column(Text)

    # Change tracking
    field_name: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    old_value: Mapped[str | None] = mapped_column(Text)
    new_value: Mapped[str | None] = mapped_column(Text)
    change_type: Mapped[str] = mapped_column(Text, nullable=False, index=True)

    # Audit
    detected_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        CheckConstraint(
            "change_type IN ('added', 'modified', 'deleted', 'unchanged')",
            name="check_change_type_valid",
        ),
        Index("idx_revisions_item_field", "item_id", "field_name"),
        Index("idx_revisions_org_project_timestamp", "org_id", "project_id", "ingest_timestamp"),
    )


class IngestLogModel(Base):
    """Track Revit schedule import operations with statistics.

    Enables:
    - Ingest history viewing
    - Import statistics
    - Error tracking
    - Performance monitoring
    """

    __tablename__ = "ingest_logs"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)

    org_id: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    project_id: Mapped[str] = mapped_column(Text, nullable=False, index=True)

    # Import details
    filename: Mapped[str] = mapped_column(Text, nullable=False)
    file_hash: Mapped[str | None] = mapped_column(Text)  # Detect duplicate imports

    # Statistics
    items_total: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    items_added: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    items_modified: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    items_unchanged: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    items_deleted: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # Error tracking
    errors: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    warnings: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_details: Mapped[dict | None] = mapped_column(JSON, default=dict)

    # Performance
    processing_time_ms: Mapped[int | None] = mapped_column(Integer)

    # Status
    status: Mapped[str] = mapped_column(Text, nullable=False, index=True)

    # Audit
    started_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), nullable=False, index=True
    )
    completed_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))

    created_by: Mapped[str] = mapped_column(Text, nullable=False, default="system")

    __table_args__ = (
        CheckConstraint(
            "status IN ('running', 'completed', 'failed', 'cancelled')",
            name="check_ingest_status_valid",
        ),
        Index("idx_ingest_org_project_started", "org_id", "project_id", "started_at"),
    )


class TrainingExampleModel(Base):
    """User feedback for training the classifier.
    
    Captures instances where a user manually confirms or corrects a match,
    providing a 'ground truth' label (classification code) for an item description.
    """
    
    __tablename__ = "training_examples"
    
    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    org_id: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    
    # Input features (snapshot at time of feedback)
    item_family: Mapped[str] = mapped_column(Text, nullable=False)
    item_type: Mapped[str] = mapped_column(Text, nullable=False)
    item_description: Mapped[str | None] = mapped_column(Text) # Constructed from attributes
    
    # Target label (Ground Truth)
    target_classification_code: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    
    # Metadata
    source_item_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), index=True)
    price_item_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), index=True)
    feedback_type: Mapped[str] = mapped_column(Text, nullable=False) # 'confirmation', 'correction'
    
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    created_by: Mapped[str] = mapped_column(Text, default="system")


