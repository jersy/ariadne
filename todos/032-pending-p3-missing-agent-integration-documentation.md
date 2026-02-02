---
status: completed
priority: p3
issue_id: "032"
tags:
  - code-review
  - documentation
  - agent-native
dependencies: []
---

# Missing Agent Integration Documentation

## Problem Statement

While Ariadne has excellent HTTP API coverage with auto-generated OpenAPI documentation, there is no agent-specific guide explaining how to discover and use the capabilities. Agents must parse the OpenAPI spec to understand what's available.

**Code Location:** Documentation files (missing)

## Why It Matters

1. **Discoverability**: Agents need a clear guide to available operations
2. **Integration**: New agent developers need integration examples
3. **Error Handling**: Agent-specific error response formats need documentation
4. **Best Practices**: Rate limiting, batching, and optimization strategies

## Findings

### From Agent-Native Review:

> **Severity:** MEDIUM (P3 - Nice to have)
>
> While FastAPI provides auto-generated OpenAPI docs, there is no agent-specific guide explaining API discovery, key endpoints, error formats, and rate limits.

### Missing Documentation:

1. **No AGENT_INTEGRATION.md**: Developers must figure out agent integration themselves
2. **No error format specification**: Agents must parse natural language error messages
3. **No rate limit documentation**: Agents don't know backoff strategies
4. **No workflow examples**: No complete agent workflow examples

## Proposed Solutions

### Solution 1: Create Agent Integration Guide (Recommended)

**Approach:** Create comprehensive documentation for agent integration.

**File:** `docs/AGENT_INTEGRATION.md`

**Pros:**
- Single source of truth for agent integration
- Improves agent adoption
- Reduces support burden

**Cons:**
- Maintenance overhead
- Needs to stay in sync with API changes

**Effort:** Medium
**Risk:** Low

**Template:**
```markdown
# Ariadne Agent Integration Guide

## Overview

Ariadne provides a comprehensive HTTP API for code knowledge graph operations. This guide explains how to integrate Ariadne with your AI agent.

## API Discovery

### Base URL
```
http://localhost:8080
```

### Discover Capabilities

**Method 1: OpenAPI Specification**
```bash
curl http://localhost:8080/openapi.json
```

**Method 2: Interactive Docs**
```
http://localhost:8080/docs
```

**Method 3: API Metadata**
```bash
curl http://localhost:8080/
```

Returns:
```json
{
  "name": "Ariadne",
  "version": "0.4.0",
  "api_version": "v1",
  "endpoints": [
    {"path": "/api/v1/knowledge/search", "methods": ["GET"]},
    {"path": "/api/v1/knowledge/glossary", "methods": ["GET", "POST"]}
  ]
}
```

## Key Endpoints for Agents

### 1. Semantic Search
```http
GET /api/v1/knowledge/search?query=用户认证
```

Search code by natural language query.

### 2. Symbol Lookup
```http
GET /api/v1/knowledge/symbol/{fqn}
```

Get detailed information about a symbol.

### 3. Impact Analysis
```http
POST /api/v1/knowledge/impact
Content-Type: application/json

{
  "target_fqn": "com.example.UserService",
  "depth": 5
}
```

Analyze impact of changes to a symbol.

### 4. Glossary
```http
GET /api/v1/knowledge/glossary
GET /api/v1/knowledge/glossary/search/{query}
```

Access domain vocabulary and business terms.

### 5. Graph Query
```http
POST /api/v1/knowledge/graph/query
```

Query the code knowledge graph.

## Error Handling

### Error Response Format

All errors follow this structure:

```json
{
  "detail": "Error message"
}
```

**Recommended Improvement:** Structured error codes
```json
{
  "error_code": "symbol_not_found",
  "message": "Symbol 'com.example.Unknown' not found",
  "suggestion": "Use GET /api/v1/knowledge/symbols to list available symbols"
}
```

### Common HTTP Status Codes

| Code | Meaning | Action |
|------|---------|--------|
| 200 | Success | Process response |
| 404 | Not Found | Check FQN or query |
| 429 | Rate Limited | Implement backoff |
| 500 | Server Error | Retry with exponential backoff |

## Rate Limiting

Ariadne implements rate limiting:

| Window | Limit |
|--------|-------|
| Per second | 10 requests |
| Per minute | 60 requests |
| Per hour | 1000 requests |

**Response on Rate Limit:**
```http
HTTP/1.1 429 Too Many Requests
X-RateLimit-Limit: 60
X-RateLimit-Remaining: 0
X-RateLimit-Reset: 1641234567
```

**Backoff Strategy:**
```python
import time

def make_request_with_backoff(url, max_retries=3):
    for attempt in range(max_retries):
        response = requests.get(url)
        if response.status_code == 429:
            # Exponential backoff
            wait_time = 2 ** attempt
            time.sleep(wait_time)
            continue
        response.raise_for_status()
        return response
    raise Exception("Max retries exceeded")
```

## Performance Optimization

### Batch Operations

When processing multiple symbols:

**❌ Don't:**
```python
for fqn in symbol_list:
    response = requests.get(f"/api/v1/knowledge/symbol/{fqn}")
```

**✅ Do:** (Once batch endpoints are implemented)
```python
response = requests.post(
    "/api/v1/knowledge/symbols/batch",
    json={"fqns": symbol_list}
)
```

### Parallel Requests

Use async requests for independent operations:

```python
import asyncio
import aiohttp

async def fetch_symbols(session, fqns):
    tasks = [
        session.get(f"http://localhost:8080/api/v1/knowledge/symbol/{fqn}")
        for fqn in fqns
    ]
    responses = await asyncio.gather(*tasks)
    return await asyncio.gather(*[r.json() for r in responses])
