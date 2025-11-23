"""Classification Mapping Module (CMM) - Vendor data translation.

Loads YAML mapping rules that translate vendor-specific classification codes
and descriptors into BIMCalc canonical classification codes.

This decouples the core matching engine from vendor data inconsistencies,
allowing new vendors to be onboarded without modifying core logic.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)


@dataclass
class MappingRule:
    """A single vendor → canonical classification mapping rule.

    Attributes:
        match: Dict of fields that must match for this rule to apply
        map_to: Dict of canonical fields to populate when matched
        priority: Optional priority (lower = higher priority for overlapping rules)
    """
    match: dict[str, Any]
    map_to: dict[str, Any]
    priority: int = 100

    def matches(self, row: dict[str, Any]) -> bool:
        """Check if row matches all conditions in this rule.

        Args:
            row: Input row data (e.g., from CSV/XLSX)

        Returns:
            True if all match conditions are satisfied
        """
        for key, expected_value in self.match.items():
            actual_value = row.get(key)

            # Case-insensitive string comparison
            if isinstance(expected_value, str) and isinstance(actual_value, str):
                if expected_value.strip().lower() != actual_value.strip().lower():
                    return False
            else:
                if expected_value != actual_value:
                    return False

        return True

    def apply(self, row: dict[str, Any]) -> dict[str, Any]:
        """Apply mapping to row, returning new row with canonical fields.

        Args:
            row: Input row data

        Returns:
            New row dict with map_to fields merged in
        """
        result = row.copy()
        result.update(self.map_to)
        return result


class ClassificationMappingLoader:
    """Loads and manages vendor classification mapping rules."""

    def __init__(self, mapping_file: Path):
        """Initialize loader with path to YAML mapping file.

        Args:
            mapping_file: Path to YAML file containing mapping rules

        Raises:
            FileNotFoundError: If mapping file doesn't exist
            ValueError: If YAML is malformed
        """
        self.mapping_file = mapping_file
        self.rules: list[MappingRule] = []
        self._load()

    def _load(self):
        """Load mapping rules from YAML file."""
        if not self.mapping_file.exists():
            raise FileNotFoundError(f"Mapping file not found: {self.mapping_file}")

        try:
            with open(self.mapping_file) as f:
                data = yaml.safe_load(f)
        except yaml.YAMLError as e:
            raise ValueError(f"Invalid YAML in {self.mapping_file}: {e}") from e

        if not isinstance(data, list):
            raise ValueError(f"Expected list of mapping rules, got {type(data)}")

        for idx, item in enumerate(data):
            if not isinstance(item, dict):
                logger.warning(f"Skipping invalid rule at index {idx}: not a dict")
                continue

            if "match" not in item or "map_to" not in item:
                logger.warning(f"Skipping rule at index {idx}: missing 'match' or 'map_to'")
                continue

            priority = item.get("priority", 100)

            rule = MappingRule(
                match=item["match"],
                map_to=item["map_to"],
                priority=priority,
            )
            self.rules.append(rule)

        # Sort by priority (lower number = higher priority)
        self.rules.sort(key=lambda r: r.priority)

        logger.info(f"Loaded {len(self.rules)} mapping rules from {self.mapping_file}")

    def find_match(self, row: dict[str, Any]) -> MappingRule | None:
        """Find first matching rule for given row.

        Args:
            row: Input row data

        Returns:
            First matching MappingRule, or None if no match found
        """
        for rule in self.rules:
            if rule.matches(row):
                return rule
        return None

    def translate(self, row: dict[str, Any]) -> tuple[dict[str, Any], bool]:
        """Translate row using mapping rules.

        Args:
            row: Input row data

        Returns:
            Tuple of (translated_row, was_mapped)
            - translated_row: Row with canonical fields applied (or original if no match)
            - was_mapped: True if a mapping rule was applied, False otherwise
        """
        rule = self.find_match(row)

        if rule:
            translated = rule.apply(row)
            logger.debug(f"Mapped row: {row.get('Description1', 'unknown')} → {translated.get('canonical_code', 'unknown')}")
            return translated, True
        else:
            logger.debug(f"No mapping found for row: {row}")
            return row, False


def load_vendor_mapping(vendor_id: str, config_dir: Path = Path("config/vendors")) -> ClassificationMappingLoader | None:
    """Load vendor mapping file by vendor ID.

    Args:
        vendor_id: Vendor identifier (e.g., 'default', 'vendor_acme')
        config_dir: Directory containing vendor mapping YAML files

    Returns:
        ClassificationMappingLoader instance, or None if no mapping file found

    Example:
        >>> loader = load_vendor_mapping("default")
        >>> row = {"Containment": "ES_CONTMNT", "Description1": "Basket", ...}
        >>> translated, was_mapped = loader.translate(row)
        >>> print(translated["canonical_code"])
        B-LEN-W450-D55-ZP
    """
    mapping_file = config_dir / f"config_vendor_{vendor_id}_classification_map.yaml"

    if not mapping_file.exists():
        logger.warning(f"No mapping file found for vendor '{vendor_id}' at {mapping_file}")
        return None

    return ClassificationMappingLoader(mapping_file)
