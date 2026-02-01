"""Rate limiting middleware for FastAPI.

Implements sliding window rate limiting using in-memory storage.
"""

import asyncio
import logging
import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Awaitable, Callable

from fastapi import HTTPException, Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)


@dataclass
class RateLimitConfig:
    """Configuration for rate limiting."""

    requests_per_minute: int = 60
    requests_per_hour: int = 1000
    burst_limit: int = 10  # Max requests in 10 second window


@dataclass
class ClientRequestHistory:
    """Track request history for a client."""

    timestamps: list[float] = field(default_factory=list)
    cleanup_after: float = 3600  # Cleanup history after 1 hour of inactivity


class InMemoryRateLimiter:
    """In-memory sliding window rate limiter.

    Uses a sliding window algorithm to track requests per client.
    Automatically cleans up stale client data.
    """

    def __init__(self, config: RateLimitConfig | None = None):
        self._config = config or RateLimitConfig()
        self._clients: dict[str, ClientRequestHistory] = defaultdict(
            lambda: ClientRequestHistory()
        )
        self._last_cleanup = time.time()
        self._cleanup_interval = 300  # Cleanup every 5 minutes
        self._lock = asyncio.Lock()

    def _get_client_key(self, request: Request) -> str:
        """Get a unique identifier for the client.

        Uses X-Forwarded-For header if present (for proxied requests),
        otherwise uses the client's direct IP address.
        """
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            # Take the first IP in the chain
            return forwarded.split(",")[0].strip()

        # Fall back to direct client address
        if request.client:
            return request.client.host

        # No client info - don't rate limit (edge case for testing)
        return "localhost"

    def _cleanup_stale_clients(self) -> None:
        """Remove stale client data to prevent memory leaks."""
        now = time.time()
        if now - self._last_cleanup < self._cleanup_interval:
            return

        stale_keys = []
        for key, history in self._clients.items():
            if history.timestamps and now - max(history.timestamps) > history.cleanup_after:
                stale_keys.append(key)
            elif not history.timestamps:
                # Empty history - remove
                stale_keys.append(key)

        for key in stale_keys:
            del self._clients[key]

        if stale_keys:
            logger.debug(f"Cleaned up {len(stale_keys)} stale rate limit entries")

        self._last_cleanup = now

    def _check_sliding_window(
        self, timestamps: list[float], window_seconds: float, limit: int
    ) -> bool:
        """Check if the request count exceeds the limit in the sliding window.

        Args:
            timestamps: List of request timestamps
            window_seconds: Size of the time window in seconds
            limit: Maximum allowed requests in the window

        Returns:
            True if within limit, False if exceeded
        """
        now = time.time()
        window_start = now - window_seconds

        # Count requests in the window
        requests_in_window = sum(1 for ts in timestamps if ts > window_start)

        return requests_in_window < limit

    async def is_allowed(
        self, request: Request, config: RateLimitConfig | None = None
    ) -> tuple[bool, str]:
        """Check if a request should be allowed.

        Args:
            request: The incoming request
            config: Optional override config (uses default if not provided)

        Returns:
            Tuple of (is_allowed, error_message)
        """
        effective_config = config or self._config
        client_key = self._get_client_key(request)

        # Acquire lock for thread safety
        async with self._lock:
            # Periodic cleanup of stale clients
            self._cleanup_stale_clients()

            now = time.time()
            history = self._clients[client_key]

            # Clean up old timestamps outside our tracking window
            window_start = now - 3600  # Keep 1 hour of history
            history.timestamps = [ts for ts in history.timestamps if ts > window_start]

            # Check burst limit (10 second window)
            if not self._check_sliding_window(
                history.timestamps, 10, effective_config.burst_limit
            ):
                retry_after = 10
                logger.warning(
                    f"Rate limit exceeded (burst) for {client_key}: "
                    f"{len(history.timestamps)} requests in last 10 seconds"
                )
                return (
                    False,
                    f"Rate limit exceeded. Maximum {effective_config.burst_limit} requests per 10 seconds.",
                )

            # Check per-minute limit
            if not self._check_sliding_window(
                history.timestamps, 60, effective_config.requests_per_minute
            ):
                retry_after = 60
                logger.warning(
                    f"Rate limit exceeded (minute) for {client_key}: "
                    f"more than {effective_config.requests_per_minute} requests in last minute"
                )
                return (
                    False,
                    f"Rate limit exceeded. Maximum {effective_config.requests_per_minute} requests per minute.",
                )

            # Check per-hour limit
            if not self._check_sliding_window(
                history.timestamps, 3600, effective_config.requests_per_hour
            ):
                retry_after = 3600
                logger.warning(
                    f"Rate limit exceeded (hour) for {client_key}: "
                    f"more than {effective_config.requests_per_hour} requests in last hour"
                )
                return (
                    False,
                    f"Rate limit exceeded. Maximum {effective_config.requests_per_hour} requests per hour.",
                )

            # Add current request timestamp
            history.timestamps.append(now)

            return True, ""


