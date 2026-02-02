---
status: pending
priority: p2
issue_id: "046"
tags:
  - code-review
  - test-coverage
  - api
  - ariadne-api
  - integration
dependencies: []
---

# P2: Zero Test Coverage on ariadne_api

## Problem Statement

**ariadne_api/ has 0% test coverage** - All API routes, schemas, and middleware are completely untested.

## What's Missing

**Files with 0% Coverage:**
- `ariadne_api/app.py` - 205 lines
- `ariadne_api/middleware.py` - 237 lines
- `ariadne_api/routes/*.py` - All route files untested:
  - `search.py` - 145 lines
  - `graph.py` - 94 lines
  - `symbol.py` - 113 lines
  - `impact.py` - 103 lines
  - `rebuild.py` - 284 lines
  - `jobs.py` - 82 lines
  - `constraints.py` - 108 lines
  - `check.py` - 106 lines
  - `glossary.py` - 56 lines
  - `tests.py` - 104 lines
  - `metrics.py` - 96 lines (Phase 4.2)
- `ariadne_api/schemas/*.py` - All schema files untested
- `ariadne_api/dependencies.py` - Untested
- `ariadne_api/rate_limiter.py` - Untested

## Impact

| Aspect | Impact |
|--------|--------|
| Risk | Very High - entire API surface untested |
| Regression | Cannot detect API breaking changes |
| Confidence | Zero in API functionality |
| Coverage | 0% across entire API module |

## Proposed Solutions

### Solution A: Add integration tests for all endpoints (RECOMMENDED)

Create `tests/api/` test files for each route:

```python
# tests/api/test_search.py
def test_search_by_name()
def test_search_by_kind()
def test_search_with_filters()
def test_search_empty_results()

# tests/api/test_graph.py
def test_get_graph()
def test_trace_call_chain()
def test_get_dependencies()

# tests/api/test_symbol.py
def test_get_symbol()
def test_get_symbol_not_found()

# tests/api/test_impact.py
def test_get_impact_analysis()

# tests/api/test_rebuild.py
def test_trigger_rebuild()

# tests/api/test_jobs.py
def test_list_jobs()
def test_get_job_status()

# tests/api/test_constraints.py
def test_check_constraints()

# tests/api/test_check.py
def test_architect_rules()

# tests/api/test_glossary.py
def test_get_glossary()
def test_add_glossary_term()

# tests/api/test_tests.py
def test_get_test_mapping()
def test_analyze_coverage()

# tests/api/test_metrics.py (Phase 4.2)
def test_get_metrics()
def test_get_endpoint_metrics()
def test_metrics_health()
def test_reset_metrics()
```

**Pros:**
- Tests all API functionality
- Catches integration issues
- Documents API behavior

**Cons:**
- Significant effort required
- Requires test database setup

**Effort:** Large (6-8 hours)

**Risk:** None

### Solution B: Start with smoke tests for critical endpoints

```python
def test_critical_endpoints_smoke():
    # Test health endpoint
    response = client.get("/health")
    assert response.status_code == 200

    # Test metrics endpoint
    response = client.get("/api/v1/metrics")
    assert response.status_code == 200
```

**Pros:**
- Quick to implement
- Verifies basic functionality

**Cons:**
- Doesn't test actual functionality
- Low confidence

**Effort:** Small (30 minutes)

**Risk:** None

## Affected Files

- `ariadne_api/` - Entire module has 0% coverage
- `tests/api/` - Needs more comprehensive tests

## Acceptance Criteria

- [ ] All API routes have at least one test
- [ ] All Phase 4.2 metrics endpoints tested
- [ ] Tests for error cases (404, 500)
- [ ] Tests for request/response validation
- [ ] At least 50% coverage on ariadne_api/

## Work Log

### 2026-02-02

**Issue discovered during:** Test coverage review

**Root cause:** API tests not created or maintained

**Status:** Pending test implementation
