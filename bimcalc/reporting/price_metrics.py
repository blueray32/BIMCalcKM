"""Price data quality and coverage metrics for executive oversight.

Provides insights into pricebook health, coverage, staleness, and
financial exposure for stakeholder reporting.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import and_, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from bimcalc.db.models import ItemModel, PriceItemModel


@dataclass
class PriceMetrics:
    """Executive-level price data quality metrics."""

    # Overall inventory
    total_price_items: int
    current_price_items: int  # is_current=True
    historical_price_items: int

    # Currency & VAT
    currency: str
    currencies_found: list[str]
    vat_specified_count: int  # Items with vat_rate specified
    vat_unspecified_count: int  # Items without vat_rate

    # Price ranges
    min_unit_price: Optional[float]
    max_unit_price: Optional[float]
    avg_unit_price: Optional[float]
    median_unit_price: Optional[float]

    # Coverage by classification
    classifications_with_prices: int
    total_classifications: int
    classification_coverage_pct: float

    # Top classifications by count
    top_classifications: list[dict]  # [{code, count, avg_price, min_price, max_price}]

    # Staleness metrics
    oldest_price_days: Optional[int]
    avg_age_days: Optional[float]
    prices_updated_last_30_days: int
    prices_updated_last_90_days: int
    stale_prices_count: int  # >365 days old

    # Top expensive items
    top_10_expensive: list[dict]  # [{code, description, unit_price, vendor, updated}]

    # Vendor distribution
    unique_vendors: int
    top_vendors: list[dict]  # [{vendor, count, avg_price}]

    # Price quality score (0-100)
    quality_score: int
    quality_status: str  # "Excellent", "Good", "Fair", "Poor"

    # Computed timestamp
    computed_at: datetime


def _calculate_quality_score(
    current_pct: float,
    classification_coverage_pct: float,
    fresh_30_day_pct: float,
    stale_pct: float,
) -> int:
    """Calculate price data quality score (0-100).

    Weighted formula:
    - 30% Current items ratio (vs historical)
    - 25% Classification coverage
    - 25% Freshness (updated last 30 days)
    - 20% Non-staleness (not >365 days old)

    Penalties:
    - -15 points if >20% stale items
    - -10 points if classification coverage <70%
    """
    score = 0.0

    # Current items ratio (30 points)
    score += (current_pct / 100) * 30

    # Classification coverage (25 points)
    score += (classification_coverage_pct / 100) * 25

    # Freshness (25 points)
    score += (fresh_30_day_pct / 100) * 25

    # Non-staleness (20 points)
    non_stale_pct = 100 - stale_pct
    score += (non_stale_pct / 100) * 20

    # Penalties
    if stale_pct > 20:
        score -= 15
    if classification_coverage_pct < 70:
        score -= 10

    return max(0, min(100, int(score)))


async def compute_price_metrics(
    session: AsyncSession, org_id: str = "default"
) -> PriceMetrics:
    """Calculate executive price data quality metrics.

    Provides oversight on pricebook health, coverage, and staleness
    for stakeholder reporting and vendor management.

    Args:
        session: Database session
        org_id: Organization ID (prices are org-scoped, not project-scoped)

    Returns:
        Complete price quality metrics
    """

    now = datetime.now(timezone.utc)

    # ========================================================================
    # 1. Overall Inventory
    # ========================================================================

    total_query = select(func.count(PriceItemModel.id)).where(
        PriceItemModel.org_id == org_id
    )
    total_price_items = (await session.execute(total_query)).scalar_one()

    if total_price_items == 0:
        return _empty_metrics()

    current_query = select(func.count(PriceItemModel.id)).where(
        and_(
            PriceItemModel.org_id == org_id,
            PriceItemModel.is_current == True
        )
    )
    current_price_items = (await session.execute(current_query)).scalar_one()
    historical_price_items = total_price_items - current_price_items

    # ========================================================================
    # 2. Currency & VAT Distribution
    # ========================================================================

    currency_query = select(
        PriceItemModel.currency,
        func.count(PriceItemModel.id).label('count')
    ).where(
        and_(
            PriceItemModel.org_id == org_id,
            PriceItemModel.is_current == True
        )
    ).group_by(PriceItemModel.currency)

    currency_result = await session.execute(currency_query)
    currencies = currency_result.all()

    # Primary currency (most common)
    primary_currency = currencies[0][0] if currencies else "EUR"
    currencies_found = [c[0] for c in currencies]

    # VAT distribution
    vat_specified_query = select(func.count(PriceItemModel.id)).where(
        and_(
            PriceItemModel.org_id == org_id,
            PriceItemModel.is_current == True,
            PriceItemModel.vat_rate.isnot(None)
        )
    )
    vat_specified_count = (await session.execute(vat_specified_query)).scalar_one()
    vat_unspecified_count = current_price_items - vat_specified_count

    # ========================================================================
    # 3. Price Ranges (current items only)
    # ========================================================================

    stats_query = select(
        func.min(PriceItemModel.unit_price).label('min_price'),
        func.max(PriceItemModel.unit_price).label('max_price'),
        func.avg(PriceItemModel.unit_price).label('avg_price')
    ).where(
        and_(
            PriceItemModel.org_id == org_id,
            PriceItemModel.is_current == True
        )
    )
    stats = (await session.execute(stats_query)).one()

    min_unit_price = float(stats.min_price) if stats.min_price else None
    max_unit_price = float(stats.max_price) if stats.max_price else None
    avg_unit_price = float(stats.avg_price) if stats.avg_price else None

    # Median (approximate using percentile)
    median_query = text("""
        SELECT PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY unit_price)
        FROM price_items
        WHERE org_id = :org_id AND is_current = true
    """)
    median_result = await session.execute(median_query, {"org_id": org_id})
    median_unit_price = median_result.scalar()

    # ========================================================================
    # 4. Classification Coverage
    # ========================================================================

    # Count distinct classifications with prices
    class_with_prices_query = select(
        func.count(func.distinct(PriceItemModel.classification_code))
    ).where(
        and_(
            PriceItemModel.org_id == org_id,
            PriceItemModel.is_current == True,
            PriceItemModel.classification_code.isnot(None)
        )
    )
    classifications_with_prices = (await session.execute(class_with_prices_query)).scalar_one()

    # Total distinct classifications needed (from Items table)
    total_class_query = select(
        func.count(func.distinct(ItemModel.classification_code))
    ).where(
        and_(
            ItemModel.org_id == org_id,
            ItemModel.classification_code.isnot(None)
        )
    )
    total_classifications = (await session.execute(total_class_query)).scalar_one()

    # If no items exist, fallback to pricebook count
    if total_classifications == 0:
        total_classifications = classifications_with_prices

    classification_coverage_pct = (classifications_with_prices / total_classifications * 100) if total_classifications > 0 else 0.0

    # Top classifications by count
    top_class_query = select(
        PriceItemModel.classification_code,
        func.count(PriceItemModel.id).label('count'),
        func.avg(PriceItemModel.unit_price).label('avg_price'),
        func.min(PriceItemModel.unit_price).label('min_price'),
        func.max(PriceItemModel.unit_price).label('max_price')
    ).where(
        and_(
            PriceItemModel.org_id == org_id,
            PriceItemModel.is_current == True,
            PriceItemModel.classification_code.isnot(None)
        )
    ).group_by(
        PriceItemModel.classification_code
    ).order_by(
        func.count(PriceItemModel.id).desc()
    ).limit(10)

    top_class_result = await session.execute(top_class_query)
    top_classifications = [
        {
            "code": row.classification_code,
            "count": row.count,
            "avg_price": float(row.avg_price) if row.avg_price else 0,
            "min_price": float(row.min_price) if row.min_price else 0,
            "max_price": float(row.max_price) if row.max_price else 0,
        }
        for row in top_class_result.all()
    ]

    # ========================================================================
    # 5. Staleness Metrics
    # ========================================================================

    # Age calculations
    age_query = select(
        func.min(PriceItemModel.last_updated).label('oldest'),
        func.avg(
            func.extract('epoch', now - PriceItemModel.last_updated) / 86400
        ).label('avg_age_days')
    ).where(
        and_(
            PriceItemModel.org_id == org_id,
            PriceItemModel.is_current == True
        )
    )
    age_stats = (await session.execute(age_query)).one()

    oldest_price_days = None
    if age_stats.oldest:
        oldest_price_days = (now - age_stats.oldest).days

    avg_age_days = float(age_stats.avg_age_days) if age_stats.avg_age_days else None

    # Recent updates
    thirty_days_ago = now - timedelta(days=30)
    ninety_days_ago = now - timedelta(days=90)
    one_year_ago = now - timedelta(days=365)

    recent_30_query = select(func.count(PriceItemModel.id)).where(
        and_(
            PriceItemModel.org_id == org_id,
            PriceItemModel.is_current == True,
            PriceItemModel.last_updated >= thirty_days_ago
        )
    )
    prices_updated_last_30_days = (await session.execute(recent_30_query)).scalar_one()

    recent_90_query = select(func.count(PriceItemModel.id)).where(
        and_(
            PriceItemModel.org_id == org_id,
            PriceItemModel.is_current == True,
            PriceItemModel.last_updated >= ninety_days_ago
        )
    )
    prices_updated_last_90_days = (await session.execute(recent_90_query)).scalar_one()

    stale_query = select(func.count(PriceItemModel.id)).where(
        and_(
            PriceItemModel.org_id == org_id,
            PriceItemModel.is_current == True,
            PriceItemModel.last_updated < one_year_ago
        )
    )
    stale_prices_count = (await session.execute(stale_query)).scalar_one()

    # ========================================================================
    # 6. Top Expensive Items
    # ========================================================================

    expensive_query = select(
        PriceItemModel.item_code,
        PriceItemModel.description,
        PriceItemModel.unit_price,
        PriceItemModel.vendor_id,
        PriceItemModel.last_updated
    ).where(
        and_(
            PriceItemModel.org_id == org_id,
            PriceItemModel.is_current == True
        )
    ).order_by(
        PriceItemModel.unit_price.desc()
    ).limit(10)

    expensive_result = await session.execute(expensive_query)
    top_10_expensive = [
        {
            "code": row.item_code,
            "description": row.description[:100] if row.description else "N/A",
            "unit_price": float(row.unit_price),
            "vendor": row.vendor_id or "Unknown",
            "updated": row.last_updated.strftime("%Y-%m-%d") if row.last_updated else "N/A"
        }
        for row in expensive_result.all()
    ]

    # ========================================================================
    # 7. Vendor Distribution
    # ========================================================================

    vendor_count_query = select(
        func.count(func.distinct(PriceItemModel.vendor_id))
    ).where(
        and_(
            PriceItemModel.org_id == org_id,
            PriceItemModel.is_current == True,
            PriceItemModel.vendor_id.isnot(None)
        )
    )
    unique_vendors = (await session.execute(vendor_count_query)).scalar_one()

    top_vendors_query = select(
        PriceItemModel.vendor_id,
        func.count(PriceItemModel.id).label('count'),
        func.avg(PriceItemModel.unit_price).label('avg_price')
    ).where(
        and_(
            PriceItemModel.org_id == org_id,
            PriceItemModel.is_current == True,
            PriceItemModel.vendor_id.isnot(None)
        )
    ).group_by(
        PriceItemModel.vendor_id
    ).order_by(
        func.count(PriceItemModel.id).desc()
    ).limit(10)

    top_vendors_result = await session.execute(top_vendors_query)
    top_vendors = [
        {
            "vendor": row.vendor_id,
            "count": row.count,
            "avg_price": float(row.avg_price) if row.avg_price else 0
        }
        for row in top_vendors_result.all()
    ]

    # ========================================================================
    # 8. Quality Score
    # ========================================================================

    current_pct = (current_price_items / total_price_items * 100) if total_price_items > 0 else 0
    fresh_30_day_pct = (prices_updated_last_30_days / current_price_items * 100) if current_price_items > 0 else 0
    stale_pct = (stale_prices_count / current_price_items * 100) if current_price_items > 0 else 0

    quality_score = _calculate_quality_score(
        current_pct,
        classification_coverage_pct,
        fresh_30_day_pct,
        stale_pct
    )

    if quality_score >= 85:
        quality_status = "Excellent"
    elif quality_score >= 70:
        quality_status = "Good"
    elif quality_score >= 50:
        quality_status = "Fair"
    else:
        quality_status = "Poor"

    # ========================================================================
    # Return Complete Metrics
    # ========================================================================

    return PriceMetrics(
        total_price_items=total_price_items,
        current_price_items=current_price_items,
        historical_price_items=historical_price_items,
        currency=primary_currency,
        currencies_found=currencies_found,
        vat_specified_count=vat_specified_count,
        vat_unspecified_count=vat_unspecified_count,
        min_unit_price=min_unit_price,
        max_unit_price=max_unit_price,
        avg_unit_price=avg_unit_price,
        median_unit_price=float(median_unit_price) if median_unit_price else None,
        classifications_with_prices=classifications_with_prices,
        total_classifications=total_classifications,
        classification_coverage_pct=classification_coverage_pct,
        top_classifications=top_classifications,
        oldest_price_days=oldest_price_days,
        avg_age_days=avg_age_days,
        prices_updated_last_30_days=prices_updated_last_30_days,
        prices_updated_last_90_days=prices_updated_last_90_days,
        stale_prices_count=stale_prices_count,
        top_10_expensive=top_10_expensive,
        unique_vendors=unique_vendors,
        top_vendors=top_vendors,
        quality_score=quality_score,
        quality_status=quality_status,
        computed_at=now
    )


def _empty_metrics() -> PriceMetrics:
    """Return empty metrics for when no price data exists."""
    return PriceMetrics(
        total_price_items=0,
        current_price_items=0,
        historical_price_items=0,
        currency="EUR",
        currencies_found=[],
        vat_specified_count=0,
        vat_unspecified_count=0,
        min_unit_price=None,
        max_unit_price=None,
        avg_unit_price=None,
        median_unit_price=None,
        classifications_with_prices=0,
        total_classifications=0,
        classification_coverage_pct=0,
        top_classifications=[],
        oldest_price_days=None,
        avg_age_days=None,
        prices_updated_last_30_days=0,
        prices_updated_last_90_days=0,
        stale_prices_count=0,
        top_10_expensive=[],
        unique_vendors=0,
        top_vendors=[],
        quality_score=0,
        quality_status="No Data",
        computed_at=datetime.now(timezone.utc)
    )
