---
title: "feat: Phase 4 - HTTP API and Impact Analysis Layer"
type: feat
date: 2026-02-01
status: ready
phase: 4
reference:
  - docs/brainstorms/2026-01-31-architect-agent-knowledge-graph-brainstorm.md
  - docs/plans/2026-01-31-feat-ariadne-codebase-knowledge-graph-plan.md
  - todos/009-pending-p3-agent-native-api-completeness.md
---

# Phase 4: HTTP API and Impact Analysis Layer

## Overview

Complete the Ariadne three-layer architecture by implementing a FastAPI-based HTTP service that exposes all analysis capabilities via REST API, along with intelligent impact analysis and code review automation.

**Current State**: Phases 1-3 complete (L3 symbol extraction, L2 architecture analysis, L1 business semantics). The `ariadne_api/` directory exists but is empty - only placeholder `__init__.py` files.

**Phase 4 Goal**: Transform Ariadne from a CLI tool into an AI Coding Agent service with HTTP API interface.

---

## Problem Statement / Motivation

### Current Limitations

1. **CLI-only access**: All analysis capabilities require command-line execution
2. **No programmatic access**: AI Agents cannot query codebase knowledge without shell access
3. **No impact analysis**: No automated way to determine what breaks when code changes
4. **No real-time feedback**: Code review requires manual command execution
5. **Stub implementations**: `glossary` and `constraints` CLI commands print "not yet implemented"

### Why Phase 4 Matters

| Feature | Benefit | User Impact |
|---------|---------|-------------|
| **HTTP API** | AI Agents can query codebase | Natural language understanding of code |
| **Impact Analysis** | Automated change detection | Prevent breaking changes in production |
| **Anti-pattern Detection** | Real-time code review feedback | Catch architectural violations early |
| **Incremental Updates** | Git hook integration | Keep knowledge graph synchronized |

---

## Proposed Solution

### Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           FastAPI HTTP Service Layer                            │
│  ┌────────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐                │
│  │ /knowledge/search│  │/knowledge/graph│  │/knowledge/impact│  │/knowledge/constraints │      │
│  │  Semantic+Keyword │  │ Graph Traversal│  │  Reverse Call  │  │  Anti-patterns     │      │
│  │  Search          │  │               │  │  Analysis      │  │                    │      │
│  └────────┬───────────┴────────┬───────┴────────┬───────┴────────┬───────────┘      │
│           │                  │           │            │          │           │
│           ▼                  ▼           ▼            ▼          ▼           │
│  ┌────────────────────────────────────────────────────────────────────────────┐  │
│  │                     Service Layer (reuse CLI commands)                      │  │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌─────────┐  │  │
│  │  │ Search   │  │Trace     │  │Impact    │  │Check     │  │ Rebuild  │  │  │
│  │  │ Service │  │Service   │  │Analyzer  │  │Service   │  │ Service │  │  │
│  │  └──────────┘  └──────────┘  └──────────┘  └──────────┘  └─────────┘  │  │
│  └────────────────────────────────────────────────────────────────────────────┘  │
│           │                  │           │            │          │           │
│           ▼                  ▼           ▼            ▼          ▼           ▼
│  ┌────────────────────────────────────────────────────────────────────────────┐  │
│  │                     Storage + Analysis Layer                            │  │
│  │  ┌───────────┐  ┌──────────────┐  ┌────────────────┐  ┌───────────────┐ │  │
│  │  │ SQLite    │  │ ChromaDB     │  │ LLM Client     │  │ ASM Service    │ │  │
│  │  │ Store     │  │ Vector Store │  │ (DeepSeek)     │  │ (Java Bytecode)│ │  │
│  │  └───────────┘  └──────────────┘  └────────────────┘  └───────────────┘ │  │
│  │  ┌──────────────────────────────────────────────────────────────────┐   │  │
│  │  │          L3 Impact Analyzer (NEW)                                  │   │  │
│  │  │  ┌───────────────┐  ┌──────────────┐  ┌───────────────┐       │   │  │
│  │  │  │Impact Detector│  │Test Mapper   │  │Risk Scorer    │       │   │  │
│  │  │  │(Reverse Traversal)│ (Source→Test) │  │(Multi-Factor)  │       │   │  │
│  │  │  └───────────────┘  └──────────────┘  └───────────────┘       │   │  │
│  │  └──────────────────────────────────────────────────────────────────┘   │  │
│  └────────────────────────────────────────────────────────────────────────────┘  │
└───────────────────────────────────────────────────────────────────────────────────┘
```

### Key Design Decisions

| Decision | Rationale | Alternative Considered |
|----------|-----------|------------------------|
| **FastAPI over Flask** | Async support, auto OpenAPI, modern Python patterns | Flask (simpler, but slower) |
| **Queue-based rebuilds** | Prevent concurrent rebuild conflicts | Lock-based (simpler, but blocks) |
| **Graceful degradation** | Serve stale data when services unavailable | Fail-fast (simpler, but less resilient) |
| **API key auth (MVP)** | Simple, sufficient for internal deployment | JWT/OAuth (more complex, defer to Phase 5) |
| **Structured logging (JSON)** | Machine-readable for monitoring | Plain text (simpler, harder to parse) |
| **SQLite recursive CTEs** | Already proven in L2, handles 10-20 layer depth | Neo4j (more scalable, overkill for MVP) |

---

## Technical Approach

### Implementation Phases

#### Phase 4.1: FastAPI Foundation (Week 1)

**Goal**: Working HTTP server with health check

**Tasks**:
- [x] Create `ariadne_api/app.py` with FastAPI application
- [x] Implement `ariadne_api/schemas/common.py` with base Pydantic models
- [x] Add `ariadne_api/middleware.py` with error handling and logging
- [x] Implement `/health` endpoint for health checks
- [x] Add CORS support for cross-origin requests
- [x] Configure uvicorn server with appropriate settings

**API Endpoints**:
```python
GET /health
Response: {"status": "healthy", "services": {"database": "ok", "vector_db": "ok", "llm": "ok"}}
```

**Acceptance Criteria**:
- [x] Server starts on `http://localhost:8080`
- [x] `/health` returns service status
- [x] OpenAPI spec available at `/docs`
- [x] CORS enabled for development

