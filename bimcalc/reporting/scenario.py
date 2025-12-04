from __future__ import annotations

from dataclasses import dataclass
from typing import List
from sqlalchemy import select, func, text
from sqlalchemy.ext.asyncio import AsyncSession

from bimcalc.db.models import PriceItemModel, ItemModel


@dataclass
class VendorScenario:
    vendor_name: str
    total_cost: float
    coverage_percent: float
    matched_items: int
    total_items: int
    missing_items: int


async def get_available_vendors(session: AsyncSession, org_id: str) -> List[str]:
    """Get list of available vendors (sources) from price items."""
    query = (
        select(PriceItemModel.source_name)
        .where(PriceItemModel.org_id == org_id, PriceItemModel.is_current == True)
        .distinct()
    )
    result = await session.execute(query)
    return [row[0] for row in result.all()]


async def compute_vendor_scenario(
    session: AsyncSession, org_id: str, project_id: str, vendor_name: str
) -> VendorScenario:
    """Calculate theoretical project cost if all items were sourced from a specific vendor.

    Matches items to the vendor's price book using classification_code.
    """

    # Get total items count for the project
    count_query = (
        select(func.count())
        .select_from(ItemModel)
        .where(ItemModel.org_id == org_id, ItemModel.project_id == project_id)
    )
    total_items = (await session.execute(count_query)).scalar_one()

    if total_items == 0:
        return VendorScenario(vendor_name, 0.0, 0.0, 0, 0, 0)

    # Calculate cost where match exists
    # We join Items -> PriceItems on classification_code AND source_name
    # Note: This assumes 1:1 mapping by classification code for simplicity in this scenario.
    # In reality, multiple items might match the same code, we take the average price or first found.
    # For a robust scenario, we'll take the average unit_price for that classification from that vendor.

    query = text("""
        WITH vendor_prices AS (
            SELECT 
                classification_code, 
                AVG(unit_price) as avg_price
            FROM price_items
            WHERE org_id = :org_id
              AND source_name = :vendor_name
              AND is_current = true
            GROUP BY classification_code
        )
        SELECT
            COUNT(i.id) as matched_count,
            SUM(i.quantity * vp.avg_price) as total_cost
        FROM items i
        JOIN vendor_prices vp ON vp.classification_code = i.classification_code
        WHERE i.org_id = :org_id
          AND i.project_id = :project_id
    """)

    result = (
        await session.execute(
            query,
            {"org_id": org_id, "project_id": project_id, "vendor_name": vendor_name},
        )
    ).first()

    matched_count = result.matched_count or 0
    total_cost = float(result.total_cost) if result.total_cost else 0.0

    coverage = (matched_count / total_items * 100) if total_items > 0 else 0.0

    return VendorScenario(
        vendor_name=vendor_name,
        total_cost=total_cost,
        coverage_percent=coverage,
        matched_items=matched_count,
        total_items=total_items,
        missing_items=total_items - matched_count,
    )
