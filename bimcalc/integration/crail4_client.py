"""Crail4 AI API client for pricing data extraction."""

from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

import httpx


class Crail4Client:
    """Client for Crail4 AI / Crawl4AI cloud scraping API."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        source_url: Optional[str] = None,
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

        self.client = httpx.AsyncClient(timeout=60.0)

    def _load_optional_json(self, path: Optional[str]) -> Optional[dict[str, Any]]:
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
        classification_filter: Optional[list[str]] = None,
        updated_since: Optional[str] = None,
        region: Optional[str] = None,
        url: Optional[str] = None,
    ) -> list[dict]:
        """Fetch price items by scraping source content via Crawl4AI cloud."""
        target_url = url or self.source_url
        if not target_url:
            raise ValueError("CRAIL4_SOURCE_URL environment variable not set")

        payload: dict[str, Any] = {
            "apikey": self.api_key,
            "url": target_url,
            "cache_mode": self.cache_mode,
        }

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

    async def fetch_delta(self, last_sync) -> list[dict]:
        """Fetch only items updated since last sync (delta query placeholder)."""
        return await self.fetch_all_items(updated_since=str(last_sync))

    async def close(self) -> None:
        """Close the HTTP client."""
        await self.client.aclose()

    async def __aenter__(self) -> "Crail4Client":
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.close()
