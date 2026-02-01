"""Tests for rate limiting middleware."""

import asyncio
from unittest.mock import Mock

import pytest
from fastapi import HTTPException, Request
from starlette.datastructures import Headers

from ariadne_api.rate_limiter import (
    InMemoryRateLimiter,
    RateLimitConfig,
    RateLimitMiddleware,
    ClientRequestHistory,
    get_rate_limiter,
)


@pytest.fixture
def rate_limit_config():
    """Create a test rate limit config."""
    return RateLimitConfig(
        requests_per_minute=5,  # Low limit for testing
        requests_per_hour=100,
        burst_limit=3,  # Very low burst limit
    )


@pytest.fixture
def limiter(rate_limit_config):
    """Create a rate limiter for testing."""
    return InMemoryRateLimiter(rate_limit_config)


@pytest.fixture
def mock_request():
    """Create a mock request."""
    request = Mock(spec=Request)
    request.client = Mock()
    request.client.host = "192.168.1.1"
    request.headers = Headers({"user-agent": "test"})
    return request


class TestInMemoryRateLimiter:
    """Tests for InMemoryRateLimiter."""

    @pytest.mark.asyncio
    async def test_allow_requests_within_limit(self, limiter, mock_request):
        """Test that requests within the limit are allowed."""
        for i in range(3):
            allowed, _ = await limiter.is_allowed(mock_request)
            assert allowed, f"Request {i+1} should be allowed"

    @pytest.mark.asyncio
    async def test_burst_limit_enforcement(self, limiter, mock_request):
        """Test that burst limit is enforced."""
        # Make requests up to burst limit
        for _ in range(limiter._config.burst_limit):
            allowed, _ = await limiter.is_allowed(mock_request)
            assert allowed

        # Next request should be rate limited
        allowed, message = await limiter.is_allowed(mock_request)
        assert not allowed, "Should be rate limited after burst limit"
        assert "Rate limit exceeded" in message

    @pytest.mark.asyncio
    async def test_different_clients_independent(self, limiter):
        """Test that different clients have independent rate limits."""
        client1 = Mock(spec=Request)
        client1.client = Mock()
        client1.client.host = "192.168.1.1"
        client1.headers = Headers({})

        client2 = Mock(spec=Request)
        client2.client = Mock()
        client2.client.host = "192.168.1.2"
        client2.headers = Headers({})

        # Client 1 exhausts burst limit
        for _ in range(limiter._config.burst_limit):
            await limiter.is_allowed(client1)

        # Client 1 should be rate limited
        allowed, _ = await limiter.is_allowed(client1)
        assert not allowed

        # Client 2 should still be allowed
        allowed, _ = await limiter.is_allowed(client2)
        assert allowed

    @pytest.mark.asyncio
    async def test_x_forwarded_for_header(self, limiter):
        """Test that X-Forwarded-For header is used for client key."""
        client1 = Mock(spec=Request)
        client1.client = Mock()
        client1.client.host = "10.0.0.1"
        client1.headers = Headers({"X-Forwarded-For": "203.0.113.1"})

        client2 = Mock(spec=Request)
        client2.client = Mock()
        client2.client.host = "10.0.0.2"
        client2.headers = Headers({"X-Forwarded-For": "203.0.113.1"})

        # Both should be tracked as the same client (by X-Forwarded-For)
        await limiter.is_allowed(client1)
        await limiter.is_allowed(client2)

        # Both clients share the same rate limit
        key1 = limiter._get_client_key(client1)
        key2 = limiter._get_client_key(client2)
        assert key1 == key2 == "203.0.113.1"

    @pytest.mark.asyncio
    async def test_cleanup_stale_clients(self, limiter, mock_request):
        """Test that stale client data is cleaned up."""
        import time

        # Set _last_cleanup to allow cleanup to run (simulate 5 minutes have passed)
        limiter._last_cleanup = time.time() - 400

        # Manually add a client with old timestamps
        client_key = limiter._get_client_key(mock_request)
        limiter._clients[client_key].timestamps = [time.time() - 4000]  # Over 1 hour ago
        assert client_key in limiter._clients

        # Trigger cleanup
        limiter._cleanup_stale_clients()

        # Client should be removed (check the actual dict, not defaultdict which recreates)
        assert client_key not in list(limiter._clients.keys())

    @pytest.mark.asyncio
    async def test_sliding_window_calculation(self, limiter):
        """Test that sliding window calculation is correct."""
        import time

        now = time.time()

        # Create timestamps in the past
        timestamps = [
            now - 2,  # 2 seconds ago
            now - 1,  # 1 second ago
            now,      # now
        ]

        # 3-second window should include all 3 requests
        assert limiter._check_sliding_window(timestamps, 3, 4), "Should allow 3 requests in 3 seconds with limit 4"

        # 1-second window should include only the recent request
        # The function returns True if count < limit
        # With limit=1, having 1 request means count (1) is NOT < limit (1), so should be False
        assert not limiter._check_sliding_window(timestamps, 1, 1), "Should reject when count >= limit"

        # With limit=2, having 1 request means count (1) < limit (2), so should be True
        assert limiter._check_sliding_window(timestamps, 1, 2), "Should allow when count < limit"


