"""Simple authentication for BIMCalc web UI.

Uses environment variables for credentials and session-based authentication.
For production, integrate with proper identity provider (OAuth, SAML, etc.).
"""

from __future__ import annotations

import hashlib
import json
import os
import secrets
from datetime import datetime, timedelta

import redis
from fastapi import Cookie, HTTPException, Request

# Redis connection for session storage
def get_redis_client() -> redis.Redis:
    """Get Redis client for session storage."""
    redis_url = os.environ.get("REDIS_URL", "redis://redis:6379/0")
    return redis.from_url(redis_url, decode_responses=True)

# Session expiry
SESSION_EXPIRY_HOURS = 24
SESSION_EXPIRY_SECONDS = SESSION_EXPIRY_HOURS * 3600


def get_credentials() -> tuple[str, str]:
    """Get username and password from environment variables.

    Returns:
        tuple: (username, password_hash)

    Raises:
        RuntimeError: If credentials not configured
    """
    username = os.environ.get("BIMCALC_USERNAME", "admin")
    password = os.environ.get("BIMCALC_PASSWORD")

    if not password:
        # For demo/development only - MUST set in production
        password = "changeme"
        print("⚠️  WARNING: Using default password 'changeme'. Set BIMCALC_PASSWORD environment variable!")

    # Hash the password for comparison
    password_hash = hashlib.sha256(password.encode()).hexdigest()

    return username, password_hash


def create_session(username: str) -> str:
    """Create a new session for authenticated user.

    Args:
        username: Username of authenticated user

    Returns:
        str: Session token
    """
    session_token = secrets.token_urlsafe(32)
    redis_client = get_redis_client()
    
    session_data = {
        "username": username,
        "created_at": datetime.utcnow().isoformat(),
        "expires_at": (datetime.utcnow() + timedelta(hours=SESSION_EXPIRY_HOURS)).isoformat(),
    }
    
    # Store in Redis with TTL
    redis_client.setex(
        f"session:{session_token}",
        SESSION_EXPIRY_SECONDS,
        json.dumps(session_data)
    )
    
    return session_token


def validate_session(session_token: str | None) -> str | None:
    """Validate session token and return username if valid.

    Args:
        session_token: Session token from cookie

    Returns:
        Optional[str]: Username if session valid, None otherwise
    """
    if not session_token:
        return None

    redis_client = get_redis_client()
    session_data_str = redis_client.get(f"session:{session_token}")
    
    if not session_data_str:
        return None

    try:
        session_data = json.loads(session_data_str)
        
        # Check if session expired (Redis TTL should handle this, but double-check)
        expires_at = datetime.fromisoformat(session_data["expires_at"])
        if datetime.utcnow() > expires_at:
            redis_client.delete(f"session:{session_token}")
            return None
        
        return session_data["username"]
    except (json.JSONDecodeError, KeyError, ValueError):
        # Invalid session data
        redis_client.delete(f"session:{session_token}")
        return None


def require_auth(request: Request, session: str | None = Cookie(default=None)) -> str:
    """Dependency to require authentication on routes.

    Args:
        request: FastAPI request object
        session: Session token from cookie

    Returns:
        str: Username of authenticated user

    Raises:
        HTTPException: If not authenticated (redirects to login)
    """
    # Check if authentication is disabled
    auth_disabled = os.environ.get("BIMCALC_AUTH_DISABLED", "false").lower() == "true"
    if auth_disabled:
        return "default_user"  # Return a default user when auth is disabled
    
    username = validate_session(session)
    if not username:
        # Redirect to login page
        raise HTTPException(
            status_code=307,
            detail="Authentication required",
            headers={"Location": "/login"}
        )

    return username


def verify_credentials(username: str, password: str) -> bool:
    """Verify username and password.

    Args:
        username: Provided username
        password: Provided password

    Returns:
        bool: True if credentials valid
    """
    valid_username, valid_password_hash = get_credentials()
    password_hash = hashlib.sha256(password.encode()).hexdigest()

    return username == valid_username and password_hash == valid_password_hash


def logout(session_token: str | None) -> None:
    """Logout user by invalidating session.

    Args:
        session_token: Session token to invalidate
    """
    if session_token:
        redis_client = get_redis_client()
        redis_client.delete(f"session:{session_token}")


def cleanup_expired_sessions() -> None:
    """Remove expired sessions from Redis.
    
    Note: Redis TTL automatically handles expiration, so this is mainly
    for manual cleanup if needed.
    """
    # Redis TTL handles expiration automatically, but we can still implement
    # manual cleanup if needed for monitoring or other purposes
    pass