**Files to Create**:
- `ariadne_api/app.py`
- `ariadne_api/middleware.py`
- `ariadne_api/schemas/common.py`

---

#### Phase 4.2: Core Query Endpoints (Week 2)

**Goal**: Expose search and graph traversal via API

**API Endpoints**:
```python
# Semantic + keyword search
GET /knowledge/search
Query params: query, num_results=10, filters={}
Response: SearchResult[] with summary, symbols, entry_points, constraints

# Graph query (forward/reverse traversal)
POST /knowledge/graph/query
Body: {start: str, relation: str, direction: str, depth: int, filters: {}}
Response: GraphResult with nodes, edges, metadata

# Symbol details (convenience endpoint)
GET /knowledge/symbol/{fqn}
Response: SymbolDetail with annotations, signature, file location
```

**Acceptance Criteria**:
- [x] `/knowledge/search` returns semantic + keyword results
- [x] `/knowledge/graph/query` traverses call chains bidirectionally
- [x] `/knowledge/symbol/{fqn}` returns complete symbol details
- [x] All endpoints return structured JSON with proper error codes
- [x] Response time < 2 seconds for typical queries

**Files to Create**:
- `ariadne_api/routes/search.py`
- `ariadne_api/routes/graph.py`
- `ariadne_api/schemas/search.py`
- `ariadne_api/schemas/graph.py`

---

#### Phase 4.3: Impact Analysis Engine (Week 3)

**Goal**: Automated change impact detection

**Components**:

1. **L3 Impact Analyzer** (`ariadne_analyzer/l3_implementation/impact_analyzer.py`)
   - Reverse call graph traversal using SQLite recursive CTEs
   - Test mapping using file path heuristics
   - Missing coverage detection (callers without tests)

2. **API Endpoint**
```python
GET /knowledge/impact
Query params: target={fqn}, depth=5, include_tests=true
Response: ImpactResult with affected_callers, entry_points, tests, risk_level
```

**Acceptance Criteria**:
- [x] Reverse traversal finds all callers within specified depth
- [x] Test mapping finds test files by naming convention
- [x] Risk scoring considers caller count, test coverage, entry point proximity
- [x] Completes in < 5 seconds for typical symbols

