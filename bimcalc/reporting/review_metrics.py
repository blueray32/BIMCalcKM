"""Review queue executive metrics for stakeholder dashboards.

Calculates aggregated statistics for review workload, risk exposure,
and review velocity trends.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import text

from bimcalc.db.models import ItemModel, MatchFlagModel, MatchResultModel
from bimcalc.models import FlagSeverity


@dataclass
class ReviewMetrics:
    """Executive-level review queue statistics."""

    # Workload metrics
    total_pending: int
    high_urgency: int  # Critical flags
    medium_urgency: int  # Advisory flags or low confidence
    low_urgency: int  # Clean, just manual review

    # Risk exposure
    critical_flags_count: int
    advisory_flags_count: int
    critical_flag_types: dict[str, int]  # flag_type -> count
    advisory_flag_types: dict[str, int]

    # Confidence distribution (for pending reviews)
    confidence_high: int  # ≥85% but still needs review
    confidence_medium: int  # 70-84%
    confidence_low: int  # <70%

    # Classification breakdown
    classification_breakdown: list[dict]  # [{code, total, critical, advisory, avg_confidence}]

    # Aging metrics
    oldest_review_days: Optional[float]
    avg_age_days: Optional[float]
    items_over_7_days: int
    items_over_30_days: int

    # Computed timestamp
    computed_at: datetime


async def compute_review_metrics(
    session: AsyncSession, org_id: str, project_id: str
) -> ReviewMetrics:
    """Calculate executive review queue metrics.

    This provides stakeholders with a high-level view of:
    - Workload (how many items need review)
    - Risk (what types of flags are present)
    - Urgency (what needs attention first)
    - Aging (how long items have been waiting)

    Args:
        session: Database session
        org_id: Organization ID
        project_id: Project ID

    Returns:
        ReviewMetrics with aggregated statistics
    """
    # Query to get latest match results for items pending review
    # "Pending review" = decision = 'manual-review' or 'pending-review' in latest result
    pending_query = text("""
        WITH ranked_results AS (
            SELECT
                mr.item_id,
                mr.decision,
                mr.confidence_score,
                mr.timestamp,
                i.classification_code,
                ROW_NUMBER() OVER (PARTITION BY mr.item_id ORDER BY mr.timestamp DESC) as rn
            FROM match_results mr
            JOIN items i ON i.id = mr.item_id
            WHERE i.org_id = :org_id
              AND i.project_id = :project_id
        )
        SELECT
            rr.item_id,
            rr.decision,
            rr.confidence_score,
            rr.timestamp,
            rr.classification_code,
            (EXTRACT(EPOCH FROM (NOW() - rr.timestamp)) / 86400) as age_days
        FROM ranked_results rr
        WHERE rr.rn = 1
          AND rr.decision IN ('manual-review', 'pending-review')
    """)

    pending_results = (await session.execute(
        pending_query, {"org_id": org_id, "project_id": project_id}
    )).fetchall()

    total_pending = len(pending_results)

    # Calculate confidence distribution
    confidence_high = sum(1 for r in pending_results if (r.confidence_score or 0) >= 85)
    confidence_medium = sum(
        1 for r in pending_results if 70 <= (r.confidence_score or 0) < 85
    )
    confidence_low = sum(1 for r in pending_results if (r.confidence_score or 0) < 70)

    # Calculate aging metrics
    def _parse_timestamp(value):
        if value is None:
            return None
        if isinstance(value, datetime):
            if value.tzinfo:
                return value.astimezone(timezone.utc).replace(tzinfo=None)
            return value
        if isinstance(value, str):
            try:
                parsed = datetime.fromisoformat(value)
            except ValueError:
                return None
            if parsed.tzinfo:
                return parsed.astimezone(timezone.utc).replace(tzinfo=None)
            return parsed
        return None

    ages: list[float] = []
    if pending_results:
        now_dt = datetime.utcnow()
        for row in pending_results:
            ts = _parse_timestamp(row.timestamp)
            if ts is None:
                continue
            age = (now_dt - ts).total_seconds() / 86400.0
            if age < 0:
                age = 0.0
            ages.append(age)

    if ages:
        oldest_review_days = max(ages)
        avg_age_days = sum(ages) / len(ages)
        items_over_7_days = sum(1 for age in ages if age > 7)
        items_over_30_days = sum(1 for age in ages if age > 30)
    else:
        oldest_review_days = None
        avg_age_days = None
        items_over_7_days = 0
        items_over_30_days = 0

    # Get flag statistics for pending items
    pending_item_ids = [r.item_id for r in pending_results]

    if pending_item_ids:
        # Query flags for pending items
        flags_query = (
            select(
                MatchFlagModel.flag_type,
                MatchFlagModel.severity,
                func.count().label("count"),
            )
            .join(MatchResultModel, MatchResultModel.id == MatchFlagModel.match_result_id)
            .where(MatchResultModel.item_id.in_(pending_item_ids))
            .group_by(MatchFlagModel.flag_type, MatchFlagModel.severity)
        )

        flag_results = (await session.execute(flags_query)).fetchall()

        # Aggregate by severity
        critical_flags_count = 0
        advisory_flags_count = 0
        critical_flag_types: dict[str, int] = {}
        advisory_flag_types: dict[str, int] = {}

        for row in flag_results:
            if row.severity == FlagSeverity.CRITICAL_VETO.value:
                critical_flags_count += row.count
                critical_flag_types[row.flag_type] = (
                    critical_flag_types.get(row.flag_type, 0) + row.count
                )
            elif row.severity == FlagSeverity.ADVISORY.value:
                advisory_flags_count += row.count
                advisory_flag_types[row.flag_type] = (
                    advisory_flag_types.get(row.flag_type, 0) + row.count
                )

        # Calculate urgency breakdown
        # High urgency = has critical flags
        # Medium urgency = has advisory flags OR low confidence (<70%)
        # Low urgency = clean, just needs review

        items_with_critical = (
            await session.execute(
                select(func.count(func.distinct(MatchResultModel.item_id)))
                .join(
                    MatchFlagModel,
                    MatchFlagModel.match_result_id == MatchResultModel.id,
                )
                .where(
                    and_(
                        MatchResultModel.item_id.in_(pending_item_ids),
                        MatchFlagModel.severity == FlagSeverity.CRITICAL_VETO.value,
                    )
                )
            )
        ).scalar()

        items_with_advisory = (
            await session.execute(
                select(func.count(func.distinct(MatchResultModel.item_id)))
                .join(
                    MatchFlagModel,
                    MatchFlagModel.match_result_id == MatchResultModel.id,
                )
                .where(
                    and_(
                        MatchResultModel.item_id.in_(pending_item_ids),
                        MatchFlagModel.severity == FlagSeverity.ADVISORY.value,
                    )
                )
            )
        ).scalar()

        high_urgency = items_with_critical or 0
        medium_urgency = (items_with_advisory or 0) + confidence_low
        low_urgency = total_pending - high_urgency - medium_urgency

        # Classification breakdown
        class_breakdown_query = text("""
            WITH ranked_results AS (
                SELECT 
                    ROW_NUMBER() OVER (PARTITION BY mr.item_id ORDER BY mr.timestamp DESC) as rn,
                    mr.item_id,
                    mr.decision,
                    mr.confidence_score,
                    mr.id as match_result_id,
                    i.classification_code
                FROM match_results mr
                JOIN items i ON i.id = mr.item_id
                WHERE i.org_id = :org_id
                  AND i.project_id = :project_id
            ),
            latest_results AS (
                SELECT * FROM ranked_results
                WHERE rn = 1
            ),
            pending_items AS (
                SELECT * FROM latest_results
                WHERE decision IN ('manual-review', 'pending-review')
            )
            SELECT
                pi.classification_code,
                COUNT(*) as total,
                COUNT(*) FILTER (
                    WHERE EXISTS (
                        SELECT 1 FROM match_flags mf
                        WHERE mf.match_result_id = pi.match_result_id
                          AND mf.severity = 'Critical-Veto'
                    )
                ) as critical_count,
                COUNT(*) FILTER (
                    WHERE EXISTS (
                        SELECT 1 FROM match_flags mf
                        WHERE mf.match_result_id = pi.match_result_id
                          AND mf.severity = 'Advisory'
                    )
                ) as advisory_count,
                AVG(pi.confidence_score) as avg_confidence
            FROM pending_items pi
            GROUP BY pi.classification_code
            ORDER BY total DESC
            LIMIT 5
        """)

        class_results = (
            await session.execute(
                class_breakdown_query, {"org_id": org_id, "project_id": project_id}
            )
        ).fetchall()

        classification_breakdown = [
            {
                "code": row.classification_code,
                "total": row.total,
                "critical": row.critical_count,
                "advisory": row.advisory_count,
                "avg_confidence": float(row.avg_confidence) if row.avg_confidence else 0,
            }
            for row in class_results
        ]

    else:
        # No pending items
        critical_flags_count = 0
        advisory_flags_count = 0
        critical_flag_types = {}
        advisory_flag_types = {}
        high_urgency = 0
        medium_urgency = 0
        low_urgency = 0
        classification_breakdown = []

    return ReviewMetrics(
        total_pending=total_pending,
        high_urgency=high_urgency,
        medium_urgency=medium_urgency,
        low_urgency=low_urgency,
        critical_flags_count=critical_flags_count,
        advisory_flags_count=advisory_flags_count,
        critical_flag_types=critical_flag_types,
        advisory_flag_types=advisory_flag_types,
        confidence_high=confidence_high,
        confidence_medium=confidence_medium,
        confidence_low=confidence_low,
        classification_breakdown=classification_breakdown,
        oldest_review_days=oldest_review_days,
        avg_age_days=avg_age_days,
        items_over_7_days=items_over_7_days,
        items_over_30_days=items_over_30_days,
        computed_at=datetime.now(),
    )
