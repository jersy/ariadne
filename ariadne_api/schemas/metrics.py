"""Schemas for performance metrics API."""

from typing import Any

from pydantic import BaseModel, Field


class MetricValue(BaseModel):
    """A single metric value with timestamp."""

    timestamp: float = Field(..., description="Unix timestamp")
    value: float = Field(..., description="Metric value")


class PerformanceMetrics(BaseModel):
    """Current performance metrics for the system."""

    # API metrics
    total_requests: int = Field(..., description="Total number of API requests")
    active_requests: int = Field(..., description="Currently active requests")
    avg_request_duration_ms: float = Field(
        ..., description="Average request duration in milliseconds"
    )
    p95_request_duration_ms: float = Field(
        ..., description="95th percentile request duration in milliseconds"
    )
    p99_request_duration_ms: float = Field(
        ..., description="99th percentile request duration in milliseconds"
    )

    # Error metrics
    error_rate: float = Field(..., description="Error rate (0-1)")
    total_errors: int = Field(..., description="Total number of errors")

    # Database metrics
    db_connection_pool_size: int = Field(..., description="Database connection pool size")
    db_avg_query_duration_ms: float = Field(
        ..., description="Average database query duration in milliseconds"
    )

    # LLM metrics
    llm_total_requests: int = Field(..., description="Total LLM API requests")
    llm_avg_duration_ms: float = Field(..., description="Average LLM request duration")
    llm_total_tokens: int = Field(..., description="Total tokens processed")
    llm_estimated_cost_usd: float = Field(..., description="Estimated LLM cost in USD")

    # Background job metrics
    active_jobs: int = Field(..., description="Number of active background jobs")
    completed_jobs: int = Field(..., description="Number of completed jobs")
    failed_jobs: int = Field(..., description="Number of failed jobs")

    # System metrics
    uptime_seconds: float = Field(..., description="System uptime in seconds")
    memory_usage_mb: float = Field(..., description="Current memory usage in MB")


class MetricsResponse(BaseModel):
    """Response for metrics endpoint."""

    metrics: PerformanceMetrics
    timestamp: float = Field(..., description="Response timestamp")


class MetricsHistoryResponse(BaseModel):
    """Response for metrics history endpoint."""

    metric_name: str = Field(..., description="Name of the metric")
    values: list[MetricValue] = Field(..., description="Historical values")


class HealthStatus(BaseModel):
    """Detailed health status with metrics."""

    status: str = Field(..., description="Overall status: healthy, degraded, unhealthy")
    uptime_seconds: float = Field(..., description="System uptime")
    services: dict[str, str] = Field(..., description="Status of individual services")
    metrics: PerformanceMetrics = Field(..., description="Current performance metrics")
