"""YAML-driven classification trust hierarchy for BIMCalc.

Assigns classification codes to items using an ordered trust hierarchy:
1. Explicit Override (priority 100)
2. Curated Manual List (priority 90)
3. Revit Category + System Type (priority 70)
4. Fallback Heuristics (priority 50)
5. Unknown (priority 0)
"""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any, Optional

import yaml

from bimcalc.config import get_config
from bimcalc.models import Item


class ConfigurationError(Exception):
    """Configuration file is invalid or missing."""

    pass


class TrustHierarchyClassifier:
    """YAML-driven classifier implementing trust hierarchy."""

    def __init__(self, config_path: Optional[Path] = None):
        """Initialize classifier from YAML configuration.

        Args:
            config_path: Path to classification_hierarchy.yaml
                        (defaults to config/classification_hierarchy.yaml)

        Raises:
            ConfigurationError: If YAML is invalid or missing
        """
        if config_path is None:
            config_path = get_config().classification_config_path

        if not config_path.exists():
            raise ConfigurationError(f"Classification config not found: {config_path}")

        try:
            with config_path.open(encoding="utf-8") as f:
                self._config = yaml.safe_load(f)
        except yaml.YAMLError as e:
            raise ConfigurationError(f"Invalid YAML in {config_path}: {e}")

        self._trust_levels = self._config.get("trust_levels", [])
        if not self._trust_levels:
            raise ConfigurationError("No trust_levels defined in configuration")

        # Load curated list if specified
        self._curated_map: dict[str, int] = {}
        self._load_curated_list()

    def _load_curated_list(self) -> None:
        """Load curated classifications from CSV if configured."""
        for level in self._trust_levels:
            if level.get("name") == "CuratedList" and "source" in level:
                csv_path = get_config().config_root / level["source"]
                if not csv_path.exists():
                    # Not an error - curated list is optional
                    continue

                try:
                    with csv_path.open(encoding="utf-8") as f:
                        reader = csv.DictReader(f)
                        for row in reader:
                            # Expected columns: family, type_name, classification_code
                            family = row.get("family", "").strip()
                            type_name = row.get("type_name", "").strip()
                            code = row.get("classification_code", "").strip()

                            if family and code:
                                # Key: "family|type_name" (type is optional)
                                key = f"{family}|{type_name}" if type_name else family
                                self._curated_map[key] = int(code)
                except (OSError, ValueError, KeyError) as e:
                    raise ConfigurationError(f"Invalid curated CSV {csv_path}: {e}")

    def classify(self, item: Item) -> int:
        """Classify item using trust hierarchy.

        Args:
            item: BIM item to classify

        Returns:
            int: Classification code (9999 if Unknown)

        Raises:
            ValueError: If item.family is None or empty
        """
        if not item.family or not item.family.strip():
            raise ValueError("item.family is required for classification")

        # Apply trust hierarchy in priority order
        for level in sorted(self._trust_levels, key=lambda x: x.get("priority", 0), reverse=True):
            name = level.get("name")

            if name == "ExplicitOverride":
                code = self._check_explicit_override(item, level)
                if code is not None:
                    return code

            elif name == "CuratedList":
                code = self._check_curated_list(item, level)
                if code is not None:
                    return code

            elif name == "RevitCategorySystem":
                code = self._check_revit_category_system(item, level)
                if code is not None:
                    return code

            elif name == "FallbackHeuristics":
                code = self._check_fallback_heuristics(item, level)
                if code is not None:
                    return code

            elif name == "Unknown":
                return level.get("classification_code", 9999)

        # Fallback to Unknown if no level matched
        return 9999

    def _check_explicit_override(self, item: Item, level: dict[str, Any]) -> Optional[int]:
        """Check explicit override fields (omniclass_code, uniformat_code)."""
        for field in level.get("fields", []):
            value = getattr(item, field, None)
            if value is not None:
                return int(value)
        return None

    def _check_curated_list(self, item: Item, level: dict[str, Any]) -> Optional[int]:
        """Check curated manual classification list (CSV lookup)."""
        if not self._curated_map:
            return None

        # Try "family|type_name" first, then "family" alone
        key_with_type = f"{item.family}|{item.type_name}" if item.type_name else None
        key_family_only = item.family

        if key_with_type and key_with_type in self._curated_map:
            return self._curated_map[key_with_type]
        if key_family_only in self._curated_map:
            return self._curated_map[key_family_only]

        return None

    def _check_revit_category_system(self, item: Item, level: dict[str, Any]) -> Optional[int]:
        """Check Revit Category + System Type heuristics."""
        rules = level.get("rules", [])
        for rule in rules:
            # Match category (required) and system_type (optional)
            category_match = rule.get("category")
            system_type_match = rule.get("system_type")

            if category_match and item.category == category_match:
                # If system_type is specified in rule, must also match
                if system_type_match:
                    if item.system_type == system_type_match:
                        return rule.get("classification_code")
                else:
                    # Category match alone is sufficient
                    return rule.get("classification_code")

        return None

    def _check_fallback_heuristics(self, item: Item, level: dict[str, Any]) -> Optional[int]:
        """Check keyword pattern matching in family/type names."""
        rules = level.get("rules", [])

        # Construct search string (lowercase for case-insensitive matching)
        search_text = f"{item.family} {item.type_name or ''}".lower()

        for rule in rules:
            keywords = rule.get("family_contains", [])
            if any(keyword.lower() in search_text for keyword in keywords):
                return rule.get("classification_code")

        return None


# Singleton instance
_classifier: Optional[TrustHierarchyClassifier] = None


def get_classifier() -> TrustHierarchyClassifier:
    """Get or create singleton classifier instance.

    Returns:
        TrustHierarchyClassifier: Singleton instance

    Raises:
        ConfigurationError: If classification config is invalid
    """
    global _classifier
    if _classifier is None:
        _classifier = TrustHierarchyClassifier()
    return _classifier


def classify_item(item: Item) -> int:
    """Classify item using trust hierarchy (convenience function).

    Args:
        item: BIM item to classify

    Returns:
        int: Classification code (9999 if Unknown)

    Raises:
        ConfigurationError: If classification config is invalid
        ValueError: If item.family is None or empty
    """
    classifier = get_classifier()
    return classifier.classify(item)
