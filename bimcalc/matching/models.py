"""Data models for matching engine."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional
from uuid import UUID


@dataclass
class Item:
    """BIM item from Revit schedule."""

    id: UUID
    org_id: str
    project_id: str
    classification_code: Optional[int] = None
    canonical_key: Optional[str] = None
    category: Optional[str] = None
    family: Optional[str] = None
    type_name: Optional[str] = None
    quantity: Optional[float] = None
    unit: Optional[str] = None
    width_mm: Optional[float] = None
    height_mm: Optional[float] = None
    dn_mm: Optional[float] = None
    angle_deg: Optional[float] = None
    material: Optional[str] = None
    manufacturer_part_number: Optional[str] = None  # For exact matching
    vendor_sku: Optional[str] = None  # For exact matching
    source_file: Optional[str] = None
    created_at: Optional[datetime] = None


@dataclass
class PriceItem:
    """Price item from vendor catalog."""

    id: UUID
    classification_code: int
    vendor_id: Optional[str] = None
    sku: Optional[str] = None
    manufacturer_part_number: Optional[str] = None  # For exact matching
    description: Optional[str] = None
    family: Optional[str] = None  # Parsed from description
    type_name: Optional[str] = None  # Parsed from description
    unit: Optional[str] = None
    unit_price: Optional[float] = None
    currency: str = "EUR"
    vat_rate: Optional[float] = None
    last_updated: Optional[datetime] = None
    width_mm: Optional[float] = None
    height_mm: Optional[float] = None
    dn_mm: Optional[float] = None
    angle_deg: Optional[float] = None
    material: Optional[str] = None


@dataclass
class MappingRecord:
    """SCD Type-2 mapping record."""

    id: UUID
    org_id: str
    canonical_key: str
    price_item_id: UUID
    start_ts: datetime
    end_ts: Optional[datetime] = None
    created_by: Optional[str] = None
    reason: Optional[str] = None

    @property
    def is_active(self) -> bool:
        """Check if mapping is currently active."""
        return self.end_ts is None


class MappingMemory:
    """In-memory mapping cache for canonical key lookups."""

    def __init__(self) -> None:
        """Initialize empty mapping memory."""
        self._mappings: dict[tuple[str, str], MappingRecord] = {}

    def lookup(self, org_id: str, canonical_key: str) -> Optional[MappingRecord]:
        """Look up active mapping for canonical key.

        Args:
            org_id: Organization ID
            canonical_key: Canonical key to look up

        Returns:
            Active mapping record or None
        """
        return self._mappings.get((org_id, canonical_key))

    def add(self, mapping: MappingRecord) -> None:
        """Add mapping to memory.

        Args:
            mapping: Mapping record to add
        """
        if mapping.is_active:
            self._mappings[(mapping.org_id, mapping.canonical_key)] = mapping

    def remove(self, org_id: str, canonical_key: str) -> None:
        """Remove mapping from memory.

        Args:
            org_id: Organization ID
            canonical_key: Canonical key to remove
        """
        self._mappings.pop((org_id, canonical_key), None)

    def clear(self) -> None:
        """Clear all mappings from memory."""
        self._mappings.clear()
