"""Unit tests for MetricsCollector (Phase 4.2)."""

import threading
import time

import pytest

from ariadne_api.metrics import MetricsCollector, get_metrics_collector


@pytest.fixture
def collector():
    """Create a fresh metrics collector for each test."""
    collector = MetricsCollector()
    collector.reset()
    return collector


class TestMetricsCollectorSingleton:
    """Tests for MetricsCollector singleton pattern."""

    def test_singleton_returns_same_instance(self):
        """Test that get_metrics_collector returns the same instance."""
        collector1 = get_metrics_collector()
        collector2 = get_metrics_collector()
        assert collector1 is collector2

    def test_singleton_idempotent_initialization(self):
        """Test that singleton initialization is idempotent."""
        collector1 = MetricsCollector()
        collector2 = MetricsCollector()
        # Both should be the same instance
        assert collector1 is collector2


class TestRequestMetrics:
    """Tests for RequestMetrics."""

    def test_record_request_increments_count(self, collector):
        """Test recording requests increments counters correctly."""
        assert collector.request_metrics.total_requests == 0

        collector.record_request("GET", "/test", 100.0, 200)
        assert collector.request_metrics.total_requests == 1

        collector.record_request("GET", "/test", 200.0, 200)
        assert collector.request_metrics.total_requests == 2

    def test_record_request_with_error(self, collector):
        """Test recording requests with errors tracks correctly."""
        collector.record_request("GET", "/test", 100.0, 200)
        collector.record_request("GET", "/test", 100.0, 500)

        assert collector.request_metrics.total_requests == 2
        assert collector.request_metrics.error_count == 1
        assert collector.request_metrics.error_rate == 0.5

    def test_avg_duration_calculation(self, collector):
        """Test average duration is calculated correctly."""
        collector.record_request("GET", "/test", 100.0, 200)
        collector.record_request("GET", "/test", 200.0, 200)
        collector.record_request("GET", "/test", 300.0, 200)

        assert collector.request_metrics.avg_duration_ms == 200.0

    def test_p95_duration_calculation(self, collector):
        """Test P95 duration percentile is calculated correctly."""
        # Record 10 requests with durations 100-500
        for i in range(10):
            collector.record_request("GET", "/test", 100.0 * (i + 1), 200)

        # P95 of 10 samples is the 10th value (sorted: 100, 200, ..., 1000)
        # Index = int(10 * 0.95) = 9, but we use min(idx, len-1) = 9
        # So P95 should be 1000
        assert collector.request_metrics.p95_duration_ms == 1000.0

    def test_p99_duration_calculation(self, collector):
        """Test P99 duration percentile is calculated correctly."""
        for i in range(10):
            collector.record_request("GET", "/test", 100.0 * (i + 1), 200)

        # P99 of 10 samples is the 10th value
        assert collector.request_metrics.p99_duration_ms == 1000.0

    def test_durations_list_bounded(self, collector):
        """Test that durations list is bounded to 1000 entries."""
        # Record 2000 requests
        for i in range(2000):
            collector.record_request("GET", "/test", 100.0, 200)

        # Should only keep last 1000
        assert len(collector.request_metrics.durations) == 1000


class TestMetricsCollection:
    """Tests for metrics collection functionality."""

    def test_record_request_updates_metrics(self, collector):
        """Test recording request updates all metrics correctly."""
        collector.record_request("GET", "/api/v1/test", 150.5, 200)

        metrics = collector.get_metrics()
        assert metrics["total_requests"] == 1
        assert metrics["avg_request_duration_ms"] == 150.5
        assert metrics["error_rate"] == 0.0
        assert metrics["total_errors"] == 0

    def test_get_metrics_includes_all_fields(self, collector):
        """Test get_metrics returns all expected fields."""
        collector.record_request("GET", "/api/v1/test", 100.0, 200)

        metrics = collector.get_metrics()

        # Check all expected fields exist
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
            assert field in metrics

    def test_uptime_seconds_increases(self, collector):
        """Test that uptime_seconds is reasonable."""
        metrics = collector.get_metrics()
        assert metrics["uptime_seconds"] > 0
        assert metrics["uptime_seconds"] < 10  # Should be less than 10 seconds for test


class TestEndpointMetrics:
    """Tests for per-endpoint metrics tracking."""

    def test_endpoint_metrics_tracked_separately(self, collector):
        """Test that different endpoints are tracked separately."""
        collector.record_request("GET", "/api/v1/search", 100.0, 200)
        collector.record_request("POST", "/api/v1/rebuild", 500.0, 200)
        collector.record_request("GET", "/api/v1/search", 150.0, 200)

        endpoint_metrics = collector.get_endpoint_metrics()

        assert "GET /api/v1/search" in endpoint_metrics
        assert "POST /api/v1/rebuild" in endpoint_metrics

        search_metrics = endpoint_metrics["GET /api/v1/search"]
        assert search_metrics["total_requests"] == 2
        assert search_metrics["avg_duration_ms"] == 125.0
        assert search_metrics["error_rate"] == 0.0

        rebuild_metrics = endpoint_metrics["POST /api/v1/rebuild"]
        assert rebuild_metrics["total_requests"] == 1
        assert rebuild_metrics["avg_duration_ms"] == 500.0

    def test_endpoint_metrics_includes_percentiles(self, collector):
        """Test that endpoint metrics include percentiles."""
        for i in range(10):
            collector.record_request("GET", "/api/v1/test", 100.0 * (i + 1), 200)

        endpoint_metrics = collector.get_endpoint_metrics()
        test_metrics = endpoint_metrics["GET /api/v1/test"]

        assert "p95_duration_ms" in test_metrics
        assert "p99_duration_ms" in test_metrics


