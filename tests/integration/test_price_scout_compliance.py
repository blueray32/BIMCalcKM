"""Integration tests for Price Scout compliance features.

Tests end-to-end flow with robots.txt checking, rate limiting, and price validation.
"""

import pytest
import asyncio
import time
from unittest.mock import Mock, patch, AsyncMock
from decimal import Decimal

from bimcalc.intelligence.price_scout import SmartPriceScout
from bimcalc.intelligence.scraping_compliance import ComplianceChecker
from bimcalc.intelligence.rate_limiter import DomainRateLimiter
from bimcalc.config import PriceScoutConfig, AppConfig


@pytest.fixture
def compliance_config():
    """Create test config with compliance enabled."""
    config = Mock(spec=AppConfig)
    config.price_scout = PriceScoutConfig(
        respect_robots_txt=True,
        user_agent="BIMCalc PriceScout/1.0 (Test)",
        default_rate_limit_seconds=1.0,
        min_price_threshold=Decimal("0.01"),
        max_price_threshold=Decimal("10000.00"),
        retry_attempts=3,
    )
    config.llm = Mock()
    config.llm.api_key = "test-key"
    config.llm.llm_model = "gpt-4-1106-preview"
    return config


@pytest.mark.integration
class TestComplianceIntegration:
    """Integration tests for compliance workflow."""

    @pytest.mark.asyncio
    @patch("bimcalc.intelligence.scraping_compliance.httpx.Client")
    @patch("bimcalc.intelligence.price_scout.async_playwright")
    @patch("bimcalc.intelligence.price_scout.AsyncOpenAI")
    async def test_compliant_url_extraction_succeeds(
        self, mock_openai, mock_playwright, mock_http_client, compliance_config
    ):
        """Test extraction succeeds when URL is compliant."""
        # Mock robots.txt (allows access)
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = "User-agent: *\nAllow: /"
        mock_client = Mock()
        mock_client.__enter__ = Mock(return_value=mock_client)
        mock_client.__exit__ = Mock(return_value=False)
        mock_client.get = Mock(return_value=mock_response)
        mock_http_client.return_value = mock_client

        # Mock browser
        mock_browser = AsyncMock()
        mock_context = AsyncMock()
        mock_page = AsyncMock()
        mock_page.evaluate = AsyncMock(return_value="Sample product page content")
        mock_context.new_page = AsyncMock(return_value=mock_page)
        mock_browser.new_context = AsyncMock(return_value=mock_context)
        mock_browser.close = AsyncMock()

        mock_p = AsyncMock()
        mock_p.chromium.launch = AsyncMock(return_value=mock_browser)
        mock_playwright.return_value.__aenter__ = AsyncMock(return_value=mock_p)
        mock_playwright.return_value.__aexit__ = AsyncMock()

        # Mock OpenAI
        mock_completion = Mock()
        mock_completion.choices = [
            Mock(
                message=Mock(
                    content='{"page_type": "product_detail", "products": [{"vendor_code": "A123", "unit_price": 10.50, "currency": "EUR", "unit": "ea", "description": "Test Product"}]}'
                )
            )
        ]
        mock_client_instance = AsyncMock()
        mock_client_instance.chat.completions.create = AsyncMock(
            return_value=mock_completion
        )
        mock_client_instance.close = AsyncMock()
        mock_openai.return_value = mock_client_instance

        # Test extraction
        with patch("bimcalc.intelligence.price_scout.get_config", return_value=compliance_config):
            scout = SmartPriceScout()
            result = await scout.extract("https://example.com/products/test")

        # Should succeed
        assert result["page_type"] == "product_detail"
        assert len(result["products"]) == 1
        assert result["products"][0]["unit_price"] == 10.50

    @pytest.mark.asyncio
    @patch("bimcalc.intelligence.scraping_compliance.httpx.Client")
    async def test_non_compliant_url_raises_error(
        self, mock_http_client, compliance_config
    ):
        """Test extraction fails when URL is disallowed by robots.txt."""
        # Mock robots.txt (disallows access)
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = "User-agent: *\nDisallow: /products"
        mock_client = Mock()
        mock_client.__enter__ = Mock(return_value=mock_client)
        mock_client.__exit__ = Mock(return_value=False)
        mock_client.get = Mock(return_value=mock_response)
        mock_http_client.return_value = mock_client

        # Clear cache
        from bimcalc.intelligence.scraping_compliance import _get_robots_parser
        _get_robots_parser.cache_clear()

        # Test extraction
        with patch("bimcalc.intelligence.price_scout.get_config", return_value=compliance_config):
            scout = SmartPriceScout()

            with pytest.raises(ValueError, match="robots.txt"):
                await scout.extract("https://example.com/products/test")

    @pytest.mark.asyncio
    async def test_rate_limiting_enforced(self, compliance_config):
        """Test rate limiting delays between requests."""
        compliance_config.price_scout.default_rate_limit_seconds = 0.5

        with patch("bimcalc.intelligence.price_scout.get_config", return_value=compliance_config):
            # Disable robots.txt for this test
            compliance_config.price_scout.respect_robots_txt = False

            # Mock everything to make extraction fast
            with patch.object(
                SmartPriceScout, "_fetch_page_content_with_retry", new_callable=AsyncMock
            ) as mock_fetch:
                mock_fetch.return_value = "test content"

                with patch.object(
                    SmartPriceScout, "_analyze_content", new_callable=AsyncMock
                ) as mock_analyze:
                    mock_analyze.return_value = {
                        "page_type": "product_detail",
                        "products": [{"unit_price": 10.0}],
                    }

                    scout = SmartPriceScout()

                    # First request - should be fast
                    start = time.time()
                    await scout.extract("https://example.com/page1")
                    first_elapsed = time.time() - start
                    assert first_elapsed < 0.2  # Fast

                    # Second request - should be delayed
                    start = time.time()
                    await scout.extract("https://example.com/page2")
                    second_elapsed = time.time() - start
                    assert 0.4 <= second_elapsed <= 0.8  # ~0.5s delay

    @pytest.mark.asyncio
    @patch("bimcalc.intelligence.price_scout.async_playwright")
    @patch("bimcalc.intelligence.price_scout.AsyncOpenAI")
    async def test_price_validation_invalidates_bad_prices(
        self, mock_openai, mock_playwright, compliance_config
    ):
        """Test price validation catches and invalidates bad prices."""
        # Disable compliance checks for simplicity
        compliance_config.price_scout.respect_robots_txt = False

        # Mock browser
        mock_browser = AsyncMock()
        mock_context = AsyncMock()
        mock_page = AsyncMock()
        mock_page.evaluate = AsyncMock(return_value="Product content")
        mock_context.new_page = AsyncMock(return_value=mock_page)
        mock_browser.new_context = AsyncMock(return_value=mock_context)
        mock_browser.close = AsyncMock()

        mock_p = AsyncMock()
        mock_p.chromium.launch = AsyncMock(return_value=mock_browser)
        mock_playwright.return_value.__aenter__ = AsyncMock(return_value=mock_p)
        mock_playwright.return_value.__aexit__ = AsyncMock()

        # Mock OpenAI with some bad prices
        mock_completion = Mock()
        mock_completion.choices = [
            Mock(
                message=Mock(
                    content='{"page_type": "product_list", "products": ['
                    '{"vendor_code": "A", "unit_price": 10.0, "description": "Good"},'
                    '{"vendor_code": "B", "unit_price": -5.0, "description": "Negative"},'
                    '{"vendor_code": "C", "unit_price": "invalid", "description": "Bad format"}'
                    "]}"
                )
            )
        ]
        mock_client_instance = AsyncMock()
        mock_client_instance.chat.completions.create = AsyncMock(
            return_value=mock_completion
        )
        mock_client_instance.close = AsyncMock()
        mock_openai.return_value = mock_client_instance

        # Test extraction
        with patch("bimcalc.intelligence.price_scout.get_config", return_value=compliance_config):
            scout = SmartPriceScout()
            result = await scout.extract("https://example.com/products")

        # Check validation results
        products = result["products"]
        assert len(products) == 3

        # Good price should remain valid
        assert products[0]["unit_price"] == 10.0

        # Bad prices should be invalidated (set to None)
        assert products[1]["unit_price"] is None  # Negative
        assert products[2]["unit_price"] is None  # Invalid format


