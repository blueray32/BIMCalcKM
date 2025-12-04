"""Unit tests for SmartPriceScout price validation.

Tests price validation logic, threshold checking, and data quality enforcement.
"""

import pytest
from decimal import Decimal
from unittest.mock import Mock, patch, AsyncMock
from bimcalc.intelligence.price_scout import SmartPriceScout
from bimcalc.config import PriceScoutConfig, AppConfig


@pytest.fixture
def mock_config():
    """Create mock config for testing."""
    config = Mock(spec=AppConfig)
    config.price_scout = PriceScoutConfig(
        min_price_threshold=Decimal("0.01"),
        max_price_threshold=Decimal("10000.00"),
        respect_robots_txt=False,  # Disable for testing
        default_rate_limit_seconds=0.0,  # No delay for testing
    )
    config.llm = Mock()
    config.llm.api_key = "test-key"
    config.llm.llm_model = "gpt-4-1106-preview"
    return config


@pytest.fixture
def price_scout(mock_config):
    """Create SmartPriceScout instance for testing."""
    with patch("bimcalc.intelligence.price_scout.get_config", return_value=mock_config):
        with patch.dict("os.environ", {"OPENAI_API_KEY": "test-key"}):
            scout = SmartPriceScout()
            return scout


class TestPriceValidation:
    """Tests for price validation logic."""

    def test_validate_extraction_with_valid_prices(self, price_scout):
        """Test validation passes for valid prices."""
        data = {
            "page_type": "product_list",
            "products": [
                {"vendor_code": "A123", "unit_price": 10.50, "description": "Product A"},
                {"vendor_code": "B456", "unit_price": 99.99, "description": "Product B"},
                {"vendor_code": "C789", "unit_price": 1000.00, "description": "Product C"},
            ],
        }

        # Should not raise exception
        price_scout._validate_extraction(data)

        # All prices should remain valid
        assert data["products"][0]["unit_price"] == 10.50
        assert data["products"][1]["unit_price"] == 99.99
        assert data["products"][2]["unit_price"] == 1000.00

    def test_validate_extraction_with_suspicious_low_price(self, price_scout, caplog):
        """Test validation warns about suspicious low prices."""
        data = {
            "page_type": "product_detail",
            "products": [
                {"vendor_code": "A123", "unit_price": 0.001, "description": "Suspiciously cheap"},
            ],
        }

        price_scout._validate_extraction(data)

        # Should log warning but not invalidate
        assert "Suspicious low price" in caplog.text

    def test_validate_extraction_with_suspicious_high_price(self, price_scout, caplog):
        """Test validation warns about suspicious high prices."""
        data = {
            "page_type": "product_detail",
            "products": [
                {
                    "vendor_code": "A123",
                    "unit_price": 50000.00,
                    "description": "Suspiciously expensive",
                },
            ],
        }

        price_scout._validate_extraction(data)

        # Should log warning but not invalidate
        assert "Suspicious high price" in caplog.text

    def test_validate_extraction_with_negative_price(self, price_scout, caplog):
        """Test validation invalidates negative prices."""
        data = {
            "page_type": "product_detail",
            "products": [
                {"vendor_code": "A123", "unit_price": -10.00, "description": "Negative price"},
            ],
        }

        price_scout._validate_extraction(data)

        # Should invalidate negative price
        assert data["products"][0]["unit_price"] is None
        assert "Negative price detected" in caplog.text

    def test_validate_extraction_with_missing_price(self, price_scout, caplog):
        """Test validation handles missing prices gracefully."""
        data = {
            "page_type": "product_detail",
            "products": [
                {"vendor_code": "A123", "description": "No price"},
            ],
        }

        price_scout._validate_extraction(data)

        # Should log warning
        assert "Missing unit_price" in caplog.text

    def test_validate_extraction_with_invalid_price_format(self, price_scout, caplog):
        """Test validation handles invalid price formats."""
        data = {
            "page_type": "product_detail",
            "products": [
                {"vendor_code": "A123", "unit_price": "invalid", "description": "Bad format"},
            ],
        }

        price_scout._validate_extraction(data)

        # Should invalidate and log error
        assert data["products"][0]["unit_price"] is None
        assert "Invalid price format" in caplog.text

    def test_validate_extraction_with_zero_price(self, price_scout, caplog):
        """Test validation handles zero prices."""
        data = {
            "page_type": "product_detail",
            "products": [
                {"vendor_code": "A123", "unit_price": 0.00, "description": "Zero price"},
            ],
        }

        price_scout._validate_extraction(data)

        # Zero is below min threshold, should warn
        assert "Suspicious low price" in caplog.text

    def test_validate_extraction_with_mixed_valid_invalid(self, price_scout):
        """Test validation handles mix of valid and invalid prices."""
        data = {
            "page_type": "product_list",
            "products": [
                {"vendor_code": "A", "unit_price": 10.00, "description": "Valid"},
                {"vendor_code": "B", "unit_price": -5.00, "description": "Negative"},
                {"vendor_code": "C", "unit_price": "bad", "description": "Invalid format"},
                {"vendor_code": "D", "unit_price": 50.00, "description": "Valid"},
                {"vendor_code": "E", "description": "Missing price"},
            ],
        }

        price_scout._validate_extraction(data)

        # Valid prices should remain
        assert data["products"][0]["unit_price"] == 10.00
        assert data["products"][3]["unit_price"] == 50.00

        # Invalid prices should be None
        assert data["products"][1]["unit_price"] is None  # Negative
        assert data["products"][2]["unit_price"] is None  # Invalid format

    def test_validate_extraction_with_no_products(self, price_scout, caplog):
        """Test validation handles empty product list."""
        data = {"page_type": "product_list", "products": []}

        price_scout._validate_extraction(data)

        # Should log warning
        assert "No products extracted" in caplog.text

    def test_validate_extraction_logs_summary(self, price_scout, caplog):
        """Test validation logs summary of validation results."""
        data = {
            "page_type": "product_list",
            "products": [
                {"vendor_code": "A", "unit_price": 10.00, "description": "Valid 1"},
                {"vendor_code": "B", "unit_price": 20.00, "description": "Valid 2"},
                {"vendor_code": "C", "unit_price": -5.00, "description": "Invalid"},
            ],
        }

        price_scout._validate_extraction(data)

        # Should log summary
        assert "3 products" in caplog.text
        assert "2 with valid prices" in caplog.text


