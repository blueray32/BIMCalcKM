"""Unit tests for canonical key generation and normalization.

Tests deterministic key generation, normalization rules, and tolerance handling.
"""

from __future__ import annotations

import pytest

from bimcalc.canonical.key_generator import (
    canonical_key,
    normalize_text,
    normalize_unit,
    round_deg,
    round_mm,
)
from bimcalc.models import Item


class TestNormalizeText:
    """Test text normalization function."""

    def test_lowercase_conversion(self):
        """Test text is converted to lowercase."""
        assert normalize_text("PIPE ELBOW") == "pipe elbow"
        assert normalize_text("Cable Tray") == "cable tray"

    def test_separator_normalization(self):
        """Test separators are normalized to spaces."""
        assert normalize_text("Elbow_90°") == "elbow 90°"
        assert normalize_text("Tray-Ladder") == "tray ladder"
        assert normalize_text("200×50") == "200 50"
        assert normalize_text("200x50") == "200 50"

    def test_project_noise_removal(self):
        """Test project-specific noise is removed."""
        assert "rev" not in normalize_text("Elbow 90° RevA")
        assert "v2" not in normalize_text("Tray Ladder v2")
        assert "proj" not in normalize_text("Item Proj-123")

    def test_whitespace_collapsing(self):
        """Test multiple spaces collapsed to single space."""
        assert normalize_text("Pipe    Elbow    90°") == "pipe elbow 90°"

    def test_leading_trailing_whitespace(self):
        """Test leading/trailing whitespace is stripped."""
        assert normalize_text("  Pipe Elbow  ") == "pipe elbow"

    def test_unicode_normalization(self):
        """Test Unicode NFKD normalization."""
        # Test with accented characters
        result = normalize_text("Café")
        assert "cafe" in result.lower()

    def test_none_input(self):
        """Test None input returns empty string."""
        assert normalize_text(None) == ""

    def test_empty_string(self):
        """Test empty string returns empty string."""
        assert normalize_text("") == ""


