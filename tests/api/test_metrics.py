"""Integration tests for metrics API endpoints (Phase 4.2)."""

import os
from typing import Generator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from ariadne_api.middleware import RequestContextMiddleware, TracingMiddleware, setup_logging
from ariadne_api.routes.check import router as check_router
from ariadne_api.routes.constraints import router as constraints_router
from ariadne_api.routes.graph import router as graph_router
from ariadne_api.routes.glossary import router as glossary_router
from ariadne_api.routes.health import router as health_router
from ariadne_api.routes.impact import router as impact_router
from ariadne_api.routes.jobs import router as jobs_router
from ariadne_api.routes.metrics import router as metrics_router
from ariadne_api.routes.rebuild import router as rebuild_router
from ariadne_api.routes.search import router as search_router
from ariadne_api.routes.symbol import router as symbol_router
from ariadne_api.routes import tests as tests_router
from ariadne_api.schemas.common import HealthResponse


def _create_test_app() -> FastAPI:
    """Create a test FastAPI app without rate limiting."""
    # Set test environment
    os.environ["ARIADNE_DB_PATH"] = ":memory:"
    os.environ["ARIADNE_LOG_LEVEL"] = "WARNING"

    # Set up logging
    setup_logging(level="WARNING", json_format=False)

    # Create test app (without rate limiting middleware)
    test_app = FastAPI(title="Ariadne Test API")

    # CORS middleware
    from fastapi.middleware.cors import CORSMiddleware
    test_app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Request context middleware
    test_app.add_middleware(RequestContextMiddleware)

    # Distributed tracing middleware
    test_app.add_middleware(TracingMiddleware, service_name="ariadne-api-test")

    # Include routers
    test_app.include_router(health_router, tags=["health"])
    test_app.include_router(search_router, prefix="/api/v1", tags=["search"])
    test_app.include_router(graph_router, prefix="/api/v1", tags=["graph"])
    test_app.include_router(symbol_router, prefix="/api/v1", tags=["symbol"])
    test_app.include_router(impact_router, prefix="/api/v1", tags=["impact"])
    test_app.include_router(rebuild_router, prefix="/api/v1", tags=["rebuild"])
    test_app.include_router(jobs_router, prefix="/api/v1", tags=["jobs"])
    test_app.include_router(constraints_router, prefix="/api/v1", tags=["constraints"])
    test_app.include_router(check_router, prefix="/api/v1", tags=["check"])
    test_app.include_router(glossary_router, prefix="/api/v1/knowledge", tags=["glossary"])
    test_app.include_router(tests_router.router, prefix="/api/v1/knowledge", tags=["tests"])
    test_app.include_router(metrics_router, prefix="/api/v1", tags=["metrics"])

    return test_app


@pytest.fixture
def client() -> Generator[TestClient, None, None]:
    """Create a test client for the API without rate limiting."""
    test_app = _create_test_app()
    with TestClient(test_app) as test_client:
        yield test_client


class TestMetricsEndpoints:
    """Integration tests for metrics API endpoints."""

    def test_get_metrics_returns_structure(self, client):
        """Test GET /api/v1/metrics returns correct structure."""
        response = client.get("/api/v1/metrics")

        assert response.status_code == 200
        data = response.json()

        assert "metrics" in data
        assert "timestamp" in data

        # Verify metrics has expected fields
        metrics = data["metrics"]
        expected_fields = [
            "total_requests",
            "active_requests",
            "avg_request_duration_ms",
            "p95_request_duration_ms",
            "p99_request_duration_ms",
            "error_rate",
            "total_errors",
            "db_connection_pool_size",
            "db_avg_query_duration_ms",
            "llm_total_requests",
            "llm_avg_duration_ms",
            "llm_total_tokens",
            "llm_estimated_cost_usd",
            "active_jobs",
            "completed_jobs",
            "failed_jobs",
            "uptime_seconds",
            "memory_usage_mb",
        ]

        for field in expected_fields:
            assert field in metrics, f"Missing field: {field}"

    def test_get_metrics_includes_generated_data(self, client):
        """Test that metrics includes data from actual requests."""
        from ariadne_api.metrics import get_metrics_collector

        # Reset to start clean
        client.post("/api/v1/metrics/reset")

        # Make some requests to generate metrics
        client.get("/health")
        client.get("/health")
        client.get("/health")

        # Get metrics
        response = client.get("/api/v1/metrics")
        assert response.status_code == 200

        data = response.json()
        metrics = data["metrics"]

        # Should have recorded 3 health endpoint requests
        assert metrics["total_requests"] >= 3

    def test_get_endpoint_metrics_returns_structure(self, client):
        """Test GET /api/v1/metrics/endpoints returns correct structure."""
        # Make some requests first
        client.get("/health")
        client.get("/health")

        response = client.get("/api/v1/metrics/endpoints")

        assert response.status_code == 200
        data = response.json()

        # Should be a dictionary
        assert isinstance(data, dict)

    def test_get_endpoint_metrics_tracks_separately(self, client):
        """Test that different endpoints are tracked separately."""
        client.post("/api/v1/metrics/reset")

        # Make requests to different endpoints
        for _ in range(3):
            client.get("/health")

        response = client.get("/api/v1/metrics/endpoints")
        assert response.status_code == 200

        endpoint_metrics = response.json()

        # Should have GET /health endpoint tracked
        assert "GET /health" in endpoint_metrics
        health_metrics = endpoint_metrics["GET /health"]
        assert health_metrics["total_requests"] == 3

    def test_get_metrics_health_combines_health_and_metrics(self, client):
        """Test GET /api/v1/metrics/health combines health status with metrics."""
        response = client.get("/api/v1/metrics/health")

        assert response.status_code == 200
        data = response.json()

        # Should have both health status and metrics
        assert "status" in data
        assert "services" in data
        assert "metrics" in data

        # Status should be one of: healthy, degraded, unhealthy
        assert data["status"] in ["healthy", "degraded", "unhealthy"]

        # Services should include database, vector_db, llm
        services = data["services"]
        assert "database" in services
        assert "vector_db" in services
        assert "llm" in services

        # Metrics should have same structure as /api/v1/metrics
        metrics = data["metrics"]
        assert "total_requests" in metrics

    def test_reset_metrics_clears_all_data(self, client):
        """Test POST /api/v1/metrics/reset clears all metrics."""
        from ariadne_api.metrics import get_metrics_collector

        # Generate some metrics first
        client.get("/health")
        client.get("/health")

        # Get metrics before reset
        response_before = client.get("/api/v1/metrics")
        assert response_before.status_code == 200
        metrics_before = response_before.json()["metrics"]
        assert metrics_before["total_requests"] >= 2

        # Reset
        response = client.post("/api/v1/metrics/reset")
        assert response.status_code == 200

        reset_data = response.json()
        assert "message" in reset_data

        # Get metrics after reset
        response_after = client.get("/api/v1/metrics")
        assert response_after.status_code == 200
        metrics_after = response_after.json()["metrics"]

        # Should have 1 request from the metrics GET call itself
        assert metrics_after["total_requests"] == 1