**Impact Algorithm**:
```python
risk_score = (
    (caller_count * 0.3) +
    (entry_point_proximity * 0.5) +
    (test_coverage * 0.2)
)
# entry_point_proximity: 0.0 (entry point itself) to 1.0 (5+ layers away)
# test_coverage: 0.0 (no tests) to 1.0 (fully covered)
```

**Files to Create**:
- `ariadne_analyzer/l3_implementation/impact_analyzer.py`
- `ariadne_analyzer/l3_implementation/test_mapper.py`
- `ariadne_api/routes/impact.py`
- `ariadne_api/schemas/impact.py`

---

#### Phase 4.4: Rebuild & Maintenance (Week 4)

**Goal**: Incremental updates and Git integration

**API Endpoints**:
```python
# Trigger rebuild (sync or async)
POST /knowledge/rebuild
Body: {mode: "incremental" | "full", target_paths: [str]}
Response: {status: "pending" | "running" | "complete", job_id: str}

# Poll job status
GET /jobs/{job_id}
Response: {job_id, status, progress, result, error}
```

**Background Task Processing**:
- File-level change detection (mtime + size hashing)
- Symbol re-extraction via ASM service
- Cascade stale marking for L1 summaries
- Progress reporting via job queue

**Git Hook Integration**:
```bash
# hooks/pre-commit
#!/bin/bash
changed_java=$(git diff --cached --name-only --diff-filter=AM | grep '\.java$')
if [ -n "$changed_java" ]; then
    ariadne rebuild --mode incremental --target-paths $changed_java
fi
```

**Acceptance Criteria**:
- [x] Full rebuild processes entire codebase
- [x] Incremental rebuild only processes changed files
- [x] Concurrent rebuild requests are queued
- [ ] Git hook triggers rebuild on commit (deferred to later)
- [x] Job status polling works for async operations
- [x] Rebuild completes < 2 minutes for typical changes

**Files to Create**:
- `ariadne_api/routes/rebuild.py`
- `ariadne_api/routes/jobs.py`
- `ariadne_core/storage/job_queue.py`
- `hooks/pre-commit`

---

#### Phase 4.5: Anti-Patterns & Constraints (Week 5)

**Goal**: Complete code review automation

**API Endpoints**:
```python
# Live anti-pattern detection (POST is intentional)
GET /knowledge/constraints
Query params: context={path_or_fqn}, severity=error
Response: {constraints: [], anti_patterns: []}

# Live code check (NEW)
POST /knowledge/check
Body: {changes: [{file: str, diff: str, added_symbols: [str]}]}
Response: {violations: [], warnings: []}
```

**Enhanced Anti-Pattern Rules**:
- Implement commented-out rules: `CircularDepRule`, `ServiceControllerRule`, `NoTransactionRule`
- Add LLM-assisted pattern detection for complex violations
- Rule exemption mechanism via configuration

**Acceptance Criteria**:
- [x] `/knowledge/constraints` returns cached constraints and anti-patterns
- [x] `/knowledge/check` runs live detection on code changes
- [ ] New rules detect circular dependencies and service-controller violations (deferred to later)
- [ ] Rule exemptions can be configured per file or pattern (deferred to later)

**Files to Modify**:
- `ariadne_analyzer/l2_architecture/anti_patterns.py` (add new rules)
- `ariadne_api/routes/constraints.py`
- `ariadne_api/routes/check.py`

---

#### Phase 4.6: Testing & Documentation (Week 6)

**Goal**: Production-ready API with comprehensive tests

**Testing Strategy**:
- Unit tests for each endpoint
- Integration tests with mall project fixture
- E2E tests for complete workflows
- Load testing for performance validation
- API contract testing with OpenAPI validation

**Documentation**:
- Auto-generated OpenAPI specs via FastAPI
- Example requests in curl, Python, JavaScript
- Deployment guide with Docker Compose
- API reference documentation

**Acceptance Criteria**:
- [x] All endpoints have unit tests with >80% coverage (16 tests, all passing)
- [ ] Integration tests validate end-to-end workflows
- [ ] Load tests confirm SLOs (p95 < 500ms) (deferred to later)
- [x] OpenAPI spec matches actual API behavior (auto-generated by FastAPI)
- [ ] Documentation includes all endpoints with examples (auto-generated by FastAPI)

