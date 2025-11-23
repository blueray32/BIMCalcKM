"""Database queries for review UI."""

from __future__ import annotations

from collections import defaultdict
from typing import Sequence
from uuid import UUID

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from bimcalc.db.models import ItemModel, MatchFlagModel, MatchResultModel, PriceItemModel
from bimcalc.models import FlagSeverity
from bimcalc.review.models import ReviewFlag, ReviewItem, ReviewPrice, ReviewRecord


async def fetch_pending_reviews(
    session: AsyncSession,
    org_id: str,
    project_id: str,
    flag_types: Sequence[str] | None = None,
    severity_filter: FlagSeverity | None = None,
    unmapped_only: bool = False,
    classification_filter: str | None = None,
) -> list[ReviewRecord]:
    """Return latest manual-review items for the project.

    Args:
        unmapped_only: If True, only return items with no matched price (price_item_id IS NULL)
        classification_filter: If provided, only return items with this classification code
    """

    # Find the latest match result for each item (regardless of decision)
    latest_subquery = (
        select(
            MatchResultModel.item_id.label("item_id"),
            func.max(MatchResultModel.timestamp).label("max_ts"),
        )
        .join(ItemModel, ItemModel.id == MatchResultModel.item_id)
        .where(
            ItemModel.org_id == org_id,
            ItemModel.project_id == project_id,
        )
        .group_by(MatchResultModel.item_id)
        .subquery()
    )

    # Then filter for items whose latest decision is manual-review
    stmt = (
        select(MatchResultModel, ItemModel, PriceItemModel)
        .join(
            latest_subquery,
            and_(
                MatchResultModel.item_id == latest_subquery.c.item_id,
                MatchResultModel.timestamp == latest_subquery.c.max_ts,
            ),
        )
        .join(ItemModel, ItemModel.id == MatchResultModel.item_id)
        .outerjoin(PriceItemModel, MatchResultModel.price_item_id == PriceItemModel.id)
        .where(MatchResultModel.decision == "manual-review")
        .order_by(MatchResultModel.timestamp.asc())
    )

    rows = await session.execute(stmt)
    records = rows.all()
    if not records:
        return []

    match_ids = [row.MatchResultModel.id for row in records]
    flags_by_match = await _load_flags(session, match_ids)

    review_records: list[ReviewRecord] = []
    for row in records:
        match_result = row.MatchResultModel
        item_model = row.ItemModel
        price_model = row.PriceItemModel

        flags = flags_by_match.get(match_result.id, [])
        record = ReviewRecord(
            match_result_id=match_result.id,
            item=_to_review_item(item_model),
            price=_to_review_price(price_model) if price_model else None,
            confidence_score=match_result.confidence_score,
            source=match_result.source,
            reason=match_result.reason,
            created_by=match_result.created_by,
            timestamp=match_result.timestamp,
            flags=flags,
        )

        if not _matches_filters(record, flag_types, severity_filter, unmapped_only, classification_filter):
            continue

        review_records.append(record)

    return review_records


async def fetch_available_classifications(
    session: AsyncSession,
    org_id: str,
    project_id: str,
) -> list[dict[str, str]]:
    """Return all distinct classification codes in the project with counts.

    Returns list of {code, name, count} dicts sorted by code.
    """
    # Classification code to name mapping (OmniClass/UniClass)
    CLASSIFICATION_NAMES = {
        "62": "Small Power",
        "63": "Earthing & Bonding",
        "64": "Lighting",
        "66": "Containment",
        "67": "Emergency Lighting",
        "68": "Fire Detection",
    }

    stmt = (
        select(
            ItemModel.classification_code,
            func.count(ItemModel.id).label("count")
        )
        .where(
            ItemModel.org_id == org_id,
            ItemModel.project_id == project_id,
            ItemModel.classification_code.isnot(None)
        )
        .group_by(ItemModel.classification_code)
        .order_by(ItemModel.classification_code)
    )

    rows = await session.execute(stmt)
    classifications = []

    for row in rows.all():
        code = row.classification_code
        name = CLASSIFICATION_NAMES.get(code, f"Class {code}")
        classifications.append({
            "code": code,
            "name": name,
            "count": row.count
        })

    return classifications