class TestMetricsHeaders:
    """Tests for metrics-related HTTP headers."""

    def test_response_includes_timing_header(self, client):
        """Test that responses include X-Process-Time-ms header."""
        response = client.get("/health")

        assert response.status_code == 200
        assert "X-Process-Time-ms" in response.headers

        # Timing should be a number
        timing = response.headers["X-Process-Time-ms"]
        assert float(timing) >= 0

    def test_response_includes_request_id_header(self, client):
        """Test that responses include X-Request-ID header."""
        response = client.get("/health")

        assert response.status_code == 200
        assert "X-Request-ID" in response.headers

        # Request ID should be a UUID-like string
        request_id = response.headers["X-Request-ID"]
        assert len(request_id) > 0


class TestMetricsAPIVersioning:
    """Tests for API versioning of metrics endpoints."""

    def test_metrics_endpoints_use_v1_prefix(self, client):
        """Test that metrics endpoints are under /api/v1/."""
        # All metrics endpoints should be under /api/v1/
        endpoints = [
            "/api/v1/metrics",
            "/api/v1/metrics/endpoints",
            "/api/v1/metrics/health",
        ]

        for endpoint in endpoints:
            response = client.get(endpoint)
            # Should not be 404 (endpoint exists)
            assert response.status_code != 404, f"Endpoint not found: {endpoint}"

    def test_metrics_reset_requires_post(self, client):
        """Test that metrics reset requires POST (not GET)."""
        # GET should not work for reset
        response = client.get("/api/v1/metrics/reset")
        assert response.status_code == 405  # Method Not Allowed


class TestMetricsIntegration:
    """Integration tests for metrics collection through API."""

    def test_request_tracking_through_api_layer(self, client):
        """Test that API requests are automatically tracked."""
        from ariadne_api.metrics import get_metrics_collector

        # Reset to start clean
        client.post("/api/v1/metrics/reset")

        # Make requests through the API
        response1 = client.get("/health")
        response2 = client.get("/health")
        response3 = client.get("/api/v1/metrics")

        assert response1.status_code == 200
        assert response2.status_code == 200
        assert response3.status_code == 200

        # Check metrics
        metrics_response = client.get("/api/v1/metrics")
        metrics = metrics_response.json()["metrics"]

        # Should have at least 3 requests tracked
        assert metrics["total_requests"] >= 3

    def test_error_tracking_through_api_layer(self, client):
        """Test that API errors are tracked in metrics."""
        client.post("/api/v1/metrics/reset")

        # Make a request that will 404
        response = client.get("/api/v1/nonexistent-endpoint-12345")

        assert response.status_code == 404

        # Check metrics
        metrics_response = client.get("/api/v1/metrics")
        metrics = metrics_response.json()["metrics"]

        # Should have tracked the error
        assert metrics["total_errors"] >= 1
        assert metrics["error_rate"] >= 0

    def test_concurrent_requests_tracked_correctly(self, client):
        """Test that concurrent requests are tracked correctly."""
        import threading

        client.post("/api/v1/metrics/reset")

        def make_request():
            client.get("/health")

        # Launch 10 concurrent requests
        threads = []
        for _ in range(10):
            t = threading.Thread(target=make_request)
            threads.append(t)
            t.start()

        for t in threads:
            t.join()

        # Check metrics
        metrics_response = client.get("/api/v1/metrics")
        metrics = metrics_response.json()["metrics"]

        # Should have all 10 requests tracked
        assert metrics["total_requests"] >= 10