class TestThreadSafety:
    """Tests for thread-safe metrics collection."""

    def test_concurrent_request_recording(self, collector):
        """Test that concurrent request recording is thread-safe."""
        collector.reset()

        def record_requests(thread_id):
            for i in range(100):
                collector.record_request(
                    "GET",
                    f"/api/v1/test/{thread_id}/{i}",
                    100.0 + i,
                    200,
                )

        # Launch 10 threads
        threads = []
        for i in range(10):
            t = threading.Thread(target=record_requests, args=(i,))
            threads.append(t)
            t.start()

        # Wait for completion
        for t in threads:
            t.join()

        # Verify all requests recorded
        metrics = collector.get_metrics()
        assert metrics["total_requests"] == 1000  # 10 threads * 100 requests
        assert metrics["error_rate"] == 0.0

    def test_concurrent_endpoint_recording(self, collector):
        """Test that concurrent endpoint metrics tracking is thread-safe."""
        collector.reset()

        def record_requests(thread_id):
            for i in range(50):
                # All threads record to the same endpoint (without thread_id in path)
                collector.record_request(
                    "GET",
                    "/api/v1/test",
                    100.0,
                    200,
                )

        # Launch 5 threads
        threads = []
        for i in range(5):
            t = threading.Thread(target=record_requests, args=(i,))
            threads.append(t)
            t.start()

        for t in threads:
            t.join()

        # Verify endpoint metrics
        endpoint_metrics = collector.get_endpoint_metrics()
        # All threads recorded to same endpoint
        test_metrics = endpoint_metrics["GET /api/v1/test"]
        assert test_metrics["total_requests"] == 250  # 5 threads * 50 requests


class TestActiveRequestTracking:
    """Tests for active request tracking."""

    def test_increment_decrement_active_requests(self, collector):
        """Test incrementing and decrementing active requests."""
        assert collector.request_metrics.active_requests == 0

        collector.increment_active_requests()
        assert collector.request_metrics.active_requests == 1

        collector.increment_active_requests()
        assert collector.request_metrics.active_requests == 2

        collector.decrement_active_requests()
        assert collector.request_metrics.active_requests == 1

        collector.decrement_active_requests()
        assert collector.request_metrics.active_requests == 0

    def test_decrement_never_negative(self, collector):
        """Test that decrement never goes below zero."""
        collector.increment_active_requests()
        collector.decrement_active_requests()
        # Extra decrement should not go negative
        collector.decrement_active_requests()
        assert collector.request_metrics.active_requests == 0


class TestReset:
    """Tests for metrics reset functionality."""

    def test_reset_clears_all_metrics(self, collector):
        """Test that reset clears all metrics."""
        # Record some data
        collector.record_request("GET", "/test", 100.0, 200)
        collector.record_request("GET", "/test", 100.0, 500)
        collector.increment_active_requests()

        # Reset
        collector.reset()

        # Verify all cleared
        assert collector.request_metrics.total_requests == 0
        assert collector.request_metrics.active_requests == 0
        assert collector.request_metrics.error_count == 0

        # Verify endpoint metrics cleared
        endpoint_metrics = collector.get_endpoint_metrics()
        assert len(endpoint_metrics) == 0


class TestDatabaseMetrics:
    """Tests for database metrics tracking."""

    def test_record_db_query(self, collector):
        """Test recording database query metrics."""
        collector.record_db_query(5.2)
        collector.record_db_query(10.8)
        collector.record_db_query(7.5)

        assert collector.db_metrics.total_queries == 3
        assert collector.db_metrics.avg_query_duration_ms == pytest.approx(7.83, rel=1e-2)


class TestLLMMetrics:
    """Tests for LLM metrics tracking."""

    def test_record_llm_request(self, collector):
        """Test recording LLM request metrics."""
        collector.record_llm_request(
            duration_ms=1500.0,
            tokens=500,
            cost_usd=0.001,
        )

        assert collector.llm_metrics.total_requests == 1
        assert collector.llm_metrics.avg_duration_ms == 1500.0
        assert collector.llm_metrics.total_tokens == 500
        assert collector.llm_metrics.total_cost_usd == 0.001


class TestJobMetrics:
    """Tests for job metrics tracking."""

    def test_record_job_completion(self, collector):
        """Test recording job completion."""
        collector.increment_active_jobs()
        assert collector.job_metrics.active_jobs == 1

        collector.record_job_completion(success=True)
        assert collector.job_metrics.active_jobs == 0
        assert collector.job_metrics.completed_jobs == 1
        assert collector.job_metrics.failed_jobs == 0

    def test_record_job_failure(self, collector):
        """Test recording job failure."""
        collector.increment_active_jobs()
        collector.record_job_completion(success=False)

        assert collector.job_metrics.active_jobs == 0
        assert collector.job_metrics.completed_jobs == 0
        assert collector.job_metrics.failed_jobs == 1
