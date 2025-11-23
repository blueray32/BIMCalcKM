"""Test Crail4 sync with mock data."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

from bimcalc.db.connection import get_session
from bimcalc.integration.classification_mapper import ClassificationMapper
from bimcalc.integration.crail4_transformer import Crail4Transformer


async def test_sync():
    """Test ETL with sample data."""

    fixture_path = Path("tests/fixtures/crail4_sample_response.json")
    with fixture_path.open() as handle:
        data = json.load(handle)

    raw_items = data["items"]
    print(f"Loaded {len(raw_items)} test items")

    async with get_session() as session:
        mapper = ClassificationMapper(session, "acme-construction")
        transformer = Crail4Transformer(mapper, "UniClass2015")

        valid, rejections = await transformer.transform_batch(raw_items)

        print(f"✅ Valid items: {len(valid)}")
        print(f"❌ Rejected: {sum(rejections.values())}")
        print(f"Rejection breakdown: {rejections}")

        if valid:
            import pprint

            print("\nSample transformed item:")
            pprint.pprint(valid[0])


if __name__ == "__main__":
    asyncio.run(test_sync())
