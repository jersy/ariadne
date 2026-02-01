---
title: "P1 #025 - Two-Phase Commit Rollback Tracking Failure"
category: database-issues
severity: P1
date_created: 2026-02-02
related_issues:
  - "025-pending-p1-two-phase-commit-rollback-tracking-failure.md"
  - "017-pending-p1-rebuild-operation-data-loss-risk.md"
tags:
  - two-phase-commit
  - transaction-rollback
  - orphaned-vectors
  - chromadb
  - sqlite
---

## Problem

When SQLite transaction rollback occurs during the two-phase commit process for dual-write operations (SQLite + ChromaDB), orphaned ChromaDB vectors cannot be tracked for cleanup because the tracking INSERT statement was inside the rolled-back transaction.

### Symptom

**File**: `ariadne_core/storage/sqlite_store.py`

When `create_summary_with_vector()` fails during the SQLite write phase after successfully writing to ChromaDB:

1. ChromaDB write succeeds (vector stored)
2. SQLite write fails (exception thrown)
3. Rollback of ChromaDB is attempted
4. If rollback also fails, orphan tracking INSERT is attempted
5. **BUG**: The tracking INSERT is inside the same transaction that rolled back
6. **RESULT**: Orphaned vector is never tracked for cleanup

### Original Buggy Code

```python
# Lines 1118-1141 (simplified)
except Exception as e:
    logger.error(f"SQLite write failed, rolling back ChromaDB: {e}")

    if vector_id and vector_store is not None:
        try:
            vector_store.delete_summaries([vector_id])
        except Exception as rollback_error:
            # BUGGY: This INSERT is inside the rolled-back transaction context
            cursor.execute(
                """INSERT INTO pending_vectors (...) VALUES (...)"""
            )
            # Never gets committed because transaction will be rolled back
            raise
    raise  # Re-raises original exception, causing implicit rollback
```

### Impact

- Orphaned vectors accumulate in ChromaDB
- No mechanism to track and clean them up
- Storage bloat and potential inconsistency between stores

---

## Root Cause Analysis

The issue stems from a fundamental misunderstanding of transaction scope:

1. **Transaction Context**: The `with self.conn:` context manager (lines 1096-1141) wraps the entire operation
2. **Implicit Rollback**: When an exception is raised within the context, Python's `__exit__` automatically rolls back
3. **Tracking Inside Transaction**: The orphan tracking INSERT happens before the exception is re-raised
4. **Tracking Lost**: When rollback occurs, the tracking INSERT is also rolled back

### Why This Was Missed

- The tracking was added as a "safety measure" without considering transaction boundaries
- Tests typically don't simulate double-failure scenarios (both SQLite and ChromaDB failing)
- No integration tests for rollback behavior

---

## Solution

The fix creates `_track_orphaned_vector_separate_txn()`, which uses a **separate database connection** outside the rollback context to ensure tracking persists.

### Implementation

**File**: `ariadne_core/storage/sqlite_store.py` (lines 1389-1456)

```python
def _track_orphaned_vector_separate_txn(
    self,
    vector_id: str,
    target_fqn: str,
    rollback_error: Exception,
    original_error: Exception,
) -> None:
    """Track an orphaned vector in a separate transaction (outside rollback context).

    This is called when the two-phase commit fails and we need to track
    an orphaned ChromaDB vector for later cleanup. Using a separate
    database connection ensures the tracking survives the main transaction rollback.

    Args:
        vector_id: The vector_id that was written to ChromaDB
        target_fqn: The target symbol FQN
        rollback_error: The error from ChromaDB rollback attempt
        original_error: The original SQLite write error
    """
    import sqlite3
    from datetime import datetime

    try:
        # Create a new database connection (outside the rolled-back transaction)
        tracking_conn = sqlite3.connect(self.db_path, timeout=30.0)
        try:
            tracking_conn.execute("BEGIN IMMEDIATE")

            # Insert tracking record with detailed error information
            tracking_conn.execute(
                """INSERT INTO pending_vectors (temp_id, operation_type, sqlite_table, payload, vector_id, error_message, created_at)
                   VALUES (?, 'delete', 'summaries', ?, ?, ?)
                """,
                (
                    vector_id,
                    json.dumps({
                        "fqn": target_fqn,
                        "original_error": str(original_error),
                        "rollback_error": str(rollback_error),
                        "tracking_time": datetime.utcnow().isoformat(),
                    }),
                    vector_id,
                    f"Orphan after rollback: {rollback_error}",
                ),
            )
            tracking_conn.commit()

            logger.info(
                f"Tracked orphaned vector {vector_id} for later cleanup",
                extra={"event": "orphan_tracked", "vector_id": vector_id, "target_fqn": target_fqn}
            )

        finally:
            tracking_conn.close()

    except Exception as tracking_error:
        # This is critical - if we can't track, we need to log at CRITICAL level
        logger.critical(
            f"CRITICAL: Failed to track orphaned vector {vector_id}. "
            f"Manual cleanup required. Original error: {original_error}, "
            f"Rollback error: {rollback_error}, Tracking error: {tracking_error}",
            extra={
                "event": "orphan_tracking_failed",
                "vector_id": vector_id,
                "target_fqn": target_fqn,
            }
        )
```

