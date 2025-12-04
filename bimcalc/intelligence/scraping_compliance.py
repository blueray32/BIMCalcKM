"""Legal and ethical compliance utilities for web scraping in Price Scout.

This module ensures Price Scout operates within legal and ethical boundaries
by checking robots.txt, enforcing rate limits, and validating against ToS.
"""

from __future__ import annotations

import logging
import urllib.parse
import urllib.robotparser
from functools import lru_cache

import httpx

logger = logging.getLogger(__name__)


@lru_cache(maxsize=100)
def _get_robots_parser(base_url: str) -> urllib.robotparser.RobotFileParser | None:
    """Get cached robots.txt parser for a domain.

    Args:
        base_url: Base URL (scheme + netloc) of the site

    Returns:
        RobotFileParser instance or None if robots.txt not available
    """
    try:
        robots_url = f"{base_url}/robots.txt"

        # Use synchronous httpx for simplicity with lru_cache
        with httpx.Client(timeout=10.0) as client:
            response = client.get(robots_url, follow_redirects=True)

        if response.status_code == 404:
            logger.debug(f"No robots.txt at {robots_url}")
            return None

        if response.status_code != 200:
            logger.warning(f"Error fetching robots.txt: {response.status_code}")
            return None

        # Parse robots.txt
        rp = urllib.robotparser.RobotFileParser()
        rp.parse(response.text.splitlines())

        return rp

    except Exception as e:
        logger.error(f"Error parsing robots.txt for {base_url}: {e}")
        return None


def is_url_allowed(url: str, user_agent: str = "BIMCalc PriceScout/1.0") -> bool:
    """Check if URL is allowed per robots.txt.

    This function checks the robots.txt file for the domain and determines
    if the given user agent is allowed to access the URL.

    Args:
        url: The URL to check
        user_agent: User agent string to check against

    Returns:
        True if allowed (including if robots.txt doesn't exist or can't be fetched),
        False if explicitly disallowed

    Examples:
        >>> is_url_allowed("https://example.com/products")
        True
        >>> is_url_allowed("https://example.com/admin")
        False  # If robots.txt disallows /admin
    """
    try:
        # Parse URL to get base
        parsed = urllib.parse.urlparse(url)
        base_url = f"{parsed.scheme}://{parsed.netloc}"

        # Get robots parser (cached)
        rp = _get_robots_parser(base_url)

        if rp is None:
            # No robots.txt = allowed (fail open)
            logger.debug(f"No robots.txt for {base_url}, allowing access")
            return True

        # Check if URL is allowed
        allowed = rp.can_fetch(user_agent, url)

        if not allowed:
            logger.warning(f"Robots.txt disallows {url} for user-agent '{user_agent}'")

        return allowed

    except Exception as e:
        logger.error(f"Error checking robots.txt for {url}: {e}")
        # Fail open (allow on error) - but log the error
        return True


def get_crawl_delay(
    url: str, user_agent: str = "BIMCalc PriceScout/1.0"
) -> float | None:
    """Get crawl delay from robots.txt if specified.

    Args:
        url: URL to check
        user_agent: User agent string

    Returns:
        Crawl delay in seconds, or None if not specified
    """
    try:
        parsed = urllib.parse.urlparse(url)
        base_url = f"{parsed.scheme}://{parsed.netloc}"

        rp = _get_robots_parser(base_url)

        if rp is None:
            return None

        # Try to get crawl delay
        delay = rp.crawl_delay(user_agent)

        if delay:
            logger.info(f"Crawl delay for {base_url}: {delay}s")

        return delay

    except Exception as e:
        logger.error(f"Error getting crawl delay for {url}: {e}")
        return None


class ComplianceChecker:
    """Validates URLs against compliance rules before scraping."""

    def __init__(self, user_agent: str = "BIMCalc PriceScout/1.0"):
        self.user_agent = user_agent

    def check_url(self, url: str) -> tuple[bool, str | None]:
        """Check if URL is compliant for scraping.

        Args:
            url: URL to check

        Returns:
            Tuple of (is_allowed, reason_if_blocked)
        """
        # Check robots.txt
        if not is_url_allowed(url, self.user_agent):
            return False, "Disallowed by robots.txt"

        # Check URL scheme (only http/https)
        parsed = urllib.parse.urlparse(url)
        if parsed.scheme not in ["http", "https"]:
            return False, f"Invalid URL scheme: {parsed.scheme}"

        # All checks passed
        return True, None

    def get_recommended_delay(self, url: str, default: float = 2.0) -> float:
        """Get recommended delay between requests.

        Args:
            url: URL being accessed
            default: Default delay if not specified in robots.txt

        Returns:
            Recommended delay in seconds
        """
        robots_delay = get_crawl_delay(url, self.user_agent)

        if robots_delay is not None:
            # Respect robots.txt crawl-delay
            return max(robots_delay, default)

        return default
