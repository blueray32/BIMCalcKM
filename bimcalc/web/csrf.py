"""CSRF Protection Middleware for FastAPI.

Provides Cross-Site Request Forgery protection using synchronizer tokens.
Tokens are stored in sessions and validated on state-changing requests.
"""

from __future__ import annotations

import logging
import secrets
from typing import Callable

from fastapi import HTTPException, Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)

# CSRF token length (32 bytes = 256 bits of entropy)
CSRF_TOKEN_LENGTH = 32

# Header name for CSRF token
CSRF_HEADER_NAME = "X-CSRF-Token"

# Form field name for CSRF token
CSRF_FORM_FIELD = "csrf_token"

# Safe HTTP methods that don't require CSRF protection
SAFE_METHODS = {"GET", "HEAD", "OPTIONS", "TRACE"}

# Paths that are exempt from CSRF protection (e.g., API endpoints with their own auth)
EXEMPT_PATHS = {
    "/api/",
    "/docs",
    "/redoc",
    "/openapi.json",
    "/metrics",
    "/health",
}


def generate_csrf_token() -> str:
    """Generate a cryptographically secure CSRF token.
    
    Returns:
        str: URL-safe base64 encoded token
    """
    return secrets.token_urlsafe(CSRF_TOKEN_LENGTH)


def get_csrf_token_from_request(request: Request) -> str | None:
    """Extract CSRF token from request (header or form field).
    
    Args:
        request: FastAPI request object
        
    Returns:
        CSRF token if found, None otherwise
    """
    # Check header first
    token = request.headers.get(CSRF_HEADER_NAME)
    if token:
        return token
    
    # Check form data (if already parsed)
    if hasattr(request, "_form") and request._form:
        return request._form.get(CSRF_FORM_FIELD)
    
    return None


def is_exempt_path(path: str) -> bool:
    """Check if path is exempt from CSRF protection.
    
    Args:
        path: Request path
        
    Returns:
        True if path is exempt
    """
    return any(path.startswith(exempt) for exempt in EXEMPT_PATHS)


class CSRFMiddleware(BaseHTTPMiddleware):
    """Middleware that enforces CSRF protection on state-changing requests.
    
    Usage:
        app.add_middleware(CSRFMiddleware)
        
    Tokens are stored in the session cookie and must be included in
    either the X-CSRF-Token header or csrf_token form field.
    """
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Skip CSRF check for safe methods
        if request.method in SAFE_METHODS:
            return await call_next(request)
        
        # Skip CSRF check for exempt paths
        if is_exempt_path(request.url.path):
            return await call_next(request)
        
        # Get session token from cookie
        session_token = request.cookies.get("csrf_token")
        
        # Get submitted token from request
        submitted_token = get_csrf_token_from_request(request)
        
        # If no form data yet, try to parse it for CSRF token
        if not submitted_token and request.headers.get("content-type", "").startswith(
            "application/x-www-form-urlencoded"
        ):
            try:
                form = await request.form()
                submitted_token = form.get(CSRF_FORM_FIELD)
            except Exception:
                pass
        
        # Validate token
        if not session_token or not submitted_token:
            logger.warning(
                f"CSRF token missing for {request.method} {request.url.path}"
            )
            raise HTTPException(
                status_code=403,
                detail="CSRF token missing"
            )
        
        if not secrets.compare_digest(session_token, submitted_token):
            logger.warning(
                f"CSRF token mismatch for {request.method} {request.url.path}"
            )
            raise HTTPException(
                status_code=403,
                detail="CSRF token invalid"
            )
        
        return await call_next(request)


def set_csrf_cookie(response: Response, token: str) -> None:
    """Set CSRF token cookie on response.
    
    Args:
        response: FastAPI response object
        token: CSRF token to set
    """
    response.set_cookie(
        key="csrf_token",
        value=token,
        httponly=False,  # JavaScript needs access for AJAX requests
        secure=True,  # Only send over HTTPS (set to False for local dev)
        samesite="strict",  # Strict same-site policy
        max_age=86400,  # 24 hours
    )
