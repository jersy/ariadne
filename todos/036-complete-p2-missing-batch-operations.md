---
title: Missing Batch Operations for Agent Efficiency
type: agent-native
priority: P2
status: pending
source: pr-review-5
severity: important
---

# Missing Batch Operations for Agent Efficiency

## Problem

The test mapping API lacks batch query capabilities, forcing agents to make multiple API calls when analyzing multiple symbols. This violates agent-native design principles.

## Current Implementation

Single-symbol API only:

```http
GET /api/v1/knowledge/tests/{fqn}
GET /api/v1/knowledge/coverage?target={fqn}
```

## Agent Impact

**Scenario:** Agent needs to analyze all modified classes in a PR (50 classes)

**Current Approach (Inefficient):**
```python
# Agent must make 50 HTTP requests
for fqn in modified_classes:
    test_mapping = api.get_test_mapping(fqn)  # 50 API calls
    coverage = api.get_coverage(fqn)          # 50 more API calls
    # Total: 100 API calls
```

**Network Cost:** ~100 HTTP requests × ~50ms = **5+ seconds**

**With Batch API (Efficient):**
```python
# Single request for all data
test_mappings = api.get_test_mappings_batch(modified_classes)  # 1 API call
coverages = api.get_coverages_batch(modified_classes)           # 1 API call
# Total: 2 API calls
```

**Network Cost:** ~2 HTTP requests × ~100ms = **0.2 seconds** (25x faster!)

## Solution

### API Design

**Endpoint 1: Batch Test Mapping**

```http
POST /api/v1/knowledge/tests/batch

Content-Type: application/json

{
  "fqns": [
    "com.example.service.UserService",
    "com.example.controller.UserController",
    "com.example.repository.UserRepository"
  ],
  "include_methods": true
}
```

**Response:**
```json
{
  "mappings": {
    "com.example.service.UserService": {
      "source_file": "src/main/java/com/example/service/UserService.java",
      "test_mappings": [
        {
          "test_file": "src/test/java/com/example/service/UserServiceTest.java",
          "test_exists": true,
          "test_methods": ["testCreateUser", "testDeleteUser"]
        }
      ]
    },
    "com.example.controller.UserController": {
      "source_file": "src/main/java/com/example/controller/UserController.java",
      "test_mappings": []
    }
  },
  "summary": {
    "total": 3,
    "found": 2,
    "with_tests": 1
  }
}
```

**Endpoint 2: Batch Coverage Analysis**

```http
POST /api/v1/knowledge/coverage/batch

Content-Type: application/json

{
  "targets": [
    "com.example.service.UserService",
    "com.example.controller.UserController"
  ]
}
```

**Response:**
```json
{
  "coverage": {
    "com.example.service.UserService": {
      "statistics": {"total_callers": 5, "tested_callers": 3, "coverage_percentage": 60.0},
      "warnings": [...]
    },
    "com.example.controller.UserController": {
      "statistics": {"total_callers": 2, "tested_callers": 0, "coverage_percentage": 0.0},
      "warnings": [...]
    }
  },
  "aggregate_stats": {
    "average_coverage": 30.0,
    "total_warnings": 5
  }
}
```

### Implementation

```python
# ariadne_api/routes/tests.py

@router.post("/knowledge/tests/batch", response_model=BatchTestMappingResponse)
async def get_test_mappings_batch(request: BatchTestMappingRequest):
    """Get test file mappings for multiple source symbols in one request."""
    with get_store() as store:
        mappings = {}
        for fqn in request.fqns:
            mapping = store.get_test_mapping(fqn)
            mappings[fqn] = mapping

        summary = {
            "total": len(request.fqns),
            "found": len([m for m in mappings.values() if m["source_file"]]),
            "with_tests": len([m for m in mappings.values() if m["test_mappings"]]),
        }

        return BatchTestMappingResponse(mappings=mappings, summary=summary)
```

## Acceptance Criteria

- [ ] POST `/api/v1/knowledge/tests/batch` endpoint implemented
- [ ] POST `/api/v1/knowledge/coverage/batch` endpoint implemented
- [ ] Batch size limit enforced (e.g., max 100 symbols per request)
- [ ] Request validation added
- [ ] Unit tests for batch endpoints
- [ ] Integration tests for batch operations
- [ ] API documentation updated

## Agent-Native Principles

**What makes this agent-native:**

1. **Single Call for Multiple Items:** Agent can analyze entire PR in one request
2. **Reduced Network Latency:** Fewer HTTP round-trips
3. **Consistent Response Format:** Batch responses match single-item structure
4. **Efficient Data Access:** Agent can work with large codebases without API rate limits

## References

- **Source:** PR #5 Review - Agent-Native Reviewer Agent
- **Principle:** Agent operations should match user workflows
- **Pattern:** Batch operations are core to agent efficiency
