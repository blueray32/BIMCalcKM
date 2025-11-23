"""Template for API-based importers (RS Components, Farnell, Trimble Luckins, etc.).

Demonstrates the pattern for REST API data sources with rate limiting
and pagination support.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator
from decimal import Decimal

import aiohttp

from bimcalc.pipeline.base_importer import BaseImporter
from bimcalc.pipeline.types import PriceRecord

logger = logging.getLogger(__name__)


class APIImporter(BaseImporter):
    """Base class for REST API-based importers.

    Configuration required:
    - api_base_url: Base URL for API
    - api_key: Authentication key (stored in env var recommended)
    - region: Geographic region
    - rate_limit_delay: Seconds between requests (optional, default: 0.1)
    - batch_size: Records per API call (optional, default: 100)

    Subclasses must implement:
    - _fetch_batch(): Fetch one batch/page from API
    - _parse_api_response(): Parse API response to PriceRecords
    """

    async def fetch_data(self) -> AsyncIterator[PriceRecord]:
        """Fetch data from API with pagination and rate limiting."""

        api_base_url = self._get_config_value("api_base_url", required=True)
        api_key = self._get_config_value("api_key", required=True)
        region = self._get_config_value("region", required=True)
        rate_limit_delay = self._get_config_value("rate_limit_delay", 0.1)
        batch_size = self._get_config_value("batch_size", 100)

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Accept": "application/json",
        }

        async with aiohttp.ClientSession(headers=headers) as session:
            offset = 0
            has_more = True

            while has_more:
                try:
                    # Fetch one batch
                    response_data = await self._fetch_batch(
                        session, api_base_url, offset, batch_size
                    )

                    if not response_data:
                        break

                    # Parse and yield records
                    records = self._parse_api_response(response_data, region)

                    for record in records:
                        record.source_name = self.source_name
                        yield record

                    # Check pagination
                    has_more = len(records) >= batch_size
                    offset += len(records)

                    self.logger.debug(
                        f"Fetched {len(records)} records (total: {offset})"
                    )

                    # Rate limiting
                    if has_more and rate_limit_delay > 0:
                        await asyncio.sleep(rate_limit_delay)

                except Exception as e:
                    self.logger.error(f"Batch fetch error at offset {offset}: {e}")
                    break

        self.logger.info(f"API import completed: {offset} total records")

    async def _fetch_batch(
        self, session: aiohttp.ClientSession, base_url: str, offset: int, limit: int
    ) -> dict:
        """Fetch one batch from API.

        Args:
            session: aiohttp session
            base_url: API base URL
            offset: Pagination offset
            limit: Batch size

        Returns:
            API response as dict

        Raises:
            Exception: On API errors
        """
        url = f"{base_url}/prices?offset={offset}&limit={limit}"

        async with session.get(url) as response:
            response.raise_for_status()
            return await response.json()

    def _parse_api_response(self, data: dict, region: str) -> list[PriceRecord]:
        """Parse API response to list of PriceRecords.

        Args:
            data: API response dict
            region: Geographic region

        Returns:
            List of PriceRecord objects
        """
        # This is a template - subclasses should override with actual parsing logic
        records = []

        items = data.get("items", [])

        for item in items:
            try:
                record = PriceRecord(
                    item_code=item["item_code"],
                    region=region,
                    classification_code=int(item["classification_code"]),
                    description=item["description"],
                    unit=item["unit"],
                    unit_price=Decimal(str(item["price"])),
                    currency=item.get("currency", "EUR"),
                    source_currency=item.get("currency", "EUR"),
                    sku=item.get("sku", item["item_code"]),
                    vendor_id=item.get("vendor_id"),
                    source_name=self.source_name,
                )

                records.append(record)

            except (KeyError, ValueError, TypeError) as e:
                self.logger.warning(f"Failed to parse API item: {e}")
                continue

        return records


class RSComponentsImporter(APIImporter):
    """RS Components API importer.

    Specialized for RS Components API format and authentication.
    """

    async def _fetch_batch(
        self, session: aiohttp.ClientSession, base_url: str, offset: int, limit: int
    ) -> dict:
        """Fetch from RS Components API."""
        # RS-specific endpoint structure
        url = f"{base_url}/v1/products/search"
        params = {
            "offset": offset,
            "limit": limit,
            "searchTerm": "*",  # Get all products
        }

        async with session.get(url, params=params) as response:
            response.raise_for_status()
            return await response.json()

    def _parse_api_response(self, data: dict, region: str) -> list[PriceRecord]:
        """Parse RS Components API response."""
        records = []

        products = data.get("products", [])

        for product in products:
            try:
                # RS-specific field mapping
                stock_number = product["stockNumber"]
                description = product["displayName"]

                # RS provides pricing in nested structure
                pricing = product.get("pricing", {})
                unit_price = Decimal(str(pricing.get("unitPrice", 0)))
                currency = pricing.get("currency", "GBP")

                record = PriceRecord(
                    item_code=stock_number,
                    region=region,
                    classification_code=9999,  # Would need category mapping
                    description=description,
                    unit="ea",
                    unit_price=unit_price,
                    currency=currency,
                    source_currency=currency,
                    sku=stock_number,
                    vendor_id="rs_components",
                    source_name=self.source_name,
                )

                records.append(record)

            except (KeyError, ValueError) as e:
                self.logger.warning(f"Failed to parse RS product: {e}")
                continue

        return records
