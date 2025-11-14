"""CSV/Excel file-based importer for manufacturer price lists.

Handles periodic file drops from manufacturers like OBO, Philips, etc.
Supports both CSV and Excel formats.
"""

from __future__ import annotations

import logging
from decimal import Decimal
from pathlib import Path
from typing import AsyncIterator

import pandas as pd

from bimcalc.pipeline.base_importer import BaseImporter
from bimcalc.pipeline.types import PriceRecord

logger = logging.getLogger(__name__)


class CSVFileImporter(BaseImporter):
    """Import price data from CSV or Excel files.

    Configuration required:
    - file_path: Path to CSV/XLSX file
    - region: Geographic region (e.g., 'UK', 'DE')
    - column_mapping: Dict mapping file columns to PriceRecord fields

    Example config:
        {
            "file_path": "/data/prices/obo_q4_2024.csv",
            "region": "DE",
            "column_mapping": {
                "Item Code": "item_code",
                "Description": "description",
                "Class": "classification_code",
                "Price": "unit_price",
                "Currency": "currency",
                "Unit": "unit"
            }
        }
    """

    async def fetch_data(self) -> AsyncIterator[PriceRecord]:
        """Read file and yield normalized price records."""

        file_path = Path(self._get_config_value("file_path", required=True))
        region = self._get_config_value("region", required=True)
        column_mapping = self._get_config_value("column_mapping", required=True)

        if not file_path.exists():
            raise FileNotFoundError(f"Price file not found: {file_path}")

        # Read file based on extension
        if file_path.suffix.lower() == ".csv":
            df = pd.read_csv(file_path)
        elif file_path.suffix.lower() in (".xlsx", ".xls"):
            df = pd.read_excel(file_path)
        else:
            raise ValueError(f"Unsupported file format: {file_path.suffix}")

        self.logger.info(f"Read {len(df)} rows from {file_path}")

        # Process each row
        for idx, row in df.iterrows():
            try:
                record = self._parse_row(row, column_mapping, region)
                if record:
                    yield record

            except Exception as e:
                self.logger.warning(f"Row {idx} parsing error: {e}")
                continue

    def _parse_row(
        self, row: pd.Series, mapping: dict, region: str
    ) -> PriceRecord | None:
        """Parse a single row into PriceRecord.

        Args:
            row: DataFrame row
            mapping: Column name mapping (CSV column -> field name)
            region: Geographic region

        Returns:
            PriceRecord or None if parsing fails
        """

        # Invert mapping: field_name -> csv_column
        inv_mapping = {v: k for k, v in mapping.items()}

        def get_value(field: str, default=None):
            """Get value using column mapping."""
            col_name = inv_mapping.get(field)
            if col_name and col_name in row and pd.notna(row[col_name]):
                return row[col_name]
            return default

        # Required fields
        item_code = get_value("item_code")
        description = get_value("description")
        classification_code = get_value("classification_code")
        unit_price = get_value("unit_price")
        currency = get_value("currency", "EUR")
        unit = get_value("unit", "ea")

        if not all([item_code, description, classification_code, unit_price]):
            return None

        # Normalize types
        item_code = str(item_code).strip()
        description = str(description).strip()
        classification_code = int(classification_code)
        unit_price = Decimal(str(unit_price))
        currency = str(currency).upper()
        unit = str(unit).lower()

        # Validate
        if unit_price < 0:
            self.logger.warning(f"Negative price for {item_code}, skipping")
            return None

        # Optional fields
        width_mm = self._get_float(get_value("width_mm"))
        height_mm = self._get_float(get_value("height_mm"))
        dn_mm = self._get_float(get_value("dn_mm"))
        angle_deg = self._get_float(get_value("angle_deg"))
        material = get_value("material")
        sku = get_value("sku", item_code)
        vendor_id = self._get_config_value("vendor_id")

        return PriceRecord(
            item_code=item_code,
            region=region,
            classification_code=classification_code,
            description=description,
            unit=unit,
            unit_price=unit_price,
            currency=currency,
            source_currency=currency,
            width_mm=width_mm,
            height_mm=height_mm,
            dn_mm=dn_mm,
            angle_deg=angle_deg,
            material=material,
            vendor_id=vendor_id,
            sku=sku,
            source_name=self.source_name,
        )

    def _get_float(self, value) -> float | None:
        """Safely convert value to float."""
        if value is None or pd.isna(value):
            return None

        try:
            # Handle strings with units (e.g., "200mm")
            if isinstance(value, str):
                value = value.replace("mm", "").replace("deg", "").strip()
            return float(value)
        except (ValueError, TypeError):
            return None
