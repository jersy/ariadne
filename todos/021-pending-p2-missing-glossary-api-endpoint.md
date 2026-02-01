---
status: pending
priority: p2
issue_id: "021"
tags:
  - code-review
  - agent-native
  - api
  - architecture
dependencies: []
---

# Missing L1 Glossary API Endpoint

## Problem Statement

The plan defines L1 Business Layer with a **domain glossary** (Code Term → Business Meaning mappings) as a core feature, but there is **no HTTP API endpoint** to access this data. Agents cannot discover domain vocabulary, a critical differentiator of the system.

**Plan Definition (Phase 3.3):**
```yaml
# From plan: "L1 业务层"
└─ 领域词汇表 (Ubiquitous Language Glossary)
    - Code Term ↔ Business Meaning 映射
    - LLM 生成 Code Term → Business Meaning 映射
    - 支持同义词关联
```

**Storage Schema (exists):**
```sql
CREATE TABLE glossary (
    id INTEGER PRIMARY KEY,
    code_term TEXT NOT NULL,
    business_meaning TEXT NOT NULL,
    synonyms TEXT,
    source_fqn TEXT,
    vector_id TEXT
);
```

**API Endpoints (missing):**
```yaml
# Expected but NOT implemented:
GET /knowledge/glossary          # List all terms
GET /knowledge/glossary/{term}    # Get specific term
GET /knowledge/glossary/search    # Semantic search
```

## Why It Matters

1. **Agent Capability Gap**: Agents cannot access L1 domain knowledge
2. **Feature Incomplete**: Core L1 feature not exposed via API
3. **Value Proposition Lost**: Domain vocabulary is a key differentiator
4. **Documentation Mismatch**: Plan describes feature, API doesn't deliver

## Findings

### From Agent-Native Review:

> **Severity:** HIGH
>
> The L1 glossary is a core feature that gives agents "business understanding" of code. Without an API endpoint, agents cannot discover what "Sku", "Spu", or "OrderStatus" mean in the business context.

### From Implementation Review:

> **Observation:** The `glossary.py` module exists and generates glossary entries, but no API route exposes this data.

### Affected Components:

| Component | Status | Gap |
|-----------|--------|-----|
| `ariadne_analyzer/l1_business/glossary.py` | ✅ Implemented | No API route |
| `ariadne_api/routes/` | ❌ Missing | No glossary endpoints |
| `ariadne_api/schemas/` | ❌ Missing | No response models |

## Proposed Solutions

### Solution 1: Add Glossary API Endpoints (Recommended)

**Approach:** Implement standard CRUD endpoints for glossary access.

**Pros:**
- Complete L1 API coverage
- Enables agent access to domain vocabulary
- Follows existing API patterns

**Cons:**
- Additional code to maintain
- Need to design query filters

**Effort:** Low
**Risk:** Low

**Implementation:**
```python
# ariadne_api/routes/glossary.py
from fastapi import APIRouter, Query
from ariadne_api.schemas.glossary import (
    GlossaryTerm,
    GlossaryTermList,
    GlossarySearchResponse
)

router = APIRouter(prefix="/glossary", tags=["glossary"])

@router.get("", response_model=GlossaryTermList)
async def list_glossary_terms(
    prefix: str = Query(None, description="Filter by term prefix"),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0)
) -> GlossaryTermList:
    """List all domain glossary terms"""

    terms = store.get_glossary_terms(
        prefix=prefix,
        limit=limit,
        offset=offset
    )

    return GlossaryTermList(
        terms=terms,
        total=len(terms),
        limit=limit,
        offset=offset
    )

@router.get("/{code_term}", response_model=GlossaryTerm)
async def get_glossary_term(code_term: str) -> GlossaryTerm:
    """Get specific glossary term with business meaning"""

    term = store.get_glossary_term(code_term)
    if not term:
        raise HTTPException(status_code=404, detail=f"Term '{code_term}' not found")

    return term

@router.get("/search/{query}", response_model=GlossarySearchResponse)
async def search_glossary(
    query: str,
    num_results: int = Query(10, ge=1, le=100)
) -> GlossarySearchResponse:
    """Semantic search for glossary terms"""

    # Use vector store for semantic search
    results = vector_store.search_glossary(
        query=query,
        num_results=num_results
    )

    return GlossarySearchResponse(
        query=query,
        results=results
    )
```

**Response Models:**
```python
# ariadne_api/schemas/glossary.py
from pydantic import BaseModel
from typing import List, Optional

class GlossaryTerm(BaseModel):
    """Domain glossary term"""

    code_term: str
    business_meaning: str
    synonyms: List[str]
    source_fqn: Optional[str]
    examples: List[str]  # Generated from usage

    class Config:
        json_schema_extra = {
            "example": {
                "code_term": "Sku",
                "business_meaning": "Stock Keeping Unit - 唯一标识一个可售卖的商品规格",
                "synonyms": ["规格", "商品SKU"],
                "source_fqn": "com.example.product.Sku",
                "examples": ["iPhone 15 Pro 256GB Black", "Nike Air Max 90 Size 42"]
            }
        }

class GlossaryTermList(BaseModel):
    """List of glossary terms"""

    terms: List[GlossaryTerm]
    total: int
    limit: int
    offset: int

class GlossarySearchResponse(BaseModel):
    """Glossary search results"""

    query: str
    results: List[GlossaryTerm]
    num_results: int
```

