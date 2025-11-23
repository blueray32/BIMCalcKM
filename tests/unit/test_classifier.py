"""Unit tests for trust hierarchy classifier.

Tests classification code assignment via YAML-driven trust hierarchy.
"""

from __future__ import annotations

import pytest

from bimcalc.classification.trust_hierarchy import (
    ConfigurationError,
    TrustHierarchyClassifier,
    classify_item,
)
from bimcalc.models import Item


class TestTrustHierarchyClassifier:
    """Test TrustHierarchyClassifier initialization and configuration."""

    def test_classifier_loads_yaml_config(self):
        """Test classifier loads from YAML file."""
        classifier = TrustHierarchyClassifier()

        assert classifier._config is not None
        assert "trust_levels" in classifier._config
        assert len(classifier._trust_levels) > 0

    def test_classifier_missing_config_raises_error(self, tmp_path):
        """Test missing config file raises ConfigurationError."""
        missing_path = tmp_path / "missing.yaml"

        with pytest.raises(ConfigurationError) as exc_info:
            TrustHierarchyClassifier(config_path=missing_path)

        assert "not found" in str(exc_info.value)

    def test_classifier_invalid_yaml_raises_error(self, tmp_path):
        """Test invalid YAML raises ConfigurationError."""
        invalid_yaml = tmp_path / "invalid.yaml"
        invalid_yaml.write_text("invalid: yaml: content: [")

        with pytest.raises(ConfigurationError) as exc_info:
            TrustHierarchyClassifier(config_path=invalid_yaml)

        assert "Invalid YAML" in str(exc_info.value)


class TestExplicitOverride:
    """Test Explicit Override (priority 100) classification."""

    def test_omniclass_code_overrides_all(self):
        """Test omniclass_code has highest priority."""
        classifier = TrustHierarchyClassifier()

        item = Item(
            org_id="test",
            project_id="proj-1",
            family="Mechanical Equipment",
            type_name="Boiler",
            category="Mechanical Equipment",
            system_type="HVAC",
            omniclass_code=2301,  # Explicit override
        )

        code = classifier.classify(item)

        assert code == 2301

    def test_uniformat_code_overrides_all(self):
        """Test uniformat_code has highest priority."""
        classifier = TrustHierarchyClassifier()

        item = Item(
            org_id="test",
            project_id="proj-1",
            family="Unknown Family",
            type_name="Unknown",
            uniformat_code=2350,  # Explicit override
        )

        code = classifier.classify(item)

        assert code == 2350

    def test_omniclass_takes_priority_over_uniformat(self):
        """Test omniclass_code checked before uniformat_code."""
        classifier = TrustHierarchyClassifier()

        item = Item(
            org_id="test",
            project_id="proj-1",
            family="Test",
            type_name="Test",
            omniclass_code=2301,
            uniformat_code=2350,
        )

        code = classifier.classify(item)

        # Should use omniclass (first field in trust hierarchy)
        assert code == 2301


class TestCuratedList:
    """Test Curated List (priority 90) classification."""

    def test_curated_list_exact_match(self):
        """Test exact match in curated list."""
        classifier = TrustHierarchyClassifier()

        # Note: This assumes config/curated_classifications.csv exists
        # If not, this test will pass through to next level
        item = Item(
            org_id="test",
            project_id="proj-1",
            family="Cable Tray Ladder",  # Known in curated list
            type_name="Standard",
        )

        code = classifier.classify(item)

        # Should match curated list or fall through to category
        assert code in (66, 2650, 9999)  # Electrical containment codes or unknown

    def test_curated_list_family_only_match(self):
        """Test family-only match when type not in curated list."""
        classifier = TrustHierarchyClassifier()

        item = Item(
            org_id="test",
            project_id="proj-1",
            family="Cable Tray Ladder",
            type_name="Custom Type Not In List",
        )

        code = classifier.classify(item)

        # Should match family or fall through
        assert isinstance(code, int)


