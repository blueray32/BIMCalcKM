import sys
import os
import asyncio
from pathlib import Path
from fastapi import Request
from starlette.datastructures import URL

# Add project root to path
sys.path.append(os.getcwd())

async def reproduce_render():
    try:
        print("Importing dependencies...")
        from bimcalc.web.dependencies import get_templates
        
        print("Getting templates...")
        templates = get_templates()
        
        # Mock request
        scope = {
            "type": "http",
            "path": "/reports",
            "headers": [],
        }
        request = Request(scope)
        
        context = {
            "request": request,
            "org_id": "default",
            "project_id": "default",
        }
        
        print("Attempting to render reports.html...")
        try:
            response = templates.TemplateResponse("reports.html", context)
            print("Successfully rendered reports.html")
            # print(response.body.decode()[:200]) # Print first 200 chars
        except Exception as e:
            print(f"FAILED to render reports.html: {e}")
            import traceback
            traceback.print_exc()
            
        print("\nAttempting to render ingest.html...")
        try:
            response = templates.TemplateResponse("ingest.html", context)
            print("Successfully rendered ingest.html")
        except Exception as e:
            print(f"FAILED to render ingest.html: {e}")
            import traceback
            traceback.print_exc()

    except Exception as e:
        print(f"Global Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(reproduce_render())
