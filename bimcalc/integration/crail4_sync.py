"""Crail4 AI → BIMCalc ETL orchestration script."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Optional

import httpx
from fastapi.encoders import jsonable_encoder

from bimcalc.db.connection import get_session
from bimcalc.integration.crail4_client import Crail4Client
from bimcalc.integration.classification_mapper import ClassificationMapper
from bimcalc.integration.crail4_transformer import Crail4Transformer

logger = logging.getLogger(__name__)


async def sync_crail4_prices(
    org_id: str,
    target_scheme: str = "UniClass2015",
    delta_days: Optional[int] = 7,
    classification_filter: Optional[list[str]] = None,
    region: Optional[str] = None,
) -> dict:
    """Execute Crail4 → BIMCalc end-to-end sync."""
    updated_since = None
    if delta_days:
        updated_since = datetime.utcnow() - timedelta(days=delta_days)

    async with get_session() as session:
        async with Crail4Client() as client:
            raw_items = await client.fetch_all_items(
                classification_filter=classification_filter,
                updated_since=updated_since,
                region=region,
            )

        logger.info("Fetched %s items from Crail4", len(raw_items))
        if not raw_items:
            return {
                "status": "no_data",
                "items_fetched": 0,
                "items_loaded": 0,
                "rejection_reasons": {},
            }

        mapper = ClassificationMapper(session, org_id)
        transformer = Crail4Transformer(mapper, target_scheme)
        valid_items, rejection_stats = await transformer.transform_batch(raw_items)
        logger.info(
            "Transformed %s items (%s rejected)",
            len(valid_items),
            sum(rejection_stats.values()),
        )

    if not valid_items:
        return {
            "status": "no_valid_items",
            "items_fetched": len(raw_items),
            "items_loaded": 0,
            "rejection_reasons": rejection_stats,
        }

    payload = {
        "org_id": org_id,
        "items": jsonable_encoder(valid_items),
        "source": "crail4_api",
        "target_scheme": target_scheme,
    }

    api_url = "http://localhost:8001/api/price-items/bulk-import"

    async with httpx.AsyncClient(timeout=300.0) as http_client:
        response = await http_client.post(api_url, json=payload)
        response.raise_for_status()
        result = response.json()

    result["transform_rejections"] = rejection_stats
    return result


async def scheduled_sync() -> None:
    """Run scheduled sync with default parameters."""
    try:
        result = await sync_crail4_prices(
            org_id="acme-construction",
            target_scheme="UniClass2015",
            delta_days=7,
            classification_filter=["62", "63", "64", "66", "67", "68"],
        )
        logger.info("Scheduled Crail4 sync result: %s", result)
    except Exception as exc:  # pragma: no cover - defensive logging
        logger.error("Scheduled Crail4 sync failed: %s", exc, exc_info=True)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(scheduled_sync())
