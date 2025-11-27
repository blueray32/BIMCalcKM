"""Crail4 AI API client for pricing data extraction."""

from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any

import httpx


class Crail4Client:
    """Client for Crail4 AI / Crawl4AI cloud scraping API."""

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        source_url: str | None = None,
    ):
        self.api_key = api_key or os.getenv("CRAIL4_API_KEY")
        self.base_url = base_url or os.getenv(
            "CRAIL4_BASE_URL", "https://www.crawl4ai-cloud.com/query"
        )
        self.source_url = source_url or os.getenv("CRAIL4_SOURCE_URL")
        self.cache_mode = os.getenv("CRAIL4_CACHE_MODE", "bypass")
        self.json_css_schema = self._load_optional_json(
            os.getenv("CRAIL4_JSON_CSS_SCHEMA_PATH")
        )

        if not self.api_key:
            raise ValueError("CRAIL4_API_KEY environment variable not set")

        self.client = httpx.AsyncClient(
            timeout=60.0,
            headers={
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.114 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.5",
            }
        )

    def _load_optional_json(self, path: str | None) -> dict[str, Any] | None:
        if not path:
            return None
        schema_path = Path(path)
        if not schema_path.exists():
            return None
        try:
            return json.loads(schema_path.read_text())
        except json.JSONDecodeError:
            return None

    async def fetch_all_items(
        self,
        classification_filter: list[str] | None = None,
        updated_since: str | None = None,
        region: str | None = None,
        url: str | None = None,
    ) -> list[dict]:
        """Fetch all items from configured sources."""
        all_items = []
        
        sources = [
            {
                "url": "https://www.tlc-direct.co.uk/Main_Index/Wiring_Accessories_Menu_Index/A_White_All/BG_NEXUS/index.html",
                "classification_code": "Pr_65_70_48",  # Switches/Sockets
                "classification_scheme": "UniClass2015"
            },
            {
                "url": "https://www.tlc-direct.co.uk/Main_Index/Cable_Index/Twin_and_Earth/index.html",
                "classification_code": "Pr_65_70_13",  # Cable
                "classification_scheme": "UniClass2015"
            }
        ]

        for source in sources:
            try:
                items = await self._fetch_with_browser(
                    source["url"], 
                    source["classification_code"], 
                    source["classification_scheme"]
                )
                all_items.extend(items)
            except Exception as e:
                print(f"Error fetching from {source['url']}: {e}")
                
        return all_items

    async def _fetch_with_browser(self, url: str, class_code: str, class_scheme: str) -> list[dict]:
        """Fetch and extract data using headless browser."""
        from playwright.async_api import async_playwright

        async with async_playwright() as p:
            # Connect to the browser service
            cdp_url = os.getenv("PLAYWRIGHT_CDP_URL", "ws://browser:3000")
            browser = await p.chromium.connect_over_cdp(cdp_url)
            context = browser.contexts[0]
            page = await context.new_page()
            await page.set_viewport_size({"width": 1920, "height": 1080})
            
            # Capture console logs
            page.on("console", lambda msg: print(f"Browser console: {msg.text}"))
            
            try:
                print(f"Navigating to {url} with headless browser...")
                await page.goto(url, wait_until="networkidle", timeout=60000)
                
                title = await page.title()
                print(f"Page title: {title}")
                
                # Wait for content to load
                try:
                    print("Waiting for product links...")
                    await page.wait_for_selector("a.product__description-link", timeout=10000)
                    print("Product links found!")
                except Exception as e:
                    print(f"Timeout waiting for selector: {e}")
                
                # Extract data using schema selectors
                # Pass classification data to the browser script
                items = await page.evaluate("""([classCode, classScheme]) => {
                    const items = [];
                    const seenCodes = new Set();
                    // Find all description links first, as we know they exist
                    const descLinks = document.querySelectorAll('a.product__description-link');
                    console.log(`Found ${descLinks.length} description links`);
                    
                    descLinks.forEach(descEl => {
                        // Find the container row (tr)
                        const row = descEl.closest('tr');
                        if (!row) {
                            console.log("Description link not inside a tr!");
                            return;
                        }
                        
                        const codeEl = row.querySelector('a.product__code-link');
                        // Price might be in a different column or structure
                        // Let's try to find any price-like element in the row
                        const priceEl = row.querySelector('.product__price .price_red') || row.querySelector('.product__price .price-breaks__price p');
                        
                        if (codeEl) {
                            const code = codeEl.innerText.trim();
                            if (seenCodes.has(code)) return;
                            seenCodes.add(code);

                            let price = priceEl ? priceEl.innerText.trim() : "0.00";
                            price = price.replace(/[^\d.]/g, ''); // Remove currency symbol
                            
                            items.push({
                                description: descEl.innerText.trim(),
                                vendor_code: code,
                                unit_price: price,
                                unit: 'each',
                                currency: 'GBP',
                                classification_code: classCode,
                                classification_scheme: classScheme
                            });
                        } else {
                            console.log("Missing code element for " + descEl.innerText);
                        }
                    });
                    console.log(`Extracted ${items.length} items`);
                    return items;
                }""", [class_code, class_scheme])
                print(f"Extracted {len(items)} items from browser.")
                return items
            finally:
                await page.close()

        """Fetch price items by scraping source content via Crawl4AI cloud."""
        target_url = url or self.source_url
        if not target_url:
            raise ValueError("CRAIL4_SOURCE_URL environment variable not set")

        # Check if we should use browser (e.g. for TLC)
        use_browser = "tlc-direct.co.uk" in target_url

        if use_browser:
            try:
                return await self._fetch_with_browser(target_url)
            except Exception as e:
                print(f"Browser fetch failed: {e}, falling back to API")

        payload: dict[str, Any] = {
            "apikey": self.api_key,
            "url": target_url,
            "cache_mode": self.cache_mode,
        }
        
        # ... rest of the method ...
        if classification_filter:
            payload["classification_filter"] = classification_filter
        if isinstance(updated_since, datetime):
            payload["updated_since"] = updated_since.isoformat()
        elif updated_since:
            payload["updated_since"] = str(updated_since)
        if region:
            payload["region"] = region
        if self.json_css_schema:
            payload["json_css_schema"] = self.json_css_schema

        try:
            response = await self.client.post(self.base_url, json=payload)
            response.raise_for_status()
            data = response.json()
        except httpx.HTTPStatusError as exc:  # pragma: no cover - network failure
            raise RuntimeError(
                f"Crail4 API error: {exc.response.status_code} {exc.response.text}"
            ) from exc
        except httpx.RequestError as exc:  # pragma: no cover - network failure
            raise RuntimeError(f"Crail4 API request failed: {exc}") from exc

        if "items" in data and isinstance(data["items"], list):
            return data["items"]
        if "extractions" in data and isinstance(data["extractions"], list):
            return data["extractions"]
        if "content" in data:
            return [{"content": data["content"]}]
        return []

    def _parse_locally(self, html_content: str) -> list[dict]:
        return []

    async def fetch_delta(self, last_sync) -> list[dict]:
        """Fetch only items updated since last sync (delta query placeholder)."""
        return await self.fetch_all_items(updated_since=str(last_sync))

    async def close(self) -> None:
        """Close the HTTP client."""
        await self.client.aclose()

    async def __aenter__(self) -> Crail4Client:
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.close()
