"""Review UI business operations (approve/reject)."""

from __future__ import annotations

from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from bimcalc.db.match_results import record_match_result
from bimcalc.mapping.scd2 import MappingMemory
from bimcalc.models import Flag, MatchDecision, MatchResult
from bimcalc.review.models import ReviewRecord


async def approve_review_record(
    session: AsyncSession,
    record: ReviewRecord,
    created_by: str,
    annotation: Optional[str] = None,
) -> None:
    if record.price is None:
        raise ValueError("Cannot approve record without a price candidate")

    if not record.item.canonical_key:
        raise ValueError("Item is missing canonical key; run matching first")

    mapping = MappingMemory(session)
    await mapping.write(
        org_id=record.item.org_id,
        canonical_key=record.item.canonical_key,
        price_item_id=record.price.id,
        created_by=created_by,
        reason=annotation or "review-ui approval",
    )

    match_result = MatchResult(
        item_id=record.item.id,
        price_item_id=record.price.id,
        confidence_score=record.confidence_score,
        source="review_ui",
        flags=[
            Flag(type=flag.type, severity=flag.severity, message=flag.message)
            for flag in record.flags
        ],
        decision=MatchDecision.AUTO_ACCEPTED,
        reason=_build_reason(annotation, record),
        created_by=created_by,
    )

    await record_match_result(session, record.item.id, match_result)


def _build_reason(annotation: Optional[str], record: ReviewRecord) -> str:
    base = "Manual approval via review UI"
    if record.has_critical_flags:
        base += " (override)"
    if annotation:
        return f"{base}: {annotation.strip()}"
    return base
