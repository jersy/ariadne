---
status: pending
priority: p2
issue_id: "019"
tags:
  - code-review
  - performance
  - database
  - architecture
dependencies: []
---

# N+1 Query Pattern in Impact Analysis

## Problem Statement

The impact analysis endpoint performs **N+1 database queries** when tracing reverse call chains. For a low-level utility method called by 500+ other methods, this means 500+ database round-trips, violating the < 500ms performance target.

**Current Implementation Pattern:**
```python
# From ariadne_analyzer/l3_implementation/impact_analyzer.py
def analyze_impact(self, target_fqn: str) -> ImpactResult:
    # 1 query to get the target
    target = self.store.get_symbol(target_fqn)

    # N queries to get all callers
    callers = self.store.get_callers(target_fqn)  # Returns list
    for caller in callers:
        # Another query for EACH caller's callers
        caller.callers = self.store.get_callers(caller.fqn)

    # Exponential query explosion: 1 + N + N^2 + ...
```

**Performance Impact:**
- Small project (100 callers): ~100 queries, ~200ms
- Medium project (500 callers): ~500 queries, ~1-2 seconds
- Large project (2000 callers): ~2000 queries, ~5-10 seconds

**Target:** < 500ms for ALL project sizes

## Why It Matters

1. **Performance Degradation**: Query count grows O(n) with call depth
2. **Timeout Risk**: Deep call hierarchies cause API timeouts
3. **Resource Waste**: Each query has overhead (connection, parsing, results)
4. **Scalability Block**: Cannot handle large enterprise codebases
5. **User Experience**: Slow impact analysis discourages use

## Findings

### From Performance Oracle Review:

> **Severity:** HIGH
>
> The N+1 query pattern in impact analysis is a critical performance bottleneck. The current schema design makes single-query recursive traversal difficult but not impossible.

### From Architecture Strategist Review:

> **Severity:** MEDIUM
>
> Impact analyzer directly accesses database internals via store.conn.cursor() instead of using repository methods. This encapsulates SQL knowledge in the analyzer layer.

### From Implementation Review:

> **Observation:** The impact analyzer uses iterative calls instead of recursive CTE.

### Affected Code Locations:

| File | Lines | Issue |
|------|-------|-------|
| `ariadne_analyzer/l3_implementation/impact_analyzer.py` | All | N+1 query pattern |
| `ariadne_core/storage/sqlite_store.py` | - | No recursive query method |

## Proposed Solutions

### Solution 1: Recursive CTE with Single Query (Recommended)

**Approach:** Use SQLite's recursive CTE to fetch entire call tree in one query.

**Pros:**
- Single database round-trip
- Constant time regardless of tree size
- Leverages database query planner
- Eliminates Python loop overhead

**Cons:**
- Need to implement recursive SQL
- Depth limit still applies (SQLite CTE limitation)

**Effort:** Medium
**Risk:** Low

**Implementation:**
```python
class ImpactAnalyzer:
    def analyze_impact_single_query(self, target_fqn: str, max_depth: int = 10) -> ImpactResult:
        """Analyze impact using single recursive CTE query"""

        query = """
        WITH RECURSIVE caller_tree AS (
            -- Base case: direct callers
            SELECT
                0 as depth,
                e.from_fqn,
                s.kind as caller_kind,
                s.name as caller_name,
                e.relation
            FROM edges e
            JOIN symbols s ON e.from_fqn = s.fqn
            WHERE e.to_fqn = ?

            UNION ALL

            -- Recursive case: indirect callers
            SELECT
                ct.depth + 1,
                e.from_fqn,
                s.kind,
                s.name,
                e.relation
            FROM edges e
            JOIN symbols s ON e.from_fqn = s.fqn
            JOIN caller_tree ct ON e.to_fqn = ct.from_fqn
            WHERE ct.depth < ?
        )
        SELECT DISTINCT
            depth,
            from_fqn,
            caller_kind,
            caller_name,
            relation
        FROM caller_tree
        ORDER BY depth, from_fqn
        """

        rows = self.store.conn.execute(query, (target_fqn, max_depth)).fetchall()

        # Build result tree
        return self._build_impact_tree(rows)
```

### Solution 2: Batch Query with Pre-fetching

**Approach:** Fetch all edges once, build tree in memory.

**Pros:**
- Still single query for data
- More flexible tree building in Python
- Can handle complex tree transformations

**Cons:**
- Higher memory usage for large graphs
- More Python code to maintain
- Still need database round-trip

**Effort:** Medium
**Risk:** Low

### Solution 3: Materialized Path with Pre-computed Index

**Approach:** Pre-compute call paths during build, query index directly.

**Pros:**
- Instant impact analysis (single SELECT)
- No recursive queries needed
- Can cache results

**Cons:**
- Requires schema change
- Additional storage overhead
- Index must be updated on changes

**Effort:** High
**Risk:** Medium

## Recommended Action

