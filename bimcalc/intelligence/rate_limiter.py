"""Rate limiting utilities for Price Scout web scraping.

Implements token bucket rate limiting on a per-domain basis to ensure
ethical scraping practices and avoid overloading supplier websites.
"""

from __future__ import annotations

import asyncio
import logging
import time
import urllib.parse
from collections import defaultdict
from typing import Dict

logger = logging.getLogger(__name__)


class RateLimiter:
    """Simple token bucket rate limiter per domain.

    Ensures minimum delay between requests to the same domain to avoid
    overloading servers and comply with ethical scraping practices.

    Example:
        >>> limiter = RateLimiter(delay_seconds=2.0)
        >>> await limiter.acquire("example.com")  # First call: no wait
        >>> await limiter.acquire("example.com")  # Second call: waits 2s
    """

    def __init__(self, delay_seconds: float = 2.0):
        """Initialize rate limiter.

        Args:
            delay_seconds: Minimum delay between requests to the same domain
        """
        self.delay = delay_seconds
        self.last_request: Dict[str, float] = defaultdict(float)
        self.lock = asyncio.Lock()

    async def acquire(self, domain: str) -> None:
        """Wait until rate limit allows next request to domain.

        Args:
            domain: Domain name (e.g., "example.com")
        """
        async with self.lock:
            now = time.time()
            last = self.last_request[domain]
            elapsed = now - last

            if elapsed < self.delay:
                wait = self.delay - elapsed
                logger.debug(f"Rate limiting {domain}: waiting {wait:.2f}s")
                await asyncio.sleep(wait)

            self.last_request[domain] = time.time()

    def get_domain_from_url(self, url: str) -> str:
        """Extract domain from URL.

        Args:
            url: Full URL

        Returns:
            Domain name (netloc)

        Example:
            >>> limiter.get_domain_from_url("https://example.com/path")
            'example.com'
        """
        parsed = urllib.parse.urlparse(url)
        return parsed.netloc


class DomainRateLimiter:
    """Advanced rate limiter with per-domain custom delays.

    Allows setting different rate limits for different domains,
    useful when suppliers specify different crawl delays in robots.txt.

    Example:
        >>> limiter = DomainRateLimiter(default_delay=2.0)
        >>> limiter.set_domain_delay("slow-site.com", 5.0)
        >>> await limiter.acquire("https://slow-site.com/page")  # Uses 5s delay
        >>> await limiter.acquire("https://fast-site.com/page")  # Uses 2s delay
    """

    def __init__(self, default_delay: float = 2.0):
        """Initialize domain rate limiter.

        Args:
            default_delay: Default delay for domains without custom settings
        """
        self.default_delay = default_delay
        self.domain_delays: Dict[str, float] = {}
        self.last_request: Dict[str, float] = defaultdict(float)
        self.lock = asyncio.Lock()

    def set_domain_delay(self, domain: str, delay: float) -> None:
        """Set custom delay for a specific domain.

        Args:
            domain: Domain name
            delay: Delay in seconds
        """
        self.domain_delays[domain] = delay
        logger.info(f"Set custom delay for {domain}: {delay}s")

    def get_delay_for_domain(self, domain: str) -> float:
        """Get delay for a specific domain.

        Args:
            domain: Domain name

        Returns:
            Delay in seconds (custom or default)
        """
        return self.domain_delays.get(domain, self.default_delay)

    async def acquire(self, url: str) -> None:
        """Wait until rate limit allows next request to URL's domain.

        Args:
            url: Full URL to access
        """
        # Extract domain
        parsed = urllib.parse.urlparse(url)
        domain = parsed.netloc

        # Get delay for this domain
        delay = self.get_delay_for_domain(domain)

        async with self.lock:
            now = time.time()
            last = self.last_request[domain]
            elapsed = now - last

            if elapsed < delay:
                wait = delay - elapsed
                logger.debug(f"Rate limiting {domain}: waiting {wait:.2f}s")
                await asyncio.sleep(wait)

            self.last_request[domain] = time.time()

    def reset_domain(self, domain: str) -> None:
        """Reset rate limit state for a domain.

        Useful for testing or when switching contexts.

        Args:
            domain: Domain to reset
        """
        if domain in self.last_request:
            del self.last_request[domain]
            logger.debug(f"Reset rate limit state for {domain}")

    def get_time_until_ready(self, url: str) -> float:
        """Get time until next request to URL's domain is allowed.

        Args:
            url: Full URL

        Returns:
            Seconds until ready (0 if ready now)
        """
        parsed = urllib.parse.urlparse(url)
        domain = parsed.netloc

        delay = self.get_delay_for_domain(domain)
        now = time.time()
        last = self.last_request.get(domain, 0)
        elapsed = now - last

        if elapsed >= delay:
            return 0

        return delay - elapsed
