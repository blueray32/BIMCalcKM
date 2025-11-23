"""BIMCalc Pydantic models for type-safe data validation.

All models follow EU locale defaults and BIMCalc invariants.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Any, Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, field_validator


class FlagSeverity(str, Enum):
    """Risk flag severity levels."""

    CRITICAL_VETO = "Critical-Veto"  # Blocks auto-accept, disables UI "Accept" button
    ADVISORY = "Advisory"  # Warns but allows accept with annotation


class MatchDecision(str, Enum):
    """Match decision outcomes."""

    AUTO_ACCEPTED = "auto-accepted"
    MANUAL_REVIEW = "manual-review"
    REJECTED = "rejected"


class Item(BaseModel):
    """BIM item from Revit schedule or other source."""

    id: UUID = Field(default_factory=uuid4)
    org_id: str
    project_id: str

    # Classification
    classification_code: int | None = None
    canonical_key: str | None = None

    # Revit metadata
    category: str | None = None
    family: str
    type_name: str
    system_type: str | None = None

    # Explicit classification overrides (highest trust)
    omniclass_code: int | None = None
    uniformat_code: int | None = None

    # Quantities
    quantity: Decimal | None = None
    unit: str | None = None  # "m", "ea", "m2", "m3"

    # Physical attributes (for canonical key and matching)
    width_mm: float | None = None
    height_mm: float | None = None
    dn_mm: float | None = None  # Pipe diameter
    angle_deg: float | None = None
    material: str | None = None

    # Audit
    source_file: str | None = None
    created_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        json_schema_extra = {
            "example": {
                "org_id": "acme-construction",
                "project_id": "project-a",
                "family": "Pipe Elbow",
                "type_name": "90° DN100 Steel",
                "category": "Pipe Fittings",
                "classification_code": 2215,
                "canonical_key": "a1b2c3d4e5f6g7h8",
                "width_mm": 100.0,
                "angle_deg": 90.0,
                "material": "Steel",
                "unit": "ea",
                "quantity": Decimal("10"),
            }
        }


class PriceItem(BaseModel):
    """Vendor price item from catalog."""

    id: UUID = Field(default_factory=uuid4)
    classification_code: int  # Required for classification blocking
    vendor_id: str | None = None
    sku: str
    description: str

    # Unit pricing
    unit: str  # "m", "ea", "m2", "m3"
    unit_price: Decimal
    currency: str = "EUR"  # Default EU
    vat_rate: Decimal | None = None  # 0.23 for Irish/EU standard

    # Physical attributes (stored in JSONB or explicit columns)
    width_mm: float | None = None
    height_mm: float | None = None
    dn_mm: float | None = None
    angle_deg: float | None = None
    material: str | None = None

    # Audit & metadata
    last_updated: datetime | None = None
    vendor_note: str | None = None  # "Discontinued", "12-week lead time", etc.
    attributes: dict[str, Any] = Field(default_factory=dict)  # Additional JSONB data

    @field_validator("unit_price")
    @classmethod
    def validate_unit_price(cls, v: Decimal) -> Decimal:
        if v < 0:
            raise ValueError("unit_price must be non-negative")
        return v

    class Config:
        json_schema_extra = {
            "example": {
                "classification_code": 2215,
                "vendor_id": "acme-supplies",
                "sku": "ELB-100-90-STL",
                "description": "Steel Pipe Elbow 90° DN100",
                "unit": "ea",
                "unit_price": Decimal("45.50"),
                "currency": "EUR",
                "vat_rate": Decimal("0.23"),
                "width_mm": 100.0,
                "angle_deg": 90.0,
                "material": "Steel",
            }
        }


class Flag(BaseModel):
    """Business risk flag detected during matching."""

    type: str  # "UnitConflict", "SizeMismatch", etc.
    severity: FlagSeverity
    message: str

    class Config:
        json_schema_extra = {
            "example": {
                "type": "UnitConflict",
                "severity": "Critical-Veto",
                "message": "Item unit 'm' does not match price unit 'ea'",
            }
        }


class MatchResult(BaseModel):
    """Result of matching an item to a price."""

    item_id: UUID
    price_item_id: UUID | None
    confidence_score: float  # 0-100
    source: Literal["mapping_memory", "fuzzy_match", "review_ui"]  # Match origin
    flags: list[Flag] = Field(default_factory=list)
    decision: MatchDecision
    reason: str
    created_by: str  # User email or "system"
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    @field_validator("confidence_score")
    @classmethod
    def validate_confidence(cls, v: float) -> float:
        if not 0 <= v <= 100:
            raise ValueError("confidence_score must be between 0 and 100")
        return v

    class Config:
        json_schema_extra = {
            "example": {
                "item_id": "550e8400-e29b-41d4-a716-446655440000",
                "price_item_id": "660e8400-e29b-41d4-a716-446655440111",
                "confidence_score": 95.5,
                "source": "mapping_memory",
                "flags": [],
                "decision": "auto-accepted",
                "reason": "High confidence, no flags, via canonical key mapping",
                "created_by": "system",
            }
        }


class MappingEntry(BaseModel):
    """SCD Type-2 mapping memory entry."""

    id: UUID = Field(default_factory=uuid4)
    org_id: str
    canonical_key: str
    price_item_id: UUID

    # SCD2 temporal fields
    start_ts: datetime = Field(default_factory=datetime.utcnow)
    end_ts: datetime | None = None  # NULL = active row

    # Audit
    created_by: str  # User email or "system"
    reason: str  # "manual match", "auto-accept", "correction", etc.

    @property
    def is_active(self) -> bool:
        """Check if this mapping is currently active (end_ts is NULL)."""
        return self.end_ts is None

    class Config:
        json_schema_extra = {
            "example": {
                "org_id": "acme-construction",
                "canonical_key": "a1b2c3d4e5f6g7h8",
                "price_item_id": "660e8400-e29b-41d4-a716-446655440111",
                "start_ts": "2025-01-15T10:30:00Z",
                "end_ts": None,
                "created_by": "engineer@example.com",
                "reason": "manual match after flag resolution",
            }
        }


class CandidateMatch(BaseModel):
    """A candidate price item with similarity score."""

    price_item: PriceItem
    score: float  # Fuzzy match score (0-100)
    flags: list[Flag] = Field(default_factory=list)

    class Config:
        json_schema_extra = {
            "example": {
                "price_item": {
                    "sku": "ELB-100-90-STL",
                    "description": "Steel Pipe Elbow 90° DN100",
                    "unit_price": Decimal("45.50"),
                },
                "score": 87.5,
                "flags": [],
            }
        }


class ReportRow(BaseModel):
    """Single row in a BIMCalc cost report."""

    item_id: UUID
    family: str
    type_name: str
    quantity: Decimal | None
    unit: str | None

    # Matched price
    canonical_key: str | None = None
    sku: str | None = None
    description: str | None = None
    unit_price: Decimal | None = None
    currency: str = "EUR"
    vat_rate: Decimal | None = None

    # Calculated totals
    total_price: Decimal | None = None
    total_price_with_vat: Decimal | None = None

    # Audit
    matched_by: str | None = None
    match_reason: str | None = None

    class Config:
        json_schema_extra = {
            "example": {
                "item_id": "550e8400-e29b-41d4-a716-446655440000",
                "family": "Pipe Elbow",
                "type_name": "90° DN100 Steel",
                "quantity": Decimal("10"),
                "unit": "ea",
                "sku": "ELB-100-90-STL",
                "unit_price": Decimal("45.50"),
                "total_price": Decimal("455.00"),
                "total_price_with_vat": Decimal("559.65"),
                "matched_by": "engineer@example.com",
                "match_reason": "manual match",
            }
        }