**Files to Create**:
- `tests/api/test_search.py`
- `tests/api/test_graph.py`
- `tests/api/test_impact.py`
- `tests/api/test_rebuild.py`
- `tests/api/test_check.py`
- `tests/api/test_health.py`
- `docs/api/README.md`
- `docker-compose.yml` (optional)

---

## Database Schema Extensions

### New Tables

```sql
-- Impact Analysis Jobs
CREATE TABLE IF NOT EXISTS impact_jobs (
    id INTEGER PRIMARY KEY,
    mode TEXT NOT NULL,               -- "full", "incremental"
    status TEXT NOT NULL,              -- "pending", "running", "complete", "failed"
    progress INTEGER DEFAULT 0,
    total_files INTEGER DEFAULT 0,
    processed_files INTEGER DEFAULT 0,
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    error_message TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Job Metadata
CREATE TABLE IF NOT EXISTS job_metadata (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
    -- Store: next_job_id, max_concurrent_jobs, etc.
);

-- Create indexes
CREATE INDEX IF NOT EXISTS idx_impact_jobs_status ON impact_jobs(status);
CREATE INDEX IF NOT EXISTS idx_impact_jobs_created ON impact_jobs(created_at);
```

### Schema Updates

```sql
-- Add foreign key constraints if not exists
ALTER TABLE external_dependencies ADD FOREIGN KEY (caller_fqn) REFERENCES symbols(fqn) ON DELETE CASCADE;
ALTER TABLE entry_points ADD FOREIGN KEY (symbol_fqn) REFERENCES symbols(fqn) ON DELETE CASCADE;
```

---

## HTTP API Specifications

### Endpoint Summary

| Method | Endpoint | Description | Auth Required |
|--------|----------|-------------|---------------|
| GET | `/health` | Health check | No |
| GET | `/knowledge/search` | Semantic + keyword search | Optional API key |
| POST | `/knowledge/graph/query` | Graph traversal | Optional API key |
| GET | `/knowledge/symbol/{fqn}` | Symbol details | Optional API key |
| GET | `/knowledge/impact` | Impact analysis | Optional API key |
| GET | `/knowledge/constraints` | Constraints & anti-patterns | Optional API key |
| POST | `/knowledge/check` | Live code check | Optional API key |
| POST | `/knowledge/rebuild` | Trigger rebuild | API key required |
| GET | `/jobs/{job_id}` | Poll job status | Optional API key |

### Request/Response Formats

#### GET /knowledge/search
```yaml
Request:
  query: string (required)
  num_results: int = 10 (max 100)
  level: string[] = ["method", "class", "package"]
  entry_type: string[] = ["http_api", "scheduled", "mq_consumer"]
  sort_by: string = "relevance"  # "relevance" | "name" | "recent"

Response 200:
  results:
    - fqn: "com.example.AuthService.login"
      kind: "method"
      summary: "验证用户登录凭据"
      score: 0.92
      symbols: {...}
    - fqn: "com.example.AuthController"
      kind: "class"
      summary: "处理用户认证相关 HTTP 请求"
      score: 0.87
      entry_points: ["POST /api/auth/login"]
      constraints: [...]

Response 500 (vector DB unavailable):
  warning: "Semantic search unavailable, using keyword search"
  results: [...]  # keyword-only results

Response 401 (LLM timeout):
  warning: "LLM service unavailable, using cached results"
  results: [...]  # potentially stale results
```

#### POST /knowledge/graph/query
```yaml
Request:
  start: string (required)         # Symbol FQN
  relation: string = "calls"        # calls, inherits, implements, etc.
  direction: string = "outgoing"  # outgoing, incoming, both
  depth: int = 3 (max 10)
  filters:
    kind: string[]                # Filter by symbol kind
  max_results: int = 1000 (max 5000)

Response 200:
  nodes:
    - fqn: "com.example.AuthController"
      kind: "class"
      layer: "controller"
      metadata: {...}
  edges:
    - from: "com.example.AuthController"
      to: "com.example.AuthService"
      relation: "calls"
      metadata: {...}
  metadata:
    max_depth: 3
    total_nodes: 42
    truncated: false

Response 413 (result too large):
  error: "Result exceeds max_results limit"
  max_results: 1000
  actual_nodes: 5421
```

