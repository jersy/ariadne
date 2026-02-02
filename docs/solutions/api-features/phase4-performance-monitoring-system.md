---
title: "Phase 4.2: 性能监控系统"
category: api-features
component: ariadne_api/metrics.py, ariadne_api/routes/metrics.py, ariadne_api/middleware.py
severity: Informational
status: implemented
created: 2026-02-02
tags:
  - performance-monitoring
  - metrics
  - observability
  - thread-safety
  - psutil
  - phase-4.2
---

# Phase 4.2: 性能监控系统

## Overview

实现了一套完整的性能监控系统，为 Ariadne API 提供实时的性能指标收集和查询能力。系统采用线程安全的单例模式收集指标，并通过 REST API 暴露给客户端。

**New Files Created:**
- `ariadne_api/metrics.py` - MetricsCollector 核心实现 (273 行)
- `ariadne_api/routes/metrics.py` - API 端点 (96 行)
- `ariadne_api/schemas/metrics.py` - Pydantic 数据模型 (72 行)

**Architecture:**
```
Request → RequestContextMiddleware → MetricsCollector → Thread-safe Storage
                                                    ↓
                                    REST API Endpoints (/api/v1/metrics)
```

## Problem

**No Performance Monitoring**

API 层缺少性能监控能力：
- **Symptom**: 无法追踪请求延迟、错误率或资源使用
- **Impact**: 无法检测性能下降、识别瓶颈或追踪系统健康状态
- **Gap**: Middleware 只记录请求完成日志，不聚合指标数据

## Architecture Design

### Component Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                         MetricsCollector                           │
│                    (Thread-Safe Singleton)                        │
│                                                                      │
│  ┌─────────────────┬─────────────────┬─────────────────────────┐  │
│  │ RequestMetrics  │  DatabaseMetrics │  LLMMetrics             │  │
│  │                 │                 │                         │  │
│  │ - total_requests│ - avg_query_ms  │ - total_tokens          │  │
│  │ - p95/p99 latency│ - total_queries │ - estimated_cost_usd    │  │
│  │ - error_rate    │                 │                         │  │
│  └─────────────────┴─────────────────┴─────────────────────────┘  │
│                                                                      │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │              Per-Endpoint Metrics                           │   │
│  │  endpoint_metrics: Dict[str, RequestMetrics]               │   │
│  └─────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────┘
                                    ▲
                                    │
        ┌───────────────────────────┼───────────────────────────┐
        │                           │                           │
┌───────┴────────┐        ┌────────┴─────────┐       ┌────────┴────────┐
│   Middleware   │        │  API Endpoints   │       │   Background     │
│   Auto-collect │        │  Query metrics   │       │   Jobs/LLM      │
└────────────────┘        └──────────────────┘       └─────────────────┘
```

### Thread Safety Design

**Double-Checked Locking Singleton:**
```python
class MetricsCollector:
    _instance: "MetricsCollector | None" = None
    _lock: Lock = Lock()

    def __new__(cls) -> "MetricsCollector":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    def record_request(self, ...) -> None:
        with self._lock:  # Thread-safe for all mutations
            self.request_metrics.record_request(...)
```

## Implementation Details

### 1. MetricsCollector Class

**File**: `ariadne_api/metrics.py`

#### RequestMetrics Dataclass

```python
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

    @property
    def p95_duration_ms(self) -> float:
        if not self.durations:
            return 0.0
        sorted_durations = sorted(self.durations)
        idx = int(len(sorted_durations) * 0.95)
        return sorted_durations[min(idx, len(sorted_durations) - 1)]

    @property
    def p99_duration_ms(self) -> float:
        if not self.durations:
            return 0.0
        sorted_durations = sorted(self.durations)
        idx = int(len(sorted_durations) * 0.99)
        return sorted_durations[min(idx, len(sorted_durations) - 1)]
