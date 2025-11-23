"""Vendor data translation using Classification Mapping Module (CMM).

Integrates CMM into the ingestion pipeline to translate vendor-specific
codes and descriptors into BIMCalc canonical classification codes.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from bimcalc.classification.cmm_loader import ClassificationMappingLoader, load_vendor_mapping

logger = logging.getLogger(__name__)


@dataclass
class TranslationResult:
    """Result of translating a row using CMM.

    Attributes:
        row: The translated row data
        was_mapped: True if a mapping rule was applied
        canonical_code: Extracted canonical classification code (if mapped)
        internal_group: Extracted internal group (if mapped)
        original_fields: Original field values before translation (for audit)
    """
    row: dict[str, Any]
    was_mapped: bool
    canonical_code: str | None = None
    internal_group: str | None = None
    original_fields: dict[str, Any] | None = None


class VendorTranslator:
    """Translates vendor data using CMM mapping rules."""

    def __init__(self, vendor_id: str, config_dir: Path = Path("config/vendors")):
        """Initialize translator for specific vendor.

        Args:
            vendor_id: Vendor identifier (e.g., 'default', 'vendor_acme')
            config_dir: Directory containing vendor mapping YAML files
        """
        self.vendor_id = vendor_id
        self.config_dir = config_dir
        self.loader: ClassificationMappingLoader | None = None
        self._mapped_count = 0
        self._unmapped_count = 0

        # Try to load mapping file
        self.loader = load_vendor_mapping(vendor_id, config_dir)

        if self.loader:
            logger.info(f"Loaded vendor mapping for '{vendor_id}' with {len(self.loader.rules)} rules")
        else:
            logger.info(f"No vendor mapping found for '{vendor_id}', translation disabled")

    def translate_row(self, row: dict[str, Any]) -> TranslationResult:
        """Translate a single row using CMM rules.

        Args:
            row: Input row data (e.g., from CSV/XLSX ingestion)

        Returns:
            TranslationResult with translated data and metadata
        """
        if not self.loader:
            # No mapping file, return original row
            self._unmapped_count += 1  # Count as unmapped
            return TranslationResult(
                row=row,
                was_mapped=False,
            )

        # Store original fields for audit trail
        original_fields = {
            "description": row.get("Description", row.get("Description1", "")),
            "classification_code": row.get("Classification Code", row.get("classification_code", "")),
        }

        # Apply translation
        translated_row, was_mapped = self.loader.translate(row)

        # Update stats
        if was_mapped:
            self._mapped_count += 1
        else:
            self._unmapped_count += 1

        # Extract canonical fields
        canonical_code = translated_row.get("canonical_code")
        internal_group = translated_row.get("internal_group")

        return TranslationResult(
            row=translated_row,
            was_mapped=was_mapped,
            canonical_code=canonical_code,
            internal_group=internal_group,
            original_fields=original_fields if was_mapped else None,
        )

    def get_stats(self) -> dict[str, int]:
        """Get translation statistics.

        Returns:
            Dict with mapped_count and unmapped_count
        """
        return {
            "mapped": self._mapped_count,
            "unmapped": self._unmapped_count,
            "total": self._mapped_count + self._unmapped_count,
        }

    def reset_stats(self):
        """Reset translation statistics."""
        self._mapped_count = 0
        self._unmapped_count = 0


def translate_batch(
    rows: list[dict[str, Any]],
    vendor_id: str,
    config_dir: Path = Path("config/vendors"),
) -> tuple[list[TranslationResult], dict[str, int]]:
    """Translate a batch of rows using CMM.

    Args:
        rows: List of input row dicts
        vendor_id: Vendor identifier
        config_dir: Directory containing vendor mapping YAML files

    Returns:
        Tuple of (results, stats)
        - results: List of TranslationResult objects
        - stats: Dict with mapped/unmapped counts

    Example:
        >>> rows = [
        ...     {"Containment": "ES_CONTMNT", "Description1": "Basket", ...},
        ...     {"Containment": "ES_CONTMNT", "Description1": "Ladder", ...},
        ... ]
        >>> results, stats = translate_batch(rows, "default")
        >>> print(f"Mapped: {stats['mapped']}/{stats['total']}")
        Mapped: 2/2
    """
    translator = VendorTranslator(vendor_id, config_dir)

    results = []
    for row in rows:
        result = translator.translate_row(row)
        results.append(result)

    stats = translator.get_stats()

    return results, stats
