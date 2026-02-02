---
status: pending
priority: p1
issue_id: "044"
tags:
  - code-review
  - test-coverage
  - phase-4.2
  - metrics
  - monitoring
dependencies: []
---

# P1: No Tests for MetricsCollector (Phase 4.2)

## Problem Statement

**Phase 4.2 MetricsCollector has zero test coverage** - The entire performance monitoring system (MetricsCollector, metrics API routes, middleware integration) is completely untested.

## What's Missing

**Feature:** Phase 4.2 - Performance Monitoring System

**Missing Tests:**
- No unit tests for `MetricsCollector` class
- No tests for `RequestMetrics`, `DatabaseMetrics`, `LLMMetrics`, `JobMetrics`
- No tests for thread safety (singleton pattern)
- No tests for percentile calculations (p95, p99)
- No tests for metrics API endpoints (`/api/v1/metrics`, etc.)
- No tests for middleware auto-collection
- No tests for metrics reset functionality

**Files Missing Coverage:**
- `ariadne_api/metrics.py` - 0% coverage (273 lines untested)
- `ariadne_api/routes/metrics.py` - 0% coverage (96 lines untested)
- `ariadne_api/schemas/metrics.py` - 0% coverage (35 lines untested)
- `ariadne_api/middleware.py` - Metrics collection untested

## Impact

| Aspect | Impact |
|--------|--------|
| Risk | High - core infrastructure untested |
| Regression | Cannot detect if metrics break |
| Confidence | Zero in monitoring system |
| Coverage | ariadne_api/ - 0% coverage overall |

## Proposed Solutions

### Solution A: Create comprehensive test suite (RECOMMENDED)

Create `tests/unit/test_metrics_collector.py`:

```python
class TestMetricsCollector:
    def test_singleton_pattern(self):
        collector1 = get_metrics_collector()
        collector2 = get_metrics_collector()
        assert collector1 is collector2

    def test_record_request(self):
        collector = get_metrics_collector()
        collector.record_request("GET", "/test", 100, 200)
        metrics = collector.get_metrics()
        assert metrics["total_requests"] == 1

    def test_percentile_calculation(self):
        collector = get_metrics_collector()
        for duration in [100, 200, 300, 400, 500]:
            collector.record_request("GET", "/test", duration, 200)
        metrics = collector.get_metrics()
        assert metrics["p95_request_duration_ms"] == 500
        assert metrics["p99_request_duration_ms"] == 500

    def test_error_rate_calculation(self):
        collector = get_metrics_collector()
        collector.record_request("GET", "/test", 100, 200)
        collector.record_request("GET", "/test", 100, 500)
        metrics = collector.get_metrics()
        assert metrics["error_rate"] == 0.5

    def test_thread_safety(self):
        import threading
        collector = MetricsCollector()
        collector.reset()

        def record_requests():
            for i in range(100):
                collector.record_request("GET", f"/test/{i}", 100, 200)

        threads = [threading.Thread(target=record_requests) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        metrics = collector.get_metrics()
        assert metrics["total_requests"] == 1000
```

Create `tests/api/test_metrics.py`:

```python
def test_get_metrics():
    response = client.get("/api/v1/metrics")
    assert response.status_code == 200
    data = response.json()
    assert "metrics" in data
    assert "timestamp" in data

def test_get_endpoint_metrics():
    response = client.get("/api/v1/metrics/endpoints")
    assert response.status_code == 200

def test_metrics_health():
    response = client.get("/api/v1/metrics/health")
    assert response.status_code == 200

def test_reset_metrics():
    response = client.post("/api/v1/metrics/reset")
    assert response.status_code == 200
```

**Pros:**
- Comprehensive coverage
- Tests thread safety
- Tests API endpoints
- Documents expected behavior

**Cons:**
- More code to maintain
- Longer implementation time

**Effort:** Medium (2-3 hours)

**Risk:** None

## Affected Files

- `ariadne_api/metrics.py` - 273 lines, 0% coverage
- `ariadne_api/routes/metrics.py` - 96 lines, 0% coverage
- `ariadne_api/schemas/metrics.py` - 35 lines, 0% coverage
- `ariadne_api/middleware.py` - Metrics integration untested

## Acceptance Criteria

- [ ] Test file created: `tests/unit/test_metrics_collector.py`
- [ ] Test file created: `tests/api/test_metrics.py`
- [ ] Test singleton pattern works correctly
- [ ] Test request recording and metrics retrieval
- [ ] Test percentile calculations (p95, p99)
- [ ] Test error rate calculation
- [ ] Test thread safety with concurrent requests
- [ ] Test all 4 API endpoints return correct responses
- [ ] Test metrics reset functionality
- [ ] All tests pass
- [ ] Coverage for metrics.py > 80%

## Work Log

### 2026-02-02

**Issue discovered during:** Test coverage review

**Root cause:** Phase 4.2 implementation delivered without tests

**Status:** Pending test implementation