class RateLimitMiddleware(BaseHTTPMiddleware):
    """FastAPI middleware for rate limiting.

    Applies rate limiting to all requests. Exempts health check endpoints.
    Can be disabled via ARIADNE_RATE_LIMIT_ENABLED environment variable.
    """

    def __init__(
        self,
        app,
        limiter: InMemoryRateLimiter | None = None,
        config: RateLimitConfig | None = None,
        exempt_paths: set[str] | None = None,
        enabled: bool | None = None,
    ):
        super().__init__(app)
        self._limiter = limiter or InMemoryRateLimiter(config)
        self._exempt_paths = exempt_paths or {"/health", "/docs", "/openapi.json", "/"}
        # Allow disabling rate limiting via environment variable or parameter
        import os
        if enabled is None:
            enabled = os.environ.get("ARIADNE_RATE_LIMIT_ENABLED", "true").lower() == "true"
        self._enabled = enabled

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        """Process request with rate limiting.

        Args:
            request: The incoming request
            call_next: The next middleware or route handler

        Returns:
            Response or raises HTTPException if rate limited

        Raises:
            HTTPException: 429 Too Many Requests if rate limit exceeded
        """
        # Skip rate limiting if disabled
        if not self._enabled:
            return await call_next(request)

        # Skip rate limiting for exempt paths
        if request.url.path in self._exempt_paths:
            return await call_next(request)

        # Check rate limit
        allowed, error_message = await self._limiter.is_allowed(request)

        if not allowed:
            raise HTTPException(
                status_code=429,
                detail=error_message,
                headers={
                    "Retry-After": "60",
                    "X-RateLimit-Limit": str(self._limiter._config.requests_per_minute),
                    "X-RateLimit-Remaining": "0",
                },
            )

        # Process request
        response = await call_next(request)

        # Add rate limit headers to response
        response.headers["X-RateLimit-Limit"] = str(self._limiter._config.requests_per_minute)
        response.headers["X-RateLimit-Remaining"] = str(
            max(0, self._limiter._config.requests_per_minute - len(self._limiter._clients.get(self._limiter._get_client_key(request), ClientRequestHistory()).timestamps))
        )
        response.headers["X-RateLimit-Reset"] = str(int(time.time()) + 60)

        return response


# Global rate limiter instance
_default_limiter: InMemoryRateLimiter | None = None


def get_rate_limiter(config: RateLimitConfig | None = None) -> InMemoryRateLimiter:
    """Get or create the global rate limiter instance.

    Args:
        config: Optional configuration (uses default on first call)

    Returns:
        The global rate limiter instance
    """
    global _default_limiter
    if _default_limiter is None:
        _default_limiter = InMemoryRateLimiter(config)
    return _default_limiter
