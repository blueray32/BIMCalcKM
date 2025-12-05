"""Simple authentication for BIMCalc web UI.

Uses environment variables for credentials and session-based authentication.
For production, integrate with proper identity provider (OAuth, SAML, etc.).
"""

from __future__ import annotations

import json
import logging
import os
import secrets
from datetime import datetime, timedelta

import bcrypt
import redis
from fastapi import Cookie, HTTPException, Request
from sqlalchemy import select

from bimcalc.db.connection import get_session
from bimcalc.db.models import UserModel

logger = logging.getLogger(__name__)

# Redis connection for session storage
def get_redis_client() -> redis.Redis:
    """Get Redis client for session storage."""
    redis_url = os.environ.get("REDIS_URL", "redis://redis:6379/0")
    return redis.from_url(redis_url, decode_responses=True)


# Session expiry
SESSION_EXPIRY_HOURS = 24
SESSION_EXPIRY_SECONDS = SESSION_EXPIRY_HOURS * 3600

# In-memory fallback for development when Redis is missing
_memory_sessions = {}

# Cache for bcrypt password hash (expensive to compute)
_password_hash_cache: bytes | None = None


def _get_password_hash() -> bytes:
    """Get or create bcrypt password hash from environment.
    
    Returns:
        bytes: bcrypt hash of the password
    """
    global _password_hash_cache
    
    if _password_hash_cache is not None:
        return _password_hash_cache
    
    password = os.environ.get("BIMCALC_PASSWORD")
    
    if not password:
        # For demo/development only - MUST set in production
        password = "changeme"
        logger.warning(
            "Using default password 'changeme'. Set BIMCALC_PASSWORD environment variable!"
        )
    
    # Generate bcrypt hash (includes salt automatically)
    _password_hash_cache = bcrypt.hashpw(password.encode(), bcrypt.gensalt(rounds=12))
    return _password_hash_cache


def get_credentials() -> tuple[str, bytes]:
    """Get username and password hash from environment variables.

    Returns:
        tuple: (username, bcrypt_password_hash)

    Raises:
        RuntimeError: If credentials not configured
    """
    username = os.environ.get("BIMCALC_USERNAME", "admin")
    password_hash = _get_password_hash()
    
    return username, password_hash


def create_session(username: str, role: str = "viewer", user_id: str | None = None) -> str:
    """Create a new session for authenticated user.

    Args:
        username: Username of authenticated user
        role: User role (admin, manager, viewer)
        user_id: Database ID of user

    Returns:
        str: Session token
    """
    session_token = secrets.token_urlsafe(32)

    session_data = {
        "username": username,
        "role": role,
        "user_id": user_id,
        "created_at": datetime.utcnow().isoformat(),
        "expires_at": (
            datetime.utcnow() + timedelta(hours=SESSION_EXPIRY_HOURS)
        ).isoformat(),
    }

    try:
        redis_client = get_redis_client()
        # Store in Redis with TTL
        redis_client.setex(
            f"session:{session_token}", SESSION_EXPIRY_SECONDS, json.dumps(session_data)
        )
    except (redis.exceptions.ConnectionError, redis.exceptions.TimeoutError):
        print("⚠️  Redis unavailable, using in-memory session storage")
        _memory_sessions[session_token] = session_data

    return session_token


def validate_session(session_token: str | None) -> dict | None:
    """Validate session token and return session data if valid.

    Args:
        session_token: Session token from cookie

    Returns:
        Optional[dict]: Session data (username, role, etc.) if valid, None otherwise
    """
    if not session_token:
        return None

    session_data_str = None

    try:
        redis_client = get_redis_client()
        session_data_str = redis_client.get(f"session:{session_token}")
    except (redis.exceptions.ConnectionError, redis.exceptions.TimeoutError):
        # Fallback to memory
        session_data = _memory_sessions.get(session_token)
        if session_data:
            # Check expiry for memory sessions
            expires_at = datetime.fromisoformat(session_data["expires_at"])
            if datetime.utcnow() > expires_at:
                del _memory_sessions[session_token]
                return None
            return session_data
        return None

    if not session_data_str:
        return None

    try:
        session_data = json.loads(session_data_str)

        # Check if session expired (Redis TTL should handle this, but double-check)
        expires_at = datetime.fromisoformat(session_data["expires_at"])
        if datetime.utcnow() > expires_at:
            redis_client.delete(f"session:{session_token}")
            return None

        return session_data
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

    session_data = validate_session(session)
    if not session_data:
        # Redirect to login page
        raise HTTPException(
            status_code=307,
            detail="Authentication required",
            headers={"Location": "/login"},
        )

    return session_data["username"]


def require_admin(request: Request, session: str | None = Cookie(default=None)) -> str:
    """Dependency to require admin role.

    Args:
        request: FastAPI request object
        session: Session token from cookie

    Returns:
        str: Username of authenticated admin

    Raises:
        HTTPException: If not authenticated or not admin
    """
    # Check if authentication is disabled
    auth_disabled = os.environ.get("BIMCALC_AUTH_DISABLED", "false").lower() == "true"
    if auth_disabled:
        return "default_admin"

    session_data = validate_session(session)
    if not session_data:
        raise HTTPException(
            status_code=307,
            detail="Authentication required",
            headers={"Location": "/login"},
        )

    if session_data.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")

    return session_data["username"]


async def verify_credentials_db(email: str, password: str) -> tuple[bool, UserModel | None]:
    """Verify credentials against database.

    Args:
        email: User email
        password: User password

    Returns:
        tuple: (is_valid, user_object)
    """
    try:
        async with get_session() as session:
            stmt = select(UserModel).where(UserModel.email == email)
            result = await session.execute(stmt)
            user = result.scalars().first()

            if not user:
                return False, None

            if not user.is_active:
                return False, None

            # Verify password
            # Note: password_hash in DB is string, bcrypt needs bytes
            if bcrypt.checkpw(password.encode(), user.password_hash.encode()):
                # Update last login
                user.last_login = datetime.utcnow()
                await session.commit()
                return True, user

            return False, None
    except Exception as e:
        logger.error(f"Database auth failed: {e}")
        return False, None


def verify_credentials(username: str, password: str) -> bool:
    """Verify username and password using bcrypt.

    Args:
        username: Provided username
        password: Provided password

    Returns:
        bool: True if credentials valid
    """
    valid_username, valid_password_hash = get_credentials()
    
    # Use bcrypt's secure comparison (constant-time to prevent timing attacks)
    password_matches = bcrypt.checkpw(password.encode(), valid_password_hash)
    
    return username == valid_username and password_matches


def logout(session_token: str | None) -> None:
    """Logout user by invalidating session.

    Args:
        session_token: Session token to invalidate
    """
    if session_token:
        try:
            redis_client = get_redis_client()
            redis_client.delete(f"session:{session_token}")
        except (redis.exceptions.ConnectionError, redis.exceptions.TimeoutError):
            if session_token in _memory_sessions:
                del _memory_sessions[session_token]


def cleanup_expired_sessions() -> None:
    """Remove expired sessions from Redis.

    Note: Redis TTL automatically handles expiration, so this is mainly
    for manual cleanup if needed.
    """
    # Redis TTL handles expiration automatically, but we can still implement
    # manual cleanup if needed for monitoring or other purposes
    pass
