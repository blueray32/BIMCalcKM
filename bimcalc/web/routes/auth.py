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

from bimcalc.web.auth import create_session, verify_credentials, verify_credentials_db, validate_session
from bimcalc.web.auth import logout as auth_logout
from bimcalc.web.dependencies import get_templates
from bimcalc.core.audit_logger import log_action

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
    # Try DB auth first
    is_valid, user = await verify_credentials_db(username, password)
    if is_valid:
        session_token = create_session(username, role=user.role, user_id=str(user.id))
        response = RedirectResponse(url="/", status_code=302)
        response.set_cookie(
            key="session",
            value=session_token,
            httponly=True,
            max_age=86400,  # 24 hours
            samesite="lax",
        )
        await log_action(request, "LOGIN", username, user_id=user.id, resource_type="system", details={"method": "db"})
        return response

    # Fallback to env auth (legacy admin)
    if verify_credentials(username, password):
        # Create session (env user is always admin)
        session_token = create_session(username, role="admin")

        # Set cookie
        response = RedirectResponse(url="/", status_code=302)
        response.set_cookie(
            key="session",
            value=session_token,
            httponly=True,
            max_age=86400,  # 24 hours
            samesite="lax",
        )
        await log_action(request, "LOGIN", username, resource_type="system", details={"method": "env"})
        return response
    else:
        # Invalid credentials
        await log_action(request, "LOGIN_FAILED", username, resource_type="system")
        return RedirectResponse(url="/login?error=invalid", status_code=302)


@router.get("/logout")
async def logout(request: Request, response: Response, session: str | None = Cookie(default=None)):
    """Logout and clear session.

    Invalidates session and redirects to login page.

    Extracted from: app_enhanced.py:219
    """

    session_data = validate_session(session)
    username = session_data["username"] if session_data else "unknown"
    user_id = session_data.get("user_id") if session_data else None

    if session:
        auth_logout(session)
    
    if username != "unknown":
        await log_action(request, "LOGOUT", username, user_id=user_id, resource_type="system")

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
