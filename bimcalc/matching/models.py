"""Data models for matching engine."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass
class Item:
    """BIM item from Revit schedule."""

    id: UUID
    org_id: str
    project_id: str
    classification_code: int | None = None
    canonical_key: str | None = None
    category: str | None = None
    family: str | None = None
    type_name: str | None = None
    quantity: float | None = None
    unit: str | None = None
    width_mm: float | None = None
    height_mm: float | None = None
    dn_mm: float | None = None
    angle_deg: float | None = None
    material: str | None = None
    manufacturer_part_number: str | None = None  # For exact matching
    vendor_sku: str | None = None  # For exact matching
    source_file: str | None = None
    created_at: datetime | None = None


@dataclass
class PriceItem:
    """Price item from vendor catalog."""

    id: UUID
    classification_code: int
    vendor_id: str | None = None
    sku: str | None = None
    manufacturer_part_number: str | None = None  # For exact matching
    description: str | None = None
    family: str | None = None  # Parsed from description
    type_name: str | None = None  # Parsed from description
    unit: str | None = None
    unit_price: float | None = None
    currency: str = "EUR"
    vat_rate: float | None = None
    last_updated: datetime | None = None
    width_mm: float | None = None
    height_mm: float | None = None
    dn_mm: float | None = None
    angle_deg: float | None = None
    material: str | None = None


@dataclass
class MappingRecord:
    """SCD Type-2 mapping record."""

    id: UUID
    org_id: str
    canonical_key: str
    price_item_id: UUID
    start_ts: datetime
    end_ts: datetime | None = None
    created_by: str | None = None
    reason: str | None = None

    @property
    def is_active(self) -> bool:
        """Check if mapping is currently active."""
        return self.end_ts is None


class MappingMemory:
    """In-memory mapping cache for canonical key lookups."""

    def __init__(self) -> None:
        """Initialize empty mapping memory."""
        self._mappings: dict[tuple[str, str], MappingRecord] = {}

    def lookup(self, org_id: str, canonical_key: str) -> MappingRecord | None:
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
