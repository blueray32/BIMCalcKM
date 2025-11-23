"""Enhanced normalization with synonym expansion and advanced cleaning."""

from __future__ import annotations

import re
import unicodedata
from pathlib import Path
from typing import Any

import yaml


class SynonymExpander:
    """Expand synonyms for materials, manufacturers, and units."""

    def __init__(self, config_path: Path | None = None) -> None:
        """Initialize synonym expander with optional config file.

        Args:
            config_path: Path to synonyms.yaml config file
        """
        self.materials: dict[str, str] = {}
        self.manufacturers: dict[str, str] = {}
        self.units: dict[str, str] = {}
        self.abbreviations: dict[str, str] = {}

        if config_path and config_path.exists():
            self._load_config(config_path)
        else:
            self._load_defaults()

    def _load_config(self, config_path: Path) -> None:
        """Load synonyms from YAML config.

        Args:
            config_path: Path to synonyms.yaml
        """
        with open(config_path) as f:
            config = yaml.safe_load(f)

        # Build material synonym map
        for group in config.get("materials", []):
            canonical = group[0].lower()  # First is canonical
            for variant in group:
                self.materials[variant.lower()] = canonical

        # Build manufacturer synonym map
        for group in config.get("manufacturers", []):
            canonical = group[0].lower()
            for variant in group:
                self.manufacturers[variant.lower()] = canonical

        # Build unit synonym map
        for group in config.get("units", []):
            canonical = group[0]  # Keep case for units
            for variant in group:
                self.units[variant.lower()] = canonical

        # Build abbreviation map
        self.abbreviations = {
            k.lower(): v for k, v in config.get("abbreviations", {}).items()
        }

    def _load_defaults(self) -> None:
        """Load default synonym mappings."""
        # Material synonyms
        self.materials = {
            "ss": "stainless_steel",
            "stainless": "stainless_steel",
            "stainless steel": "stainless_steel",
            "inox": "stainless_steel",
            "gs": "galvanized_steel",
            "galv": "galvanized_steel",
            "galvanized": "galvanized_steel",
            "galvanised": "galvanized_steel",
            "zinc coated": "galvanized_steel",
            "cs": "carbon_steel",
            "carbon steel": "carbon_steel",
            "mild steel": "carbon_steel",
            "cu": "copper",
            "copper": "copper",
            "pvc": "pvc",
            "poly": "pvc",
            "plastic": "pvc",
        }

        # Manufacturer synonyms
        self.manufacturers = {
            "victaulic": "victaulic",
            "victaulic company": "victaulic",
            "victaulic corp": "victaulic",
            "grundfos": "grundfos",
            "grundfos pumps": "grundfos",
        }

        # Unit synonyms
        self.units = {
            "m": "m",
            "meter": "m",
            "metre": "m",
            "meters": "m",
            "metres": "m",
            "ea": "ea",
            "each": "ea",
            "unit": "ea",
            "piece": "ea",
            "pcs": "ea",
            "pc": "ea",
            "m2": "m2",
            "m²": "m2",
            "sqm": "m2",
            "square meter": "m2",
            "m3": "m3",
            "m³": "m3",
            "cum": "m3",
            "cubic meter": "m3",
        }

        # Common abbreviations
        self.abbreviations = {
            "dn": "diameter_nominal",
            "od": "outer_diameter",
            "id": "inner_diameter",
            "thk": "thickness",
            "wt": "wall_thickness",
            "dia": "diameter",
            "diam": "diameter",
            "temp": "temperature",
            "max": "maximum",
            "min": "minimum",
            "std": "standard",
        }

    def expand_material(self, text: str) -> str:
        """Expand material synonyms to canonical form.

        Args:
            text: Material name (may contain synonyms)

        Returns:
            Text with materials normalized to canonical form
        """
        text_lower = text.lower()
        for synonym, canonical in sorted(
            self.materials.items(), key=lambda x: len(x[0]), reverse=True
        ):
            if synonym in text_lower:
                text = re.sub(
                    re.escape(synonym), canonical, text, flags=re.IGNORECASE
                )
        return text

    def expand_manufacturer(self, text: str) -> str:
        """Normalize manufacturer names.

        Args:
            text: Text containing manufacturer names

        Returns:
            Text with manufacturers normalized
        """
        text_lower = text.lower()
        for variant, canonical in sorted(
            self.manufacturers.items(), key=lambda x: len(x[0]), reverse=True
        ):
            if variant in text_lower:
                text = re.sub(
                    re.escape(variant), canonical, text, flags=re.IGNORECASE
                )
        return text

    def expand_unit(self, text: str) -> str:
        """Normalize unit abbreviations.

        Args:
            text: Text containing unit names

        Returns:
            Text with units normalized
        """
        text_lower = text.lower()
        for variant, canonical in sorted(
            self.units.items(), key=lambda x: len(x[0]), reverse=True
        ):
            # Match whole words only for units
            pattern = r"\b" + re.escape(variant) + r"\b"
            if re.search(pattern, text_lower):
                text = re.sub(pattern, canonical, text, flags=re.IGNORECASE)
        return text

    def expand_abbreviations(self, text: str) -> str:
        """Expand common abbreviations to full terms.

        Args:
            text: Text with abbreviations

        Returns:
            Text with abbreviations expanded
        """
        text_lower = text.lower()
        for abbrev, full_term in self.abbreviations.items():
            # Match whole word OR abbreviation followed by digit (e.g., "DN100")
            pattern = r"\b" + re.escape(abbrev) + r"(?=\b|\d)"
            if re.search(pattern, text_lower):
                text = re.sub(pattern, full_term, text, flags=re.IGNORECASE)
        return text