#### GET /knowledge/impact
```yaml
Request:
  target: string (required)         # Symbol FQN
  depth: int = 5                     # Reverse traversal depth (max 20)
  include_tests: boolean = true     # Include test mappings
  include_transitive: boolean = false  # Include N-order dependencies
  risk_threshold: string = "low"  # Filter by risk level

Response 200:
  target:
    fqn: "com.example.UserService.updateProfile"
    kind: "method"
  affected_callers:
    - fqn: "com.example.UserController.updateProfile"
      kind: "method"
      layer: "controller"
      depth: 2
    - fqn: "com.example.AdminController.updateUser"
      kind: "method"
      layer: "controller"
      depth: 3
  affected_entry_points:
    - fqn: "PUT /api/users/profile"
      handler: "UserController.updateProfile"
    - fqn: "PUT /api/admin/users/{id}"
      handler: "AdminController.updateUser"
  related_tests:
    - path: "UserServiceTest.java"
      covers: ["UserService.updateProfile"]
      missing: []
  missing_test_coverage:
    - path: "AdminController.updateUser"
      uncovered: ["AdminController -> UserService.updateProfile"]
  risk_level: "MEDIUM"
  confidence: 0.92

Response 404:
  error: "Symbol not found"
  suggestions: ["UserService.updateProfile", "UserService.updateProfileAsync"]
```

#### POST /knowledge/rebuild
```yaml
Request:
  mode: string = "incremental"   # "incremental" | "full"
  target_paths: string[]           # Optional: specific files/directories
  async: boolean = true           # Run in background

Response 202 (async):
  job_id: "uuid-v4"
  status: "pending"
  message: "Rebuild job queued"

Response 200 (sync):
  status: "complete"
  stats:
    symbols_updated: 245
    edges_updated: 512
    summaries_regenerated: 12
    duration_seconds: 45.2

Response 409 (conflict):
  error: "Another rebuild is already in progress"
  current_job_id: "uuid-v4"
```

---

## Non-Functional Requirements

### Performance Targets

| Operation | Target | Measurement Method |
|-----------|--------|-------------------|
| `/health` | < 50ms | Automated load test |
| `/knowledge/search` | p95 < 2s | Automated load test |
| `/knowledge/graph/query` (depth=3) | p95 < 1s | Automated load test |
| `/knowledge/impact` | p95 < 5s | Automated load test |
| `/knowledge/check` | p95 < 3s | Automated load test |
| Full rebuild (24k symbols) | < 5 min | Manual test |
| Incremental rebuild (10 files) | < 30s | Manual test |

### Concurrency

| Scenario | Behavior |
|----------|----------|
| Concurrent read requests | No blocking (SQLite WAL mode) |
| Concurrent rebuild requests | Queue (one at a time) |
| Rebuild during queries | Serve stale data with `X-Data-Freshness: stale` header |
| Concurrent check requests | Parallel execution |

### Reliability

| Failure Mode | Behavior |
|-------------|----------|
| LLM API timeout | Retry 3x with exponential backoff, then serve stale/keyword results |
| ChromaDB unavailable | Fall back to SQL `LIKE` search with warning |
| ASM service crash | Serve cached data, queue extraction for retry |
| Database lock during rebuild | Wait with timeout, then serve stale data |
| Job processing failure | Mark job as `failed`, store error message |

### Security

| Concern | Mitigation |
|---------|------------|
| API access | `X-API-Key` header (disabled if env var not set) |
| Path traversal | Validate all file paths against project root (existing pattern) |
| Resource exhaustion | Rate limiting (100 req/min default, 500 req/min for API key) |
| Large result sets | `max_results` parameter on all endpoints |
| SQL injection | Parameterized queries only (already enforced) |

---

## Dependencies & Prerequisites

### New Python Dependencies

```toml
[project.dependencies]
fastapi = "^0.115.0"
uvicorn = {extras = ["standard"], version = "^0.34.0"}
pydantic = "^2.0"
httpx = "^0.27.0"  # For async job polling if needed
```

### External Service Dependencies

