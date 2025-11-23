"""Pytest configuration and fixtures for BIMCalc tests.

Provides common fixtures for testing.
"""

from __future__ import annotations

from decimal import Decimal
from uuid import uuid4

import pytest

from bimcalc.models import Item, PriceItem


@pytest.fixture
def test_org_id() -> str:
    """Test organization ID."""
    return "test-org"


@pytest.fixture
def test_project_id() -> str:
    """Test project ID."""
    return "test-project"


@pytest.fixture
def sample_item(test_org_id: str, test_project_id: str) -> Item:
    """Create a sample test item."""
    return Item(
        org_id=test_org_id,
        project_id=test_project_id,
        family="Pipe Elbow",
        type_name="90° DN100",
        category="Pipe Fittings",
        classification_code=2215,
        unit="ea",
        dn_mm=100.0,
        angle_deg=90.0,
        material="stainless_steel",
        quantity=Decimal("10"),
    )


@pytest.fixture
def sample_price_item() -> PriceItem:
    """Create a sample price item."""
    return PriceItem(
        classification_code=2215,
        sku="ELB-90-100-SS",
        description="Pipe Elbow 90° DN100 Stainless Steel",
        unit="ea",
        unit_price=Decimal("45.50"),
        currency="EUR",
        vat_rate=Decimal("0.23"),
        dn_mm=100.0,
        angle_deg=90.0,
        material="stainless_steel",
    )


@pytest.fixture
def cable_tray_item(test_org_id: str, test_project_id: str) -> Item:
    """Create a cable tray elbow item (for two-pass demo)."""
    return Item(
        org_id=test_org_id,
        project_id=test_project_id,
        family="Cable Tray Elbow",
        type_name="90° 200×50 Galvanised",
        category="Cable Tray",
        classification_code=2650,
        width_mm=200.0,
        height_mm=50.0,
        angle_deg=90.0,
        material="galvanised_steel",
        unit="ea",
        quantity=Decimal("5"),
    )


@pytest.fixture
def duct_item(test_org_id: str, test_project_id: str) -> Item:
    """Create a rectangular duct item."""
    return Item(
        org_id=test_org_id,
        project_id=test_project_id,
        family="Duct",
        type_name="Rectangular 400x200",
        category="Ducts",
        classification_code=2302,
        width_mm=400.0,
        height_mm=200.0,
        material="galvanized_steel",
        unit="m",
        quantity=Decimal("25.5"),
    )


@pytest.fixture
def price_items_catalog() -> list[PriceItem]:
    """Create a sample price catalog."""
    return [
        PriceItem(
            classification_code=2215,
            sku="ELB-90-100-SS",
            description="Pipe Elbow 90° DN100 Stainless Steel",
            unit="ea",
            unit_price=Decimal("45.50"),
        ),
        PriceItem(
            classification_code=2215,
            sku="ELB-45-100-SS",
            description="Pipe Elbow 45° DN100 Stainless Steel",
            unit="ea",
            unit_price=Decimal("42.00"),
        ),
        PriceItem(
            classification_code=2302,
            sku="DUCT-400x200",
            description="Rectangular Duct 400x200 Galvanized",
            unit="m",
            unit_price=Decimal("25.00"),
        ),
        PriceItem(
            classification_code=2650,
            sku="TRAY-ELB-200x50",
            description="Cable Tray Elbow 90° 200x50 Galvanized",
            unit="ea",
            unit_price=Decimal("35.00"),
        ),
    ]


@pytest.fixture(autouse=True)
def setup_test_env(monkeypatch):
    """Set up test environment variables."""
    # Set DATABASE_URL for config tests
    monkeypatch.setenv("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
    monkeypatch.setenv("DEFAULT_ORG_ID", "test-org")
    monkeypatch.setenv("LOG_LEVEL", "DEBUG")
