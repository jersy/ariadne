---
status: completed
priority: p1
issue_id: "016"
tags:
  - code-review
  - data-integrity
  - architecture
  - critical
dependencies: []
---

# Dual-Write Consistency Risk: SQLite-ChromaDB Synchronization

## Problem Statement

The system performs dual-writes to SQLite and ChromaDB without proper distributed transaction semantics. When writes to one store succeed and the other fails, the system enters an **inconsistent state**.

**Current Implementation Pattern:**
```python
# From sqlite_store.py:731-796
def create_summary_with_vector(self, summary, embedding, vector_store):
    with self.conn:
        # 1. Insert SQLite record
        cursor.execute(...)  # SUCCESS
        summary_id = cursor.fetchone()[0]

        # 2. Add to ChromaDB
        vector_store.add_summary(...)  # MAY FAIL

        # 3. Update SQLite with vector_id
        cursor.execute("UPDATE summaries SET vector_id = ?")
```

**Failure Scenario:**
1. SQLite insert succeeds
2. ChromaDB add fails (network, storage full, timeout)
3. SQLite record exists without vector_id
4. Future semantic searches miss this record
5. **Silent data corruption**

## Why It Matters

1. **Data Loss**: Summaries created but not searchable via L1 semantic layer
2. **User Confusion**: Incomplete search results, missing capabilities
3. **Silent Failure**: Current code logs error but continues, leaving inconsistent state
4. **No Recovery**: No mechanism to identify or fix orphaned records

## Findings

### From Architecture Strategist Review:

> **Severity:** CRITICAL
>
> The dual-write pattern lacks proper transactional semantics. The comment "ChromaDB failed but SQLite record was created - this is acceptable" is NOT acceptable for a knowledge graph where semantic search is a core feature.

### From Data Integrity Guardian Review:

> **Severity:** CRITICAL
>
> ChromaDB does NOT support ACID transactions. If ChromaDB write succeeds but SQLite write fails, we get orphaned vectors with no SQLite record. No rollback mechanism exists.

### Affected Code Locations:

| File | Lines | Issue |
|------|-------|-------|
| `ariadne_core/storage/sqlite_store.py` | 731-796 | Dual-write without rollback |
| `ariadne_core/storage/sqlite_store.py` | 786-789 | Acceptable error comment (incorrect) |

## Proposed Solutions

### Solution 1: Two-Phase Commit with Tracking Table (Recommended)

**Approach:** Create a `vector_sync_state` table to track pending operations and enable cleanup.

**Pros:**
- Atomic write tracking
- Recovery mechanism for failed operations
- Audit trail for all sync operations

**Cons:**
- Additional table and query overhead
- More complex code flow

**Effort:** Medium
**Risk:** Low

**Implementation:**
```python
def create_summary_with_vector_safe(self, summary, embedding, vector_store):
    """Atomic write to both SQLite and ChromaDB with rollback"""

    # 1. Create tracking record in SQLite FIRST
    pending_id = self.conn.execute(
        "INSERT INTO pending_vectors (temp_id, payload, created_at) VALUES (?, ?, ?)",
        (generate_uuid(), json.dumps(summary), datetime.now())
    ).lastrowid

    vector_id = None

    try:
        # 2. Insert SQLite record
        cursor.execute("INSERT INTO summaries (...) VALUES (...)")
        summary_id = cursor.lastrowid

        # 3. Write to ChromaDB
        vector_id = vector_store.add_summary(embedding, metadata)

        # 4. Link them
        cursor.execute("UPDATE summaries SET vector_id = ? WHERE id = ?", (vector_id, summary_id))

        # 5. Clean up tracking record
        cursor.execute("DELETE FROM pending_vectors WHERE id = ?", (pending_id,))

    except Exception as e:
        # Rollback SQLite
        self.conn.rollback()

        # Cleanup ChromaDB write
        if vector_id:
            try:
                vector_store.delete(vector_id)
            except:
                pass  # Best effort cleanup

        # Clean up tracking record
        cursor.execute("DELETE FROM pending_vectors WHERE id = ?", (pending_id,))

        raise DataIntegrityError(f"Failed to sync summary: {e}")
```

### Solution 2: Write-Ahead Log Pattern

**Approach:** Always write to a staging area first, then atomically promote to production.

**Pros:**
- Clean separation of staged vs. production data
- Easy to verify before promotion
- Can batch promote operations

**Cons:**
- Requires schema changes (staging tables)
- More complex query patterns

**Effort:** High
**Risk:** Medium

