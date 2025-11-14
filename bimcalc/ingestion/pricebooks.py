"""Vendor price book ingestion for BIMCalc.

Parses CSV/XLSX vendor catalogs and creates PriceItem records.

Now supports Classification Mapping Module (CMM) to translate vendor-specific
codes and descriptors into BIMCalc canonical classification codes.
"""

from __future__ import annotations

import logging
from decimal import Decimal
from pathlib import Path

import pandas as pd
from sqlalchemy.ext.asyncio import AsyncSession

from bimcalc.classification.translator import VendorTranslator
from bimcalc.db.models import PriceItemModel

logger = logging.getLogger(__name__)


async def ingest_pricebook(
    session: AsyncSession,
    file_path: Path,
    vendor_id: str = "default",
    org_id: str = "default",
    region: str = "IE",
    use_cmm: bool = True,
    config_dir: Path = Path("config/vendors"),
) -> tuple[int, list[str]]:
    """Ingest vendor price book from CSV or XLSX file.

    Expected columns:
    - SKU (required)
    - Description (required)
    - Classification Code (required - integer, e.g., 2215) OR vendor fields for CMM
    - Unit Price (required)
    - Unit (required - "m", "ea", "m2", "m3")
    - Currency (optional, default EUR)
    - VAT Rate (optional, e.g., 0.23)
    - Width / Height / DN / Angle (optional, numeric attributes)
    - Material (optional)

    CMM Support (Classification Mapping Module):
    - If use_cmm=True, attempts to load vendor mapping file
    - Translates vendor-specific codes/descriptors to canonical codes
    - Falls back to direct ingestion if no mapping file found
    - Reports unmapped items in error messages

    Args:
        session: Database session
        file_path: Path to CSV or XLSX file
        vendor_id: Vendor identifier
        org_id: Organization ID for multi-tenant scoping (required)
        region: Region code (e.g., 'IE', 'UK', 'EU') for price localization
        use_cmm: Enable Classification Mapping Module translation
        config_dir: Directory containing vendor mapping YAML files

    Returns:
        Tuple of (success_count, error_messages)

    Raises:
        FileNotFoundError: If file doesn't exist
        ValueError: If file format is invalid
    """
    if not file_path.exists():
        raise FileNotFoundError(f"Price book not found: {file_path}")

    # Read file
    if file_path.suffix.lower() == ".csv":
        df = pd.read_csv(file_path)
    elif file_path.suffix.lower() in (".xlsx", ".xls"):
        df = pd.read_excel(file_path)
    else:
        raise ValueError(f"Unsupported file format: {file_path.suffix}")

    # Initialize CMM translator if enabled
    translator = None
    if use_cmm:
        translator = VendorTranslator(vendor_id, config_dir)
        if translator.loader:
            logger.info(f"CMM enabled for vendor '{vendor_id}' with {len(translator.loader.rules)} rules")
        else:
            logger.info(f"CMM enabled but no mapping file found for '{vendor_id}'")

    # Validate required columns
    has_translator = translator is not None and translator.loader is not None

    required_cols = {"SKU", "Unit Price"}
    if not has_translator:
        required_cols.update({"Description", "Unit"})

    # Classification Code is required when CMM translation cannot provide it
    if not use_cmm or not has_translator:
        required_cols.add("Classification Code")

    missing = required_cols - set(df.columns)
    if missing:
        raise ValueError(f"Missing required columns: {missing}")

    success_count = 0
    errors = []
    cmm_mapped_count = 0
    cmm_unmapped_count = 0

    for idx, row in df.iterrows():
        try:
            # Apply CMM translation if enabled
            row_dict = row.to_dict()
            translation_result = None

            if translator and translator.loader:
                translation_result = translator.translate_row(row_dict)
                row_dict = translation_result.row  # Use translated row

                if translation_result.was_mapped:
                    cmm_mapped_count += 1
                else:
                    cmm_unmapped_count += 1

            # Required fields
            sku = str(row_dict["SKU"]).strip()
            description = str(row_dict.get("Description", row_dict.get("Description1", ""))).strip()
            unit_price = Decimal(str(row_dict["Unit Price"]))
            unit = _get_str_from_dict(row_dict, [
                "Unit",
                "unit",
                "Units",
                "units",
                "Unit Type",
            ])
            unit = unit.lower() if unit else "ea"

            if not sku or not description:
                errors.append(f"Row {idx}: Missing SKU or Description")
                continue

            if unit_price < 0:
                errors.append(f"Row {idx}: Negative unit price")
                continue

            # Classification code from CMM or direct column
            classification_code = None
            if translation_result and translation_result.canonical_code:
                # Use canonical_code from CMM as classification_code
                # Try to extract numeric code from canonical_code or use classification_code field
                if "classification_code" in row_dict:
                    classification_code = int(row_dict["classification_code"])
                else:
                    # Try to parse from canonical_code or use a default
                    logger.warning(f"Row {idx}: CMM mapped but no classification_code in map_to, using fallback")
                    classification_code = 9999  # Fallback/unknown code
            else:
                # Direct from column (old path)
                if "Classification Code" in row_dict and pd.notna(row_dict["Classification Code"]):
                    classification_code = int(row_dict["Classification Code"])
                else:
                    errors.append(f"Row {idx}: No classification code (CMM unmapped, no Classification Code column)")
                    continue

            # Optional fields
            currency = str(row_dict.get("Currency", "EUR")).strip().upper()
            vat_rate = None
            if "VAT Rate" in row_dict and pd.notna(row_dict["VAT Rate"]):
                vat_rate = Decimal(str(row_dict["VAT Rate"]))

            # Physical attributes (check translated row_dict)
            width_mm = _get_float_from_dict(row_dict, ["Width", "Width (mm)", "W"])
            height_mm = _get_float_from_dict(row_dict, ["Height", "Height (mm)", "H"])
            dn_mm = _get_float_from_dict(row_dict, ["DN", "Diameter", "D"])
            angle_deg = _get_float_from_dict(row_dict, ["Angle", "Angle (deg)"])
            material = _get_str_from_dict(row_dict, "Material")
            vendor_note = _get_str_from_dict(row_dict, ["Vendor Note", "Note", "Comments"])

            # Add CMM metadata to vendor_note if mapped
            if translation_result and translation_result.was_mapped:
                cmm_note = f"CMM: {translation_result.canonical_code or 'mapped'}"
                vendor_note = f"{cmm_note}; {vendor_note}" if vendor_note else cmm_note

            # Create PriceItem model with required SCD2 and multi-tenant fields
            price_model = PriceItemModel(
                org_id=org_id,  # CRITICAL: Multi-tenant isolation
                item_code=sku,  # Use SKU as item_code (can be customized)
                region=region,  # Price localization by region
                vendor_id=vendor_id,
                sku=sku,
                description=description,
                classification_code=classification_code,
                unit=unit,
                unit_price=unit_price,
                currency=currency,
                vat_rate=vat_rate,
                width_mm=width_mm,
                height_mm=height_mm,
                dn_mm=dn_mm,
                angle_deg=angle_deg,
                material=material,
                source_name=f"{vendor_id}_{file_path.stem}",  # Traceable source
                source_currency=currency,
                vendor_note=vendor_note,
            )

            session.add(price_model)
            success_count += 1

        except Exception as e:
            errors.append(f"Row {idx}: {str(e)}")
            continue

    # Commit all items
    await session.commit()

    # Add CMM statistics to errors (informational)
    if translator and translator.loader:
        stats = translator.get_stats()
        logger.info(f"CMM Stats: {stats['mapped']} mapped, {stats['unmapped']} unmapped, {stats['total']} total")
        if stats['unmapped'] > 0:
            errors.append(f"ℹ️  CMM: {stats['mapped']}/{stats['total']} items mapped, {stats['unmapped']} unmapped (using direct classification)")

    return success_count, errors


