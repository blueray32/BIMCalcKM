"""Tests for Classification Mapping Module (CMM) loader."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest
import yaml

from bimcalc.classification.cmm_loader import ClassificationMappingLoader, MappingRule, load_vendor_mapping


@pytest.fixture
def sample_mapping_yaml(tmp_path: Path) -> Path:
    """Create a sample vendor mapping YAML file."""
    mapping_data = [
        {
            "match": {
                "Containment": "ES_CONTMNT",
                "Description1": "Basket",
                "Description2": "Length",
                "Width": "450mm",
                "Depth": "55mm",
                "Finish": "Zinc Plated",
            },
            "map_to": {
                "canonical_code": "B-LEN-W450-D55-ZP",
                "internal_group": "ES_CONTMNT",
                "short": 6620,
                "classification_code": "2650",
            },
        },
        {
            "match": {
                "Containment": "ES_CONTMNT",
                "Description1": "Ladder",
                "Description2": "Elbow 90deg",
                "Width": "200mm",
                "Depth": "50mm",
                "Finish": "Galvanized",
            },
            "map_to": {
                "canonical_code": "L-ELB90-W200-D50-GALV",
                "internal_group": "ES_CONTMNT",
                "short": 6620,
                "classification_code": "2650",
            },
        },
        {
            "match": {
                "Description1": "LED Panel",
                "Width": "600mm",
                "Height": "600mm",
            },
            "map_to": {
                "canonical_code": "LED-600X600-STD",
                "classification_code": "2603",
            },
            "priority": 50,
        },
    ]

    yaml_file = tmp_path / "config_vendor_test_classification_map.yaml"
    with open(yaml_file, "w") as f:
        yaml.safe_dump(mapping_data, f)

    return yaml_file


def test_mapping_rule_matches_exact():
    """Test MappingRule matches when all fields match exactly."""
    rule = MappingRule(
        match={"Containment": "ES_CONTMNT", "Description1": "Basket"},
        map_to={"canonical_code": "B-TEST"},
    )

    row = {"Containment": "ES_CONTMNT", "Description1": "Basket", "Width": "450mm"}

    assert rule.matches(row) is True


def test_mapping_rule_matches_case_insensitive():
    """Test MappingRule matches are case-insensitive for strings."""
    rule = MappingRule(
        match={"Description1": "basket"},
        map_to={"canonical_code": "B-TEST"},
    )

    row = {"Description1": "BASKET"}

    assert rule.matches(row) is True


def test_mapping_rule_no_match_missing_field():
    """Test MappingRule doesn't match when required field is missing."""
    rule = MappingRule(
        match={"Containment": "ES_CONTMNT", "Description1": "Basket"},
        map_to={"canonical_code": "B-TEST"},
    )

    row = {"Containment": "ES_CONTMNT"}  # Missing Description1

    assert rule.matches(row) is False


def test_mapping_rule_no_match_wrong_value():
    """Test MappingRule doesn't match when field has wrong value."""
    rule = MappingRule(
        match={"Description1": "Basket"},
        map_to={"canonical_code": "B-TEST"},
    )

    row = {"Description1": "Ladder"}

    assert rule.matches(row) is False


def test_mapping_rule_apply():
    """Test MappingRule.apply merges map_to fields into row."""
    rule = MappingRule(
        match={"Description1": "Basket"},
        map_to={"canonical_code": "B-TEST", "classification_code": "2650"},
    )

    row = {"Description1": "Basket", "Width": "450mm"}
    result = rule.apply(row)

    assert result["Description1"] == "Basket"
    assert result["Width"] == "450mm"
    assert result["canonical_code"] == "B-TEST"
    assert result["classification_code"] == "2650"


def test_loader_loads_rules(sample_mapping_yaml: Path):
    """Test ClassificationMappingLoader loads rules from YAML."""
    loader = ClassificationMappingLoader(sample_mapping_yaml)

    assert len(loader.rules) == 3
    assert loader.rules[0].priority == 50  # Sorted by priority
    assert loader.rules[1].priority == 100
    assert loader.rules[2].priority == 100