class TestRateLimitMiddleware:
    """Tests for RateLimitMiddleware."""

    @pytest.mark.asyncio
    async def test_exempt_paths_not_rate_limited(self, rate_limit_config):
        """Test that exempt paths bypass rate limiting."""
        from starlette.responses import Response

        exempt_paths = {"/health", "/docs"}

        # Create a simple ASGI app that returns a response
        async def dummy_app(scope, receive, send):
            response = Response(content="OK", status_code=200)
            await response(scope, receive, send)

        middleware = RateLimitMiddleware(
            dummy_app, config=rate_limit_config, exempt_paths=exempt_paths
        )

        # Create mock request for exempt path
        request = Mock(spec=Request)
        request.url = Mock()
        request.url.path = "/health"
        request.headers = Headers({})

        async def call_next(req):
            return Response(content="OK", status_code=200)

        # Should not raise HTTPException
        response = await middleware.dispatch(request, call_next)
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_rate_limit_headers_added(self, limiter):
        """Test that rate limit headers are added to responses."""
        async def call_next(request):
            from starlette.responses import Response
            return Response(content="OK", status_code=200)

        request = Mock(spec=Request)
        request.url = Mock()
        request.url.path = "/api/search"
        request.client = Mock()
        request.client.host = "192.168.1.1"
        request.headers = Headers({})

        middleware = RateLimitMiddleware(None, limiter=limiter)

        response = await middleware.dispatch(request, call_next)

        # Check headers
        assert "X-RateLimit-Limit" in response.headers
        assert "X-RateLimit-Remaining" in response.headers
        assert "X-RateLimit-Reset" in response.headers


class TestGlobalRateLimiter:
    """Tests for global rate limiter instance."""

    def test_get_rate_limiter_returns_singleton(self):
        """Test that get_rate_limiter returns the same instance."""
        config = RateLimitConfig(requests_per_minute=100)

        # First call creates instance
        limiter1 = get_rate_limiter(config)

        # Second call returns same instance
        limiter2 = get_rate_limiter()

        assert limiter1 is limiter2

    @pytest.mark.asyncio
    async def test_global_limiter_works(self):
        """Test that the global limiter instance works."""
        limiter = get_rate_limiter()
        request = Mock(spec=Request)
        request.client = Mock()
        request.client.host = "10.0.0.1"
        request.headers = Headers({})

        # First request should be allowed
        allowed, _ = await limiter.is_allowed(request)
        assert allowed


class TestRateLimitConfig:
    """Tests for RateLimitConfig."""

    def test_default_values(self):
        """Test that RateLimitConfig has sensible defaults."""
        config = RateLimitConfig()

        assert config.requests_per_minute == 60
        assert config.requests_per_hour == 1000
        assert config.burst_limit == 10

    def test_custom_values(self):
        """Test that RateLimitConfig accepts custom values."""
        config = RateLimitConfig(
            requests_per_minute=30,
            requests_per_hour=500,
            burst_limit=5,
        )

        assert config.requests_per_minute == 30
        assert config.requests_per_hour == 500
        assert config.burst_limit == 5
