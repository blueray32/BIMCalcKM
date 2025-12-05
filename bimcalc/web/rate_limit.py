"""Rate Limiting Middleware for FastAPI.

Provides Redis-backed rate limiting with configurable limits per endpoint.
Uses sliding window algorithm for accurate rate limiting.
"""

from __future__ import annotations

import logging
import os
import time
from typing import Callable

from fastapi import HTTPException, Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)

# Default rate limits (requests per minute)
DEFAULT_RATE_LIMIT = 60  # 60 requests per minute for general endpoints
API_RATE_LIMIT = 30  # 30 requests per minute for API endpoints
HEAVY_RATE_LIMIT = 10  # 10 requests per minute for heavy operations

# Rate limit window in seconds
RATE_LIMIT_WINDOW = 60


def get_redis_client():
    """Get Redis client for rate limiting."""
    try:
        import redis
        redis_url = os.environ.get("REDIS_URL", "redis://redis:6379/0")
        return redis.from_url(redis_url, decode_responses=True)
    except Exception as e:
        logger.warning(f"Redis unavailable for rate limiting: {e}")
        return None


def get_client_identifier(request: Request) -> str:
    """Extract client identifier for rate limiting.
    
    Uses X-Forwarded-For header if behind proxy, otherwise client IP.
    
    Args:
        request: FastAPI request object
        
    Returns:
        Client identifier string
    """
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        # Take the first IP in the chain (client's IP)
        return forwarded_for.split(",")[0].strip()
    
    if request.client:
        return request.client.host
    
    return "unknown"


def get_rate_limit_for_path(path: str) -> int:
    """Determine rate limit based on request path.
    
    Args:
        path: Request path
        
    Returns:
        Rate limit (requests per minute)
    """
    # Heavy operations
    if any(p in path for p in ["/match", "/sync", "/import", "/export"]):
        return HEAVY_RATE_LIMIT
    
    # API endpoints
    if path.startswith("/api/"):
        return API_RATE_LIMIT
    
    # Default
    return DEFAULT_RATE_LIMIT


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Middleware that enforces rate limiting on requests.
    
    Usage:
        app.add_middleware(RateLimitMiddleware)
        
    Rate limits are stored in Redis with sliding window algorithm.
    Falls back to no rate limiting if Redis is unavailable.
    """
    
    # Paths exempt from rate limiting
    EXEMPT_PATHS = {"/health", "/metrics", "/static", "/favicon.ico"}
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        path = request.url.path
        
        # Skip rate limiting for exempt paths
        if any(path.startswith(exempt) for exempt in self.EXEMPT_PATHS):
            return await call_next(request)
        
        # Get Redis client
        redis_client = get_redis_client()
        if not redis_client:
            # No rate limiting without Redis
            return await call_next(request)
        
        # Get client identifier and rate limit
        client_id = get_client_identifier(request)
        rate_limit = get_rate_limit_for_path(path)
        
        # Build Redis key
        key = f"rate_limit:{client_id}:{path}"
        
        try:
            # Use sliding window counter
            now = time.time()
            window_start = now - RATE_LIMIT_WINDOW
            
            # Remove old entries and count current
            pipe = redis_client.pipeline()
            pipe.zremrangebyscore(key, 0, window_start)
            pipe.zadd(key, {str(now): now})
            pipe.zcard(key)
            pipe.expire(key, RATE_LIMIT_WINDOW + 1)
            results = pipe.execute()
            
            request_count = results[2]
            
            # Check if over limit
            if request_count > rate_limit:
                retry_after = RATE_LIMIT_WINDOW
                logger.warning(
                    f"Rate limit exceeded for {client_id} on {path}: "
                    f"{request_count}/{rate_limit}"
                )
                raise HTTPException(
                    status_code=429,
                    detail=f"Rate limit exceeded. Try again in {retry_after} seconds.",
                    headers={
                        "Retry-After": str(retry_after),
                        "X-RateLimit-Limit": str(rate_limit),
                        "X-RateLimit-Remaining": "0",
                        "X-RateLimit-Reset": str(int(now + retry_after)),
                    }
                )
            
            # Add rate limit headers to response
            response = await call_next(request)
            response.headers["X-RateLimit-Limit"] = str(rate_limit)
            response.headers["X-RateLimit-Remaining"] = str(rate_limit - request_count)
            response.headers["X-RateLimit-Reset"] = str(int(now + RATE_LIMIT_WINDOW))
            
            return response
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Rate limiting error: {e}")
            # On error, allow the request through
            return await call_next(request)
