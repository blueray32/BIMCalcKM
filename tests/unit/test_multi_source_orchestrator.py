"""Unit tests for MultiSourceOrchestrator.

Tests parallel fetching, deduplication, price comparison, and error handling
for multi-source price intelligence.
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch
import os
from uuid import uuid4

from bimcalc.intelligence.multi_source_orchestrator import (
    MultiSourceOrchestrator,
    MultiSourceResult,
)
from bimcalc.db.models import PriceSourceModel


@pytest.fixture
def mock_session():
    """Create mock database session."""
    session = AsyncMock()
    session.__aenter__ = AsyncMock(return_value=session)
    session.__aexit__ = AsyncMock()
    return session


@pytest.fixture
def sample_sources():
    """Create sample price sources."""
    return [
        PriceSourceModel(
            id=uuid4(),
            org_id="test-org",
            name="Supplier A",
            url="https://suppliera.com/products",
            domain="suppliera.com",
            enabled=True,
            cache_ttl_seconds=86400,
            rate_limit_seconds=2.0,
        ),
        PriceSourceModel(
            id=uuid4(),
            org_id="test-org",
            name="Supplier B",
            url="https://supplierb.com/catalog",
            domain="supplierb.com",
            enabled=True,
            cache_ttl_seconds=86400,
            rate_limit_seconds=2.0,
        ),
        PriceSourceModel(
            id=uuid4(),
            org_id="test-org",
            name="Supplier C",
            url="https://supplierc.com/items",
            domain="supplierc.com",
            enabled=False,  # Disabled
            cache_ttl_seconds=86400,
            rate_limit_seconds=2.0,
        ),
    ]


class TestMultiSourceResult:
    """Test MultiSourceResult container."""

    def test_initialization(self):
        """Test MultiSourceResult initializes with empty state."""
        result = MultiSourceResult()

        assert result.products == []
        assert result.source_results == {}
        assert result.errors == []
        assert result.stats == {
            "sources_attempted": 0,
            "sources_succeeded": 0,
            "sources_failed": 0,
            "total_products": 0,
            "unique_products": 0,
            "duplicates_removed": 0,
        }


class TestMultiSourceOrchestrator:
    """Test MultiSourceOrchestrator core functionality."""

    @pytest.mark.asyncio
    @patch.dict("os.environ", {"OPENAI_API_KEY": "test-key"})
    async def test_context_manager(self, mock_session):
        """Test orchestrator works as async context manager."""
        orchestrator = MultiSourceOrchestrator(org_id="test-org", session=mock_session)

        async with orchestrator as orch:
            assert orch.org_id == "test-org"
            assert orch.scout is not None

        # Scout should be cleaned up
        assert orchestrator.scout is not None  # Scout object exists but closed

    @pytest.mark.asyncio
    async def test_get_enabled_sources(self, mock_session, sample_sources):
        """Test getting only enabled sources."""
        # Mock database query to return sample sources
        mock_result = Mock()
        mock_result.scalars.return_value.all.return_value = [
            s for s in sample_sources if s.enabled
        ]
        mock_session.execute = AsyncMock(return_value=mock_result)

        orchestrator = MultiSourceOrchestrator(org_id="test-org", session=mock_session)

        sources = await orchestrator.get_enabled_sources()

        # Should return only 2 enabled sources (A and B, not C)
        assert len(sources) == 2
        assert all(s.enabled for s in sources)
        assert sources[0].name == "Supplier A"
        assert sources[1].name == "Supplier B"

    @pytest.mark.asyncio
    async def test_fetch_from_source_success(self, mock_session, sample_sources):
        """Test successful fetch from a single source."""
        orchestrator = MultiSourceOrchestrator(org_id="test-org", session=mock_session)
        orchestrator.scout = AsyncMock()

        # Mock scout.extract to return products
        orchestrator.scout.extract = AsyncMock(
            return_value={
                "page_type": "product_list",
                "products": [
                    {
                        "vendor_code": "ABC123",
                        "unit_price": 10.50,
                        "description": "Product 1",
                    },
                    {
                        "vendor_code": "XYZ789",
                        "unit_price": 25.00,
                        "description": "Product 2",
                    },
                ],
            }
        )

        source = sample_sources[0]
        result = await orchestrator.fetch_from_source(source)

        # Check success
        assert result["success"] is True
        assert result["source_id"] == source.id
        assert result["source_name"] == "Supplier A"
        assert len(result["products"]) == 2

        # Check source metadata added to products
        assert result["products"][0]["_source_id"] == str(source.id)
        assert result["products"][0]["_source_name"] == "Supplier A"
        assert "_fetched_at" in result["products"][0]

        # Check duration
        assert "duration_ms" in result
        assert "duration_ms" in result
        assert result["duration_ms"] >= 0

    @pytest.mark.asyncio
    async def test_fetch_from_source_compliance_error(
        self, mock_session, sample_sources
    ):
        """Test fetch handles compliance errors gracefully."""
        orchestrator = MultiSourceOrchestrator(org_id="test-org", session=mock_session)
        orchestrator.scout = AsyncMock()

        # Mock scout.extract to raise ValueError (compliance error)
        orchestrator.scout.extract = AsyncMock(
            side_effect=ValueError("Disallowed by robots.txt")
        )

        source = sample_sources[0]
        result = await orchestrator.fetch_from_source(source)

        # Check failure
        assert result["success"] is False
        assert result["source_id"] == source.id
        assert "Compliance error" in result["error"]
        assert "robots.txt" in result["error"]

    @pytest.mark.asyncio
    async def test_fetch_from_source_network_error(self, mock_session, sample_sources):
        """Test fetch handles network errors gracefully."""
        orchestrator = MultiSourceOrchestrator(org_id="test-org", session=mock_session)
        orchestrator.scout = AsyncMock()

        # Mock scout.extract to raise generic exception
        orchestrator.scout.extract = AsyncMock(
            side_effect=Exception("Connection timeout")
        )

        source = sample_sources[0]
        result = await orchestrator.fetch_from_source(source)

        # Check failure
        assert result["success"] is False
        assert result["source_id"] == source.id
        assert "Extraction failed" in result["error"]
        assert "Connection timeout" in result["error"]

    @pytest.mark.asyncio
    async def test_deduplicate_products_no_duplicates(self):
        """Test deduplication with no duplicate products."""
        orchestrator = MultiSourceOrchestrator(org_id="test-org")

        products = [
            {"vendor_code": "A123", "unit_price": 10.0, "_source_name": "Source A"},
            {"vendor_code": "B456", "unit_price": 20.0, "_source_name": "Source A"},
            {"vendor_code": "C789", "unit_price": 30.0, "_source_name": "Source B"},
        ]

        unique, duplicates_removed = orchestrator._deduplicate_products(products)

        assert len(unique) == 3
        assert duplicates_removed == 0
        assert unique == products

    @pytest.mark.asyncio
    async def test_deduplicate_products_with_duplicates(self):
        """Test deduplication keeps lowest price."""
        orchestrator = MultiSourceOrchestrator(org_id="test-org")

        products = [
            {
                "vendor_code": "A123",
                "unit_price": 12.0,
                "_source_name": "Source A",
                "_source_url": "https://a.com",
            },
            {
                "vendor_code": "A123",
                "unit_price": 10.0,  # Cheapest
                "_source_name": "Source B",
                "_source_url": "https://b.com",
            },
            {
                "vendor_code": "A123",
                "unit_price": 15.0,
                "_source_name": "Source C",
                "_source_url": "https://c.com",
            },
        ]

        unique, duplicates_removed = orchestrator._deduplicate_products(products)

        assert len(unique) == 1
        assert duplicates_removed == 2

        # Should keep cheapest (10.0 from Source B)
        assert unique[0]["unit_price"] == 10.0
        assert unique[0]["_source_name"] == "Source B"

        # Should track all sources
        assert "_duplicate_sources" in unique[0]
        assert len(unique[0]["_duplicate_sources"]) == 3

        # Should calculate variance
        assert "_price_variance" in unique[0]
        variance = unique[0]["_price_variance"]
        assert variance["min"] == 10.0
        assert variance["max"] == 15.0
        assert variance["sources_count"] == 3
        assert variance["variance_pct"] > 0

    @pytest.mark.asyncio
    async def test_deduplicate_products_handles_none_prices(self):
        """Test deduplication handles None/invalid prices."""
        orchestrator = MultiSourceOrchestrator(org_id="test-org")

        products = [
            {
                "vendor_code": "A123",
                "unit_price": None,
                "_source_name": "Source A",
                "_source_url": "https://a.com",
            },
            {
                "vendor_code": "A123",
                "unit_price": 10.0,  # Only valid price
                "_source_name": "Source B",
                "_source_url": "https://b.com",
            },
        ]

        unique, duplicates_removed = orchestrator._deduplicate_products(products)

        assert len(unique) == 1
        assert duplicates_removed == 1

        # Should keep the one with valid price
        assert unique[0]["unit_price"] == 10.0
        assert unique[0]["_source_name"] == "Source B"

    @pytest.mark.asyncio
    async def test_calculate_price_variance(self):
        """Test price variance calculation."""
        orchestrator = MultiSourceOrchestrator(org_id="test-org")

        products = [
            {"unit_price": 10.0},
            {"unit_price": 12.0},
            {"unit_price": 15.0},
        ]

        variance = orchestrator._calculate_price_variance(products)

        assert variance is not None
        assert variance["min"] == 10.0
        assert variance["max"] == 15.0
        assert variance["mean"] == pytest.approx(12.33, rel=0.01)
        # Variance: (15-10)/12.33 * 100 = 40.5%
        assert variance["variance_pct"] == pytest.approx(40.5, rel=0.1)
        assert variance["sources_count"] == 3

    @pytest.mark.asyncio
    async def test_calculate_price_variance_insufficient_data(self):
        """Test variance calculation with < 2 prices returns None."""
        orchestrator = MultiSourceOrchestrator(org_id="test-org")

        products = [{"unit_price": 10.0}]

        variance = orchestrator._calculate_price_variance(products)

        assert variance is None

    @pytest.mark.asyncio
    async def test_fetch_all_success(self, mock_session, sample_sources):
        """Test fetch_all orchestrates parallel fetching successfully."""
        orchestrator = MultiSourceOrchestrator(org_id="test-org", session=mock_session)

        # Mock get_enabled_sources to return 2 sources
        orchestrator.get_enabled_sources = AsyncMock(
            return_value=[sample_sources[0], sample_sources[1]]
        )

        # Mock fetch_from_source for each source
        async def mock_fetch(source, **kwargs):
            if source.name == "Supplier A":
                return {
                    "success": True,
                    "source_id": source.id,
                    "source_name": source.name,
                    "products": [
                        {
                            "vendor_code": "A123",
                            "unit_price": 10.0,
                            "_source_name": source.name,
                            "_source_url": source.url,
                        }
                    ],
                    "duration_ms": 100,
                }
            else:  # Supplier B
                return {
                    "success": True,
                    "source_id": source.id,
                    "source_name": source.name,
                    "products": [
                        {
                            "vendor_code": "B456",
                            "unit_price": 20.0,
                            "_source_name": source.name,
                            "_source_url": source.url,
                        }
                    ],
                    "duration_ms": 150,
                }

        orchestrator.fetch_from_source = mock_fetch

        result = await orchestrator.fetch_all()

        # Check stats
        assert result.stats["sources_attempted"] == 2
        assert result.stats["sources_succeeded"] == 2
        assert result.stats["sources_failed"] == 0
        assert result.stats["total_products"] == 2
        assert result.stats["unique_products"] == 2
        assert result.stats["duplicates_removed"] == 0

        # Check products
        assert len(result.products) == 2
        assert len(result.errors) == 0

    @pytest.mark.asyncio
    async def test_fetch_all_partial_failure(self, mock_session, sample_sources):
        """Test fetch_all handles partial failures gracefully."""
        orchestrator = MultiSourceOrchestrator(org_id="test-org", session=mock_session)

        # Mock get_enabled_sources to return 2 sources
        orchestrator.get_enabled_sources = AsyncMock(
            return_value=[sample_sources[0], sample_sources[1]]
        )

        # Mock fetch_from_source: one success, one failure
        async def mock_fetch(source, **kwargs):
            if source.name == "Supplier A":
                return {
                    "success": True,
                    "source_id": source.id,
                    "source_name": source.name,
                    "products": [
                        {
                            "vendor_code": "A123",
                            "unit_price": 10.0,
                            "_source_name": source.name,
                            "_source_url": source.url,
                        }
                    ],
                    "duration_ms": 100,
                }
            else:  # Supplier B fails
                return {
                    "success": False,
                    "source_id": source.id,
                    "source_name": source.name,
                    "error": "Connection timeout",
                    "duration_ms": 5000,
                }

        orchestrator.fetch_from_source = mock_fetch

        result = await orchestrator.fetch_all()

        # Check stats
        assert result.stats["sources_attempted"] == 2
        assert result.stats["sources_succeeded"] == 1
        assert result.stats["sources_failed"] == 1
        assert result.stats["total_products"] == 1
        assert result.stats["unique_products"] == 1

        # Check products (should have 1 from successful source)
        assert len(result.products) == 1

        # Check errors
        assert len(result.errors) == 1
        assert result.errors[0]["source"] == "Supplier B"
        assert "Connection timeout" in result.errors[0]["error"]

    @pytest.mark.asyncio
    async def test_fetch_all_with_duplicates(self, mock_session, sample_sources):
        """Test fetch_all deduplicates products across sources."""
        orchestrator = MultiSourceOrchestrator(org_id="test-org", session=mock_session)

        # Mock get_enabled_sources to return 2 sources
        orchestrator.get_enabled_sources = AsyncMock(
            return_value=[sample_sources[0], sample_sources[1]]
        )

        # Mock fetch_from_source: both return same vendor_code, different prices
        async def mock_fetch(source, **kwargs):
            if source.name == "Supplier A":
                return {
                    "success": True,
                    "source_id": source.id,
                    "source_name": source.name,
                    "products": [
                        {
                            "vendor_code": "A123",
                            "unit_price": 12.0,
                            "_source_name": source.name,
                            "_source_url": source.url,
                        }
                    ],
                    "duration_ms": 100,
                }
            else:  # Supplier B has cheaper price
                return {
                    "success": True,
                    "source_id": source.id,
                    "source_name": source.name,
                    "products": [
                        {
                            "vendor_code": "A123",
                            "unit_price": 10.0,  # Cheaper
                            "_source_name": source.name,
                            "_source_url": source.url,
                        }
                    ],
                    "duration_ms": 150,
                }

        orchestrator.fetch_from_source = mock_fetch

        result = await orchestrator.fetch_all()

        # Check stats
        assert result.stats["sources_attempted"] == 2
        assert result.stats["sources_succeeded"] == 2
        assert result.stats["total_products"] == 2
        assert result.stats["unique_products"] == 1  # Deduplicated
        assert result.stats["duplicates_removed"] == 1

        # Check products (should have 1 with cheapest price)
        assert len(result.products) == 1
        assert result.products[0]["unit_price"] == 10.0
        assert result.products[0]["_source_name"] == "Supplier B"

        # Check duplicate tracking
        assert "_duplicate_sources" in result.products[0]
        assert len(result.products[0]["_duplicate_sources"]) == 2

    @pytest.mark.asyncio
    async def test_fetch_all_no_sources(self, mock_session):
        """Test fetch_all handles case with no enabled sources."""
        orchestrator = MultiSourceOrchestrator(org_id="test-org", session=mock_session)

        # Mock get_enabled_sources to return empty list
        orchestrator.get_enabled_sources = AsyncMock(return_value=[])

        result = await orchestrator.fetch_all()

        # Check stats
        assert result.stats["sources_attempted"] == 0
        assert result.stats["sources_succeeded"] == 0
        assert result.stats["sources_failed"] == 0
        assert result.stats["total_products"] == 0
        assert result.stats["unique_products"] == 0

        # Check products
        assert len(result.products) == 0
        assert len(result.errors) == 0