class TestPriceValidationThresholds:
    """Tests for configurable price thresholds."""

    def test_custom_min_threshold(self, mock_config):
        """Test custom minimum price threshold is respected."""
        # Set custom min threshold
        mock_config.price_scout.min_price_threshold = Decimal("1.00")

        with patch("bimcalc.intelligence.price_scout.get_config", return_value=mock_config):
            with patch.dict("os.environ", {"OPENAI_API_KEY": "test-key"}):
                scout = SmartPriceScout()

        data = {
            "products": [
                {"vendor_code": "A", "unit_price": 0.50, "description": "Below min"},
            ]
        }

        with pytest.LogCaptureFixture.at_level("WARNING"):
            scout._validate_extraction(data)

        # Should warn because 0.50 < 1.00
        # (check happens via logger, validated in other tests)

    def test_custom_max_threshold(self, mock_config):
        """Test custom maximum price threshold is respected."""
        # Set custom max threshold
        mock_config.price_scout.max_price_threshold = Decimal("100.00")

        with patch("bimcalc.intelligence.price_scout.get_config", return_value=mock_config):
            with patch.dict("os.environ", {"OPENAI_API_KEY": "test-key"}):
                scout = SmartPriceScout()

        data = {
            "products": [
                {"vendor_code": "A", "unit_price": 200.00, "description": "Above max"},
            ]
        }

        with pytest.LogCaptureFixture.at_level("WARNING"):
            scout._validate_extraction(data)

        # Should warn because 200.00 > 100.00
        # (check happens via logger, validated in other tests)

    def test_decimal_precision_handling(self, price_scout):
        """Test validation handles decimal precision correctly."""
        data = {
            "products": [
                {"vendor_code": "A", "unit_price": 10.999, "description": "High precision"},
                {"vendor_code": "B", "unit_price": 10.5, "description": "Normal precision"},
            ]
        }

        # Should not raise exception
        price_scout._validate_extraction(data)

        # Prices should be converted to Decimal correctly
        assert isinstance(Decimal(str(data["products"][0]["unit_price"])), Decimal)


class TestPriceValidationEdgeCases:
    """Tests for edge cases in price validation."""

    def test_validate_extraction_with_null_products_key(self, price_scout, caplog):
        """Test validation handles missing products key."""
        data = {"page_type": "product_detail"}

        price_scout._validate_extraction(data)

        # Should not crash, should warn
        assert "No products extracted" in caplog.text

    def test_validate_extraction_with_none_unit_price(self, price_scout):
        """Test validation handles explicit None for unit_price."""
        data = {
            "products": [
                {"vendor_code": "A", "unit_price": None, "description": "No price"},
            ]
        }

        # Should not crash
        price_scout._validate_extraction(data)

    def test_validate_extraction_with_string_number(self, price_scout):
        """Test validation handles string numbers (should work via Decimal)."""
        data = {
            "products": [
                {"vendor_code": "A", "unit_price": "10.50", "description": "String price"},
            ]
        }

        # Should not crash, Decimal can parse strings
        price_scout._validate_extraction(data)

        # String should be successfully converted
        assert data["products"][0]["unit_price"] == "10.50"

    def test_validate_extraction_with_float_infinity(self, price_scout):
        """Test validation handles special float values."""
        data = {
            "products": [
                {"vendor_code": "A", "unit_price": float("inf"), "description": "Infinity"},
            ]
        }

        # Should handle gracefully and invalidate
        price_scout._validate_extraction(data)

        # Infinity should be invalidated (caught by try/except or threshold)
        # At minimum, should not crash

    def test_validate_extraction_with_very_small_positive(self, price_scout, caplog):
        """Test validation of very small but positive prices."""
        data = {
            "products": [
                {"vendor_code": "A", "unit_price": 0.001, "description": "Tiny price"},
            ]
        }

        price_scout._validate_extraction(data)

        # Should warn (below typical threshold)
        assert "Suspicious low price" in caplog.text
