"""Classification-first candidate generation for BIMCalc.

Reduces candidate space by ≥20× through classification blocking and numeric pre-filters.
"""

from __future__ import annotations

from typing import Optional

from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from bimcalc.config import get_config
from bimcalc.db.models import PriceItemModel
from bimcalc.models import Item, PriceItem


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

        if limit is None:
            limit = self.config.matching.max_candidates_per_item

        # Start with classification blocking (CRITICAL for 20× reduction)
        stmt = select(PriceItemModel).where(
            PriceItemModel.classification_code == item.classification_code
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

        # Optional unit filter (strict match)
        if item.unit is not None:
            stmt = stmt.where(
                or_(PriceItemModel.unit == item.unit, PriceItemModel.unit.is_(None))
            )

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
