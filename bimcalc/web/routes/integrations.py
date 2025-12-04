"""External integrations routes for BIMCalc web UI.

Extracted from app_enhanced.py as part of Phase 3.15 web refactor.
Handles OAuth and API integrations with external services like
Autodesk Construction Cloud (ACC).

Routes:
- GET /api/integrations/acc/connect  - Initiate ACC OAuth flow
- GET /api/integrations/acc/callback - Handle ACC OAuth callback
- GET /integrations/acc/browser      - Browse ACC projects and files
"""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse

# Create router with integrations tag
router = APIRouter(tags=["integrations"])


# ============================================================================
# ACC (Autodesk Construction Cloud) Integration Routes
# ============================================================================


@router.get("/api/integrations/acc/connect")
async def acc_connect():
    """Initiate ACC OAuth flow.

    Redirects user to Autodesk authentication page to authorize
    the application to access their ACC projects and files.

    Extracted from: app_enhanced.py:575
    """
    from bimcalc.integrations.acc import get_acc_client

    client = get_acc_client()
    return RedirectResponse(client.get_auth_url())


@router.get("/api/integrations/acc/callback")
async def acc_callback(code: str, request: Request):
    """Handle ACC OAuth callback.

    Receives authorization code from Autodesk, exchanges it for
    an access token, and stores the token in a cookie.

    Extracted from: app_enhanced.py:582
    """
    from bimcalc.integrations.acc import get_acc_client

    client = get_acc_client()
    tokens = await client.exchange_code(code)

    # Store token in session or cookie (simplified for MVP)
    response = RedirectResponse("/integrations/acc/browser")
    response.set_cookie(
        "acc_token", tokens["access_token"], max_age=3600, httponly=True
    )
    return response


@router.get("/integrations/acc/browser", response_class=HTMLResponse)
async def acc_browser(request: Request):
    """Browser for ACC files.

    Shows list of ACC projects and files, allowing users to
    browse and import BIM data from Autodesk Construction Cloud.

    Requires valid ACC OAuth token in cookie.

    Extracted from: app_enhanced.py:594
    """
    token = request.cookies.get("acc_token")
    if not token:
        return RedirectResponse("/api/integrations/acc/connect")

    from bimcalc.integrations.acc import get_acc_client

    client = get_acc_client()
    projects = await client.list_projects(token)

    # Simple HTML for file browsing
    project_list = "".join(
        [f"<li><a href='?project_id={p['id']}'>{p['name']}</a></li>" for p in projects]
    )

    files_html = ""
    project_id = request.query_params.get("project_id")
    if project_id:
        files = await client.list_files(token, project_id)
        files_html = (
            "<h3>Files</h3><ul>"
            + "".join(
                [
                    f"<li>{f.name} (v{f.version}) - <button onclick='importFile(\"{f.id}\")'>Import</button></li>"
                    for f in files
                ]
            )
            + "</ul>"
        )

    return f"""
    <html>
        <head><title>ACC Browser</title></head>
        <body>
            <h1>Autodesk Construction Cloud</h1>
            <h2>Projects</h2>
            <ul>{project_list}</ul>
            {files_html}
            <script>
                function importFile(fileId) {{
                    alert('Importing file ' + fileId);
                    // Call ingest API here
                }}
            </script>
        </body>
    </html>
    """