```

#### MetricsCollector Singleton

```python
class MetricsCollector:
    """Central metrics collector - thread-safe singleton."""

    _instance: "MetricsCollector | None" = None
    _lock: Lock = Lock()

    def __init__(self) -> None:
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

    def record_request(
        self, method: str, path: str, duration_ms: float, status_code: int
    ) -> None:
        """Record an API request."""
        with self._lock:
            is_error = status_code >= 400
            self.request_metrics.record_request(duration_ms, is_error)

            endpoint = f"{method} {path}"
            self.endpoint_metrics[endpoint].record_request(duration_ms, is_error)

    def get_metrics(self) -> dict[str, Any]:
        """Get current metrics snapshot."""
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
                "db_connection_pool_size": 1,
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
        """Get per-endpoint metrics."""
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
```

### 2. Middleware Integration

**File**: `ariadne_api/middleware.py`

```python
async def dispatch(self, request: Request, call_next: Callable) -> Response:
    start_time = time.time()

    # Track metrics
    from ariadne_api.metrics import get_metrics_collector
    metrics_collector = get_metrics_collector()
    metrics_collector.increment_active_requests()

    try:
        response = await call_next(request)
        duration_ms = (time.time() - start_time) * 1000

        # Record metrics
        metrics_collector.record_request(
            method=request.method,
            path=request.url.path,
            duration_ms=duration_ms,
            status_code=response.status_code,
        )

        response.headers["X-Process-Time-ms"] = f"{duration_ms:.2f}"
        return response

    except Exception as e:
        duration_ms = (time.time() - start_time) * 1000
        metrics_collector.record_request(
            method=request.method,
            path=request.url.path,
            duration_ms=duration_ms,
            status_code=500,
        )
        raise

    finally:
        metrics_collector.decrement_active_requests()
```

### 3. API Endpoints

**File**: `ariadne_api/routes/metrics.py`

```python
@router.get("/api/v1/metrics", response_model=MetricsResponse)
async def get_metrics() -> MetricsResponse:
    """Get current performance metrics."""
    collector = get_metrics_collector()
    metrics = collector.get_metrics()
    return MetricsResponse(metrics=metrics, timestamp=time.time())


@router.get("/api/v1/metrics/endpoints")
async def get_endpoint_metrics() -> dict[str, dict]:
    """Get per-endpoint performance metrics."""
    collector = get_metrics_collector()
    return collector.get_endpoint_metrics()


@router.get("/api/v1/metrics/health", response_model=HealthStatus)
async def get_health_with_metrics() -> HealthStatus:
    """Get detailed health status with performance metrics."""
    collector = get_metrics_collector()
    metrics_dict = collector.get_metrics()

    # Get service status
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


@router.post("/api/v1/metrics/reset")
async def reset_metrics() -> dict[str, str]:
    """Reset all performance metrics."""
    collector = get_metrics_collector()
    collector.reset()
    return {"message": "Metrics reset successfully"}
```

### 4. Pydantic Schemas

**File**: `ariadne_api/schemas/metrics.py`

```python
class PerformanceMetrics(BaseModel):
    """Current performance metrics for the system."""

    # API metrics
    total_requests: int
    active_requests: int
    avg_request_duration_ms: float
    p95_request_duration_ms: float
    p99_request_duration_ms: float

    # Error metrics
    error_rate: float
    total_errors: int

    # Database metrics
    db_connection_pool_size: int
    db_avg_query_duration_ms: float

    # LLM metrics
    llm_total_requests: int
    llm_avg_duration_ms: float
    llm_total_tokens: int
    llm_estimated_cost_usd: float

    # Background job metrics
    active_jobs: int
    completed_jobs: int
    failed_jobs: int

    # System metrics
    uptime_seconds: float
    memory_usage_mb: float


class MetricsResponse(BaseModel):
    """Response for metrics endpoint."""
    metrics: PerformanceMetrics
    timestamp: float


class HealthStatus(BaseModel):
    """Detailed health status with metrics."""
    status: str
    uptime_seconds: float
    services: dict[str, str]
    metrics: PerformanceMetrics
