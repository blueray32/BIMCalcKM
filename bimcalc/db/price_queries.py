"""Common price query utilities with SCD Type-2 awareness.

This module provides helper functions for querying price data correctly
from the SCD Type-2 schema. All queries must respect the temporal validity
of price records.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID

from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from bimcalc.db.models import PriceItemModel
from bimcalc.models import PriceItem


async def get_current_price(
    session: AsyncSession,
    item_code: str,
    region: str = "UK",
) -> Optional[PriceItem]:
    """Get the current active price for an item.

    This is the most common query pattern for real-time cost calculations.

    Args:
        session: Database session
        item_code: Manufacturer part number or standardized code
        region: Geographic region (default: UK)

    Returns:
        PriceItem if found, None otherwise
    """
    stmt = select(PriceItemModel).where(
        and_(
            PriceItemModel.item_code == item_code,
            PriceItemModel.region == region,
            PriceItemModel.is_current == True,
        )
    )

    result = await session.execute(stmt)
    row = result.scalar_one_or_none()

    if row is None:
        return None

    return _row_to_price_item(row)


async def get_historical_price(
    session: AsyncSession,
    item_code: str,
    region: str,
    as_of: datetime,
) -> Optional[PriceItem]:
    """Get the price that was active at a specific point in time.

    This enables historical cost analysis and variance reporting.

    Args:
        session: Database session
        item_code: Manufacturer part number or standardized code
        region: Geographic region
        as_of: The timestamp to query prices for

    Returns:
        PriceItem if found at that time, None otherwise
    """
    stmt = select(PriceItemModel).where(
        and_(
            PriceItemModel.item_code == item_code,
            PriceItemModel.region == region,
            PriceItemModel.valid_from <= as_of,
            or_(
                PriceItemModel.valid_to.is_(None),
                PriceItemModel.valid_to > as_of,
            ),
        )
    )

    result = await session.execute(stmt)
    row = result.scalar_one_or_none()

    if row is None:
        return None

    return _row_to_price_item(row)


async def get_price_history(
    session: AsyncSession,
    item_code: str,
    region: str,
    limit: int = 10,
) -> list[PriceItem]:
    """Get price change history for an item.

    Returns all historical price records, ordered by most recent first.

    Args:
        session: Database session
        item_code: Manufacturer part number or standardized code
        region: Geographic region
        limit: Max number of historical records to return

    Returns:
        List of PriceItem records (most recent first)
    """
    stmt = (
        select(PriceItemModel)
        .where(
            and_(
                PriceItemModel.item_code == item_code,
                PriceItemModel.region == region,
            )
        )
        .order_by(PriceItemModel.valid_from.desc())
        .limit(limit)
    )

    result = await session.execute(stmt)
    rows = result.scalars().all()

    return [_row_to_price_item(row) for row in rows]


async def get_price_by_id(
    session: AsyncSession,
    price_item_id: UUID,
) -> Optional[PriceItem]:
    """Get a specific price record by its UUID.

    This is used by the mapping system to retrieve exact historical prices.
    Used in reports to show the exact price that was used in a mapping,
    even if that price is no longer current.

    Args:
        session: Database session
        price_item_id: UUID of the price record

    Returns:
        PriceItem if found, None otherwise
    """
    stmt = select(PriceItemModel).where(PriceItemModel.id == price_item_id)

    result = await session.execute(stmt)
    row = result.scalar_one_or_none()

    if row is None:
        return None

    return _row_to_price_item(row)


def _row_to_price_item(row: PriceItemModel) -> PriceItem:
    """Convert database row to Pydantic model.

    Args:
        row: SQLAlchemy model instance

    Returns:
        Pydantic PriceItem
    """
    return PriceItem(
        id=row.id,
        classification_code=row.classification_code,
        vendor_id=row.vendor_id,
        sku=row.sku,
        description=row.description,
        unit=row.unit,
        unit_price=row.unit_price,
        currency=row.currency,
        vat_rate=row.vat_rate,
        width_mm=row.width_mm,
        height_mm=row.height_mm,
        dn_mm=row.dn_mm,
        angle_deg=row.angle_deg,
        material=row.material,
        last_updated=row.last_updated,
        vendor_note=row.vendor_note,
        attributes=row.attributes or {},
    )