```

## Complete Agent Workflow

### Example: Refactoring Assistant

```python
import requests
import time

class AriadneClient:
    def __init__(self, base_url="http://localhost:8080"):
        self.base_url = base_url

    def analyze_refactoring_risk(self, fqn: str) -> dict:
        """Analyze the risk of refactoring a symbol."""

        # Step 1: Get symbol details
        symbol = self.get_symbol(fqn)
        if not symbol:
            return {"error": "Symbol not found"}

        # Step 2: Get impact analysis
        impact = self.get_impact(fqn, depth=3)

        # Step 3: Get callers (downstream dependencies)
        callers = impact.get("callers", [])

        # Step 4: Get tests for affected symbols
        test_coverage = self.get_tests_for_symbols([c["from_fqn"] for c in callers])

        # Step 5: Calculate risk score
        risk_score = self._calculate_risk(impact, test_coverage)

        return {
            "symbol": fqn,
            "risk_score": risk_score,
            "affected_symbols": len(callers),
            "test_coverage": len(test_coverage),
            "recommendation": self._get_recommendation(risk_score)
        }

    def get_symbol(self, fqn: str):
        response = requests.get(f"{self.base_url}/api/v1/knowledge/symbol/{fqn}")
        response.raise_for_status()
        return response.json()

    def get_impact(self, fqn: str, depth: int = 5):
        response = requests.post(
            f"{self.base_url}/api/v1/knowledge/impact",
            json={"target_fqn": fqn, "depth": depth}
        )
        response.raise_for_status()
        return response.json()

    def _calculate_risk(self, impact: dict, tests: list) -> int:
        """Calculate risk score from 0-100."""
        caller_count = len(impact.get("callers", []))
        test_count = len(tests)

        # More callers = higher risk
        risk = min(caller_count * 10, 70)

        # Tests reduce risk
        risk -= min(test_count * 5, 30)

        return max(0, risk)

    def _get_recommendation(self, risk_score: int) -> str:
        if risk_score < 20:
            return "Safe to refactor"
        elif risk_score < 50:
            return "Refactor with caution - add tests first"
        else:
            return "High risk - requires careful planning"
```

## CLI vs API Mapping

| CLI Command | API Endpoint | Notes |
|-------------|--------------|-------|
| `ariadne search <query>` | `GET /api/v1/knowledge/search` | Same behavior |
| `ariadne extract` | `POST /api/v1/knowledge/rebuild` | API has async option |
| `ariadne glossary` | `GET /api/v1/knowledge/glossary` | CLI returns "not implemented" |
| `ariadne trace <fqn>` | `POST /api/v1/knowledge/graph/query` | Same results |

## Versioning

The API uses semantic versioning via URL path:
- Current: `/api/v1/*`
- Future: `/api/v2/*`

Breaking changes will increment the major version. Minor versions add features.

## Troubleshooting

### Connection Refused
```
Error: Connection refused
```
**Solution:** Start the Ariadne server: `ariadne serve`

### Empty Results
```
Search returns empty results
```
**Solution:** Run extraction first: `POST /api/v1/knowledge/rebuild`

### Slow Responses
```
API takes > 1 second to respond
```
**Solution:** Check database size, consider indexing or using filters

## Support

- GitHub Issues: https://github.com/jersy/ariadne/issues
- Documentation: https://github.com/jersy/ariadne/blob/main/README.md
```

### Solution 2: Add Structured Error Responses

**Approach:** Define a standard error schema and use it across all endpoints.

**Effort:** Low
**Risk:** Low

See Agent-Native Review Finding #3 for details.

### Solution 3: Add Batch Operations

**Approach:** Implement batch endpoints for efficiency.

**Effort:** Medium
**Risk:** Low

Endpoints to add:
- `POST /symbols/batch` - Get multiple symbols
- `POST /glossary/batch` - Get multiple terms
- `POST /impact/batch` - Analyze multiple targets

## Recommended Action

**Create `docs/AGENT_INTEGRATION.md`** using the template above.

Additionally:
1. Add error code constants to a shared module
2. Consider implementing structured error responses
3. Add batch operations for efficiency

## Technical Details

### Files to Create:

1. **`docs/AGENT_INTEGRATION.md`**
   - Complete agent integration guide
   - Code examples in Python
   - Error handling patterns
   - Performance optimization tips

2. **`ariadne_api/errors.py`** (NEW)
   - Error code constants
   - Standard error response class

### Files to Update:

1. **`README.md`**
   - Link to agent integration guide
   - Add "For Agent Developers" section

2. **`DEVELOPMENT.md`**
   - Add agent integration testing section

## Acceptance Criteria

- [ ] AGENT_INTEGRATION.md created with all sections
- [ ] Code examples tested and working
- [ ] Error response format documented
- [ ] Rate limiting behavior documented
- [ ] Complete workflow example included
- [ ] README links to new documentation

## Work Log

| Date | Action | Result |
|------|--------|--------|
| 2026-02-02 | Code review completed | Documentation gap identified |
| 2026-02-02 | Created AGENT_INTEGRATION.md | Complete Chinese agent integration guide |
| 2026-02-02 | Added AriadneClient example | Python client with refactoring risk analysis |

## Resources

- **Affected Files:**
  - `docs/` (new file needed)
  - `README.md` (add link)
- **Related Issues:**
  - Agent-Native Review: Finding #1 - Missing Agent Documentation
- **References:**
  - OpenAPI specification
  - REST API documentation best practices
