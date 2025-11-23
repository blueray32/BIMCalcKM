"""CSV Price List Importer for Supplier Catalogs.

Handles importing price lists from suppliers like CEF, Rexel, etc.
with flexible column mapping and classification translation.
"""

import csv
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any
from uuid import uuid4

import pandas as pd
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from bimcalc.db import get_session
from bimcalc.db.models import PriceItemModel, PriceImportRunModel

logger = logging.getLogger(__name__)


class CSVPriceImporter:
    """Import supplier price lists from CSV/Excel files."""

    # Common column name variations for auto-detection
    COLUMN_MAPPINGS = {
        "code": ["code", "product code", "product_code", "item_code", "item code", "sku", "part_number", "part number", "part_no", "part no"],
        "description": ["description", "product_description", "product description", "item_description", "item description", "product_name", "product name", "name"],
        "unit_price": ["price", "unit price", "unit_price", "unitprice", "cost", "unit_cost", "unit cost", "list_price", "list price"],
        "unit": ["unit", "uom", "unit_of_measure", "unit of measure", "measure"],
        "manufacturer": ["manufacturer", "brand", "make"],
        "category": ["category", "product_category", "product category", "type", "classification"],
        "currency": ["currency", "curr"],
    }

    def __init__(
        self,
        org_id: str,
        vendor_name: str,
        classification_scheme: str = "UniClass2015",
    ):
        self.org_id = org_id
        self.vendor_name = vendor_name
        self.classification_scheme = classification_scheme

    async def import_from_file(
        self,
        file_path: Path,
        column_mapping: Optional[Dict[str, str]] = None,
        sheet_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Import price items from CSV or Excel file.

        Args:
            file_path: Path to CSV or Excel file
            column_mapping: Custom column mapping (field_name -> column_name)
            sheet_name: Sheet name for Excel files (default: first sheet)

        Returns:
            Import statistics dictionary
        """
        logger.info(f"Starting CSV import from {file_path}")

        # Read file based on extension
        suffix = file_path.suffix.lower()
        if suffix == ".csv":
            df = pd.read_csv(file_path)
        elif suffix in [".xlsx", ".xls"]:
            df = pd.read_excel(file_path, sheet_name=sheet_name or 0)
        else:
            raise ValueError(f"Unsupported file format: {suffix}")

        logger.info(f"Loaded {len(df)} rows from {file_path}")

        # Auto-detect or use provided column mapping
        if not column_mapping:
            column_mapping = self._auto_detect_columns(df.columns.tolist())
            logger.info(f"Auto-detected column mapping: {column_mapping}")

        # Validate required columns
        required = ["code", "description", "unit_price"]
        missing = [f for f in required if f not in column_mapping]
        if missing:
            raise ValueError(f"Missing required columns: {missing}")

        # Create import run
        run_id = str(uuid4())
        import_run = PriceImportRunModel(
            id=run_id,
            org_id=self.org_id,
            source=f"csv_{self.vendor_name.lower()}",
            started_at=datetime.utcnow(),
            status="in_progress",
            items_fetched=len(df),
            items_loaded=0,
            items_rejected=0,
        )

        # Process rows
        items_loaded = 0
        items_rejected = 0
        rejection_reasons = {}

        async with get_session() as session:
            # Save import run
            session.add(import_run)
            await session.flush()

            for idx, row in df.iterrows():
                try:
                    item = self._process_row(row, column_mapping, run_id)
                    if item:
                        session.add(item)
                        items_loaded += 1
                    else:
                        items_rejected += 1
                        rejection_reasons["validation_failed"] = rejection_reasons.get("validation_failed", 0) + 1
                except Exception as e:
                    items_rejected += 1
                    reason = type(e).__name__
                    rejection_reasons[reason] = rejection_reasons.get(reason, 0) + 1
                    logger.warning(f"Row {idx + 2} rejected: {e}")

            # Update import run
            import_run.completed_at = datetime.utcnow()
            import_run.status = "completed"
            import_run.items_received = len(df)
            import_run.items_loaded = items_loaded
            import_run.items_rejected = items_rejected
            import_run.rejection_breakdown = rejection_reasons

            await session.commit()

        result = {
            "run_id": run_id,
            "items_received": len(df),
            "items_loaded": items_loaded,
            "items_rejected": items_rejected,
            "rejection_reasons": rejection_reasons,
        }

        logger.info(f"Import completed: {result}")
        return result

    def _auto_detect_columns(self, columns: List[str]) -> Dict[str, str]:
        """Auto-detect column mapping from header names."""
        mapping = {}
        columns_lower = [c.lower().strip() for c in columns]

        for field, variations in self.COLUMN_MAPPINGS.items():
            for var in variations:
                if var in columns_lower:
                    idx = columns_lower.index(var)
                    mapping[field] = columns[idx]
                    break

        return mapping

    def _process_row(
        self,
        row: pd.Series,
        column_mapping: Dict[str, str],
        run_id: str,
    ) -> Optional[PriceItemModel]:
        """Process a single row into a PriceItem."""
        # Extract fields
        code = str(row.get(column_mapping["code"], "")).strip()
        description = str(row.get(column_mapping["description"], "")).strip()
        unit_price_str = str(row.get(column_mapping["unit_price"], "")).strip()

        # Validate required fields
        if not code or not description or not unit_price_str:
            return None

        # Parse unit price
        try:
            # Remove currency symbols and whitespace
            unit_price_clean = unit_price_str.replace("€", "").replace("£", "").replace(",", "").strip()
            unit_price = float(unit_price_clean)
        except (ValueError, TypeError):
            logger.warning(f"Invalid unit price: {unit_price_str}")
            return None

        # Extract optional fields
        unit = str(row.get(column_mapping.get("unit", ""), "ea")).strip() or "ea"
        manufacturer = str(row.get(column_mapping.get("manufacturer", ""), "")).strip() or None
        category = str(row.get(column_mapping.get("category", ""), "")).strip() or None
        currency = str(row.get(column_mapping.get("currency", ""), "EUR")).strip() or "EUR"

        # Normalize unit
        unit = self._normalize_unit(unit)

        # Try to extract classification from category or description
        classification_code_str = self._extract_classification(category, description)
        if not classification_code_str:
            # Default to 66 (cable tray/management) if no classification found
            classification_code_str = "66"

        classification_code = int(classification_code_str)

        # Create PriceItem
        item = PriceItemModel(
            id=uuid4(),
            org_id=self.org_id,
            item_code=code,
            sku=code,
            vendor_code=code,
            description=description,
            unit=unit,
            unit_price=unit_price,
            currency=currency,
            classification_code=classification_code,
            region="IE",  # Default to Ireland
            source_name=self.vendor_name,
            source_currency=currency,
            is_current=True,
        )

        return item

    def _normalize_unit(self, unit: str) -> str:
        """Normalize unit of measure."""
        unit_lower = unit.lower().strip()

        # Common unit mappings
        unit_map = {
            "each": "ea",
            "piece": "ea",
            "pcs": "ea",
            "metre": "m",
            "meter": "m",
            "metres": "m",
            "meters": "m",
            "sq.m": "m²",
            "sqm": "m²",
            "square metre": "m²",
            "square meter": "m²",
            "kg": "kg",
            "kilogram": "kg",
            "litre": "L",
            "liter": "L",
            "litres": "L",
            "liters": "L",
        }

        return unit_map.get(unit_lower, unit)

    def _extract_classification(self, category: Optional[str], description: str) -> Optional[str]:
        """Try to extract classification code from category or description."""
        # Common electrical classifications (UniClass2015)
        classification_keywords = {
            "66": ["cable tray", "cable management", "trunking", "containment"],
            "62": ["socket", "outlet", "power point", "small power"],
            "64": ["light", "luminaire", "lamp", "lighting"],
            "68": ["fire alarm", "smoke detector", "fire detection"],
            "67": ["emergency light", "exit sign", "emergency lighting"],
        }

        text = f"{category or ''} {description}".lower()

        for code, keywords in classification_keywords.items():
            if any(kw in text for kw in keywords):
                return code

        return None


async def import_supplier_pricelist(
    file_path: str,
    org_id: str,
    vendor_name: str,
    column_mapping: Optional[Dict[str, str]] = None,
    sheet_name: Optional[str] = None,
) -> Dict[str, Any]:
    """Import supplier price list from CSV/Excel file.

    Args:
        file_path: Path to file
        org_id: Organization ID
        vendor_name: Vendor/supplier name
        column_mapping: Optional custom column mapping
        sheet_name: Sheet name for Excel files

    Returns:
        Import statistics
    """
    importer = CSVPriceImporter(org_id=org_id, vendor_name=vendor_name)
    return await importer.import_from_file(
        file_path=Path(file_path),
        column_mapping=column_mapping,
        sheet_name=sheet_name,
    )