@pytest.mark.integration
class TestRetryLogic:
    """Integration tests for retry logic."""

    @pytest.mark.asyncio
    async def test_retry_on_transient_failure(self, compliance_config):
        """Test extraction retries on transient failures."""
        compliance_config.price_scout.respect_robots_txt = False

        call_count = 0

        async def mock_fetch_that_fails_twice(url):
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise Exception("Transient error")
            return "Success content"

        with patch("bimcalc.intelligence.price_scout.get_config", return_value=compliance_config):
            with patch.object(
                SmartPriceScout,
                "_fetch_page_content",
                side_effect=mock_fetch_that_fails_twice,
            ):
                with patch.object(
                    SmartPriceScout, "_analyze_content", new_callable=AsyncMock
                ) as mock_analyze:
                    mock_analyze.return_value = {
                        "page_type": "product_detail",
                        "products": [{"unit_price": 10.0}],
                    }

                    scout = SmartPriceScout()
                    result = await scout.extract("https://example.com/page")

        # Should succeed after retries
        assert result["page_type"] == "product_detail"
        assert call_count == 3  # Failed twice, succeeded on third

    @pytest.mark.asyncio
    async def test_retry_exhaustion_raises_error(self, compliance_config):
        """Test extraction fails after max retries."""
        compliance_config.price_scout.respect_robots_txt = False

        async def mock_fetch_that_always_fails(url):
            raise Exception("Persistent error")

        with patch("bimcalc.intelligence.price_scout.get_config", return_value=compliance_config):
            with patch.object(
                SmartPriceScout,
                "_fetch_page_content",
                side_effect=mock_fetch_that_always_fails,
            ):
                scout = SmartPriceScout()

                with pytest.raises(Exception, match="Persistent error"):
                    await scout.extract("https://example.com/page")


