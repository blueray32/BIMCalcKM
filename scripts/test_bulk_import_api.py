"""Test bulk import API endpoint via local CLI (no HTTP)."""

from __future__ import annotations

import asyncio

from bimcalc.db.connection import get_session
from bimcalc.integration.crail4_transformer import Crail4Transformer
from bimcalc.integration.classification_mapper import ClassificationMapper


async def test_cli_bulk_import():
    payload = {
        "org_id": "acme-construction",
        "source": "manual_test",
        "target_scheme": "UniClass2015",
        "items": [
            {
                "classification_code": "66",
                "classification_scheme": "UniClass2015",
                "description": "Cable Tray Elbow 90° Test",
                "unit": "ea",
                "unit_price": "45.50",
                "currency": "EUR",
                "vat_rate": "0.23",
                "vendor_code": "TEST-CLI-001",
            }
        ],
    }

    async with get_session() as session:
        mapper = ClassificationMapper(session, payload["org_id"])
        transformer = Crail4Transformer(mapper, payload["target_scheme"])
        items, rejections = await transformer.transform_batch(payload["items"])
        print(f"Transformed {len(items)} items, rejections: {rejections}")


if __name__ == "__main__":
    asyncio.run(test_cli_bulk_import())
