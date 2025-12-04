"""Performance monitoring utilities."""

import logging
import time
from functools import wraps
from typing import Callable

logger = logging.getLogger(__name__)


def log_slow_queries(threshold_ms: float = 500):
    """Decorator to log slow async functions.

    Args:
        threshold_ms: Log if function takes longer than this many milliseconds

    Example:
        @log_slow_queries(threshold_ms=1000)
        async def expensive_query(session):
            ...
    """

    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            start = time.time()
            try:
                result = await func(*args, **kwargs)
                return result
            finally:
                duration_ms = (time.time() - start) * 1000

                if duration_ms > threshold_ms:
                    logger.warning(
                        f"Slow query detected: {func.__name__} took {duration_ms:.2f}ms "
                        f"(threshold: {threshold_ms}ms)"
                    )
                else:
                    logger.debug(f"{func.__name__} completed in {duration_ms:.2f}ms")

        return wrapper

    return decorator


class QueryTimer:
    """Context manager for timing code blocks.

    Example:
        async with QueryTimer("expensive_operation"):
            result = await do_something()
    """

    def __init__(self, operation_name: str, threshold_ms: float = 500):
        self.operation_name = operation_name
        self.threshold_ms = threshold_ms
        self.start_time = None

    def __enter__(self):
        self.start_time = time.time()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        duration_ms = (time.time() - self.start_time) * 1000

        if duration_ms > self.threshold_ms:
            logger.warning(
                f"Slow operation: {self.operation_name} took {duration_ms:.2f}ms"
            )
        else:
            logger.debug(f"{self.operation_name} completed in {duration_ms:.2f}ms")
