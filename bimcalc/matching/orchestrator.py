"""End-to-end matching orchestrator for BIMCalc.

Coordinates classification → canonical key → mapping lookup → candidate generation
→ fuzzy ranking → flag evaluation → auto-routing.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from bimcalc.canonical.key_generator import canonical_key
from bimcalc.classification.trust_hierarchy import classify_item
from bimcalc.config import get_config
from bimcalc.flags.engine import compute_flags
from bimcalc.mapping.scd2 import MappingMemory
from bimcalc.matching.auto_router import AutoRouter
from bimcalc.matching.candidate_generator import CandidateGenerator
from bimcalc.matching.fuzzy_ranker import FuzzyRanker
from bimcalc.models import CandidateMatch, Item, MatchResult, PriceItem


class MatchOrchestrator:
    """Orchestrates end-to-end matching pipeline."""

    def __init__(self, session: AsyncSession):
        """Initialize orchestrator with database session.

        Args:
            session: SQLAlchemy async session
        """
        self.session = session
        self.config = get_config()

        # Initialize components
        self.mapping_memory = MappingMemory(session)
        self.candidate_generator = CandidateGenerator(session)
        self.fuzzy_ranker = FuzzyRanker()
        self.auto_router = AutoRouter()

    async def match(
        self, item: Item, created_by: str = "system"
    ) -> tuple[MatchResult, PriceItem | None]:
        """Execute end-to-end matching pipeline for an item.

        Pipeline:
        1. Classification (trust hierarchy)
        2. Canonical key generation
        3. Mapping memory lookup (O(1))
        4. If miss: Generate candidates (classification-blocked)
        5. Fuzzy rank candidates (RapidFuzz)
        6. Evaluate flags for top candidate
        7. Auto-route decision (confidence + flags)
        8. Write mapping if auto-accepted

        Args:
            item: BIM item to match
            created_by: User email or "system"

        Returns:
            Tuple of (MatchResult, PriceItem) - PriceItem is None if no match

        Raises:
            ValueError: If item is invalid
            SQLAlchemyError: If database operation fails
        """
        # Step 1: Classification
        if item.classification_code is None:
            item.classification_code = classify_item(item)

        # Step 2: Canonical key
        if item.canonical_key is None:
            item.canonical_key = canonical_key(item)

        # Step 3: Mapping memory lookup (instant auto-match path)
        price_item_id = await self.mapping_memory.lookup(
            self.config.org_id, item.canonical_key
        )

        if price_item_id:
            # Mapping hit! Instant auto-match via learning curve
            price_item = await self._get_price_item(price_item_id)

            if price_item:
                # Evaluate flags even for mapping memory matches
                flags = compute_flags(item.model_dump(), price_item.model_dump())

                match = CandidateMatch(price_item=price_item, score=100.0, flags=flags)

                result = self.auto_router.route(match, source="mapping_memory", created_by=created_by)

                return result, price_item

        # Step 4: Mapping miss → Generate candidates with escape-hatch
        candidates, used_escape_hatch = await self.candidate_generator.generate_with_escape_hatch(item)

        if not candidates:
            # No candidates found even with escape-hatch
            reason = "No candidates found after classification blocking (including escape-hatch)"
            if used_escape_hatch:
                reason = "No candidates found even with escape-hatch (relaxed classification)"

            result = MatchResult(
                item_id=item.id,
                price_item_id=None,
                confidence_score=0.0,
                source="fuzzy_match",
                flags=[],
                decision="rejected",
                reason=reason,
                created_by=created_by,
            )
            return result, None

        # Step 5: Fuzzy rank candidates
        ranked = self.fuzzy_ranker.rank(item, candidates)

        if not ranked:
            # No candidates passed fuzzy threshold
            result = MatchResult(
                item_id=item.id,
                price_item_id=None,
                confidence_score=0.0,
                source="fuzzy_match",
                flags=[],
                decision="rejected",
                reason=f"No candidates scored >= {self.fuzzy_ranker.min_score}",
                created_by=created_by,
            )
            return result, None

        # Step 6: Evaluate flags for top candidate
        top_match = ranked[0]
        top_match.flags = compute_flags(item.model_dump(), top_match.price_item.model_dump())

        # If escape-hatch was used, add Classification Mismatch flag (CRITICAL-VETO)
        if used_escape_hatch:
            from bimcalc.models import Flag, FlagSeverity
            escape_flag = Flag(
                type="Classification Mismatch",
                severity=FlagSeverity.CRITICAL_VETO,
                message=(
                    f"Out-of-class match via escape-hatch: item class={item.classification_code}, "
                    f"price class={top_match.price_item.classification_code}"
                )
            )
            top_match.flags.append(escape_flag)

        # Step 7: Auto-route decision
        result = self.auto_router.route(top_match, source="fuzzy_match", created_by=created_by)
        result.item_id = item.id  # Correct the item_id

        # Step 8: Write mapping if auto-accepted
        if result.decision == "auto-accepted":
            await self.mapping_memory.write(
                org_id=self.config.org_id,
                canonical_key=item.canonical_key,
                price_item_id=top_match.price_item.id,
                created_by=created_by,
                reason="auto-accept",
            )

        return result, top_match.price_item

    async def _get_price_item(self, price_item_id: UUID) -> PriceItem | None:
        """Get PriceItem by ID.

        Args:
            price_item_id: Price item UUID

        Returns:
            PriceItem if found, None otherwise
        """
        from sqlalchemy import select

        from bimcalc.db.models import PriceItemModel

        stmt = select(PriceItemModel).where(PriceItemModel.id == price_item_id)
        result = await self.session.execute(stmt)
        row = result.scalar_one_or_none()

        if not row:
            return None

        return PriceItem(
            id=row.id,
            classification_code=row.classification_code,
            vendor_id=row.vendor_id,
            sku=row.sku,
            description=row.description,
            unit=row.unit,
            unit_price=row.unit_price,
            currency=row.currency,
            vat_rate=row.vat_rate,
            width_mm=row.width_mm,
            height_mm=row.height_mm,
            dn_mm=row.dn_mm,
            angle_deg=row.angle_deg,
            material=row.material,
            last_updated=row.last_updated,
            vendor_note=row.vendor_note,
            attributes=row.attributes or {},
        )


async def match_item(
    session: AsyncSession, item: Item, created_by: str = "system"
) -> tuple[MatchResult, PriceItem | None]:
    """Convenience function: execute end-to-end matching for an item.

    Args:
        session: SQLAlchemy async session
        item: BIM item to match
        created_by: User email or "system"

    Returns:
        Tuple of (MatchResult, PriceItem)
    """
    orchestrator = MatchOrchestrator(session)
    return await orchestrator.match(item, created_by)
