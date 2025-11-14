"""SCD Type-2 price update logic.

Implements full Slowly Changing Dimension Type-2 pattern:
- Compare incoming price with current active price
- If changed: expire old record (set valid_to, is_current=false)
- Insert new record with current timestamp

This preserves complete price history for auditability and financial analysis.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Optional
from uuid import uuid4

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from bimcalc.db.models import PriceItemModel
from bimcalc.pipeline.types import PriceRecord

logger = logging.getLogger(__name__)


class SCD2PriceUpdater:
    """Handle SCD Type-2 price updates with full history preservation."""

    def __init__(self, session: AsyncSession):
        """Initialize updater with database session.

        Args:
            session: Active async SQLAlchemy session
        """
        self.session = session
        self.stats = {
            "inserted": 0,
            "updated": 0,
            "unchanged": 0,
            "failed": 0,
        }

    async def process_price(self, record: PriceRecord) -> bool:
        """Process a single price record with SCD Type-2 logic.

        Args:
            record: Normalized price record

        Returns:
            True if successful, False if failed

        Process:
            1. Query for active record (is_current=true)
            2. If not found → INSERT new record
            3. If found and price unchanged → skip or update last_updated
            4. If found and price changed → EXPIRE old + INSERT new
        """
        try:
            # 1. Query for current active record
            stmt = select(PriceItemModel).where(
                and_(
                    PriceItemModel.item_code == record.item_code,
                    PriceItemModel.region == record.region,
                    PriceItemModel.is_current == True,
                )
            )
            result = await self.session.execute(stmt)
            current_record = result.scalar_one_or_none()

            now = datetime.utcnow()

            if current_record is None:
                # 2. New item → Insert
                await self._insert_new_record(record, now)
                self.stats["inserted"] += 1
                return True

            # 3. Compare prices
            price_changed = self._price_has_changed(current_record, record)

            if not price_changed:
                # Price unchanged → optionally update last_updated for freshness tracking
                current_record.last_updated = now
                self.stats["unchanged"] += 1
                return True

            # 4. Price changed → SCD Type-2: Expire old, Insert new
            await self._expire_and_insert(current_record, record, now)
            self.stats["updated"] += 1

            return True

        except Exception as e:
            logger.error(
                f"Failed to process price for {record.item_code} ({record.region}): {e}",
                exc_info=True,
            )
            self.stats["failed"] += 1
            return False

    async def _insert_new_record(self, record: PriceRecord, timestamp: datetime) -> None:
        """Insert a new price record.

        Args:
            record: Price data
            timestamp: Current timestamp
        """
        price_model = PriceItemModel(
            id=uuid4(),
            item_code=record.item_code,
            region=record.region,
            classification_code=record.classification_code,
            vendor_id=record.vendor_id,
            sku=record.sku or record.item_code,
            description=record.description,
            unit=record.unit,
            unit_price=record.unit_price,
            currency=record.currency,
            vat_rate=record.vat_rate,
            width_mm=record.width_mm,
            height_mm=record.height_mm,
            dn_mm=record.dn_mm,
            angle_deg=record.angle_deg,
            material=record.material,
            source_name=record.source_name,
            source_currency=record.source_currency,
            original_effective_date=record.original_effective_date,
            valid_from=timestamp,
            valid_to=None,
            is_current=True,
            last_updated=timestamp,
            vendor_note=record.vendor_note,
        )

        self.session.add(price_model)

        logger.debug(
            f"Inserted new price: {record.item_code} ({record.region}) "
            f"@ {record.unit_price} {record.currency}"
        )

    async def _expire_and_insert(
        self,
        current_record: PriceItemModel,
        new_record: PriceRecord,
        timestamp: datetime,
    ) -> None:
        """Expire old record and insert new one (SCD Type-2 core logic).

        Args:
            current_record: Existing active record
            new_record: New price data
            timestamp: Current timestamp
        """
        # Expire old record
        current_record.valid_to = timestamp
        current_record.is_current = False
        current_record.last_updated = timestamp

        logger.info(
            f"Price change detected for {new_record.item_code} ({new_record.region}): "
            f"{current_record.unit_price} {current_record.currency} → "
            f"{new_record.unit_price} {new_record.currency}"
        )

        # CRITICAL: Flush the expire operation before insert
        # This ensures the unique constraint is satisfied
        await self.session.flush()

        # Insert new record
        await self._insert_new_record(new_record, timestamp)

    def _price_has_changed(self, current: PriceItemModel, new: PriceRecord) -> bool:
        """Compare current and new price records.

        Args:
            current: Current database record
            new: New price record

        Returns:
            True if price or currency changed
        """
        # Compare critical financial fields
        price_changed = current.unit_price != new.unit_price
        currency_changed = current.source_currency != new.source_currency

        return price_changed or currency_changed

    async def commit(self) -> None:
        """Commit all changes in transaction."""
        await self.session.commit()
        logger.info(
            f"SCD2 Update committed: "
            f"{self.stats['inserted']} inserted, "
            f"{self.stats['updated']} updated, "
            f"{self.stats['unchanged']} unchanged, "
            f"{self.stats['failed']} failed"
        )

    async def rollback(self) -> None:
        """Rollback transaction on error."""
        await self.session.rollback()
        logger.error("SCD2 Update rolled back due to error")

    def get_stats(self) -> dict:
        """Get processing statistics.

        Returns:
            Dictionary with insert/update/unchanged/failed counts
        """
        return self.stats.copy()