### Solution 2: Include Glossary in Search Endpoint

**Approach:** Extend existing `/knowledge/search` to include glossary results.

**Pros:**
- No new endpoint needed
- Unified search experience

**Cons:**
- Glossary results mixed with symbol results
- Harder to filter for glossary-only
- Less discoverable

**Effort:** Low
**Risk:** Low

### Solution 3: Glossary as Part of Symbol Details

**Approach:** Include glossary terms in `/knowledge/symbol/{fqn}` response.

**Pros:**
- No new endpoint
- Contextual (glossary shown with related symbol)

**Cons:**
- Can't search glossary independently
- Need to know symbol FQN first

**Effort:** Low
**Risk:** Medium (reduces discoverability)

## Recommended Action

**Use Solution 1 (Dedicated Glossary Endpoints)**

This provides full agent access to L1 domain knowledge with proper discoverability and filtering.

## Technical Details

### API Endpoint Specifications:

```yaml
# GET /api/v1/knowledge/glossary
# List all domain glossary terms
Query Parameters:
  prefix: string?      # Filter by code_term prefix (e.g., "Order")
  limit: integer = 100 # Max results (1-1000)
  offset: integer = 0  # Pagination offset
Response:
  terms: GlossaryTerm[]
  total: integer
  limit: integer
  offset: integer

# GET /api/v1/knowledge/glossary/{code_term}
# Get specific glossary term
Path: code_term: string  # Exact code term
Response: GlossaryTerm

# GET /api/v1/knowledge/glossary/search/{query}
# Semantic search for glossary terms
Path: query: string  # Natural language query
Query Parameters:
  num_results: integer = 10
Response:
  query: string
  results: GlossaryTerm[]
  num_results: integer
```

### Database Queries:

```python
# ariadne_core/storage/sqlite_store.py
class SQLiteStore:
    def get_glossary_terms(
        self,
        prefix: Optional[str] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[GlossaryTermData]:
        """Get glossary terms with optional prefix filter"""

        query = "SELECT * FROM glossary"
        params = []

        if prefix:
            query += " WHERE code_term LIKE ?"
            params.append(f"{prefix}%")

        query += " ORDER BY code_term LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        cursor = self.conn.execute(query, params)
        return [GlossaryTermData(*row) for row in cursor.fetchall()]

    def get_glossary_term(self, code_term: str) -> Optional[GlossaryTermData]:
        """Get specific glossary term by code_term"""

        cursor = self.conn.execute(
            "SELECT * FROM glossary WHERE code_term = ?",
            (code_term,)
        )
        row = cursor.fetchone()

        if row:
            return GlossaryTermData(*row)
        return None
```

### Integration with Existing API:

```python
# ariadne_api/app.py
from ariadne_api.routes import (
    health, search, graph, impact,
    constraints, rebuild, jobs, check, symbol,
    glossary  # NEW
)

app = FastAPI(title="Ariadne Code Knowledge Graph")

# Include glossary router
app.include_router(glossary.router, prefix="/api/v1/knowledge")
```

### Files to Create:

1. **`ariadne_api/routes/glossary.py`** - NEW: Glossary endpoints
2. **`ariadne_api/schemas/glossary.py`** - NEW: Response models
3. **`tests/api/test_glossary.py`** - NEW: API tests

### Files to Modify:

1. **`ariadne_api/app.py`** - Include glossary router
2. **`ariadne_core/storage/sqlite_store.py`** - Add glossary query methods

## Acceptance Criteria

- [ ] `GET /knowledge/glossary` endpoint implemented
- [ ] `GET /knowledge/glossary/{code_term}` endpoint implemented
- [ ] `GET /knowledge/glossary/search/{query}` endpoint implemented
- [ ] Prefix filtering works
- [ ] Semantic search uses ChromaDB embeddings
- [ ] Response includes synonyms and examples
- [ ] OpenAPI docs auto-generated
- [ ] Test coverage for all endpoints
- [ ] API examples in documentation
- [ ] 404 handling for missing terms

## Work Log

| Date | Action | Result |
|------|--------|--------|
| 2026-02-02 | Plan review completed | Missing glossary API identified |
| | | |

## Resources

- **Affected Files**:
  - `ariadne_analyzer/l1_business/glossary.py` (exists)
  - `ariadne_api/routes/` (missing glossary.py)
- **Plan Reference**: Phase 3.3 - 领域词汇表
- **Related Issues**:
  - Agent-Native Review: Missing L1 capabilities
- **Documentation**:
  - Plan Section: "三层知识架构 - L1 业务与领域层"
