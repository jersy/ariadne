---
status: pending
priority: p2
issue_id: "047"
tags:
  - code-review
  - test-coverage
  - api
  - integration
  - endpoints
dependencies: []
---

# P2: No Integration Tests for API Endpoints

## Problem Statement

**No integration tests verify API endpoints work end-to-end** - API routes are not tested against actual FastAPI application.

## What's Missing

**Missing Integration Tests:**
- No tests that make actual HTTP requests to the app
- No tests that verify request/response validation
- No tests that verify middleware integration
- No tests that verify dependency injection
- No tests that verify error handling paths

**Current State:**
- `tests/api/test_search.py` exists but may only test unit logic
- `tests/api/test_api_version.py` exists but limited scope

## Impact

| Aspect | Impact |
|--------|--------|
| Risk | High - API may not work in practice |
| Integration | Cannot detect middleware/route integration issues |
| Confidence | Low in API functionality |
| Deployment | Risk of broken API in production |

## Proposed Solutions

### Solution A: Add FastAPI TestClient integration tests

Create comprehensive integration tests using FastAPI's TestClient:

```python
from fastapi.testclient import TestClient
from ariadne_api.app import app

def test_search_endpoint_integration():
    client = TestClient(app)

    # Test successful search
    response = client.get("/api/v1/search?q=User")
    assert response.status_code == 200
    data = response.json()
    assert "results" in data

    # Test empty query
    response = client.get("/api/v1/search")
    assert response.status_code == 422  # Validation error

    # Test not found
    response = client.get("/api/v1/search?q=NonExistentClass12345")
    assert response.status_code == 200
    assert len(response.json()["results"]) == 0

def test_metrics_endpoints_integration():
    client = TestClient(app)

    # Make some requests to generate metrics
    client.get("/health")
    client.get("/api/v1/search?q=test")

    # Check metrics endpoint
    response = client.get("/api/v1/metrics")
    assert response.status_code == 200
    data = response.json()
    assert "metrics" in data
    assert data["metrics"]["total_requests"] >= 2

    # Check endpoint breakdown
    response = client.get("/api/v1/metrics/endpoints")
    assert response.status_code == 200
    endpoints = response.json()
    assert isinstance(endpoints, dict)

    # Check health with metrics
    response = client.get("/api/v1/metrics/health")
    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert "metrics" in data
    assert "services" in data

def test_middleware_request_id_header():
    client = TestClient(app)
    response = client.get("/health")
    assert "X-Request-ID" in response.headers
    assert "X-Process-Time-ms" in response.headers

def test_error_responses():
    client = TestClient(app)

    # Test 404
    response = client.get("/api/v1/nonexistent")
    assert response.status_code == 404

    # Test validation error
    response = client.get("/api/v1/search")
    assert response.status_code == 422
```

**Pros:**
- Tests actual HTTP layer
- Catches integration issues
- Tests middleware automatically
- Fast and reliable (no network)

**Cons:**
- Requires test database setup
- More complex than unit tests

**Effort:** Medium (2-3 hours)

**Risk:** None

## Affected Files

- `tests/api/` - Needs integration tests
- `ariadne_api/` - All routes need integration testing

## Acceptance Criteria

- [ ] Integration tests for all `/api/v1/` routes
- [ ] Tests for Phase 4.2 metrics endpoints
- [ ] Tests for middleware (request ID, timing headers)
- [ ] Tests for error cases (404, 422, 500)
- [ ] Tests use FastAPI TestClient
- [ ] All tests pass
- [ ] Tests can run in CI/CD pipeline

## Work Log

### 2026-02-02

**Issue discovered during:** Test coverage review

**Root cause:** Integration tests not prioritized

**Status:** Pending test implementation