def _get_str(row: pd.Series, col_name: str | list[str]) -> str | None:
    """Get string value from row."""
    if isinstance(col_name, str):
        col_name = [col_name]

    for col in col_name:
        if col in row and pd.notna(row[col]):
            return str(row[col]).strip()

    return None


def _get_float(row: pd.Series, col_name: str | list[str]) -> float | None:
    """Get float value from row."""
    if isinstance(col_name, str):
        col_name = [col_name]

    for col in col_name:
        if col in row and pd.notna(row[col]):
            try:
                return float(row[col])
            except (ValueError, TypeError):
                continue

    return None


def _get_str_from_dict(row_dict: dict, col_name: str | list[str]) -> str | None:
    """Get string value from dict."""
    if isinstance(col_name, str):
        col_name = [col_name]

    for col in col_name:
        if col in row_dict and pd.notna(row_dict[col]):
            return str(row_dict[col]).strip()

    return None


def _get_float_from_dict(row_dict: dict, col_name: str | list[str]) -> float | None:
    """Get float value from dict."""
    if isinstance(col_name, str):
        col_name = [col_name]

    for col in col_name:
        if col in row_dict and pd.notna(row_dict[col]):
            try:
                # Handle strings with units (e.g., "200mm", "50mm")
                val = row_dict[col]
                if isinstance(val, str):
                    # Strip common suffixes
                    val = val.replace("mm", "").replace("deg", "").strip()
                return float(val)
            except (ValueError, TypeError):
                continue

    return None
