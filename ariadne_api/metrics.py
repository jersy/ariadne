"""Performance metrics collector for Ariadne API.

Collects and aggregates metrics from various system components:
- API request metrics (duration, error rate)
- Database query metrics
- LLM usage metrics
- Background job metrics
- System resource metrics
"""

import logging
import os
import time
from collections import defaultdict
from dataclasses import dataclass, field
from threading import Lock
from typing import Any

import psutil

logger = logging.getLogger(__name__)

# Process start time for uptime calculation
_start_time = time.time()
_process = psutil.Process()


@dataclass
class RequestMetrics:
    """Metrics for API requests."""

    total_requests: int = 0
    active_requests: int = 0
    total_duration_ms: float = 0.0
    error_count: int = 0
    durations: list[float] = field(default_factory=list)

    def record_request(self, duration_ms: float, is_error: bool = False) -> None:
        """Record a completed request."""
        self.total_requests += 1
        self.total_duration_ms += duration_ms
        self.durations.append(duration_ms)
        if is_error:
            self.error_count += 1

        # Keep only last 1000 durations for percentile calculation
        if len(self.durations) > 1000:
            self.durations = self.durations[-1000:]

    def increment_active(self) -> None:
        """Increment active request count."""
        self.active_requests += 1

    def decrement_active(self) -> None:
        """Decrement active request count."""
        self.active_requests = max(0, self.active_requests - 1)

    @property
    def avg_duration_ms(self) -> float:
        """Average request duration."""
        if self.total_requests == 0:
            return 0.0
        return self.total_duration_ms / self.total_requests

    @property
    def p95_duration_ms(self) -> float:
        """95th percentile request duration."""
        if not self.durations:
            return 0.0
        sorted_durations = sorted(self.durations)
        idx = int(len(sorted_durations) * 0.95)
        return sorted_durations[min(idx, len(sorted_durations) - 1)]

    @property
    def p99_duration_ms(self) -> float:
        """99th percentile request duration."""
        if not self.durations:
            return 0.0
        sorted_durations = sorted(self.durations)
        idx = int(len(sorted_durations) * 0.99)
        return sorted_durations[min(idx, len(sorted_durations) - 1)]

    @property
    def error_rate(self) -> float:
        """Error rate (0-1)."""
        if self.total_requests == 0:
            return 0.0
        return self.error_count / self.total_requests


@dataclass
class DatabaseMetrics:
    """Metrics for database operations."""

    avg_query_duration_ms: float = 0.0
    total_queries: int = 0
    total_duration_ms: float = 0.0

    def record_query(self, duration_ms: float) -> None:
        """Record a database query."""
        self.total_queries += 1
        self.total_duration_ms += duration_ms
        self.avg_query_duration_ms = self.total_duration_ms / self.total_queries


@dataclass
class LLMMetrics:
    """Metrics for LLM API calls."""

    total_requests: int = 0
    total_duration_ms: float = 0.0
    total_tokens: int = 0
    total_cost_usd: float = 0.0

    def record_request(
        self, duration_ms: float, tokens: int = 0, cost_usd: float = 0.0
    ) -> None:
        """Record an LLM request."""
        self.total_requests += 1
        self.total_duration_ms += duration_ms
        self.total_tokens += tokens
        self.total_cost_usd += cost_usd

    @property
    def avg_duration_ms(self) -> float:
        """Average LLM request duration."""
        if self.total_requests == 0:
            return 0.0
        return self.total_duration_ms / self.total_requests


@dataclass
class JobMetrics:
    """Metrics for background jobs."""

    active_jobs: int = 0
    completed_jobs: int = 0
    failed_jobs: int = 0

    def increment_active(self) -> None:
        """Increment active job count."""
        self.active_jobs += 1

    def decrement_active(self) -> None:
        """Decrement active job count."""
        self.active_jobs = max(0, self.active_jobs - 1)

    def record_completion(self, success: bool = True) -> None:
        """Record a job completion."""
        self.active_jobs = max(0, self.active_jobs - 1)
        if success:
            self.completed_jobs += 1
        else:
            self.failed_jobs += 1