@pytest.mark.integration
class TestEndToEndCompliance:
    """End-to-end integration tests combining all compliance features."""

    @pytest.mark.asyncio
    @patch("bimcalc.intelligence.scraping_compliance.httpx.Client")
    @patch("bimcalc.intelligence.price_scout.async_playwright")
    @patch("bimcalc.intelligence.price_scout.AsyncOpenAI")
    async def test_full_compliance_workflow(
        self, mock_openai, mock_playwright, mock_http_client, compliance_config
    ):
        """Test complete workflow: robots.txt → rate limit → fetch → validate."""
        # Mock robots.txt with crawl delay
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = "User-agent: *\nAllow: /\nCrawl-delay: 0.5"
        mock_client = Mock()
        mock_client.__enter__ = Mock(return_value=mock_client)
        mock_client.__exit__ = Mock(return_value=False)
        mock_client.get = Mock(return_value=mock_response)
        mock_http_client.return_value = mock_client

        # Mock browser
        mock_browser = AsyncMock()
        mock_context = AsyncMock()
        mock_page = AsyncMock()
        mock_page.evaluate = AsyncMock(return_value="Product content")
        mock_context.new_page = AsyncMock(return_value=mock_page)
        mock_browser.new_context = AsyncMock(return_value=mock_context)
        mock_browser.close = AsyncMock()

        mock_p = AsyncMock()
        mock_p.chromium.launch = AsyncMock(return_value=mock_browser)
        mock_playwright.return_value.__aenter__ = AsyncMock(return_value=mock_p)
        mock_playwright.return_value.__aexit__ = AsyncMock()

        # Mock OpenAI
        mock_completion = Mock()
        mock_completion.choices = [
            Mock(
                message=Mock(
                    content='{"page_type": "product_detail", "products": [{"vendor_code": "A123", "unit_price": 25.50, "currency": "EUR", "unit": "ea", "description": "Compliant Product"}]}'
                )
            )
        ]
        mock_client_instance = AsyncMock()
        mock_client_instance.chat.completions.create = AsyncMock(
            return_value=mock_completion
        )
        mock_client_instance.close = AsyncMock()
        mock_openai.return_value = mock_client_instance

        # Clear cache
        from bimcalc.intelligence.scraping_compliance import _get_robots_parser
        _get_robots_parser.cache_clear()

        # Test full workflow
        with patch("bimcalc.intelligence.price_scout.get_config", return_value=compliance_config):
            scout = SmartPriceScout()

            # First extraction
            result1 = await scout.extract("https://example.com/product1")
            assert result1["products"][0]["unit_price"] == 25.50

            # Second extraction - should respect crawl delay
            start = time.time()
            result2 = await scout.extract("https://example.com/product2")
            elapsed = time.time() - start

            # Should enforce crawl delay (0.5s from robots.txt)
            assert 0.4 <= elapsed <= 0.8
            assert result2["products"][0]["unit_price"] == 25.50

            # Verify robots.txt was checked
            assert mock_client.get.called
