from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    JSON,
    DateTime,
    Index,
    Text,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from bimcalc.db.models import Base


class ReportTemplateModel(Base):
    """User-defined template for generating custom reports."""

    __tablename__ = "report_templates"

    id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid4
    )
    org_id: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    project_id: Mapped[str | None] = mapped_column(
        Text, index=True
    )  # Optional: if null, available to all projects in org

    name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)

    # Configuration: JSON object defining sections and settings
    # Example:
    # {
    #   "sections": ["executive_summary", "cost_breakdown", "risk_assessment"],
    #   "options": {"include_charts": true, "format": "pdf"}
    # }
    configuration: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)

    created_by: Mapped[str] = mapped_column(Text, default="system", nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    __table_args__ = (Index("idx_report_templates_org", "org_id"),)