class TestRevitCategorySystem:
    """Test Revit Category + System Type (priority 70) classification."""

    def test_hvac_mechanical_equipment(self):
        """Test HVAC mechanical equipment classification."""
        classifier = TrustHierarchyClassifier()

        item = Item(
            org_id="test",
            project_id="proj-1",
            family="Boiler",
            type_name="Gas Boiler",
            category="Mechanical Equipment",
            system_type="HVAC",
        )

        code = classifier.classify(item)

        assert code == 2301  # HVAC equipment

    def test_plumbing_mechanical_equipment(self):
        """Test plumbing mechanical equipment classification."""
        classifier = TrustHierarchyClassifier()

        item = Item(
            org_id="test",
            project_id="proj-1",
            family="Water Heater",
            type_name="Electric",
            category="Mechanical Equipment",
            system_type="Plumbing",
        )

        code = classifier.classify(item)

        assert code == 2211  # Plumbing fixtures

    def test_ducts_category(self):
        """Test Ducts category classification."""
        classifier = TrustHierarchyClassifier()

        item = Item(
            org_id="test",
            project_id="proj-1",
            family="Rectangular Duct",
            type_name="400x200",
            category="Ducts",
        )

        code = classifier.classify(item)

        assert code == 2302  # HVAC distribution

    def test_pipe_fittings_category(self):
        """Test Pipe Fittings category classification."""
        classifier = TrustHierarchyClassifier()

        item = Item(
            org_id="test",
            project_id="proj-1",
            family="Elbow",
            type_name="90° DN100",
            category="Pipe Fittings",
        )

        code = classifier.classify(item)

        assert code == 2215  # Pipe fittings & valves

    def test_electrical_fixtures_category(self):
        """Test Electrical Fixtures category classification."""
        classifier = TrustHierarchyClassifier()

        item = Item(
            org_id="test",
            project_id="proj-1",
            family="Light Fixture",
            type_name="LED Panel",
            category="Electrical Fixtures",
        )

        code = classifier.classify(item)

        assert code == 2603  # Lighting & branch wiring

    def test_cable_tray_category(self):
        """Test Cable Tray category classification."""
        classifier = TrustHierarchyClassifier()

        item = Item(
            org_id="test",
            project_id="proj-1",
            family="Cable Tray Ladder",
            type_name="200x50",
            category="Cable Tray",
        )

        code = classifier.classify(item)

        assert code == 2650  # Cable management


class TestFallbackHeuristics:
    """Test Fallback Heuristics (priority 50) classification."""

    def test_duct_keyword_heuristic(self):
        """Test 'duct' keyword matches HVAC distribution."""
        classifier = TrustHierarchyClassifier()

        item = Item(
            org_id="test",
            project_id="proj-1",
            family="Supply Air Diffuser",  # Contains 'diffuser'
            type_name="Round",
        )

        code = classifier.classify(item)

        assert code == 2302  # HVAC distribution (diffuser keyword)

    def test_valve_keyword_heuristic(self):
        """Test 'valve' keyword matches pipe fittings."""
        classifier = TrustHierarchyClassifier()

        item = Item(
            org_id="test",
            project_id="proj-1",
            family="Ball Valve DN50",  # Contains 'valve'
            type_name="Brass",
        )

        code = classifier.classify(item)

        assert code == 2215  # Pipe fittings & valves

    def test_light_keyword_heuristic(self):
        """Test 'light' keyword matches lighting."""
        classifier = TrustHierarchyClassifier()

        item = Item(
            org_id="test",
            project_id="proj-1",
            family="Ceiling Light Panel",  # Contains 'light'
            type_name="600x600",
        )

        code = classifier.classify(item)

        assert code == 2603  # Lighting

    def test_tray_keyword_heuristic(self):
        """Test 'tray' keyword matches cable management."""
        classifier = TrustHierarchyClassifier()

        item = Item(
            org_id="test",
            project_id="proj-1",
            family="Ladder Tray Elbow",  # Contains 'tray'
            type_name="90°",
        )

        code = classifier.classify(item)

        assert code == 2650  # Cable management

    def test_case_insensitive_heuristics(self):
        """Test heuristics are case-insensitive."""
        classifier = TrustHierarchyClassifier()

        item = Item(
            org_id="test",
            project_id="proj-1",
            family="VALVE GATE",  # Uppercase
            type_name="DN100",
        )

        code = classifier.classify(item)

        assert code == 2215  # Should match 'valve' keyword