```

### 5. Dependency Updates

**File**: `pyproject.toml`

```toml
dependencies = [
    # ... existing dependencies ...
    "psutil>=6.0.0",  # Added for system metrics
]
```

## API Endpoints

### GET /api/v1/metrics

获取当前性能指标。

**Response:**
```json
{
  "metrics": {
    "total_requests": 1234,
    "active_requests": 2,
    "avg_request_duration_ms": 45.6,
    "p95_request_duration_ms": 123.4,
    "p99_request_duration_ms": 234.5,
    "error_rate": 0.01,
    "total_errors": 12,
    "db_connection_pool_size": 1,
    "db_avg_query_duration_ms": 5.2,
    "llm_total_requests": 100,
    "llm_avg_duration_ms": 1500.0,
    "llm_total_tokens": 50000,
    "llm_estimated_cost_usd": 0.05,
    "active_jobs": 1,
    "completed_jobs": 50,
    "failed_jobs": 2,
    "uptime_seconds": 3600.5,
    "memory_usage_mb": 128.5
  },
  "timestamp": 1738491234.567
}
```

### GET /api/v1/metrics/endpoints

获取按端点分解的性能指标。

**Response:**
```json
{
  "GET /api/v1/search": {
    "total_requests": 500,
    "avg_duration_ms": 35.2,
    "p95_duration_ms": 80.0,
    "p99_duration_ms": 120.0,
    "error_rate": 0.005
  },
  "POST /api/v1/rebuild": {
    "total_requests": 10,
    "avg_duration_ms": 5000.0,
    "p95_duration_ms": 8000.0,
    "p99_duration_ms": 10000.0,
    "error_rate": 0.0
  }
}
```

### GET /api/v1/metrics/health

获取带性能指标的详细健康状态。

### POST /api/v1/metrics/reset

重置所有性能指标（需要 POST 以防止意外重置）。

## Usage Guide

### Basic Usage

```python
from ariadne_api.metrics import get_metrics_collector

# Get singleton instance
collector = get_metrics_collector()

# Record a database query
collector.record_db_query(duration_ms=5.2)

# Record an LLM request
collector.record_llm_request(
    duration_ms=1500.0,
    tokens=500,
    cost_usd=0.001
)

# Record job completion
collector.record_job_completion(success=True)

# Get current metrics
metrics = collector.get_metrics()
print(f"Total requests: {metrics['total_requests']}")
print(f"P95 latency: {metrics['p95_request_duration_ms']}ms")
```

### Auto-Collection via Middleware

所有 API 请求自动通过 `RequestContextMiddleware` 收集指标，无需手动记录。

```python
# Request automatically tracked
response = await call_next(request)
# Metrics recorded: method, path, duration_ms, status_code
```

## Best Practices

### Metrics Collection Principles

**Collect at Entry Points:**
```python
# Middleware captures all requests automatically
class RequestContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        start_time = time.time()
        try:
            response = await call_next(request)
            duration_ms = (time.time() - start_time) * 1000

            # Always record metrics at the edge
            get_metrics_collector().record_request(
                method=request.method,
                path=request.url.path,
                duration_ms=duration_ms,
                status_code=response.status_code
            )
            return response
```

**Granular Metrics for Critical Paths:**
```python
# Database query metrics
def get_symbol(self, fqn: str) -> dict | None:
    start = time.time()
    try:
        result = self._execute_get_symbol(fqn)
        duration_ms = (time.time() - start) * 1000
        get_metrics_collector().record_db_query(duration_ms)
        return result
    except Exception as e:
        logger.error(f"Query failed for {fqn}: {e}")
        raise
