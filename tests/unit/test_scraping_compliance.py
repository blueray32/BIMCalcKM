"""Unit tests for web scraping compliance module.

Tests robots.txt checking, crawl delay detection, and compliance validation.
"""

from unittest.mock import Mock, patch

from bimcalc.intelligence.scraping_compliance import (
    is_url_allowed,
    get_crawl_delay,
    ComplianceChecker,
    _get_robots_parser,
)


class TestRobotsTxtChecking:
    """Tests for robots.txt compliance checking."""

    @patch("bimcalc.intelligence.scraping_compliance.httpx.Client")
    def test_is_url_allowed_when_allowed(self, mock_client_class):
        """Test URL is allowed when robots.txt permits."""
        # Setup mock
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = """
User-agent: *
Allow: /products
Disallow: /admin
"""
        mock_client = Mock()
        mock_client.__enter__ = Mock(return_value=mock_client)
        mock_client.__exit__ = Mock(return_value=False)
        mock_client.get = Mock(return_value=mock_response)
        mock_client_class.return_value = mock_client

        # Clear cache
        _get_robots_parser.cache_clear()

        # Test
        result = is_url_allowed("https://example.com/products/widget")

        assert result is True

    @patch("bimcalc.intelligence.scraping_compliance.httpx.Client")
    def test_is_url_allowed_when_disallowed(self, mock_client_class):
        """Test URL is disallowed when robots.txt blocks."""
        # Setup mock
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = """
User-agent: *
Disallow: /admin
"""
        mock_client = Mock()
        mock_client.__enter__ = Mock(return_value=mock_client)
        mock_client.__exit__ = Mock(return_value=False)
        mock_client.get = Mock(return_value=mock_response)
        mock_client_class.return_value = mock_client

        # Clear cache
        _get_robots_parser.cache_clear()

        # Test
        result = is_url_allowed("https://example.com/admin/users")

        assert result is False

    @patch("bimcalc.intelligence.scraping_compliance.httpx.Client")
    def test_is_url_allowed_when_no_robots_txt(self, mock_client_class):
        """Test URL is allowed when robots.txt doesn't exist."""
        # Setup mock
        mock_response = Mock()
        mock_response.status_code = 404
        mock_client = Mock()
        mock_client.__enter__ = Mock(return_value=mock_client)
        mock_client.__exit__ = Mock(return_value=False)
        mock_client.get = Mock(return_value=mock_response)
        mock_client_class.return_value = mock_client

        # Clear cache
        _get_robots_parser.cache_clear()

        # Test
        result = is_url_allowed("https://example.com/anything")

        # No robots.txt = allowed (fail open)
        assert result is True

    @patch("bimcalc.intelligence.scraping_compliance.httpx.Client")
    def test_is_url_allowed_respects_user_agent(self, mock_client_class):
        """Test different user agents get different permissions."""
        # Setup mock
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = """
User-agent: Googlebot
Allow: /

User-agent: BadBot
Disallow: /
"""
        mock_client = Mock()
        mock_client.__enter__ = Mock(return_value=mock_client)
        mock_client.__exit__ = Mock(return_value=False)
        mock_client.get = Mock(return_value=mock_response)
        mock_client_class.return_value = mock_client

        # Clear cache
        _get_robots_parser.cache_clear()

        # Test with Googlebot (allowed)
        result = is_url_allowed("https://example.com/page", user_agent="Googlebot")
        assert result is True

        # Clear cache again for new user agent
        _get_robots_parser.cache_clear()

        # Test with BadBot (disallowed)
        result = is_url_allowed("https://example.com/page", user_agent="BadBot")
        assert result is False

    @patch("bimcalc.intelligence.scraping_compliance.httpx.Client")
    def test_is_url_allowed_handles_errors_gracefully(self, mock_client_class):
        """Test error handling fails open (allows access)."""
        # Setup mock to raise exception
        mock_client = Mock()
        mock_client.__enter__ = Mock(return_value=mock_client)
        mock_client.__exit__ = Mock(return_value=False)
        mock_client.get = Mock(side_effect=Exception("Network error"))
        mock_client_class.return_value = mock_client

        # Clear cache
        _get_robots_parser.cache_clear()

        # Test
        result = is_url_allowed("https://example.com/page")

        # Should fail open (allow on error)
        assert result is True


