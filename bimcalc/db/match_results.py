"""Helpers for persisting match results and flags."""

from __future__ import annotations

from collections.abc import Iterable
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from bimcalc.db.models import MatchFlagModel, MatchResultModel
from bimcalc.models import Flag, MatchResult


def _enum_value(value):
    return value.value if hasattr(value, "value") else value


async def record_match_result(
    session: AsyncSession,
    item_id: UUID,
    match_result: MatchResult,
) -> MatchResultModel:
    """Persist match result + associated flags in a single transaction."""

    db_result = MatchResultModel(
        item_id=item_id,
        price_item_id=match_result.price_item_id,
        confidence_score=match_result.confidence_score,
        source=_enum_value(match_result.source),
        decision=_enum_value(match_result.decision),
        reason=match_result.reason,
        created_by=match_result.created_by,
        timestamp=match_result.timestamp,
    )

    session.add(db_result)
    await session.flush()

    await _record_flags(session, db_result, item_id, match_result.flags)
    return db_result


async def _record_flags(
    session: AsyncSession,
    db_result: MatchResultModel,
    item_id: UUID,
    flags: Iterable[Flag],
) -> None:
    if not flags:
        return

    price_item_id = db_result.price_item_id
    if price_item_id is None:
        return

    for flag in flags:
        session.add(
            MatchFlagModel(
                match_result_id=db_result.id,
                item_id=item_id,
                price_item_id=price_item_id,
                flag_type=flag.type,
                severity=_enum_value(flag.severity),
                message=flag.message,
            )
        )