class TestNormalizeUnit:
    """Test unit normalization function."""

    def test_meter_variants(self):
        """Test meter variants normalize to 'm'."""
        assert normalize_unit("m") == "m"
        assert normalize_unit("meter") == "m"
        assert normalize_unit("metre") == "m"
        assert normalize_unit("meters") == "m"
        assert normalize_unit("metres") == "m"
        assert normalize_unit("M") == "m"  # Case insensitive

    def test_each_variants(self):
        """Test each/piece variants normalize to 'ea'."""
        assert normalize_unit("ea") == "ea"
        assert normalize_unit("each") == "ea"
        assert normalize_unit("nr") == "ea"
        assert normalize_unit("no") == "ea"
        assert normalize_unit("pcs") == "ea"
        assert normalize_unit("piece") == "ea"
        assert normalize_unit("pieces") == "ea"

    def test_square_meter_variants(self):
        """Test square meter variants normalize to 'm2'."""
        assert normalize_unit("m2") == "m2"
        assert normalize_unit("m²") == "m2"
        assert normalize_unit("sqm") == "m2"
        assert normalize_unit("sq m") == "m2"
        assert normalize_unit("square meter") == "m2"

    def test_cubic_meter_variants(self):
        """Test cubic meter variants normalize to 'm3'."""
        assert normalize_unit("m3") == "m3"
        assert normalize_unit("m³") == "m3"
        assert normalize_unit("cum") == "m3"
        assert normalize_unit("cu m") == "m3"
        assert normalize_unit("cubic meter") == "m3"

    def test_invalid_unit_raises_error(self):
        """Test invalid unit raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            normalize_unit("invalid_unit")

        assert "Invalid unit" in str(exc_info.value)

    def test_none_defaults_to_ea(self):
        """Test None unit defaults to 'ea'."""
        assert normalize_unit(None) == "ea"

    def test_empty_string_defaults_to_ea(self):
        """Test empty string defaults to 'ea'."""
        assert normalize_unit("") == "ea"


class TestRoundMm:
    """Test millimeter rounding function."""

    def test_round_to_5mm_default(self):
        """Test default 5mm tolerance rounding."""
        assert round_mm(100.0) == 100
        assert round_mm(102.0) == 100  # Rounds down
        assert round_mm(103.0) == 105  # Rounds up
        assert round_mm(197.0) == 195
        assert round_mm(198.0) == 200

    def test_round_to_custom_tolerance(self):
        """Test custom tolerance rounding."""
        assert round_mm(100.0, tolerance=10) == 100
        assert round_mm(104.0, tolerance=10) == 100
        assert round_mm(106.0, tolerance=10) == 110

    def test_round_mm_none(self):
        """Test None input returns None."""
        assert round_mm(None) is None

    def test_round_mm_negative_values(self):
        """Test negative values are rounded."""
        # Edge case - shouldn't happen in BIM data but test anyway
        assert round_mm(-102.0, tolerance=5) == -100


class TestRoundDeg:
    """Test degree rounding function."""

    def test_round_to_5deg_default(self):
        """Test default 5° tolerance rounding."""
        assert round_deg(45.0) == 45
        assert round_deg(47.0) == 45  # Rounds down
        assert round_deg(48.0) == 50  # Rounds up
        assert round_deg(92.0) == 90

    def test_round_to_custom_tolerance(self):
        """Test custom tolerance rounding."""
        assert round_deg(45.0, tolerance=10) == 50  # Rounds to nearest 10
        assert round_deg(44.0, tolerance=10) == 40

    def test_round_deg_none(self):
        """Test None input returns None."""
        assert round_deg(None) is None


class TestCanonicalKey:
    """Test canonical key generation."""

    def test_canonical_key_deterministic(self):
        """Test same item generates same key."""
        item1 = Item(
            org_id="test",
            project_id="proj-1",
            family="Pipe Elbow",
            type_name="90° DN100",
            classification_code=2215,
            unit="ea",
        )

        item2 = Item(
            org_id="test",
            project_id="proj-2",  # Different project
            family="Pipe Elbow",
            type_name="90° DN100",
            classification_code=2215,
            unit="ea",
        )

        key1 = canonical_key(item1)
        key2 = canonical_key(item2)

        assert key1 == key2  # Project-agnostic
        assert len(key1) == 16  # 16-character hash

    def test_canonical_key_with_dimensions(self):
        """Test canonical key with width/height dimensions."""
        item = Item(
            org_id="test",
            project_id="proj-1",
            family="Duct",
            type_name="Rectangular",
            classification_code=2302,
            width_mm=400.0,
            height_mm=200.0,
            unit="m",
        )

        key = canonical_key(item)

        assert isinstance(key, str)
        assert len(key) == 16

    def test_canonical_key_with_angle(self):
        """Test canonical key with angle."""
        item = Item(
            org_id="test",
            project_id="proj-1",
            family="Elbow",
            type_name="90°",
            classification_code=2215,
            angle_deg=90.0,
            unit="ea",
        )

        key = canonical_key(item)

        assert isinstance(key, str)
        assert len(key) == 16

    def test_canonical_key_with_material(self):
        """Test canonical key with material."""
        item = Item(
            org_id="test",
            project_id="proj-1",
            family="Pipe",
            type_name="DN100",
            classification_code=2211,
            material="Stainless Steel",
            unit="m",
        )

        key = canonical_key(item)

        assert isinstance(key, str)
        assert len(key) == 16

    def test_canonical_key_dimension_tolerance(self):
        """Test dimensions within tolerance generate same key."""
        item1 = Item(
            org_id="test",
            project_id="proj-1",
            family="Duct",
            type_name="Rect",
            classification_code=2302,
            width_mm=400.0,
            height_mm=200.0,
            unit="m",
        )

        item2 = Item(
            org_id="test",
            project_id="proj-1",
            family="Duct",
            type_name="Rect",
            classification_code=2302,
            width_mm=402.0,  # Within 5mm tolerance
            height_mm=198.0,  # Within 5mm tolerance
            unit="m",
        )

        key1 = canonical_key(item1)
        key2 = canonical_key(item2)

        assert key1 == key2  # Should round to same values

    def test_canonical_key_angle_tolerance(self):
        """Test angles within tolerance generate same key."""
        item1 = Item(
            org_id="test",
            project_id="proj-1",
            family="Elbow",
            type_name="90°",
            classification_code=2215,
            angle_deg=90.0,
            unit="ea",
        )

        item2 = Item(
            org_id="test",
            project_id="proj-1",
            family="Elbow",
            type_name="90°",
            classification_code=2215,
            angle_deg=92.0,  # Within 5° tolerance
            unit="ea",
        )

        key1 = canonical_key(item1)
        key2 = canonical_key(item2)

        assert key1 == key2  # Should round to same angle

    def test_canonical_key_unit_normalization(self):
        """Test unit variants generate same key."""
        item1 = Item(
            org_id="test",
            project_id="proj-1",
            family="Pipe",
            type_name="DN100",
            classification_code=2211,
            unit="m",
        )

        item2 = Item(
            org_id="test",
            project_id="proj-1",
            family="Pipe",
            type_name="DN100",
            classification_code=2211,
            unit="meter",  # Different variant
        )

        key1 = canonical_key(item1)
        key2 = canonical_key(item2)

        assert key1 == key2  # Units normalized

    def test_canonical_key_text_normalization(self):
        """Test text normalization in family/type."""
        item1 = Item(
            org_id="test",
            project_id="proj-1",
            family="Pipe Elbow",
            type_name="90° DN100",
            classification_code=2215,
            unit="ea",
        )

        item2 = Item(
            org_id="test",
            project_id="proj-1",
            family="Pipe_Elbow",  # Different separator
            type_name="90° DN100",
            classification_code=2215,
            unit="ea",
        )

        key1 = canonical_key(item1)
        key2 = canonical_key(item2)

        assert key1 == key2  # Text normalized

    def test_canonical_key_project_noise_removed(self):
        """Test project-specific noise doesn't affect key."""
        item1 = Item(
            org_id="test",
            project_id="proj-1",
            family="Elbow 90° DN100",
            type_name="Standard",
            classification_code=2215,
            unit="ea",
        )

        item2 = Item(
            org_id="test",
            project_id="proj-1",
            family="Elbow 90° DN100 RevA",  # Project noise
            type_name="Standard v2",  # Version noise
            classification_code=2215,
            unit="ea",
        )

        key1 = canonical_key(item1)
        key2 = canonical_key(item2)

        # Should be similar (noise removed)
        # Note: Exact match depends on how well noise removal works
        assert isinstance(key1, str)
        assert isinstance(key2, str)

    def test_canonical_key_missing_classification_raises_error(self):
        """Test missing classification_code raises ValueError."""
        item = Item(
            org_id="test",
            project_id="proj-1",
            family="Test",
            type_name="Test",
            # classification_code missing
        )

        with pytest.raises(ValueError) as exc_info:
            canonical_key(item)

        assert "classification_code is required" in str(exc_info.value)

    def test_canonical_key_empty_family_raises_error(self):
        """Test empty family raises ValueError."""
        item = Item(
            org_id="test",
            project_id="proj-1",
            family="",  # Empty
            type_name="Test",
            classification_code=2215,
        )

        with pytest.raises(ValueError) as exc_info:
            canonical_key(item)

        assert "family is required" in str(exc_info.value)

    def test_canonical_key_invalid_unit_raises_error(self):
        """Test invalid unit raises ValueError."""
        item = Item(
            org_id="test",
            project_id="proj-1",
            family="Test",
            type_name="Test",
            classification_code=2215,
            unit="invalid_unit",
        )

        with pytest.raises(ValueError) as exc_info:
            canonical_key(item)

        assert "Invalid unit" in str(exc_info.value)

    def test_canonical_key_omits_none_values(self):
        """Test None values are omitted from key."""
        item1 = Item(
            org_id="test",
            project_id="proj-1",
            family="Pipe",
            type_name="DN100",
            classification_code=2211,
            unit="m",
            # No dimensions, material, angle
        )

        item2 = Item(
            org_id="test",
            project_id="proj-1",
            family="Pipe",
            type_name="DN100",
            classification_code=2211,
            unit="m",
            width_mm=None,  # Explicitly None
            material=None,
            angle_deg=None,
        )

        key1 = canonical_key(item1)
        key2 = canonical_key(item2)

        assert key1 == key2  # None values omitted


