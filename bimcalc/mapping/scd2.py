"""SCD Type-2 mapping memory operations for BIMCalc.

Provides O(1) lookup, atomic write, and as-of temporal queries.
Enforces invariant: at most one active row per (org_id, canonical_key).
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import and_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from bimcalc.db.models import ItemMappingModel
from bimcalc.models import MappingEntry


class MappingMemory:
    """SCD Type-2 mapping memory for learning curve (30-50% instant auto-match)."""

    def __init__(self, session: AsyncSession):
        """Initialize mapping memory with database session.

        Args:
            session: SQLAlchemy async session
        """
        self.session = session

    async def lookup(self, org_id: str, canonical_key: str) -> UUID | None:
        """O(1) lookup of active mapping.

        Args:
            org_id: Organization identifier
            canonical_key: 16-character canonical key hash

        Returns:
            price_item_id if active mapping exists, None otherwise

        Raises:
            SQLAlchemyError: If database query fails
        """
        # Query for active row (end_ts IS NULL)
        stmt = select(ItemMappingModel.price_item_id).where(
            and_(
                ItemMappingModel.org_id == org_id,
                ItemMappingModel.canonical_key == canonical_key,
                ItemMappingModel.end_ts.is_(None),
            )
        )

        result = await self.session.execute(stmt)
        row = result.scalar_one_or_none()

        return row if row else None

    async def write(
        self,
        org_id: str,
        canonical_key: str,
        price_item_id: UUID,
        created_by: str,
        reason: str,
    ) -> UUID:
        """Atomic SCD2 write: close current mapping and insert new active row.

        Transaction ensures at-most-one active row invariant.

        Args:
            org_id: Organization identifier
            canonical_key: 16-character canonical key hash
            price_item_id: Target price item UUID
            created_by: User email or "system"
            reason: Audit reason ("manual match", "auto-accept", etc.)

        Returns:
            UUID: New mapping entry ID

        Raises:
            IntegrityError: If SCD2 invariant would be violated
            SQLAlchemyError: If database operation fails
        """
        # Step 1: Close current active row (if exists)
        now = datetime.utcnow()

        update_stmt = (
            update(ItemMappingModel)
            .where(
                and_(
                    ItemMappingModel.org_id == org_id,
                    ItemMappingModel.canonical_key == canonical_key,
                    ItemMappingModel.end_ts.is_(None),  # Only active rows
                )
            )
            .values(end_ts=now)
        )

        await self.session.execute(update_stmt)

        # Step 2: Insert new active row
        new_mapping = ItemMappingModel(
            org_id=org_id,
            canonical_key=canonical_key,
            price_item_id=price_item_id,
            start_ts=now,
            end_ts=None,  # Active
            created_by=created_by,
            reason=reason,
        )

        self.session.add(new_mapping)
        await self.session.flush()  # Get ID without committing

        return new_mapping.id

    async def lookup_as_of(
        self, org_id: str, canonical_key: str, as_of: datetime
    ) -> UUID | None:
        """Temporal query: get mapping valid at specific timestamp.

        Enables reproducible reports (bit-for-bit identical for same timestamp).

        Args:
            org_id: Organization identifier
            canonical_key: 16-character canonical key hash
            as_of: Timestamp to query (ISO 8601)

        Returns:
            price_item_id valid at as_of timestamp, None if no mapping

        Raises:
            SQLAlchemyError: If database query fails
        """
        # Query: start_ts <= as_of < COALESCE(end_ts, +∞)
        stmt = select(ItemMappingModel.price_item_id).where(
            and_(
                ItemMappingModel.org_id == org_id,
                ItemMappingModel.canonical_key == canonical_key,
                ItemMappingModel.start_ts <= as_of,
                # end_ts IS NULL OR end_ts > as_of
                (ItemMappingModel.end_ts.is_(None)) | (ItemMappingModel.end_ts > as_of),
            )
        )

        result = await self.session.execute(stmt)
        row = result.scalar_one_or_none()

        return row if row else None

    async def get_history(self, org_id: str, canonical_key: str) -> list[MappingEntry]:
        """Get full history of mappings for a canonical key.

        Returns all SCD2 rows (active and closed) in chronological order.

        Args:
            org_id: Organization identifier
            canonical_key: 16-character canonical key hash

        Returns:
            List of MappingEntry (sorted by start_ts ascending)

        Raises:
            SQLAlchemyError: If database query fails
        """
        stmt = (
            select(ItemMappingModel)
            .where(
                and_(
                    ItemMappingModel.org_id == org_id,
                    ItemMappingModel.canonical_key == canonical_key,
                )
            )
            .order_by(ItemMappingModel.start_ts.asc())
        )

        result = await self.session.execute(stmt)
        rows = result.scalars().all()

        # Convert to Pydantic models
        return [
            MappingEntry(
                id=row.id,
                org_id=row.org_id,
                canonical_key=row.canonical_key,
                price_item_id=row.price_item_id,
                start_ts=row.start_ts,
                end_ts=row.end_ts,
                created_by=row.created_by,
                reason=row.reason,
            )
            for row in rows
        ]

    async def count_active_mappings(self, org_id: str) -> int:
        """Count active mappings for an organization.

        Useful for monitoring learning curve progress.

        Args:
            org_id: Organization identifier

        Returns:
            Number of active mappings (end_ts IS NULL)

        Raises:
            SQLAlchemyError: If database query fails
        """
        from sqlalchemy import func

        stmt = select(func.count()).where(
            and_(
                ItemMappingModel.org_id == org_id,
                ItemMappingModel.end_ts.is_(None),
            )
        )

        result = await self.session.execute(stmt)
        return result.scalar_one()


async def lookup_mapping(
    session: AsyncSession, org_id: str, canonical_key: str
) -> UUID | None:
    """Convenience function: lookup active mapping.

    Args:
        session: SQLAlchemy async session
        org_id: Organization identifier
        canonical_key: 16-character canonical key hash

    Returns:
        price_item_id if active mapping exists, None otherwise
    """
    memory = MappingMemory(session)
    return await memory.lookup(org_id, canonical_key)


async def write_mapping(
    session: AsyncSession,
    org_id: str,
    canonical_key: str,
    price_item_id: UUID,
    created_by: str,
    reason: str,
) -> UUID:
    """Convenience function: write SCD2 mapping.

    Args:
        session: SQLAlchemy async session
        org_id: Organization identifier
        canonical_key: 16-character canonical key hash
        price_item_id: Target price item UUID
        created_by: User email or "system"
        reason: Audit reason

    Returns:
        New mapping entry ID
    """
    memory = MappingMemory(session)
    return await memory.write(org_id, canonical_key, price_item_id, created_by, reason)
