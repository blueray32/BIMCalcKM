"""Unit tests for enhanced normalizer with synonym expansion."""


import pytest

from bimcalc.canonical.enhanced_normalizer import (
    EnhancedNormalizer,
    SynonymExpander,
)


@pytest.fixture
def expander() -> SynonymExpander:
    """Create synonym expander with default mappings."""
    return SynonymExpander()


@pytest.fixture
def normalizer() -> EnhancedNormalizer:
    """Create enhanced normalizer with default settings."""
    return EnhancedNormalizer(enable_expansions=True)


class TestSynonymExpander:
    """Test synonym expansion functionality."""

    def test_expand_material_stainless_steel(self, expander: SynonymExpander) -> None:
        """Test stainless steel synonyms expand correctly."""
        variants = ["SS", "stainless", "stainless steel", "inox"]
        for variant in variants:
            result = expander.expand_material(f"Pipe {variant}")
            assert "stainless_steel" in result.lower()

    def test_expand_material_galvanized(self, expander: SynonymExpander) -> None:
        """Test galvanized steel synonyms expand correctly."""
        variants = ["GS", "galv", "galvanized", "galvanised"]
        for variant in variants:
            result = expander.expand_material(f"Duct {variant}")
            assert "galvanized_steel" in result.lower()

    def test_expand_material_case_insensitive(
        self, expander: SynonymExpander
    ) -> None:
        """Test material expansion is case insensitive."""
        result_upper = expander.expand_material("STAINLESS STEEL")
        result_lower = expander.expand_material("stainless steel")
        result_mixed = expander.expand_material("Stainless Steel")

        assert result_upper == result_lower == result_mixed

    def test_expand_manufacturer_victaulic(self, expander: SynonymExpander) -> None:
        """Test manufacturer name normalization."""
        variants = ["Victaulic", "Victaulic Company", "Victaulic Corp"]
        for variant in variants:
            result = expander.expand_manufacturer(variant)
            assert "victaulic" in result.lower()

    def test_expand_unit_meter(self, expander: SynonymExpander) -> None:
        """Test unit normalization for meters."""
        variants = ["meter", "metre", "meters", "metres"]
        for variant in variants:
            result = expander.expand_unit(variant)
            assert result == "m"

    def test_expand_unit_each(self, expander: SynonymExpander) -> None:
        """Test unit normalization for each."""
        variants = ["each", "unit", "piece", "pcs", "pc"]
        for variant in variants:
            result = expander.expand_unit(variant)
            assert result == "ea"

    def test_expand_unit_whole_word_only(self, expander: SynonymExpander) -> None:
        """Test units only match whole words."""
        # "m" should match in "5 m" but not in "minimum"
        result_match = expander.expand_unit("5 m of pipe")
        result_no_match = expander.expand_unit("minimum temperature")

        # The "m" in "5 m" should be preserved (already canonical)
        assert "m" in result_match
        # The "m" in "minimum" should not be expanded
        assert "minimum" in result_no_match

    def test_expand_abbreviations(self, expander: SynonymExpander) -> None:
        """Test abbreviation expansion."""
        test_cases = [
            ("DN100", "diameter_nominal"),
            ("OD 50mm", "outer_diameter"),
            ("wall thk 2mm", "thickness"),
            ("max temp", "maximum"),
        ]

        for text, expected in test_cases:
            result = expander.expand_abbreviations(text)
            assert expected in result.lower()


