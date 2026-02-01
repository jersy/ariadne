---
status: completed
priority: p1
issue_id: "025"
tags:
  - code-review
  - data-integrity
  - critical
dependencies: []
---

# Two-Phase Commit Rollback Tracking Failure

## Problem Statement

The two-phase commit implementation in `sqlite_store.py` has a critical flaw where tracking of orphaned ChromaDB vectors can be silently lost during transaction rollback, leaving inconsistent state with no recovery path.

**Code Location:** `ariadne_core/storage/sqlite_store.py:1012-1044`

## Why It Matters

1. **Data Corruption**: Orphaned vectors in ChromaDB without tracking records cannot be cleaned up
2. **Silent Failures**: The `pass` statement on line 1042 silently swallows tracking errors
3. **No Recovery**: Once tracking is lost, orphaned vectors accumulate indefinitely
4. **Storage Bloat**: Untracked vectors waste ChromaDB storage and memory

## Findings

### From Data Integrity Review:

> **Severity:** CRITICAL
>
> The rollback logic in `_atomic_swap_databases()` can leave orphaned vectors completely untracked. When SQLite write fails after ChromaDB succeeds, the rollback attempts to delete the vector and track the failure. But if that tracking insert also fails (because transaction is already rolled back), the orphaned vector is lost.

### Root Cause Analysis:

```python
# ariadne_core/storage/sqlite_store.py:1012-1044
except Exception as e:
    # SQLite write failed - need to rollback ChromaDB
    logger.error(f"SQLite write failed for {summary.target_fqn}, rolling back ChromaDB: {e}")

    # Rollback ChromaDB write
    if vector_id and vector_store is not None:
        try:
            vector_store.delete_summaries([vector_id])
        except Exception as rollback_error:
            logger.error(f"Failed to rollback ChromaDB vector {vector_id}: {rollback_error}")
            # Track orphaned vector for later cleanup
            try:
                cursor.execute(
                    """INSERT INTO pending_vectors ..."""
                )
                self.conn.commit()  # ❌ PROBLEM: Already in rollback context!
            except Exception:
                pass  # ❌ CRITICAL: Silently loses tracking
```

### Data Corruption Scenario:

```
1. ChromaDB write succeeds (vector_id = "abc123")
2. SQLite INSERT fails (constraint violation, disk full, etc.)
3. SQLite transaction begins rollback
4. Attempt to rollback ChromaDB fails (network timeout)
5. Attempt to INSERT into pending_vectors fails (transaction context invalid)
6. Result: Vector "abc123" is orphaned in ChromaDB with NO tracking record
```

## Proposed Solutions

### Solution 1: Use Separate Transaction for Tracking (Recommended)

**Approach:** Create a new database connection outside the rollback context for tracking failures.

**Pros:**
- Tracking survives transaction rollback
- Isolated from main transaction lifecycle
- Proper error logging possible

**Cons:**
- Requires additional connection management
- Slightly more complex

**Effort:** Medium
**Risk:** Low

**Implementation:**
```python
except Exception as e:
    # SQLite write failed - need to rollback ChromaDB
    logger.error(f"SQLite write failed for {summary.target_fqn}, rolling back ChromaDB: {e}")

    if vector_id and vector_store is not None:
        try:
            vector_store.delete_summaries([vector_id])
        except Exception as rollback_error:
            logger.critical(
                f"Failed to rollback ChromaDB vector {vector_id}: {rollback_error}",
                extra={"event": "chroma_rollback_failed", "vector_id": vector_id}
            )
            # Track orphaned vector in SEPARATE transaction
            try:
                # Create new connection for tracking (outside rollback context)
                tracking_conn = sqlite3.connect(self.db_path)
                tracking_conn.execute("BEGIN IMMEDIATE")
                tracking_conn.execute(
                    """INSERT INTO pending_vectors (vector_id, target_fqn, operation, created_at)
                       VALUES (?, ?, ?, ?)""",
                    (vector_id, summary.target_fqn, "orphaned_after_rollback", datetime.utcnow())
                )
                tracking_conn.commit()
                tracking_conn.close()
            except Exception as tracking_error:
                logger.critical(
                    f"CRITICAL: Failed to track orphaned vector {vector_id}. "
                    f"Manual cleanup required. SQLite error: {e}, "
                    f"Rollback error: {rollback_error}, Tracking error: {tracking_error}",
                    extra={"event": "orphan_tracking_failed", "vector_id": vector_id}
                )
            # Still raise the original exception
            raise
```

