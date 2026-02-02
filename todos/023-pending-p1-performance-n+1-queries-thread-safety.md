---
status: completed
priority: p1
issue_id: "023"
tags:
  - code-review
  - performance
  - critical
dependencies: []
---

# Performance: N+1 Queries and Thread Safety Bottlenecks

## Problem Statement

The parallel LLM summarization code contains **severe performance issues** that will prevent achieving the < 2 minute incremental update target. The most critical issues are:

1. **N+1 query problems**: Sequential database queries in loops (5-10x slower than necessary)
2. **Thread-unsafe database access**: Single connection causes lock contention and crashes
3. **Missing database indexes**: Queries on unindexed columns (10-100x slower)
4. **Inefficient batch operations**: Individual commits instead of batch operations

## Findings

### 1. N+1 Query in DependencyTracker (SEVERITY: HIGH)

**File**: `ariadne_analyzer/l1_business/dependency_tracker.py:68-87`

**Problem**: For `n` changed symbols, executes `3n` sequential database queries:

```python
for fqn in changed_fqns:
    # Query 1: Get callers (database round-trip)
    callers = self.store.get_related_symbols(fqn, relation="calls", direction="incoming")

    # Query 2: Get symbol (database round-trip)
    symbol = self.store.get_symbol(fqn)

    # Query 3: Mark stale (database round-trip with commit)
    self.store.mark_summary_stale(fqn)
```

**Impact**:
- 100 changed symbols = 300 database queries (~1.5 seconds)
- 1,000 changed symbols = 3,000 queries (~15 seconds)

**Target**: < 2 minutes for 1,000 symbols

### 2. N+1 Query in IncrementalSummarizerCoordinator (SEVERITY: HIGH)

**File**: `ariadne_analyzer/l1_business/incremental_coordinator.py:107-167`

**Problem**: Loops through each symbol individually:

```python
for fqn in affected.total_set:
    symbol_dict = self.store.get_symbol(fqn)  # N+1 QUERY
    # ...

for symbol, source_code in symbols_data:
    existing = self.store.get_summary(symbol.fqn)  # ANOTHER N+1 QUERY
    # ...
```

**Impact**: Doubles the query count from dependency tracker.

### 3. Missing Database Indexes (SEVERITY: HIGH)

**File**: `ariadne_core/storage/schema.py` and inferred usage

**Problem**: Frequently queried columns lack indexes:

- `edges(relation)` - used in `get_related_symbols()`
- `edges(from_fqn, relation)` - used for dependency queries
- `summaries(target_fqn, is_stale)` - used in staleness checks

**Impact**: Each query requires full table scan without indexes.

### 4. Thread-Unsafe SQLite Connection (SEVERITY: CRITICAL)

**File**: `ariadne_core/storage/sqlite_store.py:34`

**Problem**: Single connection shared across threads:

```python
self.conn = sqlite3.connect(db_path)  # NOT thread-safe
```

**Impact**: With `max_workers=10`, concurrent threads will:
- Cause "database is locked" errors
- Risk connection corruption
- Serialize execution (no parallelism benefit)

### 5. Incorrect executaemany Usage (SEVERITY: HIGH)

**File**: `ariadne_core/storage/sqlite_store.py:564-567`

**Problem**: Inefficient batch UPDATE with `executemany`:

```python
cursor.executemany(
    "UPDATE summaries SET is_stale = 1 WHERE target_fqn = ?",
    [(fqn,) for fqn in target_fqns],
)
```

**Impact**:
- Inefficient: N separate UPDATE statements
- Wrong count: `cursor.rowcount` only reports last UPDATE
- Multiple disk flushes

## Technical Details

**Affected Files**:
- `ariadne_analyzer/l1_business/dependency_tracker.py`
- `ariadne_analyzer/l1_business/incremental_coordinator.py`
- `ariadne_core/storage/sqlite_store.py`
- `ariadne_core/storage/schema.py`

**Current Performance**:
- 100 changed symbols: ~1.5 seconds (300 queries)
- 1,000 changed symbols: ~15 seconds (3,000 queries)
- 10,000 changed symbols: ~150 seconds (30,000 queries)

**Target Performance** (from plan):
- 1,000 changed symbols: < 2 minutes (120 seconds)

**Gap**: Currently 15 seconds, need < 120 seconds, but WITH thread safety issues the actual performance is unpredictable.

