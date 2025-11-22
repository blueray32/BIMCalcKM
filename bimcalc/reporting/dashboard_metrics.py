"""Executive dashboard metrics aggregating project health indicators.

Combines financial, review, matching, and activity metrics into a unified
command center view for stakeholders and budget holders.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy import and_, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from bimcalc.db.models import ItemModel, MatchResultModel, PriceItemModel


CLASSIFICATION_NAMES = {
    "62": "Small Power",
    "63": "Earthing & Bonding",
    "64": "Lighting",
    "66": "Containment",
    "67": "Emergency Lighting",
    "68": "Fire Detection",
}


@dataclass
class DashboardMetrics:
    """Unified executive dashboard metrics."""

    # Financial Overview
    total_cost_net: float
    total_cost_gross: float
    high_risk_cost: float  # Low confidence items
    currency: str

    # Review Queue Status
    total_pending_review: int
    high_urgency_count: int  # Critical flags
    advisory_count: int

    # Match Progress
    total_items: int
    matched_items: int
    match_percentage: float
    auto_approved_count: int
    auto_approval_rate: float

    # Quality Metrics
    avg_confidence: Optional[float]
    high_confidence_percentage: float  # >= 85%

    # Recent Activity (last 7 days)
    recent_matches: int
    recent_approvals: int
    recent_ingestions: int

    # Classification distribution
    classification_distribution: list[dict]

    # Health Score (0-100)
    health_score: int
    health_status: str  # "Excellent", "Good", "Fair", "Poor"

    # Computed timestamp
    computed_at: datetime


async def compute_dashboard_metrics(
    session: AsyncSession, org_id: str, project_id: str
) -> DashboardMetrics:
    """Calculate unified executive dashboard metrics.

    Aggregates financial, review, matching, and activity data into a single
    high-level overview for stakeholders.

    Args:
        session: Database session
        org_id: Organization ID
        project_id: Project ID

    Returns:
        DashboardMetrics with comprehensive project health indicators
    """

    # Main overview query
    overview_query = text("""
        WITH latest_matches AS (
            SELECT 
                mr.item_id,
                ROW_NUMBER() OVER (PARTITION BY mr.item_id ORDER BY mr.timestamp DESC) as rn,
                mr.decision,
                mr.confidence_score,
                mr.timestamp,
                mr.price_item_id
            FROM match_results mr
            JOIN items i ON i.id = mr.item_id
            WHERE i.org_id = :org_id
              AND i.project_id = :project_id
            ORDER BY mr.item_id, mr.timestamp DESC
        ),
        active_mappings AS (
            SELECT canonical_key, price_item_id
            FROM item_mapping
            WHERE org_id = :org_id
              AND end_ts IS NULL
        ),
        item_costs AS (
            SELECT
                i.id,
                i.quantity,
                lm.decision,
                lm.confidence_score,
                pi.unit_price,
                pi.currency,
                pi.vat_rate,
                CASE
                    WHEN lm.decision IN ('auto-accepted', 'manual-review', 'accepted', 'pending-review')
                         AND pi.unit_price IS NOT NULL
                    THEN i.quantity * pi.unit_price
                    ELSE 0
                END as cost_net,
                CASE
                    WHEN lm.decision IN ('auto-accepted', 'manual-review', 'accepted', 'pending-review')
                         AND pi.unit_price IS NOT NULL
                    THEN i.quantity * pi.unit_price * (1 + COALESCE(pi.vat_rate, 0))
                    ELSE 0
                END as cost_gross
            FROM items i
            LEFT JOIN latest_matches lm ON lm.item_id = i.id
            LEFT JOIN active_mappings am ON am.canonical_key = i.canonical_key
            LEFT JOIN price_items pi ON pi.id = am.price_item_id
            WHERE i.org_id = :org_id
              AND i.project_id = :project_id
        )
        SELECT
            -- Financial
            COALESCE(SUM(cost_net), 0) as total_cost_net,
            COALESCE(SUM(cost_gross), 0) as total_cost_gross,
            COALESCE(SUM(cost_net) FILTER (WHERE confidence_score < 85), 0) as high_risk_cost,
            COALESCE(MAX(currency), 'EUR') as currency,

            -- Items & Matching
            COUNT(*) as total_items,
            COUNT(*) FILTER (WHERE decision IN ('auto-accepted', 'manual-review', 'accepted', 'pending-review')) as matched_items,
            COUNT(*) FILTER (WHERE decision = 'auto-accepted') as auto_approved_count,

            -- Review Queue (Note: flags not stored in DB, counts estimated from confidence)
            COUNT(*) FILTER (WHERE decision = 'manual-review' OR decision = 'pending-review') as pending_review,
            COUNT(*) FILTER (
                WHERE (decision = 'manual-review' OR decision = 'pending-review')
                  AND confidence_score < 70
            ) as high_urgency_count,
            COUNT(*) FILTER (
                WHERE (decision = 'manual-review' OR decision = 'pending-review')
                  AND confidence_score >= 70 AND confidence_score < 85
            ) as advisory_count,

            -- Quality
            AVG(confidence_score) FILTER (WHERE confidence_score IS NOT NULL) as avg_confidence,
            COUNT(*) FILTER (WHERE confidence_score >= 85) as high_confidence_count
        FROM item_costs
    """)

    result = (await session.execute(
        overview_query, {"org_id": org_id, "project_id": project_id}
    )).first()

    # Extract metrics
    total_cost_net = float(result.total_cost_net) if result.total_cost_net else 0.0
    total_cost_gross = float(result.total_cost_gross) if result.total_cost_gross else 0.0
    high_risk_cost = float(result.high_risk_cost) if result.high_risk_cost else 0.0
    currency = result.currency or 'EUR'

    total_items = result.total_items or 0
    matched_items = result.matched_items or 0
    auto_approved_count = result.auto_approved_count or 0

    pending_review = result.pending_review or 0
    high_urgency_count = result.high_urgency_count or 0
    advisory_count = result.advisory_count or 0

    avg_confidence = float(result.avg_confidence) if result.avg_confidence else None
    high_confidence_count = result.high_confidence_count or 0

    # Calculate percentages
    match_percentage = (matched_items / total_items * 100) if total_items > 0 else 0.0
    auto_approval_rate = (auto_approved_count / matched_items * 100) if matched_items > 0 else 0.0
    high_confidence_percentage = (high_confidence_count / total_items * 100) if total_items > 0 else 0.0

    # Recent activity (last 7 days)
    seven_days_ago = datetime.now() - timedelta(days=7)

    recent_activity_query = text("""
        WITH latest_matches AS (
            SELECT 
                mr.item_id,
                ROW_NUMBER() OVER (PARTITION BY mr.item_id ORDER BY mr.timestamp DESC) as rn,
                mr.decision,
                mr.timestamp
            FROM match_results mr
            JOIN items i ON i.id = mr.item_id
            WHERE i.org_id = :org_id
              AND i.project_id = :project_id
            ORDER BY mr.item_id, mr.timestamp DESC
        )
        SELECT
            COUNT(*) FILTER (WHERE timestamp >= :since) as recent_matches,
            COUNT(*) FILTER (
                WHERE timestamp >= :since
                  AND decision IN ('accepted', 'auto-accepted')
            ) as recent_approvals
        FROM latest_matches
    """)

    activity_result = (await session.execute(
        recent_activity_query,
        {"org_id": org_id, "project_id": project_id, "since": seven_days_ago}
    )).first()

    recent_matches = activity_result.recent_matches or 0
    recent_approvals = activity_result.recent_approvals or 0

    # Recent ingestions (items created in last 7 days)
    ingestion_query = select(func.count(ItemModel.id)).where(
        and_(
            ItemModel.org_id == org_id,
            ItemModel.project_id == project_id,
            ItemModel.created_at >= seven_days_ago
        )
    )
    recent_ingestions = (await session.execute(ingestion_query)).scalar() or 0

    # Classification distribution (top categories by spend)
    classification_query = text("""
        WITH ranked_results AS (
            SELECT 
                mr.item_id,
                ROW_NUMBER() OVER (PARTITION BY mr.item_id ORDER BY mr.timestamp DESC) as rn,
                mr.decision,
                mr.confidence_score,
                mr.price_item_id
            FROM match_results mr
            JOIN items i ON i.id = mr.item_id
            WHERE i.org_id = :org_id
              AND i.project_id = :project_id
        ),
        latest_results AS (
            SELECT * FROM ranked_results WHERE rn = 1
        ),
        classification_costs AS (
            SELECT
                i.classification_code,
                lr.decision,
                lr.confidence_score,
                i.quantity,
                pi.unit_price,
                CASE
                    WHEN lr.decision IN ('auto-accepted', 'manual-review', 'accepted', 'pending-review')
                         AND pi.unit_price IS NOT NULL
                    THEN i.quantity * pi.unit_price
                    ELSE 0
                END as cost_net
            FROM items i
            LEFT JOIN latest_results lr ON lr.item_id = i.id
            LEFT JOIN price_items pi ON pi.id = lr.price_item_id
            WHERE i.org_id = :org_id
              AND i.project_id = :project_id
              AND i.classification_code IS NOT NULL
        )
        SELECT
            classification_code,
            COUNT(*) as total_items,
            COUNT(*) FILTER (
                WHERE decision IN ('auto-accepted', 'manual-review', 'accepted', 'pending-review')
            ) as matched_items,
            COALESCE(SUM(cost_net), 0) as matched_cost,
            AVG(confidence_score) as avg_confidence
        FROM classification_costs
        GROUP BY classification_code
        ORDER BY matched_cost DESC, total_items DESC
        LIMIT 6
    """)

    class_rows = (await session.execute(
        classification_query, {"org_id": org_id, "project_id": project_id}
    )).fetchall()

    classification_distribution: list[dict] = []
    for row in class_rows:
        code = str(row.classification_code) if row.classification_code else "Unclassified"
        matched_cost = float(row.matched_cost) if row.matched_cost else 0.0
        avg_conf = float(row.avg_confidence) if row.avg_confidence else None
        classification_distribution.append({
            "code": code,
            "name": CLASSIFICATION_NAMES.get(code, f"Class {code}"),
            "items": row.total_items or 0,
            "matched": row.matched_items or 0,
            "matched_cost": matched_cost,
            "cost_share": (matched_cost / total_cost_net * 100) if total_cost_net > 0 else 0.0,
            "avg_confidence": avg_conf,
        })

    # Calculate health score (0-100)
    health_score = _calculate_health_score(
        match_percentage=match_percentage,
        high_confidence_percentage=high_confidence_percentage,
        auto_approval_rate=auto_approval_rate,
        pending_review=pending_review,
        total_items=total_items,
        high_urgency_count=high_urgency_count,
    )

    # Determine health status
    if health_score >= 85:
        health_status = "Excellent"
    elif health_score >= 70:
        health_status = "Good"
    elif health_score >= 50:
        health_status = "Fair"
    else:
        health_status = "Poor"

    return DashboardMetrics(
        total_cost_net=total_cost_net,
        total_cost_gross=total_cost_gross,
        high_risk_cost=high_risk_cost,
        currency=currency,
        total_pending_review=pending_review,
        high_urgency_count=high_urgency_count,
        advisory_count=advisory_count,
        total_items=total_items,
        matched_items=matched_items,
        match_percentage=match_percentage,
        auto_approved_count=auto_approved_count,
        auto_approval_rate=auto_approval_rate,
        avg_confidence=avg_confidence,
        high_confidence_percentage=high_confidence_percentage,
        recent_matches=recent_matches,
        recent_approvals=recent_approvals,
        recent_ingestions=recent_ingestions,
        classification_distribution=classification_distribution,
        health_score=health_score,
        health_status=health_status,
        computed_at=datetime.now(),
    )


def _calculate_health_score(
    match_percentage: float,
    high_confidence_percentage: float,
    auto_approval_rate: float,
    pending_review: int,
    total_items: int,
    high_urgency_count: int,
) -> int:
    """Calculate overall project health score (0-100).

    Weighted formula:
    - 40% Match coverage
    - 30% High confidence percentage
    - 20% Auto-approval rate
    - 10% Review queue status (penalty for backlog)

    Critical penalties:
    - -20 points if high urgency items > 10% of total
    - -10 points if pending review > 25% of total
    """
    score = 0.0

    # Match coverage (40 points max)
    score += (match_percentage / 100) * 40

    # High confidence quality (30 points max)
    score += (high_confidence_percentage / 100) * 30

    # Auto-approval efficiency (20 points max)
    score += (auto_approval_rate / 100) * 20

    # Review queue health (10 points max)
    if total_items > 0:
        pending_ratio = pending_review / total_items
        # Full points if <5% pending, zero points if >50% pending
        review_score = max(0, 10 - (pending_ratio * 20))
        score += review_score

    # Apply penalties
    if total_items > 0:
        if high_urgency_count / total_items > 0.10:
            score -= 20  # Too many critical issues
        if pending_review / total_items > 0.25:
            score -= 10  # Review backlog

    # Clamp to 0-100
    return max(0, min(100, int(score)))
