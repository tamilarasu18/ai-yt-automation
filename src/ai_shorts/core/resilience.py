"""
Resilience — retry decorator with exponential backoff.

Provides fault-tolerance for unreliable external service calls
(LLM APIs, network requests, GPU operations).

Usage:
    @retry_with_backoff(max_retries=3, base_delay=2.0)
    def call_external_api():
        ...
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from functools import wraps
from typing import Any, TypeVar

log = logging.getLogger(__name__)

F = TypeVar("F", bound=Callable[..., Any])


def retry_with_backoff(
    max_retries: int = 3,
    base_delay: float = 2.0,
    max_delay: float = 60.0,
    exceptions: tuple[type[Exception], ...] = (Exception,),
    on_retry: Callable[[Exception, int], None] | None = None,
) -> Callable[[F], F]:
    """Decorator: retry a function with exponential backoff.

    Args:
        max_retries: Maximum number of attempts.
        base_delay: Initial delay in seconds before first retry.
        max_delay: Maximum delay cap in seconds.
        exceptions: Tuple of exception types to catch.
        on_retry: Optional callback invoked on each retry with (exception, attempt).

    Returns:
        Decorated function with retry logic.

    Example:
        @retry_with_backoff(max_retries=3, exceptions=(ConnectionError, TimeoutError))
        def fetch_data():
            return requests.get("https://api.example.com/data")
    """

    def decorator(func: F) -> F:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            last_exception: Exception | None = None

            for attempt in range(1, max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    if attempt < max_retries:
                        delay = min(base_delay * (2 ** (attempt - 1)), max_delay)
                        log.warning(
                            "⚠️  %s failed (attempt %d/%d): %s",
                            func.__name__,
                            attempt,
                            max_retries,
                            e,
                        )
                        log.info("   Retrying in %.1fs...", delay)

                        if on_retry:
                            on_retry(e, attempt)

                        time.sleep(delay)
                    else:
                        log.error(
                            "❌ %s failed after %d attempts: %s",
                            func.__name__,
                            max_retries,
                            e,
                        )

            raise last_exception  # type: ignore[misc]

        return wrapper  # type: ignore[return-value]

    return decorator
