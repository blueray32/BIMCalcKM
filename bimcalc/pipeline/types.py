"""Type definitions for pipeline operations."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Optional
from enum import Enum


class ImportStatus(str, Enum):
    """Status of an import operation."""

    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    PARTIAL_SUCCESS = "PARTIAL_SUCCESS"
    SKIPPED = "SKIPPED"


@dataclass
class PriceRecord:
    """Normalized price record from any source.

    This is the canonical format all importers must produce.
    """

    # Business key
    item_code: str
    region: str

    # Classification & description
    classification_code: int
    description: str

    # Pricing
    unit: str
    unit_price: Decimal
    currency: str
    vat_rate: Optional[Decimal] = None

    # Physical attributes
    width_mm: Optional[float] = None
    height_mm: Optional[float] = None
    dn_mm: Optional[float] = None
    angle_deg: Optional[float] = None
    material: Optional[str] = None

    # Governance
    source_name: str = ""
    source_currency: str = ""
    original_effective_date: Optional[datetime] = None
    vendor_id: Optional[str] = None
    sku: Optional[str] = None
    vendor_note: Optional[str] = None

    def __post_init__(self):
        """Set defaults for governance fields."""
        if not self.source_currency:
            self.source_currency = self.currency
        if not self.sku:
            self.sku = self.item_code


@dataclass
class ImportResult:
    """Result of an import operation."""

    source_name: str
    status: ImportStatus
    records_inserted: int = 0
    records_updated: int = 0
    records_failed: int = 0
    message: str = ""
    error_details: Optional[dict] = None
    duration_seconds: float = 0.0

    @property
    def success(self) -> bool:
        """Check if import was successful."""
        return self.status in (ImportStatus.SUCCESS, ImportStatus.PARTIAL_SUCCESS)

    @property
    def total_records(self) -> int:
        """Total records processed."""
        return self.records_inserted + self.records_updated + self.records_failed