async def fetch_review_record(
    session: AsyncSession,
    match_result_id: UUID,
) -> ReviewRecord | None:
    stmt = (
        select(MatchResultModel, ItemModel, PriceItemModel)
        .join(ItemModel, ItemModel.id == MatchResultModel.item_id)
        .outerjoin(PriceItemModel, MatchResultModel.price_item_id == PriceItemModel.id)
        .where(MatchResultModel.id == match_result_id)
    )

    row = (await session.execute(stmt)).one_or_none()
    if row is None:
        return None

    flags_by_match = await _load_flags(session, [match_result_id])
    flags = flags_by_match.get(match_result_id, [])

    return ReviewRecord(
        match_result_id=row.MatchResultModel.id,
        item=_to_review_item(row.ItemModel),
        price=_to_review_price(row.PriceItemModel) if row.PriceItemModel else None,
        confidence_score=row.MatchResultModel.confidence_score,
        source=row.MatchResultModel.source,
        reason=row.MatchResultModel.reason,
        created_by=row.MatchResultModel.created_by,
        timestamp=row.MatchResultModel.timestamp,
        flags=flags,
    )


async def _load_flags(
    session: AsyncSession, match_result_ids: Sequence[UUID]
) -> dict[UUID, list[ReviewFlag]]:
    if not match_result_ids:
        return {}

    flags_stmt = select(MatchFlagModel).where(MatchFlagModel.match_result_id.in_(match_result_ids))
    rows = await session.execute(flags_stmt)
    flags_by_match: dict[UUID, list[ReviewFlag]] = defaultdict(list)

    for flag in rows.scalars():
        try:
            severity = FlagSeverity(flag.severity)
        except ValueError:
            severity = FlagSeverity.ADVISORY

        flags_by_match[flag.match_result_id].append(
            ReviewFlag(type=flag.flag_type, severity=severity, message=flag.message)
        )

    return flags_by_match


def _matches_filters(
    record: ReviewRecord,
    flag_types: Sequence[str] | None,
    severity_filter: FlagSeverity | None,
    unmapped_only: bool = False,
    classification_filter: str | None = None,
) -> bool:
    # Filter for unmapped items (no matched price)
    if unmapped_only and record.price is not None:
        return False

    # Filter by classification code
    if classification_filter and record.item.classification_code != classification_filter:
        return False

    if flag_types:
        if not any(flag.type in flag_types for flag in record.flags):
            return False

    if severity_filter:
        if not any(flag.severity == severity_filter for flag in record.flags):
            return False

    return True


def _to_review_item(model: ItemModel) -> ReviewItem:
    return ReviewItem(
        id=model.id,
        org_id=model.org_id,
        project_id=model.project_id,
        canonical_key=model.canonical_key,
        family=model.family,
        type_name=model.type_name,
        category=model.category,
        system_type=model.system_type,
        classification_code=model.classification_code,
        quantity=model.quantity,
        unit=model.unit,
        width_mm=model.width_mm,
        height_mm=model.height_mm,
        dn_mm=model.dn_mm,
        angle_deg=model.angle_deg,
        material=model.material,
        source_file=model.source_file,
    )


def _to_review_price(model: PriceItemModel | None) -> ReviewPrice | None:
    if model is None:
        return None

    return ReviewPrice(
        id=model.id,
        vendor_id=model.vendor_id,
        sku=model.sku,
        description=model.description,
        classification_code=model.classification_code,
        unit=model.unit,
        unit_price=model.unit_price,
        currency=model.currency,
        vat_rate=model.vat_rate,
        width_mm=model.width_mm,
        height_mm=model.height_mm,
        dn_mm=model.dn_mm,
        angle_deg=model.angle_deg,
        material=model.material,
        last_updated=model.last_updated,
        vendor_note=model.vendor_note,
    )
