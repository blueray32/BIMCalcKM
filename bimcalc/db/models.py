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
    ForeignKey,
    Index,
    Integer,
    JSON,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.sql import func


class Base(DeclarativeBase):
    """Base class for all models."""

    pass


class ItemModel(Base):
    """BIM item from Revit schedule or other source."""

    __tablename__ = "items"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
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
    """Vendor price catalog item."""

    __tablename__ = "price_items"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    classification_code: Mapped[int] = mapped_column(
        Integer, nullable=False, index=True
    )  # Required for blocking
    vendor_id: Mapped[Optional[str]] = mapped_column(Text, index=True)
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

    # Audit & metadata
    last_updated: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True))
    vendor_note: Mapped[Optional[str]] = mapped_column(Text)
    attributes: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        CheckConstraint("unit_price >= 0", name="check_unit_price_non_negative"),
        Index("idx_price_class", "classification_code"),  # CRITICAL for blocking
    )


class ItemMappingModel(Base):
    """SCD Type-2 mapping memory for learning curve."""

    __tablename__ = "item_mapping"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    org_id: Mapped[str] = mapped_column(Text, nullable=False)
    canonical_key: Mapped[str] = mapped_column(Text, nullable=False)
    price_item_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)

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
            postgresql_where="end_ts IS NULL",
        ),
        # Temporal queries (as-of)
        Index("idx_mapping_temporal", "org_id", "canonical_key", "start_ts", "end_ts"),
    )


class MatchFlagModel(Base):
    """Business risk flag detected during matching."""

    __tablename__ = "match_flags"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    match_result_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("match_results.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    item_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False, index=True)
    price_item_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False, index=True)

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

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    item_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False, index=True)
    price_item_id: Mapped[Optional[UUID]] = mapped_column(
        PGUUID(as_uuid=True), index=True
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


class DocumentModel(Base):
    """RAG knowledge base document with pgvector embeddings."""

    __tablename__ = "documents"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
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