class EnhancedNormalizer:
    """Enhanced text normalization with synonym expansion."""

    def __init__(
        self, synonym_config: Path | None = None, enable_expansions: bool = True
    ) -> None:
        """Initialize enhanced normalizer.

        Args:
            synonym_config: Path to synonyms.yaml config
            enable_expansions: Enable synonym/abbreviation expansion
        """
        self.enable_expansions = enable_expansions
        self.expander = SynonymExpander(synonym_config) if enable_expansions else None

    def normalize(self, text: str, expand_synonyms: bool = True) -> str:
        """Normalize text with optional synonym expansion.

        Args:
            text: Text to normalize
            expand_synonyms: Apply synonym expansion (default: True)

        Returns:
            Normalized text
        """
        if not text:
            return ""

        # Step 1: Synonym expansion (before normalization)
        if expand_synonyms and self.expander:
            text = self.expander.expand_material(text)
            text = self.expander.expand_manufacturer(text)
            text = self.expander.expand_abbreviations(text)
            text = self.expander.expand_unit(text)

        # Step 2: Unicode normalization
        text = unicodedata.normalize("NFKD", text)

        # Step 3: Lowercase
        text = text.lower()

        # Step 4: Replace dimension separators
        text = text.replace("×", "x")
        text = re.sub(r"\bby\b", "x", text)

        # Step 5: Remove project noise
        text = re.sub(r"\bproject[\w-]*\b", "", text)
        text = re.sub(r"\brev\s*\d+(?:\.\d+)?\b", "", text)
        text = re.sub(r"\bv\s*\d+(?:\.\d+)?\b", "", text)
        text = re.sub(r"\b\d{4}-\d{2}-\d{2}\b", "", text)  # Remove dates

        # Step 6: Remove special version markers
        text = re.sub(r"\(.*?\)", "", text)  # Remove parenthetical notes
        text = re.sub(r"\[.*?\]", "", text)  # Remove bracketed notes

        # Step 7: Collapse non-word characters
        text = re.sub(r"[^\w]+", " ", text)
        text = re.sub(r"\s+", " ", text).strip()

        return text

    def slug(self, text: str) -> str:
        """Create URL-safe slug from text.

        Args:
            text: Text to slugify

        Returns:
            Slugified text
        """
        normalized = self.normalize(text, expand_synonyms=True)
        # Replace spaces with underscores
        slug = normalized.replace(" ", "_")
        # Remove any remaining special characters
        slug = re.sub(r"[^a-z0-9_]", "", slug)
        # Collapse multiple underscores
        slug = re.sub(r"_+", "_", slug)
        return slug.strip("_")

    def extract_numeric(self, text: str, pattern: str) -> float | None:
        """Extract numeric value from text using pattern.

        Args:
            text: Text to search
            pattern: Regex pattern to match

        Returns:
            Extracted numeric value or None
        """
        match = re.search(pattern, text.lower())
        if match:
            try:
                return float(match.group(1))
            except (ValueError, IndexError):
                pass
        return None

    def parse_dimensions(self, text: str) -> dict[str, Any]:
        """Parse dimensions (width x height, DN, etc.) from text.

        Args:
            text: Text containing dimensions

        Returns:
            Dictionary with parsed dimensions
        """
        normalized = self.normalize(text, expand_synonyms=False)
        result: dict[str, Any] = {}

        # Width x Height (e.g., "200x50", "200 x 50")
        match = re.search(r"(\d{2,4})\s*x\s*(\d{2,4})", normalized)
        if match:
            result["width_mm"] = float(match.group(1))
            result["height_mm"] = float(match.group(2))

        # DN (Diameter Nominal)
        dn = self.extract_numeric(normalized, r"(?:dn|diameter_nominal)\s*(\d{2,4})")
        if dn:
            result["dn_mm"] = dn

        # Angle (45° or 90°)
        for angle_val in [45, 90]:
            if re.search(rf"\b{angle_val}\b", normalized):
                result["angle_deg"] = float(angle_val)
                break

        return result


# Global instance (singleton pattern)
_normalizer: EnhancedNormalizer | None = None


def get_normalizer(
    config_path: Path | None = None, reload: bool = False
) -> EnhancedNormalizer:
    """Get global normalizer instance.

    Args:
        config_path: Path to synonyms config
        reload: Force reload of normalizer

    Returns:
        Shared normalizer instance
    """
    global _normalizer
    if _normalizer is None or reload:
        _normalizer = EnhancedNormalizer(synonym_config=config_path)
    return _normalizer
