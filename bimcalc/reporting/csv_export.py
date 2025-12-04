"""CSV export functionality for BIMCalc data.

Provides streaming CSV generation for:
- Project Items (with pricing)
- Price Book / Vendor Catalog
- Match Results
"""

from __future__ import annotations

import csv
from io import StringIO
from typing import TYPE_CHECKING, AsyncGenerator

from sqlalchemy import text

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


async def export_items_csv(
    session: AsyncSession, org_id: str, project_id: str, category: str | None = None
) -> AsyncGenerator[str, None]:
    """Generate CSV stream for project items with pricing.

    Yields:
        CSV rows as strings
    """
    # Define headers
    headers = [
        "Category",
        "Family",
        "Type",
        "Quantity",
        "Unit",
        "Unit Price",
        "Total Cost",
        "Labor Hours",
    ]

    # Create CSV writer buffer
    output = StringIO()
    writer = csv.writer(output)

    # Write header
    writer.writerow(headers)
    yield output.getvalue()
    output.seek(0)
    output.truncate(0)

    # Query items with pricing
    sql = """
        WITH latest_matches AS (
            SELECT 
                mr.item_id,
                mr.price_item_id,
                ROW_NUMBER() OVER (PARTITION BY mr.item_id ORDER BY mr.timestamp DESC) as rn
            FROM match_results mr
            JOIN items i ON i.id = mr.item_id
            WHERE i.org_id = :org_id
              AND i.project_id = :project_id
              AND mr.decision IN ('auto-accepted', 'accepted', 'pending-review')
        ),
        active_mappings AS (
            SELECT canonical_key, price_item_id
            FROM item_mapping
            WHERE org_id = :org_id AND end_ts IS NULL
        )
        SELECT
            i.category,
            i.family,
            i.type_name,
            i.quantity,
            pi.unit,
            pi.unit_price,
            pi.labor_hours
        FROM items i
        LEFT JOIN latest_matches lm ON lm.item_id = i.id AND lm.rn = 1
        LEFT JOIN active_mappings am ON am.canonical_key = i.canonical_key
        LEFT JOIN price_items pi ON pi.id = COALESCE(lm.price_item_id, am.price_item_id)
        WHERE i.org_id = :org_id
          AND i.project_id = :project_id
    """

    params = {"org_id": org_id, "project_id": project_id}

    if category:
        sql += " AND i.category = :category"
        params["category"] = category

    sql += " ORDER BY i.category, i.family, i.type_name"

    result = await session.stream(text(sql), params)

    async for row in result:
        # Calculate total cost
        quantity = float(row.quantity) if row.quantity else 0
        unit_price = float(row.unit_price) if row.unit_price else 0
        total_cost = quantity * unit_price if quantity and unit_price else 0

        data = [
            row.category or "Uncategorized",
            row.family,
            row.type_name,
            quantity,
            row.unit or "-",
            unit_price if row.unit_price else "-",
            total_cost if row.unit_price else "-",
            float(row.labor_hours) if row.labor_hours else "-",
        ]

        writer.writerow(data)
        yield output.getvalue()
        output.seek(0)
        output.truncate(0)


async def export_prices_csv(
    session: AsyncSession,
    org_id: str,
    category: str | None = None,
    vendor: str | None = None,
) -> AsyncGenerator[str, None]:
    """Generate CSV stream for price book items.

    Yields:
        CSV rows as strings
    """
    headers = [
        "Category",
        "Item Code",
        "Description",
        "Unit",
        "Unit Price",
        "Labor Hours",
        "Vendor",
    ]

    output = StringIO()
    writer = csv.writer(output)

    writer.writerow(headers)
    yield output.getvalue()
    output.seek(0)
    output.truncate(0)

    sql = """
        SELECT 
            classification_code as category,
            item_code,
            description,
            unit,
            unit_price,
            labor_hours,
            source_name
        FROM price_items
        WHERE org_id = :org_id
    """

    params = {"org_id": org_id}

    if category:
        sql += " AND classification_code = :category"
        params["category"] = category

    if vendor:
        sql += " AND source_name = :vendor"
        params["vendor"] = vendor

    sql += " ORDER BY classification_code, item_code"

    result = await session.stream(text(sql), params)

    async for row in result:
        data = [
            row.category,
            row.item_code,
            row.description,
            row.unit,
            float(row.unit_price) if row.unit_price else 0,
            float(row.labor_hours) if row.labor_hours else 0,
            row.source_name,
        ]

        writer.writerow(data)
        yield output.getvalue()
        output.seek(0)
        output.truncate(0)


async def export_matches_csv(
    session: AsyncSession,
    org_id: str,
    project_id: str,
    min_confidence: float | None = None,
    decision: str | None = None,
) -> AsyncGenerator[str, None]:
    """Generate CSV stream for match results.

    Yields:
        CSV rows as strings
    """
    headers = [
        "Item Family",
        "Item Type",
        "Matched Price Item",
        "Confidence",
        "Decision",
        "Timestamp",
    ]

    output = StringIO()
    writer = csv.writer(output)

    writer.writerow(headers)
    yield output.getvalue()
    output.seek(0)
    output.truncate(0)

    sql = """
        SELECT 
            i.family,
            i.type_name,
            pi.description as price_item_name,
            mr.confidence_score,
            mr.decision,
            mr.timestamp
        FROM match_results mr
        JOIN items i ON i.id = mr.item_id
        JOIN price_items pi ON pi.id = mr.price_item_id
        WHERE i.org_id = :org_id
          AND i.project_id = :project_id
    """

    params = {"org_id": org_id, "project_id": project_id}

    if min_confidence is not None:
        sql += " AND mr.confidence_score >= :min_confidence"
        params["min_confidence"] = min_confidence

    if decision:
        sql += " AND mr.decision = :decision"
        params["decision"] = decision

    sql += " ORDER BY mr.timestamp DESC"

    result = await session.stream(text(sql), params)

    async for row in result:
        data = [
            row.family,
            row.type_name,
            row.price_item_name,
            f"{float(row.confidence_score):.2f}" if row.confidence_score else "-",
            row.decision,
            str(row.timestamp) if row.timestamp else "-",
        ]

        writer.writerow(data)
        yield output.getvalue()
        output.seek(0)
        output.truncate(0)
