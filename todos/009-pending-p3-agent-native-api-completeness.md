---
status: pending
priority: p3
issue_id: "009"
tags:
  - code-review
  - agent-native
  - api-design
dependencies: []
---

# Agent-Native API Completeness

## Problem Statement

The Ariadne project is described as a "code knowledge graph for architect agents," but the HTTP API layer is completely missing. The `serve` command is a placeholder that only prints a message, and there's no way for agents to access capabilities programmatically via HTTP.

**Location:** `ariadne_cli/main.py:255-257`, `ariadne_api/` directory (empty)

## Why It Matters

1. **Agent Access**: Agents cannot use HTTP API to interact with the system
2. **Feature Parity**: CLI has 13 commands, but 0 HTTP endpoints
3. **Remote Execution**: No way to run analysis remotely without SSH
4. **Integration**: Difficult to integrate with other tools/services

## Findings

### From Agent-Native Reviewer:

> **Critical Issue**: Missing HTTP API Layer
>
> The `ariadne_api/` directory exists but is completely empty. The `serve` command is a placeholder that just prints a message. Agents cannot access any capabilities via HTTP.

**Capability Map:**

| CLI Command | Python API | HTTP API | Status |
|-------------|------------|----------|--------|
| `extract` | Yes | None | ⚠️ Python only |
| `entries` | Yes | None | ⚠️ Python only |
| `deps` | Yes | None | ⚠️ Python only |
| `trace` | Yes | None | ⚠️ Python only |
| `check` | Yes | None | ⚠️ Python only |
| `summarize` | Yes | None | ⚠️ Python only |
| `summary` | Yes | None | ⚠️ Python only |
| `search` | Yes | None | ⚠️ Python only |
| `glossary` | Yes | None | ⚠️ Python only (not implemented) |
| `term-search` | Yes | None | ⚠️ Python only |
| `constraints` | Yes | None | ⚠️ Python only (not implemented) |
| `constraint-search` | Yes | None | ⚠️ Python only |
| `serve` | None | None | ❌ Placeholder |

**Agent-Native Score:** 4/13 capabilities are fully agent-accessible (Python API only, no HTTP)

## Proposed Solutions

### Solution 1: Implement FastAPI HTTP Layer (Recommended)

**Approach:** Create FastAPI routes for all CLI commands

**Pros:**
- Standard Python web framework
- Automatic OpenAPI documentation
- Async support
- Type validation with Pydantic

**Cons:**
- Significant implementation effort
- New dependency (FastAPI)

**Effort:** High
**Risk:** Low

**Implementation Outline:**
```python
# ariadne_api/app.py
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI(title="Ariadne Code Knowledge Graph")

# Pydantic schemas
class ExtractRequest(BaseModel):
    project: str
    output: str = "ariadne.db"

class ExtractResponse(BaseModel):
    symbols_inserted: int
    database: str

# Routes
@app.post("/api/v1/extract")
async def extract(request: ExtractRequest) -> ExtractResponse:
    """Extract symbols from Java project."""
    from ariadne_core.extractors.asm.extractor import extract_project
    count = extract_project(request.project, request.output)
    return ExtractResponse(symbols_inserted=count, database=request.output)

@app.get("/api/v1/entries")
async def list_entries(db: str = "ariadne.db", entry_type: str | None = None):
    """List entry points (HTTP APIs, scheduled tasks, MQ consumers)."""
    from ariadne_core.storage.sqlite_store import SQLiteStore
    with SQLiteStore(db) as store:
        entries = store.get_entry_points(entry_type=entry_type)
        return {"entries": entries, "count": len(entries)}

# ... implement all 13 commands as endpoints
```

**CLI Update:**
```python
# ariadne_cli/main.py
if args.command == "serve":
    import uvicorn
    from ariadne_api.app import app

    print(f"Starting Ariadne API server on port {args.port}")
    uvicorn.run(app, host="0.0.0.0", port=args.port)
```

### Solution 2: Expose Python API with MCP Tools

**Approach:** Create MCP tool definitions for programmatic access

**Pros:**
- Agents can use MCP directly
- No HTTP server needed
- Simpler than full API

**Cons:**
- Not RESTful
- MCP-specific
- Less flexible for integrations

**Effort:** Medium
**Risk:** Low

### Solution 3: Remove Placeholder Commands

**Approach:** Remove `serve` command and unimplemented commands until ready

**Pros:**
- Clearer about current capabilities
- No false promises

**Cons:**
- Doesn't solve agent access problem
- Removes forward-looking feature

**Effort:** Low
**Risk:** Low

## Recommended Action

**Use Solution 1 (Implement FastAPI HTTP Layer)**

Given the project's stated purpose ("for architect agents"), implementing the HTTP API is essential. Start with core commands and expand incrementally.

## Technical Details

### Files to Create:
1. `ariadne_api/app.py` - FastAPI application
2. `ariadne_api/routes/` - Route modules (extract.py, analyze.py, search.py)
3. `ariadne_api/schemas/` - Pydantic schemas (request.py, response.py)

### Implementation Priority:
**Phase 1** (Core):
- `POST /api/v1/extract` - Symbol extraction
- `GET /api/v1/entries` - List entry points
- `POST /api/v1/trace` - Trace call chains

**Phase 2** (Search):
- `POST /api/v1/search` - Semantic search
- `GET /api/v1/summary` - Get summary for symbol

**Phase 3** (Analysis):
- `GET /api/v1/deps` - List dependencies
- `POST /api/v1/check` - Check anti-patterns

**Phase 4** (Business Layer):
- `POST /api/v1/summarize` - Generate summaries
- `POST /api/v1/glossary` - Build glossary
- `POST /api/v1/constraints` - Extract constraints

### Dependencies to Add:
```toml
# pyproject.toml
dependencies = [
    "fastapi>=0.115.0",
    "uvicorn[standard]>=0.34.0",
]
```

### Acceptance Criteria:
- [ ] FastAPI application created
- [ ] At least 5 core endpoints implemented
- [ ] OpenAPI documentation auto-generated
- [ ] CLI `serve` command functional
- [ ] Tests for all endpoints
- [ ] Authentication/authorization considered
- [ ] Error handling consistent
- [ ] Rate limiting implemented

## Acceptance Criteria

- [ ] FastAPI application scaffold created
- [ ] `/api/v1/extract` endpoint implemented
- [ ] `/api/v1/entries` endpoint implemented
- [ ] `/api/v1/trace` endpoint implemented
- [ ] `/api/v1/search` endpoint implemented
- [ ] CLI `serve` command starts server
- [ ] OpenAPI docs accessible at `/docs`
- [ ] Pydantic schemas for all requests/responses
- [ ] Tests verify endpoint behavior
- [ ] CORS configuration for web access

## Work Log

| Date | Action | Result |
|------|--------|--------|
| 2026-02-01 | Code review completed | HTTP API gap identified |

## Resources

- **Files**: `ariadne_api/`, `ariadne_cli/main.py`
- **Related**: None (new feature)
- **Documentation**:
  - FastAPI: https://fastapi.tiangolo.com/
  - OpenAPI: https://swagger.io/specification/
  - MCP: https://modelcontextprotocol.io/
