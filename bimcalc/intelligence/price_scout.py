"""Smart Price Scout: AI-powered price extraction agent with compliance."""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
from decimal import Decimal, InvalidOperation
from typing import Any

from redis.asyncio import Redis

from openai import AsyncOpenAI
from playwright.async_api import (
    async_playwright,
    TimeoutError as PlaywrightTimeoutError,
)
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)

from bimcalc.config import get_config
from bimcalc.intelligence.scraping_compliance import ComplianceChecker
from bimcalc.intelligence.rate_limiter import DomainRateLimiter

logger = logging.getLogger(__name__)


class SmartPriceScout:
    """AI Agent that browses supplier websites and extracts price data.

    Features:
    - Compliance checking (robots.txt)
    - Rate limiting per domain
    - Retry logic with exponential backoff
    - Price validation
    """

    def __init__(self):
        self.config = get_config()
        self.api_key = (
            os.getenv("PRICE_SCOUT_API_KEY")
            or self.config.llm.api_key
            or os.getenv("OPENAI_API_KEY")
        )

        if not self.api_key:
            raise ValueError("OPENAI_API_KEY is required for Smart Price Scout")

        self.client = AsyncOpenAI(api_key=self.api_key)
        self.model = self.config.llm.llm_model or "gpt-4-1106-preview"

        # Initialize compliance and rate limiting from config
        self.compliance_checker = ComplianceChecker(
            user_agent=self.config.price_scout.user_agent
        )
        self.rate_limiter = DomainRateLimiter(
            default_delay=self.config.price_scout.default_rate_limit_seconds
        )

        # Initialize Redis cache
        redis_url = os.getenv("REDIS_URL", "redis://redis:6379/0")
        self.redis = Redis.from_url(redis_url, decode_responses=True)
        self.cache_ttl = int(os.getenv("PRICE_SCOUT_CACHE_TTL", "86400"))

    async def extract(self, url: str, force_refresh: bool = False) -> dict[str, Any]:
        """Extract product details from a URL using LLM.

        Includes compliance checking, rate limiting, and retry logic.

        Args:
            url: URL to extract data from

        Returns:
            Extracted data dict with structure:
            {
                "page_type": "product_detail" | "product_list",
                "products": [...]
            }

        Raises:
            ValueError: If URL is not compliant (robots.txt disallows)
            Exception: If extraction fails after retries
        """
        logger.info(f"Scouting price from: {url}")

        # 0. Check Cache
        cache_key = f"price_scout:v1:{hashlib.md5(url.encode()).hexdigest()}"
        if not force_refresh:
            try:
                cached_data = await self.redis.get(cache_key)
                if cached_data:
                    logger.info("Cache hit! Returning cached data.")
                    return json.loads(cached_data)
            except Exception as e:
                logger.warning(f"Cache lookup failed: {e}")

        # 1. Check compliance (robots.txt) if enabled
        if self.config.price_scout.respect_robots_txt:
            is_allowed, reason = self.compliance_checker.check_url(url)
            if not is_allowed:
                logger.error(f"URL not compliant: {reason}")
                raise ValueError(f"Cannot scrape {url}: {reason}")
        else:
            logger.debug("Robots.txt compliance checking disabled")

        # 2. Apply rate limiting
        await self.rate_limiter.acquire(url)

        # 3. Get recommended delay from robots.txt
        recommended_delay = self.compliance_checker.get_recommended_delay(url)
        if recommended_delay > self.rate_limiter.default_delay:
            import urllib.parse

            domain = urllib.parse.urlparse(url).netloc
            self.rate_limiter.set_domain_delay(domain, recommended_delay)
            logger.info(
                f"Updated rate limit for {domain} to {recommended_delay}s (from robots.txt)"
            )

        # 4. Fetch with retry
        content = await self._fetch_page_content_with_retry(url)

        # 5. Analyze with LLM
        logger.info(f"Fetched content length: {len(content)} chars")
        extracted_data = await self._analyze_content(content, url)

        # 6. Check for error page type
        if extracted_data.get("page_type") == "error":
            error_msg = extracted_data.get("error_message", "Unknown error on page")
            logger.warning(f"Page error detected: {error_msg}")
            raise ValueError(f"Page error: {error_msg}")

        # 7. Validate extracted data
        self._validate_extraction(extracted_data)

        # 8. Save to Cache
        try:
            await self.redis.setex(
                cache_key, self.cache_ttl, json.dumps(extracted_data)
            )
        except Exception as e:
            logger.warning(f"Failed to save to cache: {e}")

        return extracted_data

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type(
            (PlaywrightTimeoutError, asyncio.TimeoutError, Exception)
        ),
    )
    async def _fetch_page_content_with_retry(self, url: str) -> str:
        """Fetch page content with retry logic.

        Args:
            url: URL to fetch

        Returns:
            Page content as text

        Raises:
            Exception: If all retries fail
        """
        try:
            return await self._fetch_page_content(url)
        except Exception as e:
            logger.warning(f"Fetch attempt failed for {url}: {e}")
            raise

    async def _fetch_page_content(self, url: str) -> str:
        """Fetch page content using Playwright."""
        async with async_playwright() as p:
            # Connect to existing browser service if available, else launch local
            cdp_url = os.getenv("PLAYWRIGHT_CDP_URL", "ws://browser:3000")

            try:
                browser = await p.chromium.connect_over_cdp(cdp_url)
                logger.info(f"Connected to remote browser at {cdp_url}")
            except Exception:
                logger.warning(
                    "Could not connect to remote browser, launching local instance"
                )
                browser = await p.chromium.launch(headless=True)

            try:
                context = await browser.new_context(
                    viewport={"width": 1920, "height": 1080},
                    user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                )
                page = await context.new_page()

                # Block resources to speed up loading
                await page.route(
                    "**/*",
                    lambda route: route.continue_()
                    if route.request.resource_type
                    in ["document", "script", "xhr", "fetch"]
                    else route.abort(),
                )

                logger.info(f"Navigating to {url}...")
                await page.goto(url, wait_until="domcontentloaded", timeout=60000)

                # Wait a bit for dynamic content
                await page.wait_for_timeout(2000)

                # Extract visible text and relevant structure
                # We use a script to get a clean text representation to save tokens
                content = await page.evaluate("""() => {
                    // Remove clutter
                    const removeSelectors = ['style', 'script', 'noscript', 'iframe', 'svg', 'footer', 'nav'];
                    removeSelectors.forEach(s => document.querySelectorAll(s).forEach(e => e.remove()));
                    
                    // Get text content with some structure preservation
                    return document.body.innerText;
                }""")

                return content[:50000]  # Limit context window usage

            finally:
                await browser.close()

    async def _analyze_content(self, content: str, url: str) -> dict[str, Any]:
        """Use LLM to extract structured data from text content."""

        system_prompt = """You are an expert procurement agent. Your job is to extract precise product pricing and specification data from raw website text.
        
        First, determine if the page is a "product_detail" (single item) or a "product_list" (category/search results).
        
        CRITICAL: If the page content indicates an error (e.g., "Page Not Found", "404", "Access Denied", "Captcha"), return:
        {
            "page_type": "error",
            "error_message": "Description of the error found on page",
            "products": []
        }

        Otherwise, return a JSON object with the following structure:
        {
            "page_type": "product_detail" | "product_list",
            "products": [
                {
                    "description": "Full product description",
                    "vendor_code": "Supplier SKU/Code",
                    "manufacturer_code": "Manufacturer Part Number",
                    "unit_price": 123.45,
                    "currency": "EUR",
                    "unit": "each",
                    "specifications": {"key": "value"}
                }
            ]
        }
        
        Rules:
        - For "product_detail", the "products" array should contain exactly one item.
        - For "product_list", extract all distinct products found in the list (up to 20).
        - If a field is not found, use null.
        - Ensure prices are numbers (exclude currency symbols).
        """

        user_prompt = f"""Extract product data from this webpage content:
        URL: {url}
        
        CONTENT:
        {content}
        """

        response = await self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            response_format={"type": "json_object"},
            temperature=0.1,
        )

        result = response.choices[0].message.content
        if not result:
            raise ValueError("Empty response from LLM")

        return json.loads(result)

    def _validate_extraction(self, data: dict) -> None:
        """Validate extracted data meets quality standards.

        Checks for:
        - Suspicious low/high prices
        - Missing required fields
        - Invalid data types

        Args:
            data: Extracted data dict

        Raises:
            ValueError: If critical validation failures occur
        """
        products = data.get("products", [])

        if not products:
            logger.warning("No products extracted from page")
            return

        # Price validation thresholds from config
        min_price = self.config.price_scout.min_price_threshold
        max_price = self.config.price_scout.max_price_threshold

        for idx, product in enumerate(products):
            price = product.get("unit_price")

            if price is None:
                logger.warning(f"Product {idx}: Missing unit_price")
                continue

            try:
                price_decimal = Decimal(str(price))

                # Check min threshold
                if price_decimal < min_price:
                    logger.warning(
                        f"Product {idx}: Suspicious low price: {price} "
                        f"(vendor_code: {product.get('vendor_code')})"
                    )

                # Check max threshold
                if price_decimal > max_price:
                    logger.warning(
                        f"Product {idx}: Suspicious high price: {price} "
                        f"(vendor_code: {product.get('vendor_code')})"
                    )

                # Check for negative prices
                if price_decimal < 0:
                    logger.error(f"Product {idx}: Negative price detected: {price}")
                    product["unit_price"] = None  # Invalidate

            except (ValueError, TypeError, InvalidOperation) as e:
                logger.error(f"Product {idx}: Invalid price format: {price} - {e}")
                product["unit_price"] = None

        # Log extraction summary
        valid_prices = sum(1 for p in products if p.get("unit_price") is not None)
        logger.info(
            f"Extraction validation: {len(products)} products, "
            f"{valid_prices} with valid prices"
        )

    async def close(self):
        await self.client.close()
        await self.redis.close()

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()
