"""Metrics endpoint for performance monitoring."""

import logging
import os

from fastapi import APIRouter

from ariadne_api.metrics import get_metrics_collector
from ariadne_api.schemas.common import HealthResponse
from ariadne_api.schemas.metrics import (
    HealthStatus,
    MetricsHistoryResponse,
    MetricsResponse,
)

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get(
    "/metrics",
    response_model=MetricsResponse,
    tags=["metrics"],
)
async def get_metrics() -> MetricsResponse:
    """Get current performance metrics.

    Returns comprehensive metrics for:
    - API requests (count, duration, errors)
    - Database queries
    - LLM usage (requests, tokens, cost)
    - Background jobs
    - System resources (memory, uptime)
    """
    import time

    collector = get_metrics_collector()
    metrics = collector.get_metrics()

    return MetricsResponse(
        metrics=metrics,
        timestamp=time.time(),
    )


@router.get(
    "/metrics/endpoints",
    tags=["metrics"],
)
async def get_endpoint_metrics() -> dict[str, dict]:
    """Get per-endpoint performance metrics.

    Returns metrics broken down by API endpoint, including:
    - Total requests
    - Average duration
    - 95th and 99th percentile durations
    - Error rate

    Useful for identifying slow endpoints and performance bottlenecks.
    """
    collector = get_metrics_collector()
    return collector.get_endpoint_metrics()


@router.get(
    "/metrics/health",
    response_model=HealthStatus,
    tags=["metrics"],
)
async def get_health_with_metrics() -> HealthStatus:
    """Get detailed health status with performance metrics.

    Combines health check information with current performance metrics
    for comprehensive system monitoring.
    """
    import time

    from ariadne_api.schemas.metrics import PerformanceMetrics
    from ariadne_api.routes.health import (
        get_db_status,
        get_llm_status,
        get_vector_db_status,
    )

    collector = get_metrics_collector()
    metrics_dict = collector.get_metrics()

    # Get service status
    db_path = os.environ.get("ARIADNE_DB_PATH", "ariadne.db")
    services = {
        "database": get_db_status(db_path),
        "vector_db": get_vector_db_status(),
        "llm": get_llm_status(),
    }

    # Determine overall status
    if all(s == "ok" for s in services.values()):
        overall_status = "healthy"
    elif any(s in ("missing", "unavailable") for s in services.values()):
        overall_status = "unhealthy"
    else:
        overall_status = "degraded"

    return HealthStatus(
        status=overall_status,
        uptime_seconds=metrics_dict["uptime_seconds"],
        services=services,
        metrics=PerformanceMetrics(**metrics_dict),
    )


@router.post(
    "/metrics/reset",
    tags=["metrics"],
)
async def reset_metrics() -> dict[str, str]:
    """Reset all performance metrics.

    Clears all collected metrics. Useful for testing or after
    significant system changes.

    Note: This requires a POST request to prevent accidental resets.
    """
    collector = get_metrics_collector()
    collector.reset()

    logger.info("Metrics reset via API")

    return {"message": "Metrics reset successfully"}
