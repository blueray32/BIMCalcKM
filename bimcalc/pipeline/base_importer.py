"""Base class for all data source importers.

Defines the contract that all importer modules must implement.
Provides common utilities and error handling patterns.
"""

from __future__ import annotations

import logging
import time
from abc import ABC, abstractmethod
from collections.abc import AsyncIterator

from bimcalc.pipeline.types import ImportResult, ImportStatus, PriceRecord

logger = logging.getLogger(__name__)


class BaseImporter(ABC):
    """Abstract base class for price data importers.

    All source-specific importers (API, file-based, etc.) must inherit from this.

    Key principles:
    1. Each importer handles exactly ONE data source
    2. Importers are stateless and can be retried
    3. Failures are isolated - they don't crash the pipeline
    4. All importers yield PriceRecord objects in canonical format
    """

    def __init__(self, source_name: str, config: dict):
        """Initialize importer.

        Args:
            source_name: Unique identifier for this data source
            config: Configuration dict with source-specific settings
        """
        self.source_name = source_name
        self.config = config
        self.logger = logging.getLogger(f"{__name__}.{source_name}")

    @abstractmethod
    async def fetch_data(self) -> AsyncIterator[PriceRecord]:
        """Fetch and yield price records from this source.

        This is the core method each importer must implement.

        Yields:
            PriceRecord objects in canonical format

        Raises:
            Exception: Any error during fetch (will be caught by run())
        """
        pass

    async def run(self) -> ImportResult:
        """Execute import with error handling and timing.

        This is the public interface called by the orchestrator.

        Returns:
            ImportResult with status and statistics
        """
        start_time = time.time()
        result = ImportResult(source_name=self.source_name, status=ImportStatus.SUCCESS)

        try:
            self.logger.info(f"Starting import from {self.source_name}")

            record_count = 0
            async for record in self.fetch_data():
                record_count += 1

            result.records_inserted = record_count
            result.message = f"Successfully imported {record_count} records"

            self.logger.info(result.message)

        except Exception as e:
            result.status = ImportStatus.FAILED
            result.message = f"Import failed: {str(e)}"
            result.error_details = {
                "error_type": type(e).__name__,
                "error_message": str(e),
            }

            self.logger.error(
                f"Import failed for {self.source_name}: {e}",
                exc_info=True,
            )

        finally:
            result.duration_seconds = time.time() - start_time

        return result

    def _get_config_value(self, key: str, default=None, required: bool = False):
        """Get configuration value with validation.

        Args:
            key: Config key to retrieve
            default: Default value if key not found
            required: If True, raises error when key missing

        Returns:
            Config value

        Raises:
            ValueError: If required key is missing
        """
        value = self.config.get(key, default)

        if required and value is None:
            raise ValueError(
                f"Required config key '{key}' missing for {self.source_name}"
            )

        return value