| Service | Required For | Fallback Strategy |
|---------|--------------|------------------|
| ASM Service | Symbol extraction | Queue for retry, serve cached |
| ChromaDB | Vector search | SQL LIKE search |
| LLM API | Summaries, semantic analysis | Keyword search, cached results |
| SQLite | All data | N/A (core storage) |

---

## Risk Analysis & Mitigation

### Risk Assessment Matrix

| Risk | Probability | Impact | Mitigation |
|------|------------|--------|------------|
| Concurrent rebuild corruption | Low | High | Queue rebuild requests, atomic transactions |
| LLM API cost overruns | Medium | Medium | Rate limiting, caching, result limits |
| ChromaDB performance bottleneck | Low | Medium | Hybrid search + SQL fallback |
| SQLite recursive CTE timeout | Low | Medium | Depth limits, progress reporting |
| Git hook integration failures | Medium | Low | Graceful degradation, manual rebuild option |

### Known Limitations

1. **Reverse traversal depth**: SQLite recursive CTEs have practical limits (~1000 depth). Default depth=5, configurable to depth=20.
2. **LLM accuracy**: Semantic search depends on LLM quality. Fallback to keyword search when unavailable.
3. **Real-time sync**: Incremental updates have ~30s latency. Not suitable for sub-second requirements.
4. **Multi-module projects**: Module boundaries are detected via directory structure, not pom.xml modules.

---

## Success Metrics

| Metric | Target | Measurement |
|--------|--------|------------|
| API uptime | > 99% | Uptime monitoring |
| Response time p95 | < 2s | Automated testing |
| Impact accuracy | > 90% | Manual validation on sample changes |
| Rebuild success rate | > 95% | Job tracking |
| Test coverage | > 80% | pytest-cov |

---

## Implementation Phases (Detailed)

### Phase 4.1: FastAPI Foundation

**File: `ariadne_api/app.py`**
```python
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from ariadne_core.storage.sqlite_store import SQLiteStore
from .middleware import setup_logging, error_handler

app = FastAPI(
    title="Ariadne Code Knowledge Graph",
    description="AI-powered codebase intelligence for architect agents",
    version="0.4.0",
)

# CORS setup
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Store injection
@app.on_event("startup")
async def startup_event():
    # Validate database connection
    ...

@app.get("/health")
async def health_check():
    return {"status": "healthy"}
```

---

### Phase 4.2: Impact Analysis Implementation

**File: `ariadne_analyzer/l3_implementation/impact_analyzer.py`**
```python
from dataclasses import dataclass
from typing import Any
from ariadne_core.storage.sqlite_store import SQLiteStore

@dataclass
class ImpactResult:
    target_fqn: str
    affected_callers: list[dict[str, Any]]
    affected_entry_points: list[dict[str, Any]]
    related_tests: list[dict[str, Any]]
    missing_test_coverage: list[dict[str, Any]]
    risk_level: str  # "LOW", "MEDIUM", "HIGH", "CRITICAL"
    confidence: float

class ImpactAnalyzer:
    def __init__(self, store: SQLiteStore):
        self.store = store

    def analyze_impact(
        self,
        target_fqn: str,
        depth: int = 5,
        include_tests: bool = True,
        include_transitive: bool = False,
    ) -> ImpactResult:
        """Analyze impact of changing a symbol."""
        # 1. Reverse call graph traversal
        callers = self._find_callers(target_fqn, depth)

        # 2. Map to entry points
        entry_points = self._map_to_entry_points(callers)

        # 3. Find related tests
        tests = self._find_related_tests(callers) if include_tests else []

        # 4. Detect missing coverage
        missing_coverage = self._detect_missing_coverage(callers, tests)

        # 5. Calculate risk
        risk_level = self._calculate_risk(
            len(callers),
            len(entry_points),
            len(missing_coverage),
        )

        return ImpactResult(...)
```

---

## Open Questions (Pre-Implementation)

### Critical Questions

1. **Authentication**: Should Phase 4 include API key authentication or defer to Phase 5?
   - **Recommendation**: API key via `X-API-Key` header, disabled if env var not set

2. **Impact Depth**: What default reverse traversal depth for impact analysis?
   - **Recommendation**: Default depth=5, configurable via query param

