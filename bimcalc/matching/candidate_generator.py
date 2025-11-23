"""Classification-first candidate generation for BIMCalc.

Reduces candidate space by ≥20× through classification blocking and numeric pre-filters.
"""

from __future__ import annotations

import logging
from typing import Optional

from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from bimcalc.config import get_config
from bimcalc.db.models import PriceItemModel
from bimcalc.models import Item, PriceItem

logger = logging.getLogger(__name__)


class CandidateGenerator:
    """Classification-first candidate generator (20× reduction)."""

    def __init__(self, session: AsyncSession):
        """Initialize generator with database session.

        Args:
            session: SQLAlchemy async session
        """
        self.session = session
        self.config = get_config()

    async def generate(self, item: Item, limit: Optional[int] = None) -> list[PriceItem]:
        """Generate candidates using classification-first blocking.

        Filter logic (applied in order):
        1. Classification blocking (indexed)
        2. Numeric pre-filters (tolerance-based)
        3. Unit filter (optional, strict match)

        Args:
            item: BIM item with classification_code and attributes
            limit: Max candidates to return (default from config)

        Returns:
            List of candidate PriceItem objects

        Raises:
            ValueError: If item.classification_code is None
            SQLAlchemyError: If database query fails
        """
        if item.classification_code is None:
            raise ValueError("item.classification_code is required for candidate generation")

        if item.org_id is None:
            raise ValueError("item.org_id is required for multi-tenant candidate filtering")

        if limit is None:
            limit = self.config.matching.max_candidates_per_item

        # Start with classification blocking (CRITICAL for 20× reduction)
        # ALWAYS filter by is_current=True to get latest prices (SCD Type-2)
        # CRITICAL: Filter by org_id for multi-tenant isolation
        stmt = select(PriceItemModel).where(
            and_(
                PriceItemModel.org_id == item.org_id,
                PriceItemModel.classification_code == item.classification_code,
                PriceItemModel.is_current == True,
            )
        )

        # Apply numeric pre-filters (tolerance-based)
        filters = []

        if item.width_mm is not None:
            tolerance = self.config.matching.size_tolerance_mm
            filters.append(
                or_(
                    PriceItemModel.width_mm.is_(None),
                    and_(
                        PriceItemModel.width_mm.isnot(None),
                        PriceItemModel.width_mm.between(
                            item.width_mm - tolerance, item.width_mm + tolerance
                        ),
                    ),
                )
            )

        if item.height_mm is not None:
            tolerance = self.config.matching.size_tolerance_mm
            filters.append(
                or_(
                    PriceItemModel.height_mm.is_(None),
                    and_(
                        PriceItemModel.height_mm.isnot(None),
                        PriceItemModel.height_mm.between(
                            item.height_mm - tolerance, item.height_mm + tolerance
                        ),
                    ),
                )
            )

        if item.dn_mm is not None:
            tolerance = self.config.matching.dn_tolerance_mm
            filters.append(
                or_(
                    PriceItemModel.dn_mm.is_(None),
                    and_(
                        PriceItemModel.dn_mm.isnot(None),
                        PriceItemModel.dn_mm.between(
                            item.dn_mm - tolerance, item.dn_mm + tolerance
                        ),
                    ),
                )
            )

        # Apply all filters
        if filters:
            stmt = stmt.where(and_(*filters))

        # Optional unit filter (strict match) - REMOVED to allow Unit Mismatch flags
        # if item.unit is not None:
        #     stmt = stmt.where(
        #         or_(PriceItemModel.unit == item.unit, PriceItemModel.unit.is_(None))
        #     )

        # Limit results
        stmt = stmt.limit(limit)

        # Execute query
        result = await self.session.execute(stmt)
        rows = result.scalars().all()

        # Convert to Pydantic models
        return [
            PriceItem(
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
            for row in rows
        ]


    async def generate_with_escape_hatch(
        self, item: Item, max_escape_hatch: int = 2
    ) -> tuple[list[PriceItem], bool]:
        """Generate candidates with escape-hatch for out-of-class items.

        Per CLAUDE.md: "Provide an escape-hatch candidate pool (max 1–2 out-of-class)
        when no in-class candidate scores pass thresholds."

        This method:
        1. Attempts normal in-class candidate generation
        2. If no candidates found, relaxes classification filter
        3. Returns up to max_escape_hatch out-of-class candidates

        Args:
            item: BIM item with classification_code and attributes
            max_escape_hatch: Maximum out-of-class candidates (default 2)

        Returns:
            Tuple of (candidates, used_escape_hatch_flag)
            - candidates: List of PriceItem objects
            - used_escape_hatch_flag: True if classification filter was relaxed

        Raises:
            ValueError: If item.classification_code or item.org_id is None
            SQLAlchemyError: If database query fails
        """
        # First, try normal classification-first matching
        candidates = await self.generate(item)

        if len(candidates) > 0:
            # Success with normal classification blocking
            return candidates, False

        # No in-class candidates found - engage escape-hatch
        logger.warning(
            f"No in-class candidates for item {item.id} (class={item.classification_code}), "
            f"engaging escape-hatch (max {max_escape_hatch})"
        )

        if item.org_id is None:
            raise ValueError("item.org_id is required for multi-tenant candidate filtering")

        # Relaxed query: Remove classification blocking, keep all other filters
        stmt = select(PriceItemModel).where(
            and_(
                PriceItemModel.org_id == item.org_id,
                PriceItemModel.is_current == True,
            )
        )

        # Apply same numeric pre-filters as normal generate()
        filters = []

        if item.width_mm is not None:
            tolerance = self.config.matching.size_tolerance_mm
            filters.append(
                or_(
                    PriceItemModel.width_mm.is_(None),
                    and_(
                        PriceItemModel.width_mm.isnot(None),
                        PriceItemModel.width_mm.between(
                            item.width_mm - tolerance, item.width_mm + tolerance
                        ),
                    ),
                )
            )

        if item.height_mm is not None:
            tolerance = self.config.matching.size_tolerance_mm
            filters.append(
                or_(
                    PriceItemModel.height_mm.is_(None),
                    and_(
                        PriceItemModel.height_mm.isnot(None),
                        PriceItemModel.height_mm.between(
                            item.height_mm - tolerance, item.height_mm + tolerance
                        ),
                    ),
                )
            )

        if item.dn_mm is not None:
            tolerance = self.config.matching.dn_tolerance_mm
            filters.append(
                or_(
                    PriceItemModel.dn_mm.is_(None),
                    and_(
                        PriceItemModel.dn_mm.isnot(None),
                        PriceItemModel.dn_mm.between(
                            item.dn_mm - tolerance, item.dn_mm + tolerance
                        ),
                    ),
                )
            )

        if filters:
            stmt = stmt.where(and_(*filters))

        # Optional unit filter - REMOVED to allow Unit Mismatch flags
        # if item.unit is not None:
        #     stmt = stmt.where(
        #         or_(PriceItemModel.unit == item.unit, PriceItemModel.unit.is_(None))
        #     )

        # Limit to escape-hatch max
        stmt = stmt.limit(max_escape_hatch)

        # Execute query
        result = await self.session.execute(stmt)
        rows = result.scalars().all()

        # Convert to Pydantic models
        escape_candidates = [
            PriceItem(
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
            for row in rows
        ]

        if len(escape_candidates) > 0:
            logger.info(
                f"Escape-hatch found {len(escape_candidates)} out-of-class candidates "
                f"for item {item.id}"
            )

        return escape_candidates, True


async def generate_candidates(
    session: AsyncSession, item: Item, limit: Optional[int] = None
) -> list[PriceItem]:
    """Convenience function: generate candidates.

    Args:
        session: SQLAlchemy async session
        item: BIM item with classification_code
        limit: Max candidates to return

    Returns:
        List of candidate PriceItem objects
    """
    generator = CandidateGenerator(session)
    return await generator.generate(item, limit)
