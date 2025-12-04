"""Authentication routes for BIMCalc web UI.

Extracted from app_enhanced.py as part of Phase 3.1 web refactor.
Handles login, logout, and favicon requests.

Routes:
- GET  /login       - Login page
- POST /login       - Process login form
- GET  /logout      - Logout and clear session
- GET  /favicon.ico - Return empty favicon (204)
"""

from __future__ import annotations

from fastapi import APIRouter, Cookie, Depends, Form, Request, Response
from fastapi.responses import HTMLResponse, RedirectResponse

from bimcalc.web.auth import create_session, verify_credentials
from bimcalc.web.auth import logout as auth_logout
from bimcalc.web.dependencies import get_templates

# Create router with auth tag
router = APIRouter(tags=["authentication"])


# ============================================================================
# Authentication Routes
# ============================================================================


@router.get("/login", response_class=HTMLResponse)
async def login_page(
    request: Request,
    error: str | None = None,
    templates=Depends(get_templates),
):
    """Login page.

    Extracted from: app_enhanced.py:183
    """
    return templates.TemplateResponse(
        "login.html",
        {
            "request": request,
            "error": error,
        },
    )


@router.post("/login")
async def login(
    request: Request,
    response: Response,
    username: str = Form(...),
    password: str = Form(...),
):
    """Process login form.

    Creates session and sets httponly cookie on successful authentication.
    Redirects to dashboard (/) on success, back to /login?error=invalid on failure.

    Extracted from: app_enhanced.py:192
    """
    if verify_credentials(username, password):
        # Create session
        session_token = create_session(username)

        # Set cookie
        response = RedirectResponse(url="/", status_code=302)
        response.set_cookie(
            key="session",
            value=session_token,
            httponly=True,
            max_age=86400,  # 24 hours
            samesite="lax",
        )
        return response
    else:
        # Invalid credentials
        return RedirectResponse(url="/login?error=invalid", status_code=302)


@router.get("/logout")
async def logout(response: Response, session: str | None = Cookie(default=None)):
    """Logout and clear session.

    Invalidates session and redirects to login page.

    Extracted from: app_enhanced.py:219
    """
    if session:
        auth_logout(session)

    response = RedirectResponse(url="/login", status_code=302)
    response.delete_cookie("session")
    return response


# ============================================================================
# Utility Routes
# ============================================================================


@router.get("/favicon.ico", include_in_schema=False)
async def favicon():
    """Return empty favicon to prevent 404s.

    Extracted from: app_enhanced.py:149
    """
    return Response(status_code=204)