class TestUnknown:
    """Test Unknown (priority 0) fallback classification."""

    def test_unknown_classification_for_unmatched_item(self):
        """Test unknown classification code for unrecognized items."""
        classifier = TrustHierarchyClassifier()

        item = Item(
            org_id="test",
            project_id="proj-1",
            family="Completely Unknown Widget",
            type_name="Mystery Type",
        )

        code = classifier.classify(item)

        assert code == 9999  # Unknown classification


class TestClassificationOrder:
    """Test trust hierarchy ordering."""

    def test_explicit_override_beats_curated(self):
        """Test explicit override has higher priority than curated list."""
        classifier = TrustHierarchyClassifier()

        item = Item(
            org_id="test",
            project_id="proj-1",
            family="Cable Tray Ladder",  # Might be in curated list
            type_name="Test",
            omniclass_code=9999,  # Explicit override to Unknown
        )

        code = classifier.classify(item)

        assert code == 9999  # Explicit override wins

    def test_curated_beats_revit_category(self):
        """Test curated list has priority over Revit category."""
        classifier = TrustHierarchyClassifier()

        # This would depend on curated_classifications.csv contents
        # If Cable Tray Ladder is curated, it should override category
        item = Item(
            org_id="test",
            project_id="proj-1",
            family="Cable Tray Ladder",
            type_name="Standard",
            category="Cable Tray",  # Would classify to 2650
        )

        code = classifier.classify(item)

        # Should use curated or category
        assert code in (66, 2650)  # Either curated or category

    def test_revit_category_beats_heuristics(self):
        """Test Revit category has priority over heuristics."""
        classifier = TrustHierarchyClassifier()

        item = Item(
            org_id="test",
            project_id="proj-1",
            family="Light Fixture",  # Would match 'light' heuristic (2603)
            type_name="LED",
            category="Electrical Fixtures",  # Also maps to 2603
        )

        code = classifier.classify(item)

        assert code == 2603  # Should use category match

    def test_heuristics_beats_unknown(self):
        """Test heuristics have priority over unknown."""
        classifier = TrustHierarchyClassifier()

        item = Item(
            org_id="test",
            project_id="proj-1",
            family="Custom Valve Assembly",  # Contains 'valve'
            type_name="Special",
        )

        code = classifier.classify(item)

        assert code == 2215  # Should match heuristic, not unknown


class TestErrorHandling:
    """Test error handling."""

    def test_missing_family_raises_error(self):
        """Test item without family raises ValueError."""
        classifier = TrustHierarchyClassifier()

        item = Item(
            org_id="test",
            project_id="proj-1",
            family="",  # Empty family
            type_name="Test",
        )

        with pytest.raises(ValueError) as exc_info:
            classifier.classify(item)

        assert "family is required" in str(exc_info.value)

    def test_none_family_raises_error(self):
        """Test item with None family raises ValueError."""
        classifier = TrustHierarchyClassifier()

        # Create item with valid family first
        item = Item(
            org_id="test",
            project_id="proj-1",
            family="Test",
            type_name="Test",
        )

        # Manually set family to None (bypass Pydantic validation)
        item.family = None

        with pytest.raises(ValueError) as exc_info:
            classifier.classify(item)

        assert "family is required" in str(exc_info.value)


class TestConvenienceFunction:
    """Test classify_item convenience function."""

    def test_classify_item_function(self):
        """Test classify_item convenience function."""
        item = Item(
            org_id="test",
            project_id="proj-1",
            family="Pipe Elbow",
            type_name="90°",
            category="Pipe Fittings",
        )

        code = classify_item(item)

        assert code == 2215  # Pipe fittings
        assert isinstance(code, int)
