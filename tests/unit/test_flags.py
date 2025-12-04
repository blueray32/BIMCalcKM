"""Unit tests for flags engine.

Validates Critical-Veto vs Advisory flag detection with structured models.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from bimcalc.flags.engine import ADVISORY, CRITICAL, compute_flags
from bimcalc.models import FlagSeverity


def _has_flag(flags, flag_type: str, severity: FlagSeverity | None = None) -> bool:
    return any(
        flag.type == flag_type and (severity is None or flag.severity == severity)
        for flag in flags
    )


class TestCriticalFlags:
    """Critical-Veto flag scenarios."""

    def test_unit_conflict(self):
        flags = compute_flags({"unit": "m"}, {"unit": "ea"})
        assert len(flags) == 1
        assert flags[0].type == "Unit Conflict"
        assert flags[0].severity == FlagSeverity.CRITICAL_VETO
        assert "does not match" in flags[0].message

    def test_size_mismatch(self):
        flags = compute_flags({"width_mm": 400}, {"width_mm": 450})
        assert _has_flag(flags, "Size Mismatch", FlagSeverity.CRITICAL_VETO)

    def test_angle_mismatch(self):
        flags = compute_flags({"angle_deg": 90}, {"angle_deg": 40})
        assert _has_flag(flags, "Angle Mismatch", FlagSeverity.CRITICAL_VETO)

    def test_material_conflict(self):
        flags = compute_flags({"material": "steel"}, {"material": "galv"})
        assert _has_flag(flags, "Material Conflict", FlagSeverity.CRITICAL_VETO)

    def test_class_mismatch(self):
        flags = compute_flags(
            {"classification_code": 2301}, {"classification_code": 2215}
        )
        assert _has_flag(flags, "Class Mismatch", FlagSeverity.CRITICAL_VETO)


class TestAdvisoryFlags:
    """Advisory flag scenarios."""

    def test_stale_price(self):
        last_year = datetime.now(timezone.utc) - timedelta(days=400)
        flags = compute_flags({}, {"last_updated": last_year})
        assert _has_flag(flags, "StalePrice", FlagSeverity.ADVISORY)

    def test_currency_mismatch(self):
        flags = compute_flags({}, {"currency": "GBP"})
        assert _has_flag(flags, "CurrencyMismatch", FlagSeverity.ADVISORY)

    def test_vat_unclear(self):
        flags = compute_flags({}, {"vat_rate": None, "unit_price": 10})
        assert _has_flag(flags, "VATUnclear", FlagSeverity.ADVISORY)

    def test_vendor_note(self):
        flags = compute_flags({}, {"vendor_note": "Discontinued"})
        assert _has_flag(flags, "VendorNote", FlagSeverity.ADVISORY)


class TestMultipleFlags:
    """Ensure multiple issues can be reported together."""

    def test_combination(self):
        item = {"unit": "m", "width_mm": 200, "material": "steel"}
        price = {
            "unit": "ea",
            "width_mm": 260,
            "material": "plastic",
            "currency": "USD",
            "vat_rate": None,
        }
        flags = compute_flags(item, price)
        assert _has_flag(flags, "Unit Conflict", FlagSeverity.CRITICAL_VETO)
        assert _has_flag(flags, "Size Mismatch", FlagSeverity.CRITICAL_VETO)
        assert _has_flag(flags, "Material Conflict", FlagSeverity.CRITICAL_VETO)
        assert _has_flag(flags, "CurrencyMismatch", FlagSeverity.ADVISORY)
        assert _has_flag(flags, "VATUnclear", FlagSeverity.ADVISORY)

    def test_perfect_match(self):
        item = {
            "unit": "m",
            "width_mm": 200,
            "angle_deg": 45,
            "material": "steel",
            "classification_code": 2215,
        }
        price = {
            "unit": "m",
            "width_mm": 200,
            "angle_deg": 45,
            "material": "steel",
            "classification_code": 2215,
            "vat_rate": 0.23,
            "currency": "EUR",
            "last_updated": datetime.now(timezone.utc),
        }
        flags = compute_flags(item, price)
        assert flags == []


class TestEdgeCases:
    def test_missing_values(self):
        flags = compute_flags({"unit": None}, {"unit": "m"})
        assert flags == []

    def test_only_one_side_has_data(self):
        flags = compute_flags({"unit": "m"}, {})
        assert flags == []


class TestConstants:
    def test_constant_values(self):
        assert CRITICAL == FlagSeverity.CRITICAL_VETO
        assert ADVISORY == FlagSeverity.ADVISORY
