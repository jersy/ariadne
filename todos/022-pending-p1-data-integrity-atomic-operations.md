---
status: completed
priority: p1
issue_id: "022"
tags:
  - code-review
  - data-integrity
  - critical
dependencies: []
---

# Data Integrity: Non-Atomic Operations and Orphaned Vectors

## Problem Statement

The parallel LLM summarization code contains **critical data integrity issues** related to atomic operations and orphaned ChromaDB vector references. These issues cause:

1. **Inconsistent stale marking**: Changed symbols and dependents marked separately, allowing partial updates
2. **Orphaned ChromaDB vectors**: SQLite-ChromaDB operations not atomic, leaving orphaned references
3. **Incorrect rowcount reporting**: Batch operations report wrong counts
4. **Race condition in staleness**: Stale flag checked too early, allowing concurrent updates to be missed

## Findings

### 1. Non-Atomic Stale Marking in DependencyTracker

**File**: `ariadne_analyzer/l1_business/dependency_tracker.py:82-87`

**Problem**: `mark_summary_stale()` and `mark_summaries_stale()` are separate transactions:

```python
for fqn in changed_fqns:
    # ...
    self.store.mark_summary_stale(fqn)  # Transaction 1 per changed symbol

if dependents:
    self.store.mark_summaries_stale(list(dependents))  # Transaction 2 for dependents
```

**Impact**: If process crashes between marking changed symbols and marking dependents:
- Changed symbols marked stale
- Dependent symbols NOT marked stale
- Future incremental updates will miss dependent symbols

### 2. Race Condition: Staleness Check Too Early

**File**: `ariadne_analyzer/l1_business/incremental_coordinator.py:163, 192`

**Problem**: Stale flag checked BEFORE summarization (line 163), but update happens AFTER (line 192):

```python
# Line 163: Check if stale (early)
if existing and not existing.get("is_stale"):
    skipped_count += 1
    continue

# ... time passes during summarization ...

# Line 192: Set not stale (without re-checking)
is_stale=False,  # OVERWRITES concurrent staleness requests
```

**Impact**: If another process marks a summary stale during summarization, the new staleness is lost.

### 3. Incorrect executaech Usage in Batch Stale Marking

**File**: `ariadne_core/storage/sqlite_store.py:564-567`

**Problem**: `executemany` with individual UPDATE statements:

```python
def mark_summaries_stale(self, target_fqns: list[str]) -> int:
    cursor.executemany(
        "UPDATE summaries SET is_stale = 1 WHERE target_fqn = ?",
        [(fqn,) for fqn in target_fqns],
    )
    self.conn.commit()
    return cursor.rowcount  # WRONG: only counts last UPDATE
```

**Impact**: Returns count of last UPDATE only, not total count. Very inefficient.

### 4. Orphaned ChromaDB Vectors on Failure

**File**: `ariadne_core/storage/sqlite_store.py:854-872`

**Problem**: ChromaDB add operation not rolled back on SQLite failure:

```python
cursor.execute(...insert into summaries...)
summary_id = cursor.fetchone()[0]

# ChromaDB add (CAN FAIL)
if embedding and vector_store:
    vector_store.add_summary(...)  # If this fails...
    cursor.execute("UPDATE summaries SET vector_id = ?...")  # This still runs

# Result: Summary exists with vector_id=NULL, ChromaDB has orphan vector
```

**Impact**: Vectors in ChromaDB that don't match SQLite records, causing:
- Wasted storage space
- Inaccurate vector search results
- Cleanup difficult

## Technical Details

**Affected Files**:
- `ariadne_analyzer/l1_business/dependency_tracker.py`
- `ariadne_analyzer/l1_business/incremental_coordinator.py`
- `ariadne_core/storage/sqlite_store.py`

**Database Schema**:
- `summaries` table with `is_stale` flag
- `edges` table for CALLS relationships
- ChromaDB vector storage

## Proposed Solutions

### Solution 1: Atomic Stale Marking (RECOMMENDED)

**Effort**: Small
**Risk**: Low

```python
def get_affected_symbols(self, changed_fqns: list[str]) -> AffectedSymbols:
    affected = set(changed_fqns)
    dependents: set[str] = set()

    # Collect all affected symbols first
    for fqn in changed_fqns:
        callers = self.store.get_related_symbols(fqn, relation="calls", direction="incoming")
        dependents.update(c["fqn"] for c in callers)
        symbol = self.store.get_symbol(fqn)
        if symbol and symbol.get("parent_fqn"):
            affected.add(symbol["parent_fqn"])
            dependents.add(symbol["parent_fqn"])

    # ATOMIC: Mark all as stale in one transaction
    all_to_mark = list(affected | dependents)
    if all_to_mark:
        self.store.mark_summaries_stale(all_to_mark)

    return AffectedSymbols(changed=changed_fqns, dependents=list(dependents))
```

### Solution 2: Single UPDATE with IN Clause

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
    return cursor.rowcount  # Now accurate
```

### Solution 3: Re-check Staleness Before Update

**Effort**: Small
**Risk**: Low

```python
# In IncrementalSummarizerCoordinator
for fqn, summary_text in summaries.items():
    # Re-check if still needs update (concurrent modification detection)
    existing = self.store.get_summary(fqn)
    if existing and not existing.get("is_stale"):
        logger.info(f"Skipping {fqn} - no longer stale (concurrent update)")
        continue

    summary = SummaryData(
        target_fqn=fqn,
        level=level,
        summary=summary_text,
        is_stale=False,
    )
    self.store.create_summary(summary)
```

### Solution 4: Rollback SQLite on ChromaDB Failure

**Effort**: Medium
**Risk**: Medium

```python
def create_summary_with_vector(self, summary, embedding=None, vector_store=None):
    cursor = self.conn.cursor()
    try:
        with self.conn:
            # Insert SQLite record
            cursor.execute(...)
            summary_id = cursor.fetchone()[0]

            # ChromaDB add (must succeed or entire transaction rolls back)
            if embedding and vector_store:
                try:
                    vector_store.add_summary(...)
                    cursor.execute("UPDATE summaries SET vector_id = ?...")
                except Exception as e:
                    logger.error(f"ChromaDB operation failed: {e}")
                    # Rollback the entire transaction
                    raise  # Re-raise so caller knows it failed
```

## Acceptance Criteria

- [x] All stale marking operations are atomic
- [x] ChromaDB failures roll back SQLite changes
- [x] staleness re-checked before final update
- [x] Batch operations use single UPDATE with IN clause
- [x] Tests verify concurrent update scenarios

## Work Log

| Date | Action | Result |
|------|--------|--------|
| 2026-02-02 | Code review completed | Data integrity issues identified |
| 2026-02-02 | DependencyTracker verified | Already uses atomic batch stale marking |
| 2026-02-02 | mark_summaries_stale verified | Already uses single UPDATE with IN clause |
| 2026-02-02 | Staleness re-check verified | Already has concurrent modification detection |
| 2026-02-02 | Orphaned vectors verified | Already fixed by issue 016 two-phase commit |
| 2026-02-02 | All tests passing | 28 tests pass for P1 issues |
| 2026-02-02 | Verified complete | Issues already fixed by previous commits |

## Resources

- **PR**: #4 - Parallel LLM Summarization
- **Related**: docs/solutions/data-integrity/atomic-sqlite-chromadb-operations.md
- **Learning**: Transaction safety patterns
