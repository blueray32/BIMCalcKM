"""Database models for Enhanced Intelligence features.

Includes models for:
- Risk Scoring
- Compliance Rules
- Recommendations
"""

from __future__ import annotations

from datetime import datetime
from uuid import uuid4, UUID

from sqlalchemy import (
    Text,
    ForeignKey,
    Float,
    JSON,
    DateTime,
    func,
    CheckConstraint,
    Index,
)
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID as Uuid

from bimcalc.db.models import Base


class RiskScoreModel(Base):
    """Calculated risk score for a project item."""

    __tablename__ = "risk_scores"

    id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid4
    )
    org_id: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    project_id: Mapped[str] = mapped_column(Text, nullable=False, index=True)

    item_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("items.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Risk Metrics (0-100)
    total_risk_score: Mapped[float] = mapped_column(Float, nullable=False)
    confidence_risk: Mapped[float] = mapped_column(Float, nullable=False)
    price_risk: Mapped[float] = mapped_column(Float, nullable=False)
    data_quality_risk: Mapped[float] = mapped_column(Float, nullable=False)

    # Metadata
    risk_factors: Mapped[dict] = mapped_column(JSON, default=dict)  # Detailed breakdown
    calculated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        CheckConstraint(
            "total_risk_score >= 0 AND total_risk_score <= 100",
            name="check_total_risk_range",
        ),
    )


class ComplianceRuleModel(Base):
    """Configurable compliance rule for an organization."""

    __tablename__ = "compliance_rules"

    id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid4
    )
    org_id: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    project_id: Mapped[str] = mapped_column(Text, nullable=False, index=True)

    name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)

    # Rule definition
    rule_logic: Mapped[dict] = mapped_column(
        JSON, nullable=False
    )  # e.g. {"field": "fire_rating", "op": ">=", "val": 60}

    # Metadata
    source_document_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("documents.id", ondelete="SET NULL"), index=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    created_by: Mapped[str] = mapped_column(Text, default="system")


class ComplianceResultModel(Base):
    """Result of checking an item against a compliance rule."""

    __tablename__ = "compliance_results"

    id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid4
    )
    item_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("items.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    rule_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("compliance_rules.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Outcome
    status: Mapped[str] = mapped_column(
        Text, nullable=False, index=True
    )  # 'pass', 'fail', 'warning'
    message: Mapped[str] = mapped_column(Text, nullable=False)

    checked_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        CheckConstraint(
            "status IN ('pass', 'fail', 'warning')", name="check_compliance_status"
        ),
        Index("idx_compliance_results_item", "item_id"),
        Index("idx_compliance_results_rule", "rule_id"),
    )
