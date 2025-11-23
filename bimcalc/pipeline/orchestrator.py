"""Pipeline orchestrator - manages all data source importers.

Coordinates nightly pricing data refresh from multiple European sources.
Implements resilient design: single source failures don't halt the pipeline.

Key features:
- Modular: Each source is an isolated importer module
- Resilient: Failures are contained and logged per-source
- Auditable: Complete logging to data_sync_log table
- Transactional: SCD Type-2 updates are atomic per source
"""

from __future__ import annotations

import logging
from datetime import datetime
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from bimcalc.db.connection import get_session
from bimcalc.db.models import DataSyncLogModel
from bimcalc.pipeline.base_importer import BaseImporter
from bimcalc.pipeline.scd2_updater import SCD2PriceUpdater
from bimcalc.pipeline.types import ImportResult, ImportStatus

logger = logging.getLogger(__name__)


class PipelineOrchestrator:
    """Orchestrates the entire price data synchronization pipeline.

    Responsibilities:
    1. Load and configure all enabled importers
    2. Execute each importer sequentially (can be parallelized later)
    3. Apply SCD Type-2 updates for each source's data
    4. Log results to data_sync_log for monitoring
    5. Generate alerts on failures
    """

    def __init__(self, importers: list[BaseImporter]):
        """Initialize orchestrator with list of importers.

        Args:
            importers: List of configured importer instances
        """
        self.importers = importers
        self.run_timestamp = datetime.utcnow()

    async def run(self) -> dict:
        """Execute full pipeline run.

        Returns:
            Summary dict with overall status and per-source results
        """
        logger.info(f"Starting pipeline run at {self.run_timestamp}")
        logger.info(f"Configured sources: {len(self.importers)}")

        results = []
        overall_success = True

        async with get_session() as session:
            for importer in self.importers:
                result = await self._run_importer(importer, session)
                results.append(result)

                if not result.success:
                    overall_success = False
                    logger.warning(
                        f"Source {importer.source_name} failed: {result.message}"
                    )

                # Log to data_sync_log
                await self._log_result(result, session)

            # Commit all logs
            await session.commit()

        # Check for failures and potentially send alerts
        await self._check_and_alert(results)

        summary = {
            "run_timestamp": self.run_timestamp.isoformat(),
            "total_sources": len(self.importers),
            "successful_sources": sum(1 for r in results if r.success),
            "failed_sources": sum(1 for r in results if not r.success),
            "overall_success": overall_success,
            "results": results,
        }

        logger.info(
            f"Pipeline run completed: {summary['successful_sources']}/{summary['total_sources']} sources successful"
        )

        return summary

    async def _run_importer(
        self, importer: BaseImporter, session: AsyncSession
    ) -> ImportResult:
        """Run a single importer with SCD Type-2 updates.

        Args:
            importer: Importer instance
            session: Database session

        Returns:
            ImportResult with statistics
        """
        logger.info(f"Processing source: {importer.source_name}")

        result = ImportResult(
            source_name=importer.source_name,
            status=ImportStatus.SUCCESS,
        )

        try:
            # Initialize SCD2 updater
            updater = SCD2PriceUpdater(session)

            # Fetch and process records
            record_count = 0
            try:
                async for record in importer.fetch_data():
                    record.source_name = importer.source_name
                    success = await updater.process_price(record)
                    record_count += 1

                    if not success:
                        result.records_failed += 1
            except Exception as e:
                # Error during fetch/process
                logger.error(f"Error processing records from {importer.source_name}: {e}")
                result.status = ImportStatus.FAILED
                result.message = f"Processing error: {str(e)}"
                return result

            # Commit SCD2 updates for this source
            try:
                await updater.commit()
            except Exception as e:
                logger.error(f"Error committing updates for {importer.source_name}: {e}")
                await updater.rollback()
                result.status = ImportStatus.FAILED
                result.message = f"Commit error: {str(e)}"
                return result

            # Get statistics
            stats = updater.get_stats()
            result.records_inserted = stats["inserted"]
            result.records_updated = stats["updated"]
            result.records_failed = stats["failed"]

            result.message = (
                f"Processed {record_count} records: "
                f"{stats['inserted']} new, "
                f"{stats['updated']} updated, "
                f"{stats['unchanged']} unchanged, "
                f"{stats['failed']} failed"
            )

            if stats["failed"] > 0:
                result.status = ImportStatus.PARTIAL_SUCCESS

            logger.info(f"✓ {importer.source_name}: {result.message}")

        except Exception as e:
            result.status = ImportStatus.FAILED
            result.message = f"Import failed: {str(e)}"
            result.error_details = {
                "error_type": type(e).__name__,
                "error_message": str(e),
            }

            logger.error(
                f"✗ {importer.source_name} failed: {e}",
                exc_info=True,
            )

        return result

    async def _log_result(self, result: ImportResult, session: AsyncSession) -> None:
        """Log import result to data_sync_log table.

        Args:
            result: Import result to log
            session: Database session
        """
        log_entry = DataSyncLogModel(
            id=uuid4(),
            run_timestamp=self.run_timestamp,
            source_name=result.source_name,
            status=result.status.value,
            records_inserted=result.records_inserted,
            records_updated=result.records_updated,
            records_failed=result.records_failed,
            message=result.message,
            error_details=result.error_details,
            duration_seconds=result.duration_seconds,
        )

        session.add(log_entry)

    async def _check_and_alert(self, results: list[ImportResult]) -> None:
        """Check for failures and trigger alerts if needed.

        Args:
            results: List of all import results
        """
        failures = [r for r in results if not r.success]

        if not failures:
            logger.info("All sources processed successfully")
            return

        # Log summary of failures
        logger.warning(f"Pipeline completed with {len(failures)} source failures:")
        for result in failures:
            logger.warning(f"  - {result.source_name}: {result.message}")

        # TODO: Implement alerting (email, Slack, PagerDuty, etc.)
        # For now, just log. In production, this would trigger notifications.


async def run_pipeline(importers: list[BaseImporter]) -> dict:
    """Convenience function to run the pipeline.

    Args:
        importers: List of configured importers

    Returns:
        Pipeline run summary
    """
    orchestrator = PipelineOrchestrator(importers)
    return await orchestrator.run()