def test_loader_find_match(sample_mapping_yaml: Path):
    """Test ClassificationMappingLoader finds matching rule."""
    loader = ClassificationMappingLoader(sample_mapping_yaml)

    row = {
        "Containment": "ES_CONTMNT",
        "Description1": "Basket",
        "Description2": "Length",
        "Width": "450mm",
        "Depth": "55mm",
        "Finish": "Zinc Plated",
    }

    rule = loader.find_match(row)

    assert rule is not None
    assert rule.map_to["canonical_code"] == "B-LEN-W450-D55-ZP"


def test_loader_find_match_none(sample_mapping_yaml: Path):
    """Test ClassificationMappingLoader returns None when no match."""
    loader = ClassificationMappingLoader(sample_mapping_yaml)

    row = {"Description1": "Unknown Item"}

    rule = loader.find_match(row)

    assert rule is None


def test_loader_translate_mapped(sample_mapping_yaml: Path):
    """Test ClassificationMappingLoader translates matched row."""
    loader = ClassificationMappingLoader(sample_mapping_yaml)

    row = {
        "Description1": "LED Panel",
        "Width": "600mm",
        "Height": "600mm",
        "SKU": "LED-001",
    }

    translated, was_mapped = loader.translate(row)

    assert was_mapped is True
    assert translated["canonical_code"] == "LED-600X600-STD"
    assert translated["classification_code"] == "2603"
    assert translated["SKU"] == "LED-001"  # Original fields preserved


def test_loader_translate_unmapped(sample_mapping_yaml: Path):
    """Test ClassificationMappingLoader returns original row when unmapped."""
    loader = ClassificationMappingLoader(sample_mapping_yaml)

    row = {"Description1": "Unknown Item", "SKU": "UNK-001"}

    translated, was_mapped = loader.translate(row)

    assert was_mapped is False
    assert translated == row  # Unchanged


def test_loader_file_not_found():
    """Test ClassificationMappingLoader raises error for missing file."""
    with pytest.raises(FileNotFoundError):
        ClassificationMappingLoader(Path("/nonexistent/file.yaml"))


def test_loader_invalid_yaml(tmp_path: Path):
    """Test ClassificationMappingLoader raises error for invalid YAML."""
    yaml_file = tmp_path / "invalid.yaml"
    with open(yaml_file, "w") as f:
        f.write("{ invalid yaml: [")

    with pytest.raises(ValueError, match="Invalid YAML"):
        ClassificationMappingLoader(yaml_file)


def test_load_vendor_mapping_exists(sample_mapping_yaml: Path):
    """Test load_vendor_mapping loads existing mapping file."""
    loader = load_vendor_mapping("test", config_dir=sample_mapping_yaml.parent)

    assert loader is not None
    assert len(loader.rules) == 3


def test_load_vendor_mapping_not_found(tmp_path: Path):
    """Test load_vendor_mapping returns None for missing vendor."""
    loader = load_vendor_mapping("nonexistent", config_dir=tmp_path)

    assert loader is None


def test_mapping_priority_order(tmp_path: Path):
    """Test rules are sorted and matched by priority."""
    mapping_data = [
        {
            "match": {"Type": "Generic"},
            "map_to": {"canonical_code": "GENERIC"},
            "priority": 200,
        },
        {
            "match": {"Type": "Specific", "Size": "Large"},
            "map_to": {"canonical_code": "SPECIFIC-LARGE"},
            "priority": 10,
        },
        {
            "match": {"Type": "Specific"},
            "map_to": {"canonical_code": "SPECIFIC"},
            "priority": 50,
        },
    ]

    yaml_file = tmp_path / "priority_test.yaml"
    with open(yaml_file, "w") as f:
        yaml.safe_dump(mapping_data, f)

    loader = ClassificationMappingLoader(yaml_file)

    # Should match highest priority (lowest number) rule first
    row1 = {"Type": "Specific", "Size": "Large"}
    rule1 = loader.find_match(row1)
    assert rule1.map_to["canonical_code"] == "SPECIFIC-LARGE"

    # Should match second priority rule
    row2 = {"Type": "Specific", "Size": "Small"}
    rule2 = loader.find_match(row2)
    assert rule2.map_to["canonical_code"] == "SPECIFIC"

    # Should match lowest priority fallback
    row3 = {"Type": "Generic"}
    rule3 = loader.find_match(row3)
    assert rule3.map_to["canonical_code"] == "GENERIC"
