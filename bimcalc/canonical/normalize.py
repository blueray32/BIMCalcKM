"""Helper utilities for text normalization and fitting parsing."""

from __future__ import annotations

import re

from bimcalc.canonical.key_generator import normalize_text as _base_normalize_text

_MATERIAL_KEYWORDS = {
    "stainless": "stainless_steel",
    "inox": "stainless_steel",
    "galv": "galvanized_steel",
    "galvanized": "galvanized_steel",
    "pvc": "pvc",
    "plastic": "pvc",
    "copper": "copper",
    "brass": "brass",
}

_UNIT_KEYWORDS = {
    "each": "ea",
    "ea": "ea",
    "m2": "m2",
    "m²": "m2",
    "sqm": "m2",
    "m3": "m3",
    "m": "m",
}

_DIMENSION_PATTERN = re.compile(r"(?P<width>\d{2,4})\s*[x×]\s*(?P<height>\d{2,4})")
_DN_PATTERN = re.compile(r"dn\s*(?P<dn>\d{2,4})", re.IGNORECASE)
_ANGLE_PATTERN = re.compile(r"(?P<angle>\d{1,3})\s*(?:deg|°)", re.IGNORECASE)


def normalize_text(text: str | None) -> str:
    """Expose canonical normalize_text helper in a dedicated module."""
    return _base_normalize_text(text)


def parse_fitting_attributes(description: str | None) -> dict:
    """Parse fitting attributes from normalized description text."""
    if not description:
        return {}

    attrs: dict[str, object] = {}
    lowered = description.lower()

    parts = [part.strip() for part in re.split(r"[,;-]", description) if part.strip()]
    if parts:
        attrs["family"] = parts[0]
    if len(parts) > 1:
        attrs["type"] = parts[1]

    dim_match = _DIMENSION_PATTERN.search(lowered)
    if dim_match:
        attrs["width_mm"] = int(dim_match.group("width"))
        attrs["height_mm"] = int(dim_match.group("height"))

    dn_match = _DN_PATTERN.search(lowered)
    if dn_match:
        attrs["dn"] = int(dn_match.group("dn"))

    angle_match = _ANGLE_PATTERN.search(lowered)
    if angle_match:
        attrs["angle_deg"] = int(angle_match.group("angle"))

    for keyword, canonical in _MATERIAL_KEYWORDS.items():
        if keyword in lowered:
            attrs["material"] = canonical
            break

    for keyword, canonical in _UNIT_KEYWORDS.items():
        if re.search(rf"\b{re.escape(keyword)}\b", lowered):
            attrs["unit"] = canonical
            break

    return attrs
