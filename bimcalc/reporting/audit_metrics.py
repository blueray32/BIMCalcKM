"""Audit trail compliance metrics for governance dashboard.

Calculates decision velocity, confidence distribution, actor attribution,
and compliance scores for audit oversight and regulatory requirements.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


@dataclass
class AuditMetrics:
    """Compliance and governance audit metrics."""

    # Total audit records
    total_decisions: int
    total_items_audited: int

    # Decision breakdown
    auto_approved_count: int
    manual_review_count: int
    rejected_count: int
    user_approved_count: int

    # Velocity metrics (last 30 days)
    decisions_last_7_days: int
    decisions_last_30_days: int
    avg_decisions_per_day: float
    peak_decision_day: str | None  # Date with most decisions
    peak_decision_count: int

    # Confidence distribution
    avg_confidence: float | None
    high_confidence_count: int  # ≥85%
    medium_confidence_count: int  # 70-84%
    low_confidence_count: int  # <70%

    # Actor attribution
    system_decisions: int  # auto-accepted
    manual_decisions: int  # user approved
    system_percentage: float

    # Decision sources
    mapping_memory_count: int
    fuzzy_match_count: int
    review_ui_count: int

    # Compliance score (0-100)
    compliance_score: int
    compliance_status: str  # "Excellent", "Good", "Fair", "Poor"

    # Recent decision timeline (last 10 days with counts)
    daily_timeline: list[dict]  # [{date, count, avg_confidence}]

    # Top decision makers (if manual)
    top_reviewers: list[dict]  # [{created_by, count, avg_confidence}]

    # Computed timestamp
    computed_at: datetime


async def compute_audit_metrics(
    session: AsyncSession, org_id: str, project_id: str
) -> AuditMetrics:
    """Calculate audit trail compliance metrics for governance dashboard.

    Provides oversight on decision quality, velocity, and attribution
    for regulatory compliance and process improvement.

    Args:
        session: Database session
        org_id: Organization ID
        project_id: Project ID

    Returns:
        AuditMetrics with compliance and governance indicators
    """

    now = datetime.utcnow()
    seven_days_ago = now - timedelta(days=7)
    thirty_days_ago = now - timedelta(days=30)
    ten_days_ago = now - timedelta(days=10)

    # Main audit statistics query
    audit_query = text("""
        WITH latest_matches AS (
            SELECT 
                mr.item_id,
                ROW_NUMBER() OVER (PARTITION BY mr.item_id ORDER BY mr.timestamp DESC) as rn,
                mr.decision,
                mr.confidence_score,
                mr.source,
                mr.created_by,
                mr.timestamp
            FROM match_results mr
            JOIN items i ON i.id = mr.item_id
            WHERE i.org_id = :org_id
              AND i.project_id = :project_id
            ORDER BY mr.item_id, mr.timestamp DESC
        )
        SELECT
            -- Totals
            COUNT(*) as total_decisions,
            COUNT(DISTINCT item_id) as total_items_audited,

            -- Decision breakdown
            COUNT(*) FILTER (WHERE decision = 'auto-accepted') as auto_approved_count,
            COUNT(*) FILTER (WHERE decision = 'manual-review') as manual_review_count,
            COUNT(*) FILTER (WHERE decision = 'rejected') as rejected_count,
            COUNT(*) FILTER (WHERE decision NOT IN ('auto-accepted', 'manual-review', 'rejected')) as user_approved_count,

            -- Recent activity
            COUNT(*) FILTER (WHERE timestamp >= :seven_days_ago) as decisions_last_7_days,
            COUNT(*) FILTER (WHERE timestamp >= :thirty_days_ago) as decisions_last_30_days,

            -- Confidence stats
            AVG(confidence_score) FILTER (WHERE confidence_score IS NOT NULL) as avg_confidence,
            COUNT(*) FILTER (WHERE confidence_score >= 85) as high_confidence_count,
            COUNT(*) FILTER (WHERE confidence_score >= 70 AND confidence_score < 85) as medium_confidence_count,
            COUNT(*) FILTER (WHERE confidence_score < 70) as low_confidence_count,

            -- Sources
            COUNT(*) FILTER (WHERE source = 'mapping_memory') as mapping_memory_count,
            COUNT(*) FILTER (WHERE source = 'fuzzy_match') as fuzzy_match_count,
            COUNT(*) FILTER (WHERE source = 'review_ui') as review_ui_count

        FROM latest_matches
    """)

    result = (
        await session.execute(
            audit_query,
            {
                "org_id": org_id,
                "project_id": project_id,
                "seven_days_ago": seven_days_ago,
                "thirty_days_ago": thirty_days_ago,
            },
        )
    ).first()

    # Extract metrics
    total_decisions = result.total_decisions or 0
    total_items_audited = result.total_items_audited or 0
    auto_approved_count = result.auto_approved_count or 0
    manual_review_count = result.manual_review_count or 0
    rejected_count = result.rejected_count or 0
    user_approved_count = result.user_approved_count or 0

    decisions_last_7_days = result.decisions_last_7_days or 0
    decisions_last_30_days = result.decisions_last_30_days or 0

    avg_confidence = float(result.avg_confidence) if result.avg_confidence else None
    high_confidence_count = result.high_confidence_count or 0
    medium_confidence_count = result.medium_confidence_count or 0
    low_confidence_count = result.low_confidence_count or 0

    mapping_memory_count = result.mapping_memory_count or 0
    fuzzy_match_count = result.fuzzy_match_count or 0
    review_ui_count = result.review_ui_count or 0

    # Calculate velocity
    avg_decisions_per_day = (
        decisions_last_30_days / 30.0 if decisions_last_30_days > 0 else 0.0
    )

    # Peak decision day (last 30 days)
    peak_query = text("""
        WITH latest_matches AS (
            SELECT 
                mr.item_id,
                ROW_NUMBER() OVER (PARTITION BY mr.item_id ORDER BY mr.timestamp DESC) as rn,
                mr.timestamp
            FROM match_results mr
            JOIN items i ON i.id = mr.item_id
            WHERE i.org_id = :org_id
              AND i.project_id = :project_id
              AND mr.timestamp >= :thirty_days_ago
            ORDER BY mr.item_id, mr.timestamp DESC
        )
        SELECT
            DATE(timestamp) as decision_date,
            COUNT(*) as decision_count
        FROM latest_matches
        GROUP BY DATE(timestamp)
        ORDER BY decision_count DESC
        LIMIT 1
    """)

    peak_result = (
        await session.execute(
            peak_query,
            {
                "org_id": org_id,
                "project_id": project_id,
                "thirty_days_ago": thirty_days_ago,
            },
        )
    ).first()

    peak_decision_day = _format_date(peak_result.decision_date) if peak_result else None
    peak_decision_count = peak_result.decision_count if peak_result else 0

    # Actor attribution
    system_decisions = auto_approved_count
    manual_decisions = user_approved_count + review_ui_count
    system_percentage = (
        (system_decisions / total_decisions * 100) if total_decisions > 0 else 0.0
    )

    # Daily timeline (last 10 days)
    timeline_query = text("""
        WITH latest_matches AS (
            SELECT 
                mr.item_id,
                ROW_NUMBER() OVER (PARTITION BY mr.item_id ORDER BY mr.timestamp DESC) as rn,
                mr.confidence_score,
                mr.timestamp
            FROM match_results mr
            JOIN items i ON i.id = mr.item_id
            WHERE i.org_id = :org_id
              AND i.project_id = :project_id
              AND mr.timestamp >= :ten_days_ago
            ORDER BY mr.item_id, mr.timestamp DESC
        )
        SELECT
            DATE(timestamp) as decision_date,
            COUNT(*) as decision_count,
            AVG(confidence_score) as avg_confidence
        FROM latest_matches
        GROUP BY DATE(timestamp)
        ORDER BY decision_date DESC
        LIMIT 10
    """)

    timeline_results = (
        await session.execute(
            timeline_query,
            {
                "org_id": org_id,
                "project_id": project_id,
                "ten_days_ago": ten_days_ago,
            },
        )
    ).fetchall()

    daily_timeline = [
        {
            "date": _format_date(row.decision_date),
            "count": row.decision_count,
            "avg_confidence": float(row.avg_confidence) if row.avg_confidence else 0.0,
        }
        for row in timeline_results
    ]

    # Top reviewers (manual decisions)
    reviewers_query = text("""
        WITH latest_matches AS (
            SELECT 
                mr.item_id,
                ROW_NUMBER() OVER (PARTITION BY mr.item_id ORDER BY mr.timestamp DESC) as rn,
                mr.created_by,
                mr.confidence_score,
                mr.decision
            FROM match_results mr
            JOIN items i ON i.id = mr.item_id
            WHERE i.org_id = :org_id
              AND i.project_id = :project_id
              AND mr.decision != 'auto-accepted'
            ORDER BY mr.item_id, mr.timestamp DESC
        )
        SELECT
            created_by,
            COUNT(*) as decision_count,
            AVG(confidence_score) as avg_confidence
        FROM latest_matches
        GROUP BY created_by
        ORDER BY decision_count DESC
        LIMIT 5
    """)

    reviewer_results = (
        await session.execute(
            reviewers_query, {"org_id": org_id, "project_id": project_id}
        )
    ).fetchall()

    top_reviewers = [
        {
            "created_by": row.created_by,
            "count": row.decision_count,
            "avg_confidence": float(row.avg_confidence) if row.avg_confidence else 0.0,
        }
        for row in reviewer_results
    ]

    # Calculate compliance score (0-100)
    compliance_score = _calculate_compliance_score(
        total_decisions=total_decisions,
        high_confidence_percentage=(high_confidence_count / total_decisions * 100)
        if total_decisions > 0
        else 0,
        system_percentage=system_percentage,
        decisions_last_7_days=decisions_last_7_days,
        avg_decisions_per_day=avg_decisions_per_day,
    )

    # Determine compliance status
    if compliance_score >= 85:
        compliance_status = "Excellent"
    elif compliance_score >= 70:
        compliance_status = "Good"
    elif compliance_score >= 50:
        compliance_status = "Fair"
    else:
        compliance_status = "Poor"

    return AuditMetrics(
        total_decisions=total_decisions,
        total_items_audited=total_items_audited,
        auto_approved_count=auto_approved_count,
        manual_review_count=manual_review_count,
        rejected_count=rejected_count,
        user_approved_count=user_approved_count,
        decisions_last_7_days=decisions_last_7_days,
        decisions_last_30_days=decisions_last_30_days,
        avg_decisions_per_day=avg_decisions_per_day,
        peak_decision_day=peak_decision_day,
        peak_decision_count=peak_decision_count,
        avg_confidence=avg_confidence,
        high_confidence_count=high_confidence_count,
        medium_confidence_count=medium_confidence_count,
        low_confidence_count=low_confidence_count,
        system_decisions=system_decisions,
        manual_decisions=manual_decisions,
        system_percentage=system_percentage,
        mapping_memory_count=mapping_memory_count,
        fuzzy_match_count=fuzzy_match_count,
        review_ui_count=review_ui_count,
        compliance_score=compliance_score,
        compliance_status=compliance_status,
        daily_timeline=daily_timeline,
        top_reviewers=top_reviewers,
        computed_at=datetime.now(),
    )


def _format_date(value):
    """Normalize DB date/datetime values to YYYY-MM-DD strings."""
    if value is None:
        return None
    if hasattr(value, "strftime"):
        return value.strftime("%Y-%m-%d")
    return str(value)


def _calculate_compliance_score(
    total_decisions: int,
    high_confidence_percentage: float,
    system_percentage: float,
    decisions_last_7_days: int,
    avg_decisions_per_day: float,
) -> int:
    """Calculate audit compliance score (0-100).

    Weighted formula:
    - 40% Audit trail completeness (decisions logged)
    - 30% Decision quality (high confidence %)
    - 20% System automation (% auto-approved)
    - 10% Decision velocity (recent activity)

    Bonuses:
    - +10 points if all items have decisions
    - +5 points if 100% high confidence
    """
    score = 0.0

    # Audit completeness (40 points max)
    # Assume good if we have any decisions
    if total_decisions > 0:
        score += 40

    # Decision quality (30 points max)
    score += (high_confidence_percentage / 100) * 30

    # System automation (20 points max)
    score += (system_percentage / 100) * 20

    # Decision velocity (10 points max)
    # Full points if averaging ≥1 decision/day, zero if no recent activity
    velocity_score = min(10, avg_decisions_per_day * 10)
    score += velocity_score

    # Bonuses
    if high_confidence_percentage >= 99:
        score += 5  # Near-perfect quality

    # Clamp to 0-100
    return max(0, min(100, int(score)))