```

### Performance Thresholds

**Alert Thresholds:**
| Metric | Warning | Critical |
|--------|---------|----------|
| Request duration (p95) | > 500ms | > 2000ms |
| Request duration (p99) | > 1000ms | > 5000ms |
| Error rate | > 1% | > 5% |
| DB query duration | > 50ms | > 200ms |
| LLM request duration | > 5000ms | > 15000ms |
| Memory usage | > 1GB | > 2GB |

### Thread Safety Rules

**When to Use Locks:**
```python
# NEED LOCK: Mutable shared state
class Counter:
    def __init__(self):
        self._value = 0
        self._lock = Lock()

    def increment(self):
        with self._lock:
            self._value += 1

# NO LOCK NEEDED: Immutable state
class Config:
    def __init__(self, settings: dict):
        self.settings = dict(settings)  # Copy on init

    def get(self, key: str):
        return self.settings.get(key)  # Read-only, no lock

# NO LOCK NEEDED: Thread-local storage
class Store:
    def __init__(self):
        self._local = local()  # Each thread has own storage
```

## Testing

### Unit Testing Metrics

```python
def test_metrics_collector_recording():
    """Verify metrics are recorded correctly."""
    collector = MetricsCollector()
    collector.reset()

    # Record some requests
    collector.record_request("GET", "/api/v1/test", 100, 200)
    collector.record_request("GET", "/api/v1/test", 200, 200)
    collector.record_request("GET", "/api/v1/test", 50, 500)  # Error

    metrics = collector.get_metrics()

    assert metrics["total_requests"] == 3
    assert metrics["avg_request_duration_ms"] == 116.67
    assert metrics["error_rate"] == 1/3
    assert metrics["total_errors"] == 1
```

### Integration Testing

```python
def test_metrics_endpoint_integration():
    """Verify metrics are collected through API."""
    from fastapi.testclient import TestClient
    from ariadne_api.app import app

    client = TestClient(app)

    # Reset metrics
    client.post("/api/v1/metrics/reset")

    # Make some requests
    response = client.get("/health")
    assert response.status_code == 200

    # Check metrics were recorded
    metrics_response = client.get("/api/v1/metrics")
    assert metrics_response.status_code == 200

    metrics = metrics_response.json()
    assert metrics["metrics"]["total_requests"] >= 1
```

## Related Documentation

- [`/Users/jersyzhang/work/claude/ariadne/docs/solutions/performance-issues/phase4-batch-operations-performance-fix.md`](/Users/jersyzhang/work/claude/ariadne/docs/solutions/performance-issues/phase4-batch-operations-performance-fix.md) - Phase 4.1 batch operations
- [`/Users/jersyzhang/work/claude/ariadne/docs/solutions/database-issues/p025-two-phase-commit-rollback-tracking-failure.md`](/Users/jersyzhang/work/claude/ariadne/docs/solutions/database-issues/p025-two-phase-commit-rollback-tracking-failure.md) - Monitoring patterns
- [`/Users/jersyzhang/work/claude/ariadne/docs/plans/2026-02-01-feat-phase4-http-api-impact-analysis-plan.md`](/Users/jersyzhang/work/claude/ariadne/docs/plans/2026-02-01-feat-phase4-http-api-impact-analysis-plan.md) - Phase 4 plan with observability requirements

## Acceptance Criteria

- [x] MetricsCollector implemented with thread-safe singleton pattern
- [x] RequestContextMiddleware auto-collects request metrics
- [x] GET /api/v1/metrics endpoint returns current metrics
- [x] GET /api/v1/metrics/endpoints returns per-endpoint breakdown
- [x] GET /api/v1/metrics/health combines health + metrics
- [x] POST /api/v1/metrics/reset allows metric reset
- [x] System metrics (memory, uptime) via psutil
- [x] P95/P99 latency calculation
- [x] Thread-safe concurrent access
- [x] psutil>=6.0.0 added to dependencies

## Work Log

### 2026-02-02

**Implementation**: Phase 4.2 performance monitoring system

**Components delivered**:
- MetricsCollector (273 lines)
- 4 API endpoints
- Middleware integration
- Pydantic schemas (72 lines)

**Status**: Implemented and tested