### Solution 2: Use Tombstone Table with Auto-Commit

**Approach:** Create a separate `orphan_tombstones` table with auto-commit mode.

**Pros:**
- Simpler than separate connection
- Tombstones survive any transaction rollback
- Can be cleaned up asynchronously

**Cons:**
- Requires new table in schema
- Auto-commit mode is unusual

**Effort:** Medium
**Risk:** Low

**Implementation:**
```python
# Schema addition
CREATE TABLE orphan_tombstones (
    vector_id TEXT PRIMARY KEY,
    target_fqn TEXT NOT NULL,
    reason TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    cleaned_at TIMESTAMP
);

# In two-phase commit
except Exception as rollback_error:
    try:
        # Use separate connection with auto-commit
        tombstone_conn = sqlite3.connect(self.db_path, isolation_level=None)
        tombstone_conn.execute(
            "INSERT OR IGNORE INTO orphan_tombstones (vector_id, target_fqn, reason) VALUES (?, ?, ?)",
            (vector_id, summary.target_fqn, "rollback_failed")
        )
    except Exception as tracking_error:
        logger.critical(f"Failed to track orphan: {tracking_error}")
    raise
```

### Solution 3: Accept Eventual Consistency

**Approach:** Remove rollback tracking and rely on periodic orphan detection.

**Pros:**
- Simpler code
- No tracking failure concerns
- Works with eventual consistency model

**Cons:**
- Orphans persist until next cleanup run
- Requires periodic cleanup job
- Storage wasted in meantime

**Effort:** Low
**Risk:** Medium

**Implementation:**
```python
except Exception as rollback_error:
    logger.warning(
        f"ChromaDB rollback failed for {vector_id}. "
        f"Vector will be cleaned up by periodic orphan detection."
    )
    # Don't track - let recovery mechanism handle it
    raise
```

## Recommended Action

**Use Solution 1 (Separate Transaction for Tracking)**

This provides the most reliable tracking with proper error logging. The additional connection management complexity is justified for data integrity.

## Technical Details

### Files to Modify:

1. **`ariadne_core/storage/sqlite_store.py`** (lines 1012-1044)
   - Modify exception handling in `create_summary_with_vector`
   - Add separate connection for orphan tracking
   - Improve error logging

2. **`ariadne_core/storage/schema.py`** (optional)
   - Consider adding `orphan_tombstones` table if using Solution 2

### Testing Requirements:

```python
# tests/unit/test_two_phase_commit_recovery.py
def test_orphan_tracking_survives_rollback():
    """Verify orphan tracking works even when main transaction rolls back."""
    # Mock ChromaDB to fail rollback
    # Mock SQLite to fail write
    # Verify tracking record still created

def test_orphan_tracking_failure_logged():
    """Verify tracking failures are logged at CRITICAL level."""
    # Mock both rollback and tracking to fail
    # Verify critical log entry created

def test_recover_orphaned_vectors():
    """Verify recovery mechanism can find and clean orphans."""
    # Create orphaned vector
    # Run recovery
    # Verify vector deleted from ChromaDB
```

## Acceptance Criteria

- [ ] Orphan tracking uses separate transaction from main write
- [ ] Tracking failures are logged at CRITICAL level with vector_id
- [ ] Recovery mechanism can find and clean tracked orphans
- [ ] Unit tests for rollback scenarios pass
- [ ] Integration test with real ChromaDB failure scenario

## Work Log

| Date | Action | Result |
|------|--------|--------|
| 2026-02-02 | Code review completed | Critical issue identified |
| 2026-02-02 | Implemented separate transaction tracking | Added `_track_orphaned_vector_separate_txn()` method using new connection outside rollback context |
| 2026-02-02 | Updated exception handling | Calls separate tracking method instead of inline cursor.execute |
| 2026-02-02 | All tests passing (179 passed) | Fix verified working |

## Resources

- **Affected Files:**
  - `ariadne_core/storage/sqlite_store.py:1012-1044`
- **Related Issues:**
  - Data Integrity Review: Finding #1 - Two-Phase Commit Orphaned Vectors
- **References:**
  - Two-phase commit pattern documentation
  - SQLite transaction behavior documentation
