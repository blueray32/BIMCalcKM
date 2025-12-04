import sys
import os
import asyncio

# Add project root to path
sys.path.append(os.getcwd())


async def verify_templates():
    try:
        print("Attempting to import dependencies...")
        from bimcalc.web.dependencies import get_templates

        print("Getting templates instance...")
        templates = get_templates()

        print(f"Template directories: {templates.env.loader.searchpath}")

        # Check if reports.html can be found
        print("Checking for reports.html...")
        try:
            # Jinja2 loader check
            source, filename, uptodate = templates.env.loader.get_source(
                templates.env, "reports.html"
            )
            print(f"Found reports.html at: {filename}")
        except Exception as e:
            print(f"ERROR: Could not find reports.html: {e}")

        # Check if ingest.html can be found
        print("Checking for ingest.html...")
        try:
            source, filename, uptodate = templates.env.loader.get_source(
                templates.env, "ingest.html"
            )
            print(f"Found ingest.html at: {filename}")
        except Exception as e:
            print(f"ERROR: Could not find ingest.html: {e}")

    except Exception as e:
        print(f"ERROR: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(verify_templates())
