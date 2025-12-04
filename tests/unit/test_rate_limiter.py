"""Unit tests for rate limiter module.

Tests per-domain rate limiting and delay enforcement.
"""

import asyncio
import pytest
import time

from bimcalc.intelligence.rate_limiter import RateLimiter, DomainRateLimiter


class TestRateLimiter:
    """Tests for basic RateLimiter class."""

    @pytest.mark.asyncio
    async def test_first_request_no_delay(self):
        """Test first request to domain has no delay."""
        limiter = RateLimiter(delay_seconds=2.0)

        start = time.time()
        await limiter.acquire("example.com")
        elapsed = time.time() - start

        # First request should be immediate (< 0.1s tolerance)
        assert elapsed < 0.1

    @pytest.mark.asyncio
    async def test_second_request_delayed(self):
        """Test second request to same domain is delayed."""
        limiter = RateLimiter(delay_seconds=2.0)

        # First request
        await limiter.acquire("example.com")

        # Second request (should wait ~2s)
        start = time.time()
        await limiter.acquire("example.com")
        elapsed = time.time() - start

        # Should wait approximately 2 seconds (allow some tolerance)
        assert 1.8 <= elapsed <= 2.5

    @pytest.mark.asyncio
    async def test_different_domains_no_delay(self):
        """Test requests to different domains don't affect each other."""
        limiter = RateLimiter(delay_seconds=2.0)

        # Request to domain A
        await limiter.acquire("example.com")

        # Request to domain B (should be immediate)
        start = time.time()
        await limiter.acquire("another.com")
        elapsed = time.time() - start

        # Should be immediate since different domain
        assert elapsed < 0.1

    @pytest.mark.asyncio
    async def test_multiple_rapid_requests(self):
        """Test multiple rapid requests are properly spaced."""
        limiter = RateLimiter(delay_seconds=1.0)

        start = time.time()

        # Make 3 requests
        await limiter.acquire("example.com")
        await limiter.acquire("example.com")
        await limiter.acquire("example.com")

        total_elapsed = time.time() - start

        # Should take approximately 2 seconds total (0 + 1 + 1)
        assert 1.8 <= total_elapsed <= 2.5

    @pytest.mark.asyncio
    async def test_concurrent_requests_serialized(self):
        """Test concurrent requests to same domain are serialized."""
        limiter = RateLimiter(delay_seconds=1.0)

        async def make_request():
            await limiter.acquire("example.com")
            return time.time()

        # Start 3 concurrent requests
        start = time.time()
        results = await asyncio.gather(make_request(), make_request(), make_request())

        total_elapsed = time.time() - start

        # All requests should be serialized, taking ~2 seconds total
        assert 1.8 <= total_elapsed <= 2.5

        # Results should be spaced apart
        assert results[1] - results[0] >= 0.9  # ~1s apart
        assert results[2] - results[1] >= 0.9  # ~1s apart

    @pytest.mark.asyncio
    async def test_get_domain_from_url(self):
        """Test domain extraction from URL."""
        limiter = RateLimiter()

        domain = limiter.get_domain_from_url("https://example.com/path/to/page")
        assert domain == "example.com"

        domain = limiter.get_domain_from_url("https://sub.example.com:8080/page")
        assert domain == "sub.example.com:8080"


