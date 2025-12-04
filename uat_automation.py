import asyncio
from playwright.async_api import async_playwright
import os

BASE_URL = "http://localhost:8003"
SCHEDULE_FILE = os.path.abspath("tests/fixtures/sample_schedule.csv")
PRICES_FILE = os.path.abspath("tests/fixtures/sample_prices.csv")


async def run_uat():
    async with async_playwright() as p:
        # Launch browser (headless=True for CI/Server, but we can see output via logs)
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(ignore_https_errors=True)
        page = await context.new_page()

        print(f"🚀 Starting Automated UAT against {BASE_URL}")

        # 1. Dashboard Access
        print("1️⃣  Checking Dashboard...")
        await page.goto(BASE_URL)
        title = await page.title()
        print(f"   Page Title: {title}")
        if "Login" in title:
            print("   ℹ️  Login required. Attempting login...")
            await page.fill('input[name="username"]', "admin")
            await page.fill('input[name="password"]', "changeme")
            await page.click('button[type="submit"]')
            await page.wait_for_url(f"{BASE_URL}/")
            title = await page.title()
            print(f"   New Page Title: {title}")

        if "BIMCalc" not in title or "Login" in title:
            print("   ❌ Login failed or Dashboard not loaded")
            await browser.close()
            return
        else:
            print("   ✅ Dashboard loaded")

        # 2. Ingestion - Schedule
        print("\n2️⃣  Testing Schedule Ingestion...")
        await page.goto(f"{BASE_URL}/ingest")

        # Fill form
        await page.fill('input[name="org"]', "UAT-Org")
        await page.fill('input[name="project"]', "UAT-Project-Auto")

        # Upload Schedule
        print("   Uploading schedule...")
        try:
            # Take screenshot before upload
            await page.screenshot(path="uat_ingest_page.png")

            # Find the file input for schedules.
            # Assuming it's the first one or inside the schedule form.
            # We'll try to find input by name="file" inside the schedule form
            # or just use the first input[type="file"]

            # Using set_input_files directly (no chooser needed)
            await page.set_input_files('input[type="file"]', SCHEDULE_FILE)

            # Click submit
            # We need to find the submit button associated with this form.
            # Assuming it's the button next to the input or in the same form.
            # Let's try to click the button that says "Upload" or "Ingest"
            # or type="submit"

            # Wait for navigation or response
            async with page.expect_response(
                lambda response: "/ingest/schedules" in response.url
                and response.status == 200
            ) as response_info:
                await page.click('button[type="submit"]')

            print("   ✅ Schedule upload successful (200 OK)")
            await page.screenshot(path="uat_upload_success.png")

        except Exception as e:
            print(f"   ❌ Schedule upload failed: {e}")
            await page.screenshot(path="uat_upload_failure.png")

        # 3. Verify Items
        print("\n3️⃣  Verifying Items...")
        # Wait a bit for processing
        await page.wait_for_timeout(2000)

        await page.goto(f"{BASE_URL}/items?org=UAT-Org&project=UAT-Project-Auto")
        await page.wait_for_load_state("networkidle")

        # Take screenshot of items page
        await page.screenshot(path="uat_items_page.png")

        # Check if items are listed
        # Look for "Cable Tray" text
        try:
            # Print page content for debug
            content = await page.content()
            if "Cable Tray" in content:
                print("   ✅ Item 'Cable Tray' found in page content")
            else:
                print("   ❌ Item 'Cable Tray' NOT found in page content")
                print(f"   Page text preview: {await page.inner_text('body')[:500]}")

            # Check for table row with item
            item_row = page.locator("tr", has_text="Cable Tray")
            await item_row.first.wait_for(state="visible", timeout=5000)
            print("   ✅ Item 'Cable Tray' found in table row")
        except Exception as e:
            print(f"   ❌ Item verification failed: {e}")

        # 4. Ingestion - Price Book
        print("\n4️⃣  Testing Price Book Ingestion...")
        await page.goto(f"{BASE_URL}/ingest")

        # Select "Flexible Import" mode (default, but good to be explicit if needed)
        # The form id is "flexible-prices-form"

        # Fill form (Vendor Name)
        await page.fill('#flexible-prices-form input[name="vendor_name"]', "UAT-Vendor")

        # Upload Price Book
        print("   Uploading price book...")
        try:
            # Target the file input inside the flexible prices form
            await page.set_input_files(
                '#flexible-prices-form input[type="file"]', PRICES_FILE
            )

            # Click submit for prices
            # Find the submit button inside the flexible prices form
            await page.click('#flexible-prices-form button[type="submit"]')

            # Wait for success message
            # The JS updates #flexible-prices-result
            await page.wait_for_selector(
                "#flexible-prices-result .message-success", timeout=10000
            )
            print("   ✅ Price book upload successful")

        except Exception as e:
            print(f"   ❌ Price book upload failed: {e}")

        # 5. Matching Pipeline
        print("\n5️⃣  Testing Matching Pipeline...")
        await page.goto(f"{BASE_URL}/match?org=UAT-Org&project=UAT-Project-Auto")

        try:
            # Click "Run Matching"
            # Look for a button with text "Run Matching" or similar
            await page.click('button:has-text("Run Matching")')
            print("   Matching started...")

            # Wait for completion message or progress bar
            # This might take a moment
            await page.wait_for_timeout(5000)

            # Verify results on Dashboard
            print("   Verifying results on Dashboard...")
            await page.goto(f"{BASE_URL}/?org=UAT-Org&project=UAT-Project-Auto")
            await page.wait_for_load_state("networkidle")

            # Check for "Active Mappings" or "Awaiting Review"
            # We expect some items to be matched
            content = await page.content()
            if "Awaiting Review" in content:
                print("   ✅ Matching produced results (Awaiting Review found)")
            else:
                print(
                    "   ⚠️ 'Awaiting Review' not found, matching might have yielded no results or auto-approved all"
                )

        except Exception as e:
            print(f"   ❌ Matching pipeline test failed: {e}")

        # 6. Review Workflow
        print("\n6️⃣  Testing Review Workflow...")
        await page.goto(f"{BASE_URL}/review?org=UAT-Org&project=UAT-Project-Auto")

        try:
            # Check if there are items to review
            await page.wait_for_selector(".review-card", timeout=5000)
            print("   Review items found.")

            # Approve the first item
            # Look for an "Approve" button
            approve_btn = page.locator('button:has-text("Approve")').first
            if await approve_btn.is_visible():
                await approve_btn.click()
                print("   Clicked Approve.")
                await page.wait_for_timeout(1000)
                print("   ✅ Item approved")
            else:
                print("   ⚠️ No Approve button found")

        except Exception as e:
            print(
                f"   ⚠️ Review workflow test skipped or failed (might be no items to review): {e}"
            )

        await browser.close()


if __name__ == "__main__":
    asyncio.run(run_uat())