class MetricsCollector:
    """Central metrics collector for the Ariadne API.

    Thread-safe singleton that collects metrics from all system components.
    """

    _instance: "MetricsCollector | None" = None
    _lock: Lock = Lock()

    def __new__(cls) -> "MetricsCollector":
        """Get or create the singleton instance."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self) -> None:
        """Initialize the metrics collector."""
        if self._initialized:
            return

        self._initialized = True
        self._lock = Lock()

        # Metrics storage
        self.request_metrics = RequestMetrics()
        self.db_metrics = DatabaseMetrics()
        self.llm_metrics = LLMMetrics()
        self.job_metrics = JobMetrics()

        # Per-endpoint metrics
        self.endpoint_metrics: dict[str, RequestMetrics] = defaultdict(
            lambda: RequestMetrics()
        )

        logger.info("MetricsCollector initialized")

    def record_request(
        self,
        method: str,
        path: str,
        duration_ms: float,
        status_code: int,
    ) -> None:
        """Record an API request.

        Args:
            method: HTTP method
            path: Request path
            duration_ms: Request duration in milliseconds
            status_code: HTTP status code
        """
        with self._lock:
            is_error = status_code >= 400
            self.request_metrics.record_request(duration_ms, is_error)

            # Track per-endpoint metrics
            endpoint = f"{method} {path}"
            self.endpoint_metrics[endpoint].record_request(duration_ms, is_error)

    def increment_active_requests(self) -> None:
        """Increment active request count."""
        with self._lock:
            self.request_metrics.increment_active()

    def decrement_active_requests(self) -> None:
        """Decrement active request count."""
        with self._lock:
            self.request_metrics.decrement_active()

    def record_db_query(self, duration_ms: float) -> None:
        """Record a database query.

        Args:
            duration_ms: Query duration in milliseconds
        """
        with self._lock:
            self.db_metrics.record_query(duration_ms)

    def record_llm_request(
        self, duration_ms: float, tokens: int = 0, cost_usd: float = 0.0
    ) -> None:
        """Record an LLM request.

        Args:
            duration_ms: Request duration in milliseconds
            tokens: Number of tokens processed
            cost_usd: Estimated cost in USD
        """
        with self._lock:
            self.llm_metrics.record_request(duration_ms, tokens, cost_usd)

    def increment_active_jobs(self) -> None:
        """Increment active job count."""
        with self._lock:
            self.job_metrics.increment_active()

    def decrement_active_jobs(self) -> None:
        """Decrement active job count."""
        with self._lock:
            self.job_metrics.decrement_active()

    def record_job_completion(self, success: bool = True) -> None:
        """Record a job completion.

        Args:
            success: Whether the job succeeded
        """
        with self._lock:
            self.job_metrics.record_completion(success)

    def get_metrics(self) -> dict[str, Any]:
        """Get current metrics snapshot.

        Returns:
            Dictionary of current metrics
        """
        with self._lock:
            try:
                memory_info = _process.memory_info()
                memory_mb = memory_info.rss / 1024 / 1024
            except Exception:
                memory_mb = 0.0

            return {
                "total_requests": self.request_metrics.total_requests,
                "active_requests": self.request_metrics.active_requests,
                "avg_request_duration_ms": self.request_metrics.avg_duration_ms,
                "p95_request_duration_ms": self.request_metrics.p95_duration_ms,
                "p99_request_duration_ms": self.request_metrics.p99_duration_ms,
                "error_rate": self.request_metrics.error_rate,
                "total_errors": self.request_metrics.error_count,
                "db_connection_pool_size": 1,  # SQLite uses single connection
                "db_avg_query_duration_ms": self.db_metrics.avg_query_duration_ms,
                "llm_total_requests": self.llm_metrics.total_requests,
                "llm_avg_duration_ms": self.llm_metrics.avg_duration_ms,
                "llm_total_tokens": self.llm_metrics.total_tokens,
                "llm_estimated_cost_usd": self.llm_metrics.total_cost_usd,
                "active_jobs": self.job_metrics.active_jobs,
                "completed_jobs": self.job_metrics.completed_jobs,
                "failed_jobs": self.job_metrics.failed_jobs,
                "uptime_seconds": time.time() - _start_time,
                "memory_usage_mb": memory_mb,
            }

    def get_endpoint_metrics(self) -> dict[str, dict[str, Any]]:
        """Get per-endpoint metrics.

        Returns:
            Dictionary mapping endpoint names to their metrics
        """
        with self._lock:
            return {
                endpoint: {
                    "total_requests": m.total_requests,
                    "avg_duration_ms": m.avg_duration_ms,
                    "p95_duration_ms": m.p95_duration_ms,
                    "p99_duration_ms": m.p99_duration_ms,
                    "error_rate": m.error_rate,
                }
                for endpoint, m in self.endpoint_metrics.items()
            }

    def reset(self) -> None:
        """Reset all metrics (useful for testing)."""
        with self._lock:
            self.request_metrics = RequestMetrics()
            self.db_metrics = DatabaseMetrics()
            self.llm_metrics = LLMMetrics()
            self.job_metrics = JobMetrics()
            self.endpoint_metrics.clear()
            logger.info("Metrics reset")


# Singleton instance
def get_metrics_collector() -> MetricsCollector:
    """Get the singleton MetricsCollector instance."""
    return MetricsCollector()