class TestCrawlDelay:
    """Tests for crawl delay detection."""

    @patch("bimcalc.intelligence.scraping_compliance.httpx.Client")
    def test_get_crawl_delay_when_specified(self, mock_client_class):
        """Test crawl delay is returned when specified in robots.txt."""
        # Setup mock
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = """
User-agent: *
Crawl-delay: 5
"""
        mock_client = Mock()
        mock_client.__enter__ = Mock(return_value=mock_client)
        mock_client.__exit__ = Mock(return_value=False)
        mock_client.get = Mock(return_value=mock_response)
        mock_client_class.return_value = mock_client

        # Clear cache
        _get_robots_parser.cache_clear()

        # Test
        result = get_crawl_delay("https://example.com/page")

        assert result == 5.0

    @patch("bimcalc.intelligence.scraping_compliance.httpx.Client")
    def test_get_crawl_delay_when_not_specified(self, mock_client_class):
        """Test None is returned when crawl delay not specified."""
        # Setup mock
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = """
User-agent: *
Allow: /
"""
        mock_client = Mock()
        mock_client.__enter__ = Mock(return_value=mock_client)
        mock_client.__exit__ = Mock(return_value=False)
        mock_client.get = Mock(return_value=mock_response)
        mock_client_class.return_value = mock_client

        # Clear cache
        _get_robots_parser.cache_clear()

        # Test
        result = get_crawl_delay("https://example.com/page")

        assert result is None


class TestComplianceChecker:
    """Tests for ComplianceChecker class."""

    @patch("bimcalc.intelligence.scraping_compliance.is_url_allowed")
    def test_check_url_when_allowed(self, mock_is_allowed):
        """Test check_url returns True when URL is allowed."""
        mock_is_allowed.return_value = True

        checker = ComplianceChecker()
        is_allowed, reason = checker.check_url("https://example.com/page")

        assert is_allowed is True
        assert reason is None

    @patch("bimcalc.intelligence.scraping_compliance.is_url_allowed")
    def test_check_url_when_disallowed(self, mock_is_allowed):
        """Test check_url returns False with reason when disallowed."""
        mock_is_allowed.return_value = False

        checker = ComplianceChecker()
        is_allowed, reason = checker.check_url("https://example.com/admin")

        assert is_allowed is False
        assert reason == "Disallowed by robots.txt"

    def test_check_url_invalid_scheme(self):
        """Test check_url blocks invalid URL schemes."""
        checker = ComplianceChecker()
        is_allowed, reason = checker.check_url("ftp://example.com/file")

        assert is_allowed is False
        assert "Invalid URL scheme" in reason

    @patch("bimcalc.intelligence.scraping_compliance.get_crawl_delay")
    def test_get_recommended_delay_respects_robots_txt(self, mock_get_delay):
        """Test recommended delay respects robots.txt crawl-delay."""
        mock_get_delay.return_value = 10.0

        checker = ComplianceChecker()
        delay = checker.get_recommended_delay("https://example.com/page", default=2.0)

        # Should use robots.txt delay (10) instead of default (2)
        assert delay == 10.0

    @patch("bimcalc.intelligence.scraping_compliance.get_crawl_delay")
    def test_get_recommended_delay_uses_default_when_not_specified(
        self, mock_get_delay
    ):
        """Test recommended delay uses default when robots.txt doesn't specify."""
        mock_get_delay.return_value = None

        checker = ComplianceChecker()
        delay = checker.get_recommended_delay("https://example.com/page", default=2.0)

        # Should use default
        assert delay == 2.0

    @patch("bimcalc.intelligence.scraping_compliance.get_crawl_delay")
    def test_get_recommended_delay_enforces_minimum(self, mock_get_delay):
        """Test recommended delay never goes below default."""
        # robots.txt specifies 1s, but default is 2s
        mock_get_delay.return_value = 1.0

        checker = ComplianceChecker()
        delay = checker.get_recommended_delay("https://example.com/page", default=2.0)

        # Should enforce minimum (default)
        assert delay == 2.0


class TestCaching:
    """Tests for robots.txt parser caching."""

    @patch("bimcalc.intelligence.scraping_compliance.httpx.Client")
    def test_robots_parser_is_cached(self, mock_client_class):
        """Test robots.txt parser is cached between calls."""
        # Setup mock
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = "User-agent: *\nAllow: /"
        mock_client = Mock()
        mock_client.__enter__ = Mock(return_value=mock_client)
        mock_client.__exit__ = Mock(return_value=False)
        mock_client.get = Mock(return_value=mock_response)
        mock_client_class.return_value = mock_client

        # Clear cache
        _get_robots_parser.cache_clear()

        # First call
        is_url_allowed("https://example.com/page1")

        # Second call to same domain
        is_url_allowed("https://example.com/page2")

        # Should only fetch robots.txt once (cached)
        assert mock_client.get.call_count == 1