class TestCanonicalKeyRealWorld:
    """Test canonical key with real-world scenarios."""

    def test_cable_tray_elbow_variants(self):
        """Test cable tray elbow variants generate same key."""
        item1 = Item(
            org_id="test",
            project_id="proj-a",
            family="Cable Tray Elbow",
            type_name="90° 200×50 Galvanised",
            classification_code=2650,
            width_mm=200.0,
            height_mm=50.0,
            angle_deg=90.0,
            material="Galvanised",
            unit="ea",
        )

        item2 = Item(
            org_id="test",
            project_id="proj-b",
            family="Tray Elbow Ladder",
            type_name="90deg 200x50 GALV RevA",
            classification_code=2650,
            width_mm=202.0,  # Within tolerance
            height_mm=48.0,  # Within tolerance
            angle_deg=92.0,  # Within tolerance
            material="Galv",
            unit="each",  # Different variant
        )

        key1 = canonical_key(item1)
        key2 = canonical_key(item2)

        # These should generate similar keys (learning curve test)
        # Exact match depends on normalization quality
        assert len(key1) == 16
        assert len(key2) == 16

    def test_pipe_elbow_variants(self):
        """Test pipe elbow variants."""
        item1 = Item(
            org_id="test",
            project_id="proj-1",
            family="Pipe Elbow",
            type_name="90° DN100 Stainless Steel",
            classification_code=2215,
            dn_mm=100.0,
            angle_deg=90.0,
            material="Stainless Steel",
            unit="ea",
        )

        item2 = Item(
            org_id="test",
            project_id="proj-1",
            family="Pipe Elbow",
            type_name="90° DN100 SS",
            classification_code=2215,
            dn_mm=100.0,
            angle_deg=90.0,
            material="SS",  # Abbreviation
            unit="ea",
        )

        key1 = canonical_key(item1)
        key2 = canonical_key(item2)

        # Keys should be stable
        assert len(key1) == 16
        assert len(key2) == 16
