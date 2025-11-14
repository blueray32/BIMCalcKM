"""Report builder with SCD2 as-of queries and EU formatting.

Generates deterministic, reproducible cost reports.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Optional

import pandas as pd
from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from bimcalc.config import get_config
from bimcalc.db.models import ItemMappingModel, ItemModel, PriceItemModel


class ReportBuilder:
    """Builds cost reports with SCD2 temporal queries."""

    def __init__(self, session: AsyncSession):
        """Initialize builder with database session.

        Args:
            session: SQLAlchemy async session
        """
        self.session = session
        self.config = get_config()

    async def build(
        self,
        org_id: str,
        project_id: str,
        as_of: Optional[datetime] = None,
    ) -> pd.DataFrame:
        """Generate cost report using SCD2 as-of query.

        Query joins items with mappings valid at as_of timestamp,
        then joins with price items. Report is deterministic and
        reproducible for same timestamp.

        Args:
            org_id: Organization identifier
            project_id: Project identifier
            as_of: Report timestamp (default: now)

        Returns:
            pandas DataFrame with EU-formatted cost report

        Raises:
            SQLAlchemyError: If database query fails
        """
        if as_of is None:
            as_of = datetime.utcnow()

        # SCD2 as-of join query
        stmt = (
            select(
                ItemModel.id.label("item_id"),
                ItemModel.family,
                ItemModel.type_name,
                ItemModel.category,
                ItemModel.quantity,
                ItemModel.unit.label("item_unit"),
                ItemModel.canonical_key,
                ItemModel.source_file,  # ADDED: Revit source traceability
                PriceItemModel.sku,
                PriceItemModel.description,
                PriceItemModel.unit_price,
                PriceItemModel.unit.label("price_unit"),
                PriceItemModel.currency,
                PriceItemModel.vat_rate,
                ItemMappingModel.created_by.label("matched_by"),
                ItemMappingModel.reason.label("match_reason"),
            )
            .select_from(ItemModel)
            .outerjoin(
                ItemMappingModel,
                and_(
                    ItemModel.canonical_key == ItemMappingModel.canonical_key,
                    ItemMappingModel.org_id == org_id,
                    ItemMappingModel.start_ts <= as_of,
                    or_(
                        ItemMappingModel.end_ts.is_(None),
                        ItemMappingModel.end_ts > as_of,
                    ),
                ),
            )
            .outerjoin(
                PriceItemModel,
                ItemMappingModel.price_item_id == PriceItemModel.id,
            )
            .where(
                and_(
                    ItemModel.org_id == org_id,
                    ItemModel.project_id == project_id,
                )
            )
            .order_by(ItemModel.family, ItemModel.type_name)
        )

        result = await self.session.execute(stmt)
        rows = result.all()

        # Convert to list of dicts
        data = [
            {
                "item_id": str(row.item_id),
                "family": row.family,
                "type": row.type_name,
                "category": row.category,
                "quantity": float(row.quantity) if row.quantity else None,
                "unit": row.item_unit,
                "canonical_key": row.canonical_key,
                "source_file": row.source_file,  # ADDED: Revit source traceability
                "sku": row.sku,
                "description": row.description,
                "unit_price": float(row.unit_price) if row.unit_price else None,
                "currency": row.currency,
                "vat_rate": float(row.vat_rate) if row.vat_rate else None,
                "matched_by": row.matched_by,
                "match_reason": row.match_reason,
            }
            for row in rows
        ]

        # Create DataFrame
        df = pd.DataFrame(data)

        if df.empty:
            return df

        # Calculate totals
        df["total_net"] = df.apply(
            lambda x: (
                float(x["quantity"]) * float(x["unit_price"])
                if x["quantity"] and x["unit_price"]
                else None
            ),
            axis=1,
        )

        df["total_gross"] = df.apply(
            lambda x: (
                x["total_net"] * (1 + float(x["vat_rate"]))
                if x["total_net"] and x["vat_rate"]
                else x["total_net"]
            ),
            axis=1,
        )

        # Apply EU formatting
        df = self._format_eu(df)

        return df

    def _format_eu(self, df: pd.DataFrame) -> pd.DataFrame:
        """Apply EU locale formatting (EUR symbol, comma thousands, period decimal).

        Args:
            df: DataFrame to format

        Returns:
            Formatted DataFrame
        """
        eu_config = self.config.eu

        # Format currency columns
        for col in ["unit_price", "total_net", "total_gross"]:
            if col in df.columns:
                df[f"{col}_formatted"] = df[col].apply(
                    lambda x: self._format_currency(x, eu_config.currency)
                    if pd.notna(x)
                    else ""
                )

        # Format VAT rate as percentage
        if "vat_rate" in df.columns:
            df["vat_rate_formatted"] = df["vat_rate"].apply(
                lambda x: f"{x * 100:.0f}%" if pd.notna(x) else ""
            )

        return df

    def _format_currency(self, value: float, currency: str) -> str:
        """Format currency value with EU locale.

        Args:
            value: Numeric value
            currency: Currency code (default EUR)

        Returns:
            Formatted string (e.g., "€1.234,56")
        """
        # Format with thousands separator (.) and decimal separator (,)
        # Note: Using standard comma decimal for now (can be locale-specific)
        formatted = f"{value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

        # Add currency symbol
        if currency == "EUR":
            return f"€{formatted}"
        else:
            return f"{formatted} {currency}"


async def generate_report(
    session: AsyncSession,
    org_id: str,
    project_id: str,
    as_of: Optional[datetime] = None,
) -> pd.DataFrame:
    """Convenience function: generate cost report.

    Args:
        session: Database session
        org_id: Organization identifier
        project_id: Project identifier
        as_of: Report timestamp (default: now)

    Returns:
        pandas DataFrame with EU-formatted report
    """
    builder = ReportBuilder(session)
    return await builder.build(org_id, project_id, as_of)
