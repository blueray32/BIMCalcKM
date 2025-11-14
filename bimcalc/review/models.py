"""Data structures consumed by the review UI."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID

from bimcalc.models import FlagSeverity


@dataclass(slots=True)
class ReviewItem:
    id: UUID
    org_id: str
    project_id: str
    canonical_key: Optional[str]
    family: str
    type_name: str
    category: Optional[str]
    system_type: Optional[str]
    classification_code: Optional[int]  # For escape-hatch detection
    quantity: Optional[Decimal]
    unit: Optional[str]
    width_mm: Optional[float]
    height_mm: Optional[float]
    dn_mm: Optional[float]
    angle_deg: Optional[float]
    material: Optional[str]
    source_file: Optional[str]


@dataclass(slots=True)
class ReviewPrice:
    id: UUID
    vendor_id: Optional[str]
    sku: str
    description: str
    classification_code: Optional[int]  # For escape-hatch detection
    unit: str
    unit_price: Decimal
    currency: str
    vat_rate: Optional[Decimal]
    width_mm: Optional[float]
    height_mm: Optional[float]
    dn_mm: Optional[float]
    angle_deg: Optional[float]
    material: Optional[str]
    last_updated: Optional[datetime]
    vendor_note: Optional[str]


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
    price: Optional[ReviewPrice]
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
        if not self.price or self.item.classification_code is None or self.price.classification_code is None:
            return False
        return self.item.classification_code != self.price.classification_code
