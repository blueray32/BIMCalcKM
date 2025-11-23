from __future__ import annotations
import re
import unicodedata
from typing import Dict, Any

_MATERIAL_SYNONYMS = {
    "galvanised": "galv",
    "galvanized": "galv",
    "galv.": "galv",
    "stainless": "ss",
    "stainless steel": "ss"
}

def normalize_name(text: str) -> str:
    s = unicodedata.normalize("NFKD", text).lower()
    s = s.replace("×", "x")
    s = re.sub(r"\bby\b", "x", s)
    # remove project noise like 'projectX', 'rev2', 'v1.1'
    s = re.sub(r"\bproject[\w-]*\b", "", s)
    s = re.sub(r"\brev[_\s]*\d+(?:\.\d+)?\b", "", s)
    s = re.sub(r"\bv\s*\d+(?:\.\d+)?\b", "", s)
    # collapse non-word to single space
    s = re.sub(r"[^\w]+", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s

def parse_attributes(text: str) -> Dict[str, Any]:
    """Extract structured attributes from normalized text."""
    s = normalize_name(text)
    # size
    m = re.search(r"(\d{2,4})\s*x\s*(\d{2,4})", s)
    width = height = None
    if m:
        width = int(m.group(1))
        height = int(m.group(2))
    # angle
    angle = None
    for a in ("45", "90"):
        if re.search(rf"\b{a}\b", s):
            angle = int(a)
            break
    # material
    material = None
    for k, v in _MATERIAL_SYNONYMS.items():
        if k in s:
            material = v
            break
    if material is None and "galv" in s:
        material = "galv"
    # unit guess (demo)
    unit = "ea"
    if " per m" in s or " / m" in s:
        unit = "m"
    return {
        "width_mm": width,
        "height_mm": height,
        "angle_deg": angle,
        "material": material,
        "unit": unit,
        "normalized": s,
    }

def canonicalize(name: str) -> str:
    attrs = parse_attributes(name)
    parts = [
        f"width={attrs['width_mm']}" if attrs["width_mm"] else None,
        f"height={attrs['height_mm']}" if attrs["height_mm"] else None,
        f"angle={attrs['angle_deg']}" if attrs["angle_deg"] else None,
        f"material={attrs['material']}" if attrs["material"] else None,
        f"unit={attrs['unit']}" if attrs["unit"] else None,
    ]
    parts = [p for p in parts if p]
    return " | ".join(parts)
