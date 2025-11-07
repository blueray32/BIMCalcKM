"""Canonical key generation for deterministic item identity.

Generates a deterministic 16-character hash representing an item's normalized identity.
Key construction: classification_code|family|type|width|height|dn|angle|material|unit

Normalization rules:
- Text: lowercase, Unicode NFKD, strip special chars, remove project noise
- Numeric: round to tolerance (5mm for dimensions, 5° for angles)
- Unit: normalize to standard (m, ea, m2, m3)
"""

from __future__ import annotations

import hashlib
import re
import unicodedata
from typing import Optional

from bimcalc.models import Item


def normalize_text(text: Optional[str]) -> str:
    """Normalize text to canonical form.

    Args:
        text: Input string

    Returns:
        Normalized string (lowercase, Unicode NFKD, stripped)
    """
    if not text:
        return ""

    # Unicode normalization (NFKD decomposition)
    text = unicodedata.normalize("NFKD", text)

    # Lowercase
    text = text.lower()

    # Replace common separators with space
    text = re.sub(r"[_\-/\\×x]", " ", text)

    # Remove project-specific noise patterns
    text = re.sub(r"\b(rev[a-z]?|v\d+|proj-\d+)\b", "", text, flags=re.IGNORECASE)

    # Collapse multiple spaces
    text = re.sub(r"\s+", " ", text)

    # Strip leading/trailing whitespace
    text = text.strip()

    return text


def normalize_unit(unit: Optional[str]) -> str:
    """Normalize unit to standard form.

    Standard units: m, ea, m2, m3

    Args:
        unit: Input unit string

    Returns:
        Normalized unit

    Raises:
        ValueError: If unit is invalid
    """
    if not unit:
        return "ea"  # Default to "each"

    unit_lower = unit.lower().strip()

    # Meter variants
    if unit_lower in ("m", "meter", "metre", "meters", "metres"):
        return "m"

    # Each/piece variants
    if unit_lower in ("ea", "each", "nr", "no", "pcs", "piece", "pieces"):
        return "ea"

    # Square meter variants
    if unit_lower in ("m2", "m²", "sqm", "sq m", "square meter", "square metres"):
        return "m2"

    # Cubic meter variants
    if unit_lower in ("m3", "m³", "cum", "cu m", "cubic meter", "cubic metres"):
        return "m3"

    # If not recognized, raise error (fail fast on invalid units)
    raise ValueError(f"Invalid unit: {unit!r}. Expected: m, ea, m2, m3 or variants.")


def round_mm(value: Optional[float], tolerance: int = 5) -> Optional[int]:
    """Round dimension to nearest tolerance (default 5mm).

    Args:
        value: Dimension in millimeters
        tolerance: Rounding tolerance (default 5mm)

    Returns:
        Rounded dimension or None if value is None
    """
    if value is None:
        return None
    return round(value / tolerance) * tolerance


def round_deg(value: Optional[float], tolerance: int = 5) -> Optional[int]:
    """Round angle to nearest tolerance (default 5°).

    Args:
        value: Angle in degrees
        tolerance: Rounding tolerance (default 5°)

    Returns:
        Rounded angle or None if value is None
    """
    if value is None:
        return None
    return round(value / tolerance) * tolerance


def canonical_key(item: Item) -> str:
    """Generate deterministic 16-character canonical key for item.

    Key construction:
    {classification_code}|{family_slug}|{type_slug}|w={width}|h={height}|dn={dn}|a={angle}|mat={material_slug}|u={unit}

    Args:
        item: BIM item with classification_code and attributes

    Returns:
        16-character SHA256 hash prefix

    Raises:
        ValueError: If classification_code or family is missing
        ValueError: If unit is invalid
    """
    # Required fields
    if item.classification_code is None:
        raise ValueError("item.classification_code is required for canonical_key generation")

    if not item.family or not item.family.strip():
        raise ValueError("item.family is required for canonical_key generation")

    # Normalize text fields
    family_slug = normalize_text(item.family)
    type_slug = normalize_text(item.type_name) if item.type_name else ""
    material_slug = normalize_text(item.material) if item.material else ""

    # Normalize unit (raises ValueError if invalid)
    normalized_unit = normalize_unit(item.unit)

    # Round numeric attributes to tolerance
    width = round_mm(item.width_mm, tolerance=5)
    height = round_mm(item.height_mm, tolerance=5)
    dn = round_mm(item.dn_mm, tolerance=5)
    angle = round_deg(item.angle_deg, tolerance=5)

    # Construct key parts (omit None values for consistent ordering)
    parts = [str(item.classification_code), family_slug]

    if type_slug:
        parts.append(type_slug)

    if width is not None:
        parts.append(f"w={width}")

    if height is not None:
        parts.append(f"h={height}")

    if dn is not None:
        parts.append(f"dn={dn}")

    if angle is not None:
        parts.append(f"a={angle}")

    if material_slug:
        parts.append(f"mat={material_slug}")

    parts.append(f"u={normalized_unit}")

    # Join with pipe separator
    key_string = "|".join(parts)

    # Generate SHA256 hash and take first 16 characters (deterministic)
    hash_digest = hashlib.sha256(key_string.encode("utf-8")).hexdigest()
    return hash_digest[:16]