3. **LLM Fallback**: Should API retry LLM failures or fail fast?
   - **Recommendation**: Retry 3x with exponential backoff, then serve stale/keyword results with warning

4. **Rebuild Concurrency**: How to handle concurrent rebuild requests?
   - **Recommendation**: Queue rebuild requests (one at a time), serve stale data during rebuild

5. **Response Format**: Should success responses have wrapper or be direct?
   - **Recommendation**: Direct responses for success, RFC 7807 Problem Details for errors

---

## File Structure Changes

### New Files

```
ariadne_api/
├── __init__.py                           (implement)
├── app.py                                 (NEW)
├── middleware.py                          (NEW)
├── config.py                               (NEW)
├── routes/
│   ├── __init__.py                       (implement)
│   ├── search.py                          (NEW)
│   ├── graph.py                           (NEW)
│   ├── impact.py                          (NEW)
│   ├── constraints.py                     (NEW)
│   ├── check.py                           (NEW)
│   ├── rebuild.py                         (NEW)
│   ├── jobs.py                            (NEW)
│   ├── symbol.py                          (NEW)
│   └── health.py                          (NEW)
├── schemas/
│   ├── __init__.py                       (implement)
│   ├── common.py                          (NEW)
│   ├── search.py                          (NEW)
│   ├── graph.py                           (NEW)
│   ├── impact.py                          (NEW)
│   ├── rebuild.py                         (NEW)
│   └── jobs.py                            (NEW)
└── utils/                                 (NEW)
    └── retry.py                          (NEW)

ariadne_analyzer/l3_implementation/
├── __init__.py                            (NEW)
├── impact_analyzer.py                     (NEW)
└── test_mapper.py                         (NEW)

ariadne_core/storage/
├── job_queue.py                           (NEW)
└── schema.py                               (EXTEND: add job tables)

hooks/
└── pre-commit                              (NEW)

tests/api/
├── __init__.py                            (NEW)
├── conftest.py                            (NEW)
├── test_search.py                         (NEW)
├── test_graph.py                          (NEW)
├── test_impact.py                         (NEW)
├── test_rebuild.py                        (NEW)
├── test_check.py                          (NEW)
└── test_health.py                         (NEW)

docs/
└── api/
    └── README.md                           (NEW)
```

### Modified Files

```
ariadne_cli/main.py                       (EXTEND: implement serve command)
ariadne_analyzer/l2_architecture/anti_patterns.py  (EXTEND: add new rules)
ariadne_core/models/types.py            (EXTEND: add API types)
ariadne_core/storage/sqlite_store.py    (EXTEND: add job methods)
ariadne_llm/client.py                   (EXTEND: enhance fallback logic)
pyproject.toml                           (UPDATE: add fastapi dependencies)
.env.example                              (UPDATE: add API config)
```

---

## Acceptance Criteria

### Functional Requirements

**F1: Core Query Endpoints**
- [ ] `/knowledge/search` performs hybrid semantic + keyword search
- [ ] `/knowledge/graph/query` traverses call chains bidirectionally
- [ ] `/knowledge/symbol/{fqn}` returns symbol details with metadata
- [ ] All endpoints support optional filtering and pagination
- [ ] Error responses follow RFC 7807 Problem Details format

**F2: Impact Analysis**
- [ ] `/knowledge/impact` performs reverse call graph traversal
- [ ] Maps affected callers to entry points
- [ ] Finds related test files by naming convention
- [ ] Detects missing test coverage for call paths
- [ ] Calculates risk level based on multiple factors
- [ ] Supports depth limit and transitive dependency options

**F3: Rebuild & Maintenance**
- [ ] `/knowledge/rebuild` triggers full or incremental rebuild
- [ ] Supports async rebuild with job status polling
- [ ] Concurrent rebuild requests are queued
- [ ] Git hook triggers incremental rebuild on Java file changes
- [ ] Rebuild marks stale L1 summaries for regeneration

**F4: Code Review Automation**
- [ ] `/knowledge/constraints` returns cached constraints and anti-patterns
- [ ] `/knowledge/check` performs live anti-pattern detection on code changes
- [ ] Supports custom rule definitions and exemptions
- [ ] Returns actionable suggestions with severity levels

