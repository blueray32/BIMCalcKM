"""Data transformation logic for Crail4 → BIMCalc ETL pipeline."""

from __future__ import annotations

import logging
from decimal import Decimal
from typing import Optional

from bimcalc.canonical.normalize import normalize_text, parse_fitting_attributes
from bimcalc.integration.classification_mapper import ClassificationMapper

logger = logging.getLogger(__name__)


class Crail4Transformer:
    """Transforms raw Crail4 data into BIMCalc-compatible format."""

    def __init__(self, mapper: ClassificationMapper, target_scheme: str = "UniClass2015"):
        self.mapper = mapper
        self.target_scheme = target_scheme

    async def transform_item(self, raw_item: dict) -> Optional[dict]:
        """Transform a single Crail4 item."""
        try:
            source_snapshot = raw_item.get("source_data") if isinstance(raw_item, dict) else None
            source_snapshot = source_snapshot or raw_item

            source_code = raw_item.get("classification_code")
            source_scheme = raw_item.get("classification_scheme", "OmniClass")
            description = raw_item.get("name") or raw_item.get("description")
            unit = raw_item.get("unit")
            unit_price = raw_item.get("unit_price")
            currency = raw_item.get("currency", "EUR")
            vat_rate = raw_item.get("vat_rate", 0.0)
            vendor_code = raw_item.get("vendor_code") or raw_item.get("item_code")
            region = raw_item.get("region")

            if not all([source_code, description, unit, unit_price]):
                logger.warning(
                    "Skipping item with missing mandatory fields: %s", raw_item.get("id")
                )
                return None

            if source_scheme == self.target_scheme:
                target_code = source_code
            else:
                target_code = await self.mapper.translate(
                    source_code, source_scheme, self.target_scheme
                )

            if not target_code:
                logger.warning(
                    "No mapping for %s %s → %s", source_scheme, source_code, self.target_scheme
                )
                return None

            normalized_desc = normalize_text(description)

            canonical_key = None
            if target_code in ["66", "62", "63", "64", "67", "68"]:
                attrs = parse_fitting_attributes(normalized_desc)
                if attrs:
                    canonical_key = self._build_canonical_key(target_code, attrs)

            unit = self._standardize_unit(unit)

            return {
                "classification_code": target_code,
                "classification_scheme": self.target_scheme,
                "description": description,
                "unit": unit,
                "unit_price": Decimal(str(unit_price)),
                "currency": currency.upper(),
                "vat_rate": Decimal(str(vat_rate)),
                "vendor_code": vendor_code,
                "canonical_key": canonical_key,
                "region": region,
                "source_data": source_snapshot,
            }

        except Exception as exc:  # pragma: no cover - defensive logging
            logger.error("Transform error for item %s: %s", raw_item.get("id"), exc)
            return None

    async def transform_batch(self, raw_items: list[dict]) -> tuple[list[dict], dict]:
        """Transform a batch of items."""
        valid: list[dict] = []
        rejections = {
            "missing_fields": 0,
            "no_classification_mapping": 0,
            "transform_error": 0,
        }

        for raw_item in raw_items:
            transformed = await self.transform_item(raw_item)
            if transformed:
                valid.append(transformed)
            else:
                if not all([raw_item.get("classification_code"), raw_item.get("unit_price")]):
                    rejections["missing_fields"] += 1
                else:
                    rejections["no_classification_mapping"] += 1

        return valid, rejections

    def _standardize_unit(self, unit: str) -> str:
        """Normalize unit of measure to BIMCalc standard."""
        unit_map = {
            "sq.m": "m²",
            "sqm": "m²",
            "square meter": "m²",
            "meter": "m",
            "metre": "m",
            "piece": "ea",
            "each": "ea",
            "nr": "ea",
        }
        lowered = unit.lower().strip()
        return unit_map.get(lowered, unit)

    def _build_canonical_key(self, classification: str, attrs: dict) -> str:
        """Build canonical key from parsed attributes."""
        parts = [classification]

        if "family" in attrs:
            parts.append(normalize_text(attrs["family"]))
        if "type" in attrs:
            parts.append(normalize_text(attrs["type"]))
        if "width_mm" in attrs:
            parts.append(f"w={attrs['width_mm']}")
        if "height_mm" in attrs or "dn" in attrs:
            h_val = attrs.get("height_mm") or attrs.get("dn")
            parts.append(f"h={h_val}")
        if "angle_deg" in attrs:
            parts.append(f"a={attrs['angle_deg']}")
        if "material" in attrs:
            parts.append(f"mat={attrs['material']}")
        if "unit" in attrs:
            parts.append(f"u={attrs['unit']}")

        return "|".join(parts)
