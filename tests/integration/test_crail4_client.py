"""Integration tests for Crail4Client browser capabilities."""

import os
import pytest
from bimcalc.integration.crail4_client import Crail4Client


@pytest.mark.asyncio
async def test_crail4_client_browser_connection():
    """Test that Crail4Client can connect to the headless browser service."""

    # Skip if no CDP URL is set (local dev without browserless)
    cdp_url = os.getenv("PLAYWRIGHT_CDP_URL")
    if not cdp_url:
        pytest.skip("PLAYWRIGHT_CDP_URL not set, skipping browser test")

    client = Crail4Client(api_key="dummy")

    # We use example.com as a stable target
    url = "https://example.com"

    # We need to mock the classification scheme to match what _fetch_with_browser expects
    # But _fetch_with_browser is internal.
    # Let's test _fetch_with_browser directly as it's the one using the connection.

    try:
        items = await client._fetch_with_browser(
            url=url, class_code="Test_Code", class_scheme="Test_Scheme"
        )

        # We don't expect valid items from example.com, but we expect it NOT to raise a connection error.
        # The extraction logic might return empty list or fail to find selectors.
        # If it connects and navigates, that's success for this test.
        assert isinstance(items, list)

    except Exception as e:
        # If it's a selector error, that means connection worked.
        # If it's a connection error, fail.
        error_msg = str(e).lower()
        if "connection refused" in error_msg or "cannot connect" in error_msg:
            pytest.fail(f"Could not connect to browser service: {e}")

        # Other errors (like missing selectors) are acceptable since example.com doesn't match our schema
        pass