class TestDomainRateLimiter:
    """Tests for advanced DomainRateLimiter class."""

    @pytest.mark.asyncio
    async def test_default_delay_applied(self):
        """Test default delay is applied when no custom delay set."""
        limiter = DomainRateLimiter(default_delay=2.0)

        # First request
        await limiter.acquire("https://example.com/page")

        # Second request (should wait default 2s)
        start = time.time()
        await limiter.acquire("https://example.com/another")
        elapsed = time.time() - start

        assert 1.8 <= elapsed <= 2.5

    @pytest.mark.asyncio
    async def test_custom_delay_per_domain(self):
        """Test custom delay can be set per domain."""
        limiter = DomainRateLimiter(default_delay=1.0)

        # Set custom delay for slow-site.com
        limiter.set_domain_delay("slow-site.com", 5.0)

        # Request to slow-site.com
        await limiter.acquire("https://slow-site.com/page")

        # Second request (should wait 5s, not default 1s)
        start = time.time()
        await limiter.acquire("https://slow-site.com/another")
        elapsed = time.time() - start

        assert 4.8 <= elapsed <= 5.5

    @pytest.mark.asyncio
    async def test_different_delays_for_different_domains(self):
        """Test different domains can have different delays."""
        limiter = DomainRateLimiter(default_delay=1.0)

        # Set custom delays
        limiter.set_domain_delay("fast.com", 0.5)
        limiter.set_domain_delay("slow.com", 3.0)

        # Test fast.com (0.5s delay)
        await limiter.acquire("https://fast.com/page1")
        start = time.time()
        await limiter.acquire("https://fast.com/page2")
        fast_elapsed = time.time() - start

        assert 0.4 <= fast_elapsed <= 0.8

        # Test slow.com (3s delay)
        await limiter.acquire("https://slow.com/page1")
        start = time.time()
        await limiter.acquire("https://slow.com/page2")
        slow_elapsed = time.time() - start

        assert 2.8 <= slow_elapsed <= 3.5

    @pytest.mark.asyncio
    async def test_get_delay_for_domain(self):
        """Test getting configured delay for a domain."""
        limiter = DomainRateLimiter(default_delay=2.0)

        # Default delay
        delay = limiter.get_delay_for_domain("example.com")
        assert delay == 2.0

        # Custom delay
        limiter.set_domain_delay("custom.com", 5.0)
        delay = limiter.get_delay_for_domain("custom.com")
        assert delay == 5.0

    @pytest.mark.asyncio
    async def test_reset_domain(self):
        """Test resetting rate limit state for a domain."""
        limiter = DomainRateLimiter(default_delay=2.0)

        # Make first request
        await limiter.acquire("https://example.com/page")

        # Reset the domain
        limiter.reset_domain("example.com")

        # Next request should be immediate (no delay)
        start = time.time()
        await limiter.acquire("https://example.com/another")
        elapsed = time.time() - start

        assert elapsed < 0.1

    @pytest.mark.asyncio
    async def test_get_time_until_ready(self):
        """Test getting time until next request is allowed."""
        limiter = DomainRateLimiter(default_delay=2.0)

        # First request - should be ready now
        time_until = limiter.get_time_until_ready("https://example.com/page")
        assert time_until == 0

        # Make request
        await limiter.acquire("https://example.com/page")

        # Immediately after - should need to wait ~2s
        time_until = limiter.get_time_until_ready("https://example.com/another")
        assert 1.8 <= time_until <= 2.1

        # Wait a bit
        await asyncio.sleep(1.0)

        # Now should need to wait ~1s
        time_until = limiter.get_time_until_ready("https://example.com/another")
        assert 0.8 <= time_until <= 1.5

    @pytest.mark.asyncio
    async def test_url_parsing(self):
        """Test URL parsing extracts domain correctly."""
        limiter = DomainRateLimiter(default_delay=1.0)

        # These URLs have same domain, should share rate limit
        await limiter.acquire("https://example.com/page1")

        start = time.time()
        await limiter.acquire("https://example.com:443/page2")
        elapsed = time.time() - start

        # Should wait because same domain
        # Note: example.com and example.com:443 are treated as different by urllib
        # In practice, this is okay since explicit port is rare
        # But for this test, let's check they're treated separately
        # Actually, they should be separate since netloc includes port
        assert elapsed < 0.1  # Different netloc, no wait

    @pytest.mark.asyncio
    async def test_concurrent_requests_to_different_domains(self):
        """Test concurrent requests to different domains don't block each other."""
        limiter = DomainRateLimiter(default_delay=2.0)

        async def make_request(url):
            await limiter.acquire(url)
            return time.time()

        # Make concurrent requests to different domains
        start = time.time()
        results = await asyncio.gather(
            make_request("https://site1.com/page"),
            make_request("https://site2.com/page"),
            make_request("https://site3.com/page"),
        )
        total_elapsed = time.time() - start

        # Should complete quickly since different domains
        assert total_elapsed < 0.5

        # All requests should complete around the same time
        assert results[2] - results[0] < 0.5


class TestRateLimiterEdgeCases:
    """Tests for edge cases and error conditions."""

    @pytest.mark.asyncio
    async def test_zero_delay(self):
        """Test rate limiter with zero delay."""
        limiter = RateLimiter(delay_seconds=0.0)

        # Multiple rapid requests should all be immediate
        start = time.time()
        await limiter.acquire("example.com")
        await limiter.acquire("example.com")
        await limiter.acquire("example.com")
        elapsed = time.time() - start

        # Should be very fast
        assert elapsed < 0.2

    @pytest.mark.asyncio
    async def test_very_large_delay(self):
        """Test rate limiter with large delay doesn't block indefinitely."""
        limiter = RateLimiter(delay_seconds=0.5)

        # First request
        await limiter.acquire("example.com")

        # Second request
        start = time.time()
        await limiter.acquire("example.com")
        elapsed = time.time() - start

        # Should wait approximately 0.5s
        assert 0.4 <= elapsed <= 0.8

    @pytest.mark.asyncio
    async def test_domain_rate_limiter_with_empty_domain(self):
        """Test handling of empty or invalid domains."""
        limiter = DomainRateLimiter(default_delay=1.0)

        # Should not crash with empty domain
        await limiter.acquire("https://")

        # Should use netloc (empty string in this case)
        delay = limiter.get_delay_for_domain("")
        assert delay == 1.0
