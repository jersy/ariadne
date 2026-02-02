---
status: pending
priority: p1
issue_id: "039"
tags:
  - code-review
  - agent-native
  - integration
  - blocking
dependencies: []
---

# Orphaned Test Mapping Router

## Problem Statement

**Test Mapping and Coverage Analysis features are completely inaccessible to agents** due to missing router registration in FastAPI application. This is a critical **Agent-Native Violation** - the code exists and is well-tested, but agents cannot use it.

## What's Broken

The test mapping feature was implemented with:
- ✅ Complete storage layer (`sqlite_store.py` test mapping methods)
- ✅ API routes (`ariadne_api/routes/tests.py`)
- ✅ Pydantic schemas (`ariadne_api/schemas/tests.py`)
- ✅ 15/15 unit tests passing
- ❌ **Router NOT registered** in `ariadne_api/app.py`

**Impact**: All test mapping and coverage endpoints return 404. Agents cannot access:
- `GET /api/v1/knowledge/tests/{fqn}` - Single test mapping
- `POST /api/v1/knowledge/tests/batch` - Batch test mapping
- `GET /api/v1/knowledge/coverage` - Coverage analysis
- `POST /api/v1/knowledge/coverage/batch` - Batch coverage analysis

**Same issue affects**: Glossary router (`ariadne_api/routes/glossary.py`)

## Findings

### Agent Accessibility Score: 0%

**Evidence from code review:**

File: `ariadne_api/app.py` - Missing imports and registrations

```python
# Missing imports:
from ariadne_api.routes.tests import router as tests_router
from ariadne_api.routes.glossary import router as glossary_router

# Missing app.include_router calls
```

### Acceptance Scenario Impact

From `docs/brainstorms/2026-01-31-architect-agent-knowledge-graph-brainstorm.md`:

**Scenario 2: 防遗漏**
- Input: 修改 UserService 接口
- Expected Output:
  - 所有调用 UserService 的 Controller 列表
  - **关联的 Test 文件列表** ❌ NOT ACCESSIBLE
  - **未覆盖测试的调用路径警告** ❌ NOT ACCESSIBLE

**Result**: Scenario 2 is **NOT FUNCTIONAL** for agents.

## Proposed Solution

Register the routers in `ariadne_api/app.py`:

```python
# Add imports
from ariadne_api.routes.tests import router as tests_router
from ariadne_api.routes.glossary import router as glossary_router

# Add router registrations (after existing routers)
app.include_router(tests_router, prefix=f"/api/{API_VERSION}/knowledge", tags=["tests"])
app.include_router(glossary_router, prefix=f"/api/{API_VERSION}/knowledge", tags=["glossary"])
```

**Effort:** Small (5 minutes)

**Risk:** None

## Technical Details

**Affected Files:**
- `ariadne_api/app.py` - Missing router registration
- `ariadne_api/routes/tests.py` - Orphaned (258 LOC)
- `ariadne_api/routes/glossary.py` - Orphaned (~200 LOC)

**Database Changes:** None

## Acceptance Criteria

- [ ] Tests router registered in `app.py`
- [ ] Glossary router registered in `app.py`
- [ ] `curl http://localhost:8000/api/v1/knowledge/tests/com.example.Service` returns 200 (not 404)
- [ ] `curl http://localhost:8000/api/v1/knowledge/glossary` returns 200 (not 404)

## Work Log

### 2026-02-02

**Issue discovered during:** `/workflows:review` based on brainstorm document

**Root cause:** Router registration step missed during feature integration

**Status:** Pending