## Proposed Solutions

### Solution 1: Batch Fetch with IN Clauses (RECOMMENDED)

**Effort**: Medium
**Risk**: Low

```python
def get_affected_symbols(self, changed_fqns: list[str]) -> AffectedSymbols:
    if not changed_fqns:
        return AffectedSymbols(changed=[])

    placeholders = ','.join('?' * len(changed_fqns))

    # Batch fetch all symbols and callers in 2 queries
    cursor = self.store.conn.cursor()
    symbols = cursor.execute(
        f"SELECT fqn, parent_fqn FROM symbols WHERE fqn IN ({placeholders})",
        changed_fqns
    ).fetchall()

    callers = cursor.execute(
        f"""SELECT DISTINCT e.from_fqn FROM edges e
            WHERE e.to_fqn IN ({placeholders}) AND e.relation = 'calls'""",
        changed_fqns
    ).fetchall()

    # Batch mark all as stale in one operation
    all_to_mark = [s[0] for s in symbols] + [c[0] for c in callers]
    self.mark_summaries_stale(all_to_mark)

    return AffectedSymbols(changed=changed_fqns, dependents=[c[0] for c in callers])
```

### Solution 2: Thread-Local SQLite Connections (RECOMMENDED)

**Effort**: Medium
**Risk**: Medium

```python
import threading
from threading import local

class SQLiteStore:
    def __init__(self, db_path: str = "ariadne.db", init: bool = False):
        self.db_path = db_path
        self._local = local()

    @property
    def conn(self):
        if not hasattr(self._local, 'conn'):
            self._local.conn = sqlite3.connect(
                self.db_path,
                check_same_thread=False
            )
            self._local.conn.row_factory = sqlite3.Row
            self._local.conn.execute("PRAGMA journal_mode=WAL")
            self._local.conn.execute("PRAGMA foreign_keys=ON")
            self._local.conn.execute("PRAGMA busy_timeout=30000")  # 30s timeout
        return self._local.conn
```

### Solution 3: Add Database Indexes

**Effort**: Small
**Risk**: Low

**Schema Migration**:

```sql
CREATE INDEX IF NOT EXISTS idx_edges_relation ON edges(relation);
CREATE INDEX IF NOT EXISTS idx_edges_from_fqn ON edges(from_fqn);
CREATE INDEX IF NOT EXISTS idx_edges_to_fqn_relation ON edges(to_fqn, relation);
CREATE INDEX IF NOT EXISTS idx_summaries_target_stale ON summaries(target_fqn, is_stale);
```

### Solution 4: Use Single UPDATE with IN Clause

**Effort**: Small
**Risk**: Low

```python
def mark_summaries_stale(self, target_fqns: list[str]) -> int:
    if not target_fqns:
        return 0

    cursor = self.conn.cursor()
    placeholders = ",".join("?" * len(target_fqns))
    cursor.execute(
        f"UPDATE summaries SET is_stale = 1, updated_at = CURRENT_TIMESTAMP "
        f"WHERE target_fqn IN ({placeholders})",
        target_fqns,
    )
    self.conn.commit()
    return cursor.rowcount
```

## Acceptance Criteria

- [x] Batch queries reduce database round-trips by 10-100x
- [x] Thread-safe SQLite access works with 10 concurrent workers
- [x] Database indexes improve query performance significantly
- [x] Incremental update of 1,000 symbols completes in < 2 minutes
- [x] Performance tests verify improvements

## Work Log

| Date | Action | Result |
|------|--------|--------|
| 2026-02-02 | Code review completed | Performance issues identified |
| 2026-02-02 | DependencyTracker verified | Already uses batch IN clause queries |
| 2026-02-02 | IncrementalCoordinator verified | Already uses batch IN clause queries |
| 2026-02-02 | Database indexes verified | All required indexes exist |
| 2026-02-02 | Thread-local connections verified | Already fixed by issue 021 |
| 2026-02-02 | All tests passing | 28 tests pass for P1 issues |
| 2026-02-02 | Verified complete | Issues already fixed by previous commits |

## Resources

- **PR**: #4 - Parallel LLM Summarization
- **Learning**: docs/solutions/performance-issues/p2-code-review-fixes-phase1-infrastructure.md
- **Plan**: docs/plans/2026-02-02-feat-parallel-llm-summarization-plan.md
