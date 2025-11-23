"""SQLAlchemy async database models for BIMCalc.

Maps to PostgreSQL schema with SCD Type-2 support for mapping memory.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID, uuid4

from sqlalchemy import (
    TIMESTAMP,
    CheckConstraint,
    Float,
    ForeignKey,
    Index,
    Integer,
    JSON,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    text,
)
# from sqlalchemy.dialects.postgresql import UUID as PGUUID
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
    classification_code: Mapped[Optional[int]] = mapped_column(Integer, index=True)
    canonical_key: Mapped[Optional[str]] = mapped_column(Text, index=True)

    # Revit metadata
    category: Mapped[Optional[str]] = mapped_column(Text)
    family: Mapped[str] = mapped_column(Text, nullable=False)
    type_name: Mapped[str] = mapped_column(Text, nullable=False)
    system_type: Mapped[Optional[str]] = mapped_column(Text)

    # Explicit classification overrides
    omniclass_code: Mapped[Optional[int]] = mapped_column(Integer)
    uniformat_code: Mapped[Optional[int]] = mapped_column(Integer)

    # Quantities
    quantity: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 2))
    unit: Mapped[Optional[str]] = mapped_column(Text)

    # Physical attributes
    width_mm: Mapped[Optional[float]] = mapped_column()
    height_mm: Mapped[Optional[float]] = mapped_column()
    dn_mm: Mapped[Optional[float]] = mapped_column()
    angle_deg: Mapped[Optional[float]] = mapped_column()
    material: Mapped[Optional[str]] = mapped_column(Text)

    # Audit
    source_file: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        Index("idx_items_class", "classification_code"),  # CRITICAL for blocking
        Index("idx_items_canonical", "canonical_key"),  # CRITICAL for O(1) lookup
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

    classification_code: Mapped[int] = mapped_column(
        Integer, nullable=False, index=True
    )  # Required for blocking
    vendor_id: Mapped[Optional[str]] = mapped_column(Text, index=True)
    vendor_code: Mapped[Optional[str]] = mapped_column(Text, index=True)
    sku: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    description: Mapped[str] = mapped_column(Text, nullable=False)

    # Unit pricing (EU defaults)
    unit: Mapped[str] = mapped_column(Text, nullable=False)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="EUR")
    vat_rate: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 2))

    # Physical attributes
    width_mm: Mapped[Optional[float]] = mapped_column()
    height_mm: Mapped[Optional[float]] = mapped_column()
    dn_mm: Mapped[Optional[float]] = mapped_column()
    angle_deg: Mapped[Optional[float]] = mapped_column()
    material: Mapped[Optional[str]] = mapped_column(Text)

    # Governance fields (data provenance & integrity)
    source_name: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    source_currency: Mapped[str] = mapped_column(String(3), nullable=False)
    original_effective_date: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True))

    # SCD Type-2 temporal fields
    valid_from: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )
    valid_to: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True))
    is_current: Mapped[bool] = mapped_column(nullable=False, default=True, index=True)

    # Audit & metadata
    last_updated: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
    vendor_note: Mapped[Optional[str]] = mapped_column(Text)
    attributes: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), nullable=False
    )
    import_run_id: Mapped[Optional[str]] = mapped_column(
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
    completed_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True))
    status: Mapped[str] = mapped_column(Text, nullable=False)
    items_fetched: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    items_loaded: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    items_rejected: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    rejection_reasons: Mapped[Optional[dict]] = mapped_column(JSON)
    error_message: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), nullable=False
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
    mapping_source: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), nullable=False
    )
    created_by: Mapped[Optional[str]] = mapped_column(Text)

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
    end_ts: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True))

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
        TIMESTAMP(timezone=True), server_default=func.now(), nullable=False
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
    price_item_id: Mapped[Optional[UUID]] = mapped_column(
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
    message: Mapped[Optional[str]] = mapped_column(Text)
    error_details: Mapped[Optional[dict]] = mapped_column(JSON)

    # Execution metrics
    duration_seconds: Mapped[Optional[float]] = mapped_column()

    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), nullable=False
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
    # embedding: Mapped[Optional[Vector]] = mapped_column(Vector(1536))  # Requires pgvector type

    # Document metadata (renamed to avoid SQLAlchemy conflict)
    doc_metadata: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    doc_type: Mapped[Optional[str]] = mapped_column(Text, index=True)
    source_file: Mapped[Optional[str]] = mapped_column(Text)

    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), nullable=False
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
    source_filename: Mapped[Optional[str]] = mapped_column(Text)

    # Change tracking
    field_name: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    old_value: Mapped[Optional[str]] = mapped_column(Text)
    new_value: Mapped[Optional[str]] = mapped_column(Text)
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
    file_hash: Mapped[Optional[str]] = mapped_column(Text)  # Detect duplicate imports

    # Statistics
    items_total: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    items_added: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    items_modified: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    items_unchanged: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    items_deleted: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # Error tracking
    errors: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    warnings: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_details: Mapped[Optional[dict]] = mapped_column(JSON, default=dict)

    # Performance
    processing_time_ms: Mapped[Optional[int]] = mapped_column(Integer)

    # Status
    status: Mapped[str] = mapped_column(Text, nullable=False, index=True)

    # Audit
    started_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), nullable=False, index=True
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True))

    created_by: Mapped[str] = mapped_column(Text, nullable=False, default="system")

    __table_args__ = (
        CheckConstraint(
            "status IN ('running', 'completed', 'failed', 'cancelled')",
            name="check_ingest_status_valid",
        ),
        Index("idx_ingest_org_project_started", "org_id", "project_id", "started_at"),
    )