### Solution 3: Eventual Consistency with Reconciliation Job

**Approach:** Accept temporary inconsistency, run periodic job to fix discrepancies.

**Pros:**
- Simpler immediate path
- Resilient to transient failures

**Cons:**
- Temporary data loss acceptable?
- Additional background job complexity
- Harder to reason about system state

**Effort:** Medium
**Risk:** Medium (accepts inconsistency window)

## Recommended Action

**Use Solution 1 (Two-Phase Commit with Tracking Table)**

This is the only approach that provides strong consistency guarantees required for a knowledge graph system.

## Technical Details

### Schema Changes Required:

```sql
-- Track cross-store synchronization state
CREATE TABLE vector_sync_state (
    id INTEGER PRIMARY KEY,
    vector_id TEXT NOT NULL UNIQUE,           -- ChromaDB vector ID
    sqlite_table TEXT NOT NULL,                -- 'summaries', 'glossary', 'constraints'
    sqlite_record_id INTEGER NOT NULL,
    last_synced_at TIMESTAMP NOT NULL,
    sync_status TEXT NOT NULL,                 -- 'pending', 'synced', 'failed'
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_vector_sync_status ON vector_sync_state(sync_status);
CREATE INDEX idx_vector_sync_table ON vector_sync_state(sqlite_table, sqlite_record_id);

-- Orphaned vector tracking for cleanup
CREATE TABLE pending_vectors (
    id INTEGER PRIMARY KEY,
    temp_id TEXT NOT NULL UNIQUE,
    payload TEXT NOT NULL,                     -- JSON of original data
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### Files to Modify:

1. **`ariadne_core/storage/schema.py`** - Add new tables
2. **`ariadne_core/storage/sqlite_store.py`** - Implement two-phase commit
3. **`ariadne_core/storage/vector_store.py`** - Add cleanup methods
4. **`tests/unit/test_sqlite_store.py`** - Test failure scenarios

### Recovery Job:

```python
class VectorSyncRecovery:
    """Clean up failed sync operations"""

    def recover_orphans(self) -> Dict[str, int]:
        stats = {"cleaned": 0, "failed": 0}

        # Find pending records older than 1 hour
        pending = self.conn.execute("""
            SELECT id, temp_id, payload
            FROM pending_vectors
            WHERE created_at < datetime('now', '-1 hour')
        """).fetchall()

        for record in pending:
            try:
                # Attempt cleanup of any partial writes
                payload = json.loads(record['payload'])
                # Cleanup ChromaDB if vector was created
                # Cleanup SQLite if record was created
                stats["cleaned"] += 1
            except Exception as e:
                logger.error(f"Failed to recover pending {record['id']}: {e}")
                stats["failed"] += 1

        return stats
```

## Acceptance Criteria

- [ ] `vector_sync_state` table created with proper indexes
- [ ] All dual-write operations use two-phase commit pattern
- [ ] Orphaned record detection query implemented
- [ ] Recovery job tested with failure scenarios
- [ ] Test coverage for ChromaDB failure during write
- [ ] Test coverage for SQLite failure during write
- [ ] Test coverage for network timeout scenarios
- [ ] Manual reconciliation script provided
- [ ] Documentation updated with consistency guarantees

## Work Log

| Date | Action | Result |
|------|--------|--------|
| 2026-02-02 | Plan review completed | Critical dual-write issue identified |
| 2026-02-02 | Schema updated | Added vector_sync_state and pending_vectors tables |
| 2026-02-02 | Two-phase commit implemented | ChromaDB writes happen before SQLite |
| 2026-02-02 | Recovery methods added | detect_orphaned_records(), recover_orphaned_vectors() |
| 2026-02-02 | Tests added | 10 tests for dual-write consistency |
| 2026-02-02 | All tests passing | 34 total P1 consistency tests pass |
| 2026-02-02 | Committed | fix(storage): P1 dual-write consistency with two-phase commit |
| | | |

## Resources

- **Affected Files**:
  - `ariadne_core/storage/sqlite_store.py:731-796`
  - `ariadne_core/storage/schema.py`
- **Related Issues**:
  - Issue 007: Data Integrity SQLite-ChromaDB Synchronization (completed, partial fix)
- **Reference**:
  - Two-Phase Commit: https://en.wikipedia.org/wiki/Two-phase_commit_protocol
  - Distributed Transactions: https://www.databass.dev/distributed-transactions/
- **Documentation**:
  - Plan document Section: "存储 Schema 设计"
