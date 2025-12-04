"""Multi-Source Orchestrator for parallel price fetching and comparison.

Coordinates parallel fetching from multiple supplier sources, aggregates results,
performs deduplication, and provides comparative intelligence across suppliers.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bimcalc.db.connection import get_session
from bimcalc.db.models import PriceSourceModel
from bimcalc.intelligence.price_scout import SmartPriceScout

logger = logging.getLogger(__name__)


class MultiSourceResult:
    """Result from multi-source price fetching.

    Attributes:
        products: Aggregated list of products from all sources
        source_results: Per-source extraction results
        errors: List of errors encountered during fetching
        stats: Statistics about the fetch operation
    """

    def __init__(self):
        self.products: list[dict[str, Any]] = []
        self.source_results: dict[str, dict[str, Any]] = {}
        self.errors: list[dict[str, Any]] = []
        self.stats: dict[str, Any] = {
            "sources_attempted": 0,
            "sources_succeeded": 0,
            "sources_failed": 0,
            "total_products": 0,
            "unique_products": 0,
            "duplicates_removed": 0,
        }


class MultiSourceOrchestrator:
    """Orchestrates parallel price fetching from multiple supplier sources.

    Features:
    - Parallel fetching from 3-5 enabled sources
    - Per-source error handling (partial failure tolerance)
    - Product aggregation and deduplication
    - Price comparison and variance detection
    - Source metadata tracking

    Usage:
        async with MultiSourceOrchestrator(org_id="acme-construction") as orchestrator:
            result = await orchestrator.fetch_all()
            print(f"Found {result.stats['total_products']} products from {result.stats['sources_succeeded']} sources")
    """

    def __init__(self, org_id: str, session: AsyncSession | None = None):
        """Initialize orchestrator for an organization.

        Args:
            org_id: Organization ID to fetch sources for
            session: Optional database session (creates new if not provided)
        """
        self.org_id = org_id
        self._session = session
        self._owns_session = session is None
        self.scout: SmartPriceScout | None = None

    async def __aenter__(self):
        """Async context manager entry."""
        if self._owns_session:
            self._session = await get_session().__aenter__()
        self.scout = SmartPriceScout()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        if self.scout:
            await self.scout.__aexit__(exc_type, exc_val, exc_tb)
        if self._owns_session and self._session:
            await self._session.__aexit__(exc_type, exc_val, exc_tb)

    async def get_enabled_sources(self) -> list[PriceSourceModel]:
        """Get all enabled price sources for the organization.

        Returns:
            List of enabled PriceSourceModel instances
        """
        stmt = (
            select(PriceSourceModel)
            .where(
                PriceSourceModel.org_id == self.org_id,
                PriceSourceModel.enabled == True,  # noqa: E712
            )
            .order_by(PriceSourceModel.name)
        )

        result = await self._session.execute(stmt)
        sources = result.scalars().all()

        logger.info(f"Found {len(sources)} enabled sources for org {self.org_id}")
        return list(sources)

    async def fetch_from_source(
        self, source: PriceSourceModel, force_refresh: bool = False
    ) -> dict[str, Any]:
        """Fetch prices from a single source.

        Args:
            source: PriceSourceModel to fetch from

        Returns:
            Dict with keys:
                - success: bool
                - source_id: UUID
                - source_name: str
                - products: list[dict] (if success)
                - error: str (if failure)
                - duration_ms: int
        """
        start_time = datetime.utcnow()

        try:
            logger.info(f"Fetching from source: {source.name} ({source.url})")

            # Apply source-specific rate limit
            if self.scout.rate_limiter:
                domain = source.domain
                self.scout.rate_limiter.set_domain_delay(
                    domain, source.rate_limit_seconds
                )

            # Fetch products
            result = await self.scout.extract(source.url, force_refresh=force_refresh)

            # Extract products from result
            if isinstance(result, dict) and "products" in result:
                products = result["products"]
            elif isinstance(result, list):
                products = result
            else:
                products = [result] if result else []

            duration_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)

            # Update source metadata
            source.last_sync_at = datetime.utcnow()
            source.last_sync_status = "success"
            source.last_sync_items_count = len(products)
            source.last_sync_error = None
            await self._session.commit()

            logger.info(
                f"Successfully fetched {len(products)} products from {source.name} "
                f"in {duration_ms}ms"
            )

            # Add source metadata to each product
            for product in products:
                product["_source_id"] = str(source.id)
                product["_source_name"] = source.name
                product["_source_url"] = source.url
                product["_fetched_at"] = start_time.isoformat()

            return {
                "success": True,
                "source_id": source.id,
                "source_name": source.name,
                "products": products,
                "duration_ms": duration_ms,
            }

        except ValueError as e:
            # Compliance errors (robots.txt, invalid URL)
            duration_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)
            error_msg = f"Compliance error: {e}"

            logger.error(f"Compliance error for source {source.name}: {e}")

            # Update source metadata
            source.last_sync_at = datetime.utcnow()
            source.last_sync_status = "failed"
            source.last_sync_items_count = 0
            source.last_sync_error = error_msg
            await self._session.commit()

            return {
                "success": False,
                "source_id": source.id,
                "source_name": source.name,
                "error": error_msg,
                "duration_ms": duration_ms,
            }

        except Exception as e:
            # Other errors (network, LLM, timeout)
            duration_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)
            error_msg = f"Extraction failed: {str(e)}"

            logger.error(
                f"Extraction failed for source {source.name}: {e}", exc_info=True
            )

            # Update source metadata
            source.last_sync_at = datetime.utcnow()
            source.last_sync_status = "failed"
            source.last_sync_items_count = 0
            source.last_sync_error = error_msg
            await self._session.commit()

            return {
                "success": False,
                "source_id": source.id,
                "source_name": source.name,
                "error": error_msg,
                "duration_ms": duration_ms,
            }

    async def fetch_all(self, force_refresh: bool = False) -> MultiSourceResult:
        """Fetch prices from all enabled sources in parallel.

        Returns:
            MultiSourceResult with aggregated products and statistics
        """
        result = MultiSourceResult()

        # Get enabled sources
        sources = await self.get_enabled_sources()
        result.stats["sources_attempted"] = len(sources)

        if not sources:
            logger.warning(f"No enabled sources found for org {self.org_id}")
            return result

        # Fetch from all sources in parallel
        logger.info(f"Starting parallel fetch from {len(sources)} sources")
        fetch_tasks = [
            self.fetch_from_source(source, force_refresh=force_refresh)
            for source in sources
        ]
        source_results = await asyncio.gather(*fetch_tasks, return_exceptions=False)

        # Aggregate results
        all_products = []
        for source_result in source_results:
            source_name = source_result["source_name"]
            result.source_results[source_name] = source_result

            if source_result["success"]:
                result.stats["sources_succeeded"] += 1
                products = source_result.get("products", [])
                all_products.extend(products)
            else:
                result.stats["sources_failed"] += 1
                result.errors.append(
                    {
                        "source": source_name,
                        "error": source_result.get("error", "Unknown error"),
                    }
                )

        result.stats["total_products"] = len(all_products)

        # Deduplicate products
        unique_products, duplicates_removed = self._deduplicate_products(all_products)
        result.products = unique_products
        result.stats["unique_products"] = len(unique_products)
        result.stats["duplicates_removed"] = duplicates_removed

        logger.info(
            f"Multi-source fetch complete: "
            f"{result.stats['sources_succeeded']}/{result.stats['sources_attempted']} sources succeeded, "
            f"{result.stats['unique_products']} unique products "
            f"({result.stats['duplicates_removed']} duplicates removed)"
        )

        return result

    def _deduplicate_products(
        self, products: list[dict[str, Any]]
    ) -> tuple[list[dict[str, Any]], int]:
        """Deduplicate products based on vendor code.

        When duplicates are found:
        - Keep the product with the lowest unit_price
        - Store all source variants in _duplicate_sources metadata

        Args:
            products: List of products from all sources

        Returns:
            Tuple of (unique_products, duplicates_removed_count)
        """
        if not products:
            return [], 0

        # Group by vendor_code
        by_vendor_code: dict[str, list[dict[str, Any]]] = {}
        for product in products:
            vendor_code = product.get("vendor_code")
            if not vendor_code:
                continue

            if vendor_code not in by_vendor_code:
                by_vendor_code[vendor_code] = []
            by_vendor_code[vendor_code].append(product)

        # Deduplicate within each group
        unique_products = []
        duplicates_removed = 0

        for vendor_code, group in by_vendor_code.items():
            if len(group) == 1:
                # No duplicates
                unique_products.append(group[0])
            else:
                # Duplicates found - keep cheapest
                duplicates_removed += len(group) - 1

                # Sort by price (handle None values)
                valid_price_products = [
                    p for p in group if p.get("unit_price") is not None
                ]

                if not valid_price_products:
                    # No valid prices, keep first one
                    best_product = group[0]
                else:
                    # Keep cheapest
                    best_product = min(
                        valid_price_products, key=lambda p: float(p["unit_price"])
                    )

                # Add metadata about duplicate sources
                best_product["_duplicate_sources"] = [
                    {
                        "source_name": p["_source_name"],
                        "unit_price": p.get("unit_price"),
                        "url": p["_source_url"],
                    }
                    for p in group
                ]
                best_product["_price_variance"] = self._calculate_price_variance(group)

                unique_products.append(best_product)

        logger.debug(
            f"Deduplication: {len(products)} total -> "
            f"{len(unique_products)} unique ({duplicates_removed} duplicates removed)"
        )

        return unique_products, duplicates_removed

    def _calculate_price_variance(
        self, products: list[dict[str, Any]]
    ) -> dict[str, Any] | None:
        """Calculate price variance statistics for duplicate products.

        Args:
            products: List of duplicate products with same vendor_code

        Returns:
            Dict with min, max, mean, variance_pct or None if insufficient data
        """
        prices = [
            float(p["unit_price"]) for p in products if p.get("unit_price") is not None
        ]

        if len(prices) < 2:
            return None

        min_price = min(prices)
        max_price = max(prices)
        mean_price = sum(prices) / len(prices)
        variance_pct = (
            ((max_price - min_price) / mean_price * 100) if mean_price > 0 else 0
        )

        return {
            "min": round(min_price, 2),
            "max": round(max_price, 2),
            "mean": round(mean_price, 2),
            "variance_pct": round(variance_pct, 1),
            "sources_count": len(prices),
        }
