"""Price Scout → BIMCalc ETL orchestration script.

Phase 2 Enhanced: Multi-source parallel fetching with intelligent aggregation.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta

import httpx
from fastapi.encoders import jsonable_encoder

from bimcalc.db.connection import get_session
from bimcalc.integration.classification_mapper import ClassificationMapper
from bimcalc.intelligence.multi_source_orchestrator import MultiSourceOrchestrator
from bimcalc.integration.price_scout_transformer import PriceScoutTransformer

logger = logging.getLogger(__name__)


async def sync_price_scout_prices(
    org_id: str,
    target_scheme: str = "UniClass2015",
    delta_days: int | None = 7,
    classification_filter: list[str] | None = None,
    region: str | None = None,
    full_sync: bool = False,
) -> dict:
    """Execute Price Scout → BIMCalc end-to-end sync.

    Phase 2: Multi-source parallel fetching with intelligent aggregation.

    Args:
        org_id: Organization ID to sync prices for
        target_scheme: Target classification scheme (default: UniClass2015)
        delta_days: Not used in multi-source mode (kept for compatibility)
        classification_filter: Optional classification codes to filter
        region: Optional region filter
        full_sync: Whether to force refresh cache

    Returns:
        Dict with import results and statistics
    """
    updated_since = None
    if delta_days:
        updated_since = datetime.utcnow() - timedelta(days=delta_days)

    # Store multi-source stats for result
    multi_source_stats = {}

    async with get_session() as session:
        # Use MultiSourceOrchestrator for parallel fetching
        logger.info(f"Starting multi-source price sync for org: {org_id}")

        async with MultiSourceOrchestrator(org_id=org_id, session=session) as orchestrator:
            # Fetch from all enabled sources in parallel
            multi_result = await orchestrator.fetch_all(force_refresh=full_sync)

            # Store stats for result
            multi_source_stats = multi_result.stats.copy()
            multi_source_stats["errors"] = multi_result.errors.copy()

            # Log multi-source statistics
            logger.info(
                f"Multi-source fetch complete: "
                f"{multi_result.stats['sources_succeeded']}/{multi_result.stats['sources_attempted']} sources succeeded, "
                f"{multi_result.stats['unique_products']} unique products "
                f"({multi_result.stats['duplicates_removed']} duplicates removed)"
            )

            # Log any errors
            if multi_result.errors:
                for error in multi_result.errors:
                    logger.warning(
                        f"Source {error['source']} failed: {error['error']}"
                    )

            raw_items = multi_result.products

        # Transform items using existing pipeline
        logger.info(f"Fetched {len(raw_items)} unique items from {multi_result.stats['sources_succeeded']} sources")

        if not raw_items:
            logger.info("No items fetched from Price Scout")
            valid_items = []
            rejection_stats = {}
        else:
            mapper = ClassificationMapper(session, org_id)
            transformer = PriceScoutTransformer(mapper, target_scheme)
            valid_items, rejection_stats = await transformer.transform_batch(raw_items)
            logger.info(
                "Transformed %s items (%s rejected)",
                len(valid_items),
                sum(rejection_stats.values()),
            )

    payload = {
        "org_id": org_id,
        "items": jsonable_encoder(valid_items),
        "source": "price_scout_api",
        "target_scheme": target_scheme,
    }

    import os
    base_url = os.getenv("API_BASE_URL", "http://localhost:8001")
    api_url = f"{base_url}/api/price-items/bulk-import"

    async with httpx.AsyncClient(timeout=300.0) as http_client:
        response = await http_client.post(api_url, json=payload)
        response.raise_for_status()
        result = response.json()

    # Add Phase 2 statistics
    result["transform_rejections"] = rejection_stats
    result["multi_source_stats"] = multi_source_stats
    return result


async def scheduled_sync() -> None:
    """Run scheduled sync with default parameters."""
    try:
        result = await sync_price_scout_prices(
            org_id="acme-construction",
            target_scheme="UniClass2015",
            delta_days=7,
            classification_filter=["62", "63", "64", "66", "67", "68"],
        )
        logger.info("Scheduled Price Scout sync result: %s", result)
    except Exception as exc:  # pragma: no cover - defensive logging
        logger.error("Scheduled Price Scout sync failed: %s", exc, exc_info=True)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(scheduled_sync())
