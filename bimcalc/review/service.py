"""Review UI business operations (approve/reject)."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from bimcalc.db.match_results import record_match_result
from bimcalc.mapping.scd2 import MappingMemory
from bimcalc.models import Flag, MatchDecision, MatchResult
from bimcalc.review.models import ReviewRecord


async def approve_review_record(
    session: AsyncSession,
    record: ReviewRecord,
    created_by: str,
    annotation: str | None = None,
) -> None:
    if record.price is None:
        raise ValueError("Cannot approve record without a price candidate")

    if not record.item.canonical_key:
        raise ValueError("Item is missing canonical key; run matching first")

    # CRITICAL: Block approval if any Critical-Veto flags exist
    if record.has_critical_flags:
        critical_flags = [f for f in record.flags if f.severity == "Critical-Veto"]
        flag_types = ", ".join(f.type for f in critical_flags)
        raise ValueError(
            f"Cannot approve item with Critical-Veto flags: {flag_types}. "
            "These flags indicate fundamental mismatches that compromise auditability."
        )

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

    # INTELLIGENCE: Capture training example
    # If the item has a classification, or if we are confirming a match that implies a classification
    if record.price.classification_code:
        from bimcalc.db.models import TrainingExampleModel
        
        # Determine if this is a correction or confirmation
        # If item had no class, or different class, it's a correction/imputation
        feedback_type = "confirmation"
        if not record.item.classification_code or record.item.classification_code != record.price.classification_code:
            feedback_type = "correction"
            
        example = TrainingExampleModel(
            org_id=record.item.org_id,
            item_family=record.item.family,
            item_type=record.item.type_name,
            item_description=f"{record.item.family} {record.item.type_name}", # Simplified description
            target_classification_code=record.price.classification_code,
            source_item_id=record.item.id,
            price_item_id=record.price.id,
            feedback_type=feedback_type,
            created_by=created_by
        )
        session.add(example)



def _build_reason(annotation: str | None, record: ReviewRecord) -> str:
    base = "Manual approval via review UI"
    if record.has_critical_flags:
        base += " (override)"
    if annotation:
        return f"{base}: {annotation.strip()}"
    return base