### Usage in Exception Handler

```python
# In create_summary_with_vector() exception handler (line 1139)
except Exception as rollback_error:
    logger.critical(
        f"Failed to rollback ChromaDB vector {vector_id}: {rollback_error}",
        extra={"event": "chroma_rollback_failed", "vector_id": vector_id}
    )
    # Track orphaned vector in SEPARATE transaction (outside rollback context)
    self._track_orphaned_vector_separate_txn(vector_id, summary.target_fqn, rollback_error, e)
```

---

## Key Insights

### 1. Separate Connection Pattern

When you need to persist data that must survive a transaction rollback:

```python
# DON'T: Write inside the transaction that will roll back
try:
    with connection:
        # ... work ...
        raise Exception("Fail")
except Exception:
    connection.execute("INSERT INTO audit_log ...")  # Lost!
    raise

# DO: Use a separate connection
try:
    with connection:
        # ... work ...
        raise Exception("Fail")
except Exception:
    separate_conn = sqlite3.connect(db_path)
    separate_conn.execute("INSERT INTO audit_log ...")  # Survives!
    separate_conn.commit()
    separate_conn.close()
    raise
```

### 2. Immediate Transaction Mode

Using `BEGIN IMMEDIATE` ensures the tracking transaction gets a write lock immediately:

```python
tracking_conn.execute("BEGIN IMMEDIATE")
```

This prevents deadlocks if the main transaction is holding locks.

### 3. Comprehensive Error Context

The tracking record includes ALL errors for forensic analysis:

```python
json.dumps({
    "fqn": target_fqn,
    "original_error": str(original_error),
    "rollback_error": str(rollback_error),
    "tracking_time": datetime.utcnow().isoformat(),
})
```

---

## Prevention Strategies

### 1. Code Review Checklist

- [ ] Any INSERT that must survive rollback uses a separate connection
- [ ] Exception handlers document transaction scope
- [ ] Dual-write operations have rollback tracking
- [ ] Orphan cleanup is tested

### 2. Testing Guidelines

```python
# Test double-failure scenario
def test_two_phase_commit_double_failure():
    """Test that orphans are tracked when both writes fail."""
    with mock.patch.object(vector_store, 'add_summary') as mock_add:
        with mock.patch.object(store.conn, 'execute') as mock_exec:
            mock_add.side_effect = Exception("ChromaDB write succeeds")  # Actually succeeds
            mock_exec.side_effect = Exception("SQLite write fails")

            # First call succeeds, second fails
            call_count = [0]
            def side_effect(*args, **kwargs):
                call_count[0] += 1
                if call_count[0] == 1:
                    return None  # add_summary succeeds
                else:
                    raise Exception("SQLite write fails")

            mock_add.side_effect = side_effect
            mock_exec.side_effect = side_effect

            with pytest.raises(Exception):
                store.create_summary_with_vector(summary, embedding, vector_store)

            # Verify orphan was tracked in separate transaction
    # Check pending_vectors table for tracking record
```

### 3. Monitoring

Add metrics for orphan tracking:

```python
logger.info(
    "Tracked orphaned vector",
    extra={
        "event": "orphan_tracked",
        "vector_id": vector_id,
        "target_fqn": target_fqn,
        "metric": "orphaned_vector.tracked"
    }
)
```

---

## Related Documentation

- **Issue Analysis**: `docs/issues/025-pending-p1-two-phase-commit-rollback-tracking-failure.md`
- **Dual-Write Pattern**: `docs/solutions/database-issues/two-phase-commit-pattern.md`
- **Vector Sync Recovery**: Method `recover_orphaned_vectors()` in `sqlite_store.py`
- **Testing**: `tests/integration/test_two_phase_commit.py`

---

## Verification

After implementing this fix, verify:

1. **Manual Test**: Trigger a double-failure and check `pending_vectors` table
2. **Integration Test**: Run dual-write failure scenarios
3. **Recovery Test**: Run `recover_orphaned_vectors()` and verify cleanup
4. **Log Verification**: Check for "orphan_tracked" events

```sql
-- Verify tracking record exists
SELECT * FROM pending_vectors WHERE vector_id = ?;
```
