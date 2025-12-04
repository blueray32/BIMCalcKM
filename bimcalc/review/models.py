"""Data structures consumed by the review UI."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from uuid import UUID

from bimcalc.models import FlagSeverity


@dataclass(slots=True)
class ReviewItem:
    id: UUID
    org_id: str
    project_id: str
    canonical_key: str | None
    family: str
    type_name: str
    category: str | None
    system_type: str | None
    classification_code: int | None  # For escape-hatch detection
    quantity: Decimal | None
    unit: str | None
    width_mm: float | None
    height_mm: float | None
    dn_mm: float | None
    angle_deg: float | None
    material: str | None
    source_file: str | None


@dataclass(slots=True)
class ReviewPrice:
    id: UUID
    vendor_id: str | None
    sku: str
    description: str
    classification_code: int | None  # For escape-hatch detection
    unit: str
    unit_price: Decimal
    currency: str
    vat_rate: Decimal | None
    width_mm: float | None
    height_mm: float | None
    dn_mm: float | None
    angle_deg: float | None
    material: str | None
    last_updated: datetime | None
    vendor_note: str | None


@dataclass(slots=True)
class ReviewFlag:
    type: str
    severity: FlagSeverity
    message: str

    @property
    def is_critical(self) -> bool:
        return self.severity == FlagSeverity.CRITICAL_VETO


@dataclass(slots=True)
class ReviewRecord:
    match_result_id: UUID
    item: ReviewItem
    price: ReviewPrice | None
    confidence_score: float
    source: str
    reason: str
    created_by: str
    timestamp: datetime
    flags: list[ReviewFlag] = field(default_factory=list)

    @property
    def has_flags(self) -> bool:
        return len(self.flags) > 0

    @property
    def has_critical_flags(self) -> bool:
        return any(flag.is_critical for flag in self.flags)

    @property
    def flag_types(self) -> list[str]:
        return [flag.type for flag in self.flags]

    @property
    def requires_annotation(self) -> bool:
        return any(flag.severity == FlagSeverity.ADVISORY for flag in self.flags)

    @property
    def is_escape_hatch_match(self) -> bool:
        """Check if this is an out-of-class match (escape-hatch was used)."""
        if (
            not self.price
            or self.item.classification_code is None
            or self.price.classification_code is None
        ):
            return False
        return self.item.classification_code != self.price.classification_code