class TestEnhancedNormalizer:
    """Test enhanced normalization."""

    def test_basic_normalization(self, normalizer: EnhancedNormalizer) -> None:
        """Test basic text normalization."""
        text = "Pipe Elbow 90° DN100 Stainless Steel"
        result = normalizer.normalize(text)

        # Should be lowercase
        assert result.islower()
        # Should not contain special characters except spaces
        assert "°" not in result

    def test_normalize_with_synonym_expansion(
        self, normalizer: EnhancedNormalizer
    ) -> None:
        """Test normalization with synonym expansion enabled."""
        text = "Pipe Elbow 90° DN100 SS"
        result = normalizer.normalize(text, expand_synonyms=True)

        # "SS" should be expanded to "stainless_steel"
        assert "stainless_steel" in result
        # "DN" should be expanded
        assert "diameter_nominal" in result

    def test_normalize_without_synonym_expansion(
        self, normalizer: EnhancedNormalizer
    ) -> None:
        """Test normalization with synonym expansion disabled."""
        text = "Pipe Elbow 90° DN100 SS"
        result = normalizer.normalize(text, expand_synonyms=False)

        # "SS" should remain as is (just normalized)
        assert "ss" in result
        # "DN" should remain as is
        assert "dn" in result

    def test_remove_project_noise(self, normalizer: EnhancedNormalizer) -> None:
        """Test removal of project-specific noise."""
        test_cases = [
            ("Pipe Project2024 Rev3", "pipe"),
            ("Elbow v1.2", "elbow"),
            ("Valve (ProjectX-R2)", "valve"),
            ("Duct [2024-01-15]", "duct"),
        ]

        for text, expected_core in test_cases:
            result = normalizer.normalize(text, expand_synonyms=False)
            assert expected_core in result
            # Should not contain project noise
            assert "project" not in result
            assert "rev" not in result
            assert "2024" not in result

    def test_dimension_separator_normalization(
        self, normalizer: EnhancedNormalizer
    ) -> None:
        """Test dimension separator normalization."""
        test_cases = [
            "400×200",  # Multiply sign
            "400 by 200",  # "by" keyword
            "400x200",  # Already 'x'
        ]

        for text in test_cases:
            result = normalizer.normalize(text, expand_synonyms=False)
            # All should become "400 x 200" (with spaces)
            assert "400" in result and "200" in result

    def test_slug_generation(self, normalizer: EnhancedNormalizer) -> None:
        """Test slug generation for canonical keys."""
        text = "Pipe Elbow 90° DN100 Stainless Steel"
        slug = normalizer.slug(text)

        # Should be lowercase
        assert slug.islower()
        # Should use underscores instead of spaces
        assert " " not in slug
        # Should not have special characters
        assert all(c.isalnum() or c == "_" for c in slug)
        # Should have expanded synonyms
        assert "stainless_steel" in slug

    def test_slug_no_leading_trailing_underscores(
        self, normalizer: EnhancedNormalizer
    ) -> None:
        """Test slug has no leading/trailing underscores."""
        text = "  Pipe Elbow  "
        slug = normalizer.slug(text)

        assert not slug.startswith("_")
        assert not slug.endswith("_")

    def test_slug_collapse_multiple_underscores(
        self, normalizer: EnhancedNormalizer
    ) -> None:
        """Test multiple underscores collapsed to single."""
        text = "Pipe   Elbow   90"
        slug = normalizer.slug(text)

        # Should not have multiple consecutive underscores
        assert "__" not in slug

    def test_parse_dimensions_width_height(
        self, normalizer: EnhancedNormalizer
    ) -> None:
        """Test parsing width x height dimensions."""
        test_cases = [
            ("Duct 400x200", 400.0, 200.0),
            ("Duct 400 x 200", 400.0, 200.0),
            ("Duct 1200x600", 1200.0, 600.0),
        ]

        for text, expected_width, expected_height in test_cases:
            result = normalizer.parse_dimensions(text)
            assert result["width_mm"] == expected_width
            assert result["height_mm"] == expected_height

    def test_parse_dimensions_dn(self, normalizer: EnhancedNormalizer) -> None:
        """Test parsing DN (diameter nominal) dimensions."""
        test_cases = [
            "Pipe DN100",
            "Pipe DN 100",
            "Pipe diameter_nominal 100",  # After expansion
        ]

        for text in test_cases:
            result = normalizer.parse_dimensions(text)
            assert result.get("dn_mm") == 100.0

    def test_parse_dimensions_angle(self, normalizer: EnhancedNormalizer) -> None:
        """Test parsing angle values."""
        test_cases = [
            ("Elbow 90°", 90.0),
            ("Elbow 45°", 45.0),
            ("Elbow 90 degree", 90.0),
        ]

        for text, expected_angle in test_cases:
            result = normalizer.parse_dimensions(text)
            assert result.get("angle_deg") == expected_angle

    def test_parse_dimensions_no_dimensions(
        self, normalizer: EnhancedNormalizer
    ) -> None:
        """Test parsing with no dimensions present."""
        text = "Generic Item"
        result = normalizer.parse_dimensions(text)

        # Should return empty dict (no dimensions found)
        assert len(result) == 0

    def test_normalize_empty_string(self, normalizer: EnhancedNormalizer) -> None:
        """Test normalization of empty string."""
        result = normalizer.normalize("")
        assert result == ""

    def test_normalize_none_input(self, normalizer: EnhancedNormalizer) -> None:
        """Test normalization handles None input gracefully."""
        # Type ignore because we're testing edge case
        result = normalizer.normalize(None)  # type: ignore[arg-type]
        assert result == ""


class TestSynonymExpansionIntegration:
    """Integration tests for synonym expansion in full workflow."""

    def test_full_normalization_pipeline(
        self, normalizer: EnhancedNormalizer
    ) -> None:
        """Test complete normalization pipeline with all features."""
        text = "Pipe Elbow 90° DN100 SS Victaulic Project2024-Rev3"
        result = normalizer.normalize(text, expand_synonyms=True)

        # Material expansion
        assert "stainless_steel" in result
        # Abbreviation expansion
        assert "diameter_nominal" in result
        # Manufacturer normalization
        assert "victaulic" in result
        # Project noise removed
        assert "project" not in result
        assert "rev" not in result
        assert "2024" not in result
        # Lowercase
        assert result.islower()
        # Clean (no special punctuation)
        assert "°" not in result

    def test_slug_for_canonical_key(self, normalizer: EnhancedNormalizer) -> None:
        """Test slug suitable for canonical key generation."""
        text = "Cable Tray Ladder 200x50 GS"
        slug = normalizer.slug(text)

        # Should have expanded material
        assert "galvanized_steel" in slug
        # Should be clean for hashing
        assert slug.replace("_", "").replace("x", "").replace("0", "").isalnum()
        # Should be deterministic
        slug2 = normalizer.slug(text)
        assert slug == slug2


class TestConfigurableNormalizer:
    """Test normalizer with custom configuration."""

    def test_normalizer_without_expansions(self) -> None:
        """Test normalizer with expansions disabled."""
        normalizer = EnhancedNormalizer(enable_expansions=False)

        text = "Pipe SS DN100"
        result = normalizer.normalize(text, expand_synonyms=True)

        # Should not expand even if requested (expansions disabled)
        # Just basic normalization
        assert "ss" in result
        assert "stainless_steel" not in result