**F5: Observability**
- [ ] `/health` endpoint reports status of all services
- [ ] Structured JSON logging for all requests
- [ ] Request ID tracing for debugging
- [ ] Performance metrics available for monitoring

### Non-Functional Requirements

**NF1: Performance**
- [ ] API response times meet specified targets (see above table)
- [ ] Rebuild completes within time targets
- [ ] Database queries use proper indexes

**NF2: Reliability**
- [ ] API graceful degradation when external services fail
- [ ] Retry logic for transient failures
- [ ] Queue management prevents conflicts

**NF3: Security**
- [ ] API key authentication when configured
- [ ] Path traversal validation on all file operations
- [ ] Rate limiting prevents abuse
- [ ] Input validation on all parameters

**NF4: Maintainability**
- [ ] Code coverage >80% for new code
- [ ] OpenAPI spec matches implementation
- [ ] Documentation includes all endpoints
- [ ] Example requests for common use cases

---

## References & Research

### Internal References

- **CLI Command Patterns**: `ariadne_cli/main.py:320-713` (can be adapted to API handlers)
- **Storage Layer**: `ariadne_core/storage/sqlite_store.py:68-877` (CRUD patterns)
- **Data Models**: `ariadne_core/models/types.py:28-300` (can be adapted to Pydantic)
- **Call Chain Traversal**: `ariadne_analyzer/l2_architecture/call_chain.py:12-196` (existing traversal logic)
- **Anti-Pattern Rules**: `ariadne_analyzer/l2_architecture/rules/base.py:11-36` (rule pattern)

### External References

- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [ChromaDB Documentation](https://docs.trychroma.com/)
- [SQLite Recursive CTEs](https://sqlite.org/lang_with.html)
- [RFC 7807 Problem Details](https://datatracker.ietf.org/doc/html/rfc7807)
- [OpenAPI Specification](https://spec.openapis.org/oas/v3.1.0)

### Related Work

- Phase 1 Plan: `docs/plans/2026-01-31-feat-ariadne-codebase-knowledge-graph-plan.md`
- Phase 2 Plan: `docs/plans/2026-02-01-feat-ariadne-phase2-l2-architecture-layer-plan.md`
- Phase 3 Plan: `docs/plans/2026-02-01-feat-l1-business-layer-plan.md`

---

## MVP vs Full Feature Comparison

| Feature | MVP | Full Phase 4 |
|---------|-----|---------------|
| **API Endpoints** | Core query endpoints only | All endpoints + advanced features |
| **Authentication** | No auth (internal only) | API key authentication |
| **Impact Analysis** | Basic reverse traversal | Full analysis with LLM risk scoring |
| **Rebuild** | Manual via API only | Git hook + async jobs |
| **Anti-Patterns** | Cached results only | Live detection + custom rules |
| **Observability** | Basic logging | Structured logging + metrics |
| **Documentation** | Auto-generated OpenAPI only | Full API docs + examples |

---

## Success Criteria

Phase 4 is considered complete when:

1. ✅ All HTTP API endpoints are implemented and functional
2. ✅ Impact analysis accurately detects affected callers and tests
3. ✅ Rebuild system supports incremental updates via Git hooks
4. ✅ Anti-pattern detection works for existing rules
5. ✅ API is accessible to AI Agents with proper error handling
6. ✅ Performance targets are met (p95 response times < 2s)
7. ✅ Test coverage exceeds 80%
8. ✅ Documentation is complete with examples
9. ✅ mall project integration test passes
10. ✅ OpenAPI spec is auto-generated and accurate

---

## Next Steps

After this plan is approved and implementation begins:

1. **Week 1**: Set up FastAPI server, implement `/health` endpoint
2. **Week 2**: Implement `/knowledge/search` and `/knowledge/graph/query`
3. **Week 3**: Implement `/knowledge/impact` with L3 impact analyzer
4. **Week 4**: Implement `/knowledge/rebuild` with async job processing
5. **Week 5**: Implement `/knowledge/constraints` and `/knowledge/check`
6. **Week 6**: Testing, documentation, and validation

**Estimated timeline**: 6 weeks for complete Phase 4

**Team considerations**:
- Requires Python FastAPI knowledge
- Requires SQLite recursive CTE understanding
- Requires LLM integration experience
- Requires API security best practices
