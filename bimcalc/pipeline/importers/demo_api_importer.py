"""Demo API importer for testing and learning.

Simulates a realistic vendor API without requiring actual HTTP calls.
Perfect for testing the pipeline system and understanding how API imports work.

This can be used as a template for implementing real vendor APIs.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator
from decimal import Decimal

from bimcalc.pipeline.base_importer import BaseImporter
from bimcalc.pipeline.types import PriceRecord

logger = logging.getLogger(__name__)


class DemoAPIImporter(BaseImporter):
    """Demo API importer that simulates a vendor API.

    Configuration:
    - regions: List of regions to generate data for (e.g., ["UK", "IE", "DE"])
    - items_per_region: Number of items to generate per region (default: 10)
    - simulate_delay: Simulate API delay in seconds (default: 0.1)
    - simulate_pagination: Split data into pages (default: True)
    - page_size: Items per page if pagination enabled (default: 5)

    This importer demonstrates:
    - Multi-region support
    - Pagination handling
    - Rate limiting
    - Realistic product data
    - Error handling patterns
    """

    # Sample product data that looks like real electrical/MEP products
    SAMPLE_PRODUCTS = [
        {
            "base_code": "CT-LAD",
            "description": "Cable Tray Ladder Type",
            "classification": 66,
            "unit": "m",
            "base_price": {"UK": 85.00, "IE": 92.50, "DE": 88.00},
        },
        {
            "base_code": "CB-90-200x50",
            "description": "Cable Tray Elbow 90° 200x50mm",
            "classification": 66,
            "unit": "ea",
            "base_price": {"UK": 42.50, "IE": 46.00, "DE": 44.00},
        },
        {
            "base_code": "CB-45-300x50",
            "description": "Cable Tray Elbow 45° 300x50mm",
            "classification": 66,
            "unit": "ea",
            "base_price": {"UK": 38.75, "IE": 42.00, "DE": 40.00},
        },
        {
            "base_code": "TEE-200x50",
            "description": "Cable Tray Tee 200x50mm",
            "classification": 66,
            "unit": "ea",
            "base_price": {"UK": 55.00, "IE": 59.50, "DE": 57.00},
        },
        {
            "base_code": "CROSS-200x50",
            "description": "Cable Tray Cross 200x50mm",
            "classification": 66,
            "unit": "ea",
            "base_price": {"UK": 68.00, "IE": 73.50, "DE": 70.50},
        },
        {
            "base_code": "REDUCER-300-200",
            "description": "Cable Tray Reducer 300-200mm",
            "classification": 66,
            "unit": "ea",
            "base_price": {"UK": 32.50, "IE": 35.00, "DE": 33.50},
        },
        {
            "base_code": "CP-200x50",
            "description": "Cable Tray Cover Plate 200x50mm",
            "classification": 66,
            "unit": "m",
            "base_price": {"UK": 18.00, "IE": 19.50, "DE": 18.50},
        },
        {
            "base_code": "SUSP-ADJ",
            "description": "Adjustable Cable Tray Suspension",
            "classification": 66,
            "unit": "ea",
            "base_price": {"UK": 12.50, "IE": 13.50, "DE": 13.00},
        },
        {
            "base_code": "COUPLER-200",
            "description": "Cable Tray Coupler 200mm",
            "classification": 66,
            "unit": "ea",
            "base_price": {"UK": 8.75, "IE": 9.50, "DE": 9.00},
        },
        {
            "base_code": "ENDCAP-200",
            "description": "Cable Tray End Cap 200mm",
            "classification": 66,
            "unit": "ea",
            "base_price": {"UK": 5.50, "IE": 6.00, "DE": 5.75},
        },
    ]

    async def fetch_data(self) -> AsyncIterator[PriceRecord]:
        """Simulate fetching data from a vendor API."""

        # Get configuration
        regions = self._get_config_value("regions", ["UK"])
        items_per_region = self._get_config_value("items_per_region", len(self.SAMPLE_PRODUCTS))
        simulate_delay = self._get_config_value("simulate_delay", 0.1)
        simulate_pagination = self._get_config_value("simulate_pagination", True)
        page_size = self._get_config_value("page_size", 5)

        self.logger.info(
            f"Demo API: Fetching data for regions {regions}, "
            f"{items_per_region} items per region"
        )

        # Generate data for each region
        for region in regions:
            self.logger.info(f"Demo API: Fetching {region} pricing data...")

            # Get currency for region
            currency = self._get_currency_for_region(region)

            # Limit products to requested count
            products = self.SAMPLE_PRODUCTS[:items_per_region]

            # Simulate pagination if enabled
            if simulate_pagination:
                pages = [
                    products[i : i + page_size]
                    for i in range(0, len(products), page_size)
                ]

                for page_num, page_products in enumerate(pages, 1):
                    self.logger.debug(
                        f"Demo API: Fetching {region} page {page_num}/{len(pages)} "
                        f"({len(page_products)} items)"
                    )

                    # Simulate API delay
                    if simulate_delay > 0:
                        await asyncio.sleep(simulate_delay)

                    # Yield records from this page
                    for product in page_products:
                        yield self._create_price_record(product, region, currency)
            else:
                # No pagination - yield all at once
                if simulate_delay > 0:
                    await asyncio.sleep(simulate_delay)

                for product in products:
                    yield self._create_price_record(product, region, currency)

        self.logger.info("Demo API: Fetch completed")

    def _create_price_record(
        self, product: dict, region: str, currency: str
    ) -> PriceRecord:
        """Create a PriceRecord from product template."""

        # Get region-specific price or default to UK
        base_prices = product["base_price"]
        price = base_prices.get(region, base_prices.get("UK", 0.0))

        # Create region-specific item code
        item_code = f"DEMO-{region}-{product['base_code']}"

        return PriceRecord(
            item_code=item_code,
            region=region,
            classification_code=product["classification"],
            description=f"{product['description']} [{region}]",
            unit=product["unit"],
            unit_price=Decimal(str(price)),
            currency=currency,
            source_currency=currency,
            sku=item_code,
            vendor_id="demo_vendor",
            source_name=self.source_name,
        )

    def _get_currency_for_region(self, region: str) -> str:
        """Get currency code for region."""
        currency_map = {
            "UK": "GBP",
            "IE": "EUR",
            "DE": "EUR",
            "FR": "EUR",
            "ES": "EUR",
            "IT": "EUR",
            "NL": "EUR",
            "BE": "EUR",
            "US": "USD",
            "CA": "CAD",
            "AU": "AUD",
        }
        return currency_map.get(region, "EUR")
