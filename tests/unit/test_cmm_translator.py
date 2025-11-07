"""Tests for Classification Mapping Module (CMM) translator."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from bimcalc.classification.translator import VendorTranslator, translate_batch


@pytest.fixture
def sample_mapping_yaml(tmp_path: Path) -> Path:
    """Create a sample vendor mapping YAML file for testing."""
    mapping_data = [
        {
            "match": {
                "Containment": "ES_CONTMNT",
                "Description1": "Basket",
                "Description2": "Length",
                "Width": "450mm",
            },
            "map_to": {
                "canonical_code": "B-LEN-W450",
                "classification_code": "2650",
                "internal_group": "ES_CONTMNT",
            },
        },
        {
            "match": {
                "Description1": "LED Panel",
            },
            "map_to": {
                "canonical_code": "LED-STD",
                "classification_code": "2603",
            },
        },
    ]

    # Create vendor config directory
    vendor_dir = tmp_path / "vendors"
    vendor_dir.mkdir(parents=True, exist_ok=True)

    yaml_file = vendor_dir / "config_vendor_test_classification_map.yaml"
    with open(yaml_file, "w") as f:
        yaml.safe_dump(mapping_data, f)

    return tmp_path


def test_vendor_translator_init_with_mapping(sample_mapping_yaml: Path):
    """Test VendorTranslator initializes with mapping file."""
    translator = VendorTranslator("test", config_dir=sample_mapping_yaml / "vendors")

    assert translator.loader is not None
    assert len(translator.loader.rules) == 2


def test_vendor_translator_init_without_mapping(tmp_path: Path):
    """Test VendorTranslator initializes without mapping file."""
    translator = VendorTranslator("nonexistent", config_dir=tmp_path)

    assert translator.loader is None


def test_vendor_translator_translate_mapped(sample_mapping_yaml: Path):
    """Test VendorTranslator translates matched row."""
    translator = VendorTranslator("test", config_dir=sample_mapping_yaml / "vendors")

    row = {
        "Containment": "ES_CONTMNT",
        "Description1": "Basket",
        "Description2": "Length",
        "Width": "450mm",
        "SKU": "B-001",
    }

    result = translator.translate_row(row)

    assert result.was_mapped is True
    assert result.canonical_code == "B-LEN-W450"
    assert result.internal_group == "ES_CONTMNT"
    assert result.row["classification_code"] == "2650"
    assert result.row["SKU"] == "B-001"  # Original preserved
    assert result.original_fields is not None


def test_vendor_translator_translate_unmapped(sample_mapping_yaml: Path):
    """Test VendorTranslator returns original row when unmapped."""
    translator = VendorTranslator("test", config_dir=sample_mapping_yaml / "vendors")

    row = {"Description1": "Unknown Item", "SKU": "UNK-001"}

    result = translator.translate_row(row)

    assert result.was_mapped is False
    assert result.canonical_code is None
    assert result.row == row


def test_vendor_translator_no_loader(tmp_path: Path):
    """Test VendorTranslator without loader returns original rows."""
    translator = VendorTranslator("nonexistent", config_dir=tmp_path)

    row = {"Description1": "Item", "SKU": "I-001"}

    result = translator.translate_row(row)

    assert result.was_mapped is False
    assert result.canonical_code is None
    assert result.row == row


def test_vendor_translator_stats(sample_mapping_yaml: Path):
    """Test VendorTranslator tracks mapping statistics."""
    translator = VendorTranslator("test", config_dir=sample_mapping_yaml / "vendors")

    rows = [
        {"Description1": "LED Panel", "SKU": "LED-001"},  # Mapped
        {"Description1": "Unknown", "SKU": "UNK-001"},  # Unmapped
        {"Description1": "LED Panel", "SKU": "LED-002"},  # Mapped
    ]

    for row in rows:
        translator.translate_row(row)

    stats = translator.get_stats()

    assert stats["mapped"] == 2
    assert stats["unmapped"] == 1
    assert stats["total"] == 3


def test_vendor_translator_reset_stats(sample_mapping_yaml: Path):
    """Test VendorTranslator can reset statistics."""
    translator = VendorTranslator("test", config_dir=sample_mapping_yaml / "vendors")

    # Process some rows
    translator.translate_row({"Description1": "LED Panel"})
    translator.translate_row({"Description1": "Unknown"})

    assert translator.get_stats()["total"] == 2

    # Reset
    translator.reset_stats()

    stats = translator.get_stats()
    assert stats["mapped"] == 0
    assert stats["unmapped"] == 0
    assert stats["total"] == 0


def test_translate_batch(sample_mapping_yaml: Path):
    """Test translate_batch processes multiple rows."""
    rows = [
        {
            "Containment": "ES_CONTMNT",
            "Description1": "Basket",
            "Description2": "Length",
            "Width": "450mm",
        },
        {"Description1": "LED Panel"},
        {"Description1": "Unknown Item"},
    ]

    results, stats = translate_batch(
        rows,
        vendor_id="test",
        config_dir=sample_mapping_yaml / "vendors",
    )

    assert len(results) == 3
    assert results[0].was_mapped is True
    assert results[0].canonical_code == "B-LEN-W450"
    assert results[1].was_mapped is True
    assert results[1].canonical_code == "LED-STD"
    assert results[2].was_mapped is False

    assert stats["mapped"] == 2
    assert stats["unmapped"] == 1
    assert stats["total"] == 3


def test_translate_batch_no_mapping(tmp_path: Path):
    """Test translate_batch with no mapping file."""
    rows = [
        {"Description1": "Item 1"},
        {"Description1": "Item 2"},
    ]

    results, stats = translate_batch(rows, vendor_id="nonexistent", config_dir=tmp_path)

    assert len(results) == 2
    assert results[0].was_mapped is False
    assert results[1].was_mapped is False

    assert stats["mapped"] == 0
    assert stats["unmapped"] == 2


def test_translation_result_original_fields(sample_mapping_yaml: Path):
    """Test TranslationResult captures original fields for audit trail."""
    translator = VendorTranslator("test", config_dir=sample_mapping_yaml / "vendors")

    row = {
        "Description": "LED Panel 600x600",
        "Description1": "LED Panel",
        "Classification Code": "9999",  # Will be replaced by CMM
        "SKU": "LED-001",
    }

    result = translator.translate_row(row)

    assert result.was_mapped is True
    assert result.original_fields is not None
    assert "description" in result.original_fields
    assert "classification_code" in result.original_fields


def test_excel_sample_data_translation(sample_mapping_yaml: Path):
    """Test translation of Excel-like sample data with real-world fields.

    This simulates the Hierarchy Options.xlsx structure:
    - Containment, Description1, Description2, Width, Depth, Finish → Result
    """
    translator = VendorTranslator("test", config_dir=sample_mapping_yaml / "vendors")

    # Sample row from Excel (cable tray basket)
    excel_row = {
        "Containment": "ES_CONTMNT",
        "Description1": "Basket",
        "Description2": "Length",
        "Width": "450mm",
        "Depth": "55mm",
        "Finish": "Zinc Plated",
        "SKU": "BASK-450-55-ZP",
        "Unit Price": "125.50",
        "Unit": "ea",
    }

    result = translator.translate_row(excel_row)

    assert result.was_mapped is True
    assert result.canonical_code == "B-LEN-W450"
    assert result.row["classification_code"] == "2650"
    assert result.row["SKU"] == "BASK-450-55-ZP"  # Preserved
    assert result.row["Unit Price"] == "125.50"  # Preserved