**Use Solution 1 (Recursive CTE) for immediate fix, consider Solution 3 for optimization**

The recursive CTE is a straightforward SQL optimization that provides immediate performance benefits without schema changes.

## Technical Details

### Performance Comparison:

| Approach | Queries | Time (100 callers) | Time (500 callers) | Time (2000 callers) |
|----------|---------|-------------------|-------------------|--------------------|
| Current (N+1) | 100+ | ~200ms | ~1-2s | ~5-10s |
| Recursive CTE | 1 | ~20ms | ~50ms | ~200ms |
| Materialized Path | 1 | ~5ms | ~10ms | ~50ms |

### Query Optimization:

```sql
-- Optimized recursive CTE with depth limiting and performance hints
WITH RECURSIVE caller_tree AS (
    -- Base case: direct callers of target
    SELECT
        0 as depth,
        e.from_fqn,
        s.kind as caller_kind,
        s.name as caller_name,
        s.file_path,
        e.relation,
        e.metadata
    FROM edges e
    JOIN symbols s ON e.from_fqn = s.fqn
    WHERE e.to_fqn = ?1

    UNION ALL

    -- Recursive case: walk up the call tree
    SELECT
        ct.depth + 1,
        e.from_fqn,
        s.kind,
        s.name,
        s.file_path,
        e.relation,
        e.metadata
    FROM edges e
    JOIN symbols s ON e.from_fqn = s.fqn
    JOIN caller_tree ct ON e.to_fqn = ct.from_fqn
    WHERE ct.depth < ?2  -- Prevent infinite recursion
)
SELECT DISTINCT
    depth,
    from_fqn,
    caller_kind,
    caller_name,
    file_path,
    relation
FROM caller_tree
-- Optional: Filter by specific layers or kinds
-- WHERE caller_kind IN ('class', 'method')
ORDER BY depth, from_fqn
LIMIT ?3;  -- Prevent runaway results
```

### API Response Structure:

```python
# ariadne_api/schemas/impact.py
class ImpactAnalysisResponse(BaseModel):
    """Optimized impact analysis response"""

    target_fqn: str
    total_affected: int

    # Grouped by depth for efficient rendering
    affected_by_depth: Dict[int, List[AffectedSymbol]]

    # Entry points (depth 0 = direct callers that are entry points)
    affected_entry_points: List[EntryPointImpact]

    # Test coverage
    affected_tests: List[str]

    # Metadata
    max_depth_reached: int
    query_time_ms: float
```

### Files to Modify:

1. **`ariadne_analyzer/l3_implementation/impact_analyzer.py`** - Rewrite with recursive CTE
2. **`ariadne_core/storage/sqlite_store.py`** - Add `get_call_tree_recursive()` method
3. **`ariadne_api/routes/impact.py`** - Update to use optimized analyzer
4. **`tests/integration/test_impact_analysis.py`** - Add performance benchmarks

### Benchmark Test:

```python
# tests/benchmarks/test_impact_performance.py
import pytest

@pytest.mark.benchmark(group="impact-analysis")
def test_impact_analysis_small_project(benchmark, store):
    """Should complete in < 50ms for 100 callers"""

    def analyze():
        impact = ImpactAnalyzer(store)
        return impact.analyze_impact("com.example.Utility.method")

    result = benchmark(analyze)
    assert result.query_time_ms < 50

@pytest.mark.benchmark(group="impact-analysis")
def test_impact_analysis_large_project(benchmark, store):
    """Should complete in < 200ms for 1000 callers"""

    # Mock large call graph
    _create_large_call_graph(store, callers=1000)

    def analyze():
        impact = ImpactAnalyzer(store)
        return impact.analyze_impact("com.example.Utility.method")

    result = benchmark(analyze)
    assert result.query_time_ms < 200
```

## Acceptance Criteria

- [ ] Recursive CTE query implemented
- [ ] Impact analyzer uses single-query approach
- [ ] Depth limiting enforced (max_depth parameter)
- [ ] Performance benchmark: < 50ms for 100 callers
- [ ] Performance benchmark: < 200ms for 1000 callers
- [ ] API response includes query_time_ms metadata
- [ ] Test coverage for deep call hierarchies
- [ ] Test coverage for circular dependencies
- [ ] Documentation updated with performance characteristics

## Work Log

| Date | Action | Result |
|------|--------|--------|
| 2026-02-02 | Plan review completed | N+1 query pattern identified |
| | | |

## Resources

- **Affected Files**:
  - `ariadne_analyzer/l3_implementation/impact_analyzer.py`
  - `ariadne_api/routes/impact.py`
- **Plan Reference**: Phase 4.2 - 影响范围分析
- **Related Issues**:
  - Performance NFR: < 500ms graph query target
- **SQLite Documentation**:
  - Recursive CTEs: https://www.sqlite.org/lang_with.html
- **Documentation**:
  - Plan Section: "验收场景 - Scenario 2: 防遗漏"
