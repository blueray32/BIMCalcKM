"""Business risk flag evaluation for BIMCalc.

Produces Flag models with severity + message, enforcing Critical-Veto rules.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any, Optional

from bimcalc.config import get_config
from bimcalc.models import Flag, FlagSeverity

# Backwards-compatible constants (used in older tests/docs)
CRITICAL = FlagSeverity.CRITICAL_VETO
ADVISORY = FlagSeverity.ADVISORY

_STALE_PRICE_WINDOW = timedelta(days=365)


def compute_flags(item_attrs: Any, price_attrs: Any) -> list[Flag]:
    """Evaluate business risk flags for an item/price pair.

    Args:
        item_attrs: Item model, dict, or object with matching attributes
        price_attrs: Price item model, dict, or object with matching attributes

    Returns:
        List of Flag models (empty list if no issues detected)
    """

    cfg = get_config()
    matching = cfg.matching
    flags: list[Flag] = []

    # Extract project context for enhanced error messages (Finding #16)
    item_context = _build_item_context(item_attrs)

    def flag(flag_type: str, severity: FlagSeverity, message: str) -> None:
        # Enhance message with project context
        if item_context:
            message = f"{message} [{item_context}]"
        flags.append(Flag(type=flag_type, severity=severity, message=message))

    unit_item = _normalize_str(_get(item_attrs, "unit"))
    unit_price = _normalize_str(_get(price_attrs, "unit"))
    if unit_item and unit_price and unit_item != unit_price:
        flag(
            "Unit Conflict",
            FlagSeverity.CRITICAL_VETO,
            f"Item unit '{unit_item}' does not match price unit '{unit_price}'",
        )

    size_reason = _detect_size_mismatch(
        item_attrs,
        price_attrs,
        matching.size_tolerance_mm,
        matching.dn_tolerance_mm,
    )
    if size_reason:
        flag("Size Mismatch", FlagSeverity.CRITICAL_VETO, size_reason)

    angle_item = _to_float(_get(item_attrs, "angle_deg"))
    angle_price = _to_float(_get(price_attrs, "angle_deg"))
    if (
        angle_item is not None
        and angle_price is not None
        and abs(angle_item - angle_price) > matching.angle_tolerance_deg
    ):
        flag(
            "Angle Mismatch",
            FlagSeverity.CRITICAL_VETO,
            f"Angle differs (item {angle_item:g}°, price {angle_price:g}°)",
        )

    material_item = _normalize_str(_get(item_attrs, "material"))
    material_price = _normalize_str(_get(price_attrs, "material"))
    if material_item and material_price and material_item != material_price:
        flag(
            "Material Conflict",
            FlagSeverity.CRITICAL_VETO,
            f"Material mismatch (item '{material_item}', price '{material_price}')",
        )

    class_item = _to_int(_get(item_attrs, "classification_code"))
    class_price = _to_int(_get(price_attrs, "classification_code"))
    if class_item is not None and class_price is not None and class_item != class_price:
        flag(
            "Class Mismatch",
            FlagSeverity.CRITICAL_VETO,
            f"Item class {class_item} differs from price class {class_price}",
        )

    last_updated = _as_datetime(_get(price_attrs, "last_updated"))
    if last_updated and last_updated < datetime.utcnow() - _STALE_PRICE_WINDOW:
        flag(
            "StalePrice",
            FlagSeverity.ADVISORY,
            f"Price last updated on {last_updated.date().isoformat()}",
        )

    currency = _normalize_currency(_get(price_attrs, "currency"))
    if currency and currency != _normalize_currency(cfg.eu.currency):
        flag(
            "CurrencyMismatch",
            FlagSeverity.ADVISORY,
            f"Price currency '{currency}' differs from default '{cfg.eu.currency}'",
        )

    unit_price = _to_decimal(_get(price_attrs, "unit_price"))
    has_price_values = any(
        value is not None
        for value in (
            unit_price,
            currency,
            _normalize_str(_get(price_attrs, "sku")),
            _normalize_str(_get(price_attrs, "description")),
        )
    )

    vat_rate = _to_decimal(_get(price_attrs, "vat_rate"))
    if has_price_values and vat_rate is None:
        flag(
            "VATUnclear",
            FlagSeverity.ADVISORY,
            "VAT rate missing; provide explicit assumption",
        )

    vendor_note = _normalize_note(_get(price_attrs, "vendor_note"))
    if vendor_note:
        flag(
            "VendorNote",
            FlagSeverity.ADVISORY,
            f"Vendor note: {vendor_note}",
        )

    return flags


def _get(source: Any, key: str) -> Any:
    if isinstance(source, Mapping):
        return source.get(key)
    return getattr(source, key, None)


def _normalize_str(value: Any) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    return text.lower() if text else None


def _normalize_currency(value: Any) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    return text.upper() if text else None


def _normalize_note(value: Any) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    return text if text else None


def _to_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        if isinstance(value, Decimal):
            return float(value)
        return float(value)
    except (TypeError, ValueError):
        return None


def _to_int(value: Any) -> Optional[int]:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _to_decimal(value: Any) -> Optional[Decimal]:
    if value is None:
        return None
    try:
        return Decimal(str(value))
    except (ValueError, TypeError):
        return None


def _as_datetime(value: Any) -> Optional[datetime]:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value)
        except ValueError:
            return None
    return None


def _build_item_context(item_attrs: Any) -> str:
    """Build context string from item attributes for enhanced error messages.

    Extracts project_id, org_id, family, type_name to provide debugging context.

    Args:
        item_attrs: Item attributes (model, dict, or object)

    Returns:
        Context string like "org:acme project:demo Cable Tray:Elbow 90"
        Returns empty string if no context available

    Example:
        >>> attrs = {"org_id": "acme", "project_id": "demo", "family": "Cable Tray", "type_name": "Elbow 90"}
        >>> _build_item_context(attrs)
        'org:acme project:demo Cable Tray:Elbow 90'
    """
    parts = []

    org_id = _get(item_attrs, "org_id")
    if org_id:
        parts.append(f"org:{org_id}")

    project_id = _get(item_attrs, "project_id")
    if project_id:
        parts.append(f"project:{project_id}")

    family = _get(item_attrs, "family")
    type_name = _get(item_attrs, "type_name")

    if family and type_name:
        parts.append(f"{family}:{type_name}")
    elif family:
        parts.append(family)

    return " ".join(parts)


def _detect_size_mismatch(
    item_attrs: Any,
    price_attrs: Any,
    linear_tolerance: float,
    dn_tolerance: float,
) -> Optional[str]:
    comparisons = [
        ("width_mm", linear_tolerance, "width"),
        ("height_mm", linear_tolerance, "height"),
        ("dn_mm", dn_tolerance, "diameter"),
    ]

    for attr, tolerance, label in comparisons:
        item_value = _to_float(_get(item_attrs, attr))
        price_value = _to_float(_get(price_attrs, attr))
        if item_value is None or price_value is None:
            continue
        if abs(item_value - price_value) > tolerance:
            diff = abs(item_value - price_value)
            return (
                f"{label.capitalize()} differs by {diff:g}mm (item {item_value:g}mm, "
                f"price {price_value:g}mm)"
            )

    return None
