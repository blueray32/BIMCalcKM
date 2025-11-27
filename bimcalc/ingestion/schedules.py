"""Revit schedule ingestion for BIMCalc.

Parses CSV/XLSX schedule exports and creates Item records.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
from sqlalchemy.ext.asyncio import AsyncSession

from bimcalc.db.models import ItemModel


async def ingest_schedule(
    session: AsyncSession,
    file_path: Path,
    org_id: str,
    project_id: str,
) -> tuple[int, list[str]]:
    """Ingest Revit schedule from CSV or XLSX file.

    Expected columns:
    - Family (required)
    - Type (required)
    - Category (optional)
    - System Type (optional)
    - Count / Quantity (optional)
    - Width / Height / DN / Angle (optional, numeric attributes)
    - Material (optional)
    - Unit (optional)

    Args:
        session: Database session
        file_path: Path to CSV or XLSX file
        org_id: Organization identifier
        project_id: Project identifier

    Returns:
        Tuple of (success_count, error_messages)

    Raises:
        FileNotFoundError: If file doesn't exist
        ValueError: If file format is invalid
    """
    if not file_path.exists():
        raise FileNotFoundError(f"Schedule file not found: {file_path}")

    # Check file size limit (50MB max)
    MAX_FILE_SIZE_MB = 50
    file_size_mb = file_path.stat().st_size / (1024 * 1024)
    if file_size_mb > MAX_FILE_SIZE_MB:
        raise ValueError(
            f"File too large ({file_size_mb:.1f}MB). Maximum allowed: {MAX_FILE_SIZE_MB}MB"
        )

    # Read file (CSV or XLSX)
    if file_path.suffix.lower() == ".csv":
        df = pd.read_csv(file_path)
    elif file_path.suffix.lower() in (".xlsx", ".xls"):
        df = pd.read_excel(file_path)
    else:
        raise ValueError(f"Unsupported file format: {file_path.suffix}. Use CSV or XLSX.")

    # Check row count limit
    MAX_ROWS = 50000
    if len(df) > MAX_ROWS:
        raise ValueError(
            f"Too many rows ({len(df):,}). Maximum allowed: {MAX_ROWS:,}"
        )

    # Validate required columns
    required_cols = {"Family", "Type"}
    missing = required_cols - set(df.columns)
    if missing:
        raise ValueError(f"Missing required columns: {missing}")

    success_count = 0
    errors = []

    for idx, row in df.iterrows():
        try:
            # Required fields
            family = str(row.get("Family", "")).strip()
            type_name = str(row.get("Type", "")).strip()

            if not family or not type_name:
                errors.append(f"Row {idx}: Missing family or type")
                continue

            # Optional fields
            category = _get_str(row, "Category")
            system_type = _get_str(row, "System Type")
            quantity_col = row.get("Count") or row.get("Quantity")
            quantity = float(quantity_col) if pd.notna(quantity_col) else None
            unit = _get_str(row, "Unit")

            # Physical attributes (try multiple column name variants)
            width_mm = _get_float(row, ["Width", "Width (mm)", "W"])
            height_mm = _get_float(row, ["Height", "Height (mm)", "H"])
            dn_mm = _get_float(row, ["DN", "Diameter", "D"])
            angle_deg = _get_float(row, ["Angle", "Angle (deg)", "Degrees"])
            material = _get_str(row, "Material")

            # Create Item model
            item_model = ItemModel(
                org_id=org_id,
                project_id=project_id,
                family=family,
                type_name=type_name,
                category=category,
                system_type=system_type,
                quantity=quantity,
                unit=unit,
                width_mm=width_mm,
                height_mm=height_mm,
                dn_mm=dn_mm,
                angle_deg=angle_deg,
                material=material,
                source_file=str(file_path),
            )

            # Check for duplicate before inserting
            from sqlalchemy import select
            existing_item = await session.execute(
                select(ItemModel).where(
                    ItemModel.org_id == org_id,
                    ItemModel.project_id == project_id,
                    ItemModel.family == family,
                    ItemModel.type_name == type_name,
                )
            )
            
            if existing_item.scalar_one_or_none():
                # Item already exists - skip or update
                errors.append(f"Row {idx}: Duplicate item (Family='{family}', Type='{type_name}') - skipped")
                continue

            session.add(item_model)
            success_count += 1

        except Exception as e:
            errors.append(f"Row {idx}: {str(e)}")
            continue

    # Commit all items
    await session.commit()

    return success_count, errors


def _get_str(row: pd.Series, col_name: str | list[str]) -> str | None:
    """Get string value from row, trying multiple column names."""
    if isinstance(col_name, str):
        col_name = [col_name]

    for col in col_name:
        if col in row and pd.notna(row[col]):
            return str(row[col]).strip()

    return None


def _get_float(row: pd.Series, col_name: str | list[str]) -> float | None:
    """Get float value from row, trying multiple column names."""
    if isinstance(col_name, str):
        col_name = [col_name]

    for col in col_name:
        if col in row and pd.notna(row[col]):
            try:
                return float(row[col])
            except (ValueError, TypeError):
                continue

    return None
