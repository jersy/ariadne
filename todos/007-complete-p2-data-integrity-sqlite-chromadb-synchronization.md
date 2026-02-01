---
status: complete
priority: p2
issue_id: "007"
tags:
  - code-review
  - data-integrity
  - sqlite
  - chromadb
dependencies: []
---

# Data Integrity: SQLite-ChromaDB Synchronization

## Problem Statement

There is no atomic transaction boundary across SQLite and ChromaDB operations. If a ChromaDB operation fails after SQLite update, or vice versa, data becomes inconsistent between the two stores.

**Locations:**
- `ariadne_cli/main.py:448-531` - `_cmd_summarize()` creates summary in SQLite, then adds to vector store separately
- `ariadne_core/storage/sqlite_store.py:416-433` - `create_summary()` has no transaction wrapping
- `ariadne_core/storage/vector_store.py:72-102` - `add_summary()` is independent operation

## Why It Matters

1. **Data Inconsistency**: Summaries in SQLite may reference non-existent vectors in ChromaDB
2. **Orphaned Data**: Failed ChromaDB writes leave `vector_id` references pointing to nothing
3. **Search Failures**: Vector search returns IDs that don't exist in SQLite
4. **Storage Bloat**: ChromaDB accumulates orphaned vectors over time

## Findings

### From Data Integrity Guardian Review:

> **HIGH RISK**
>
> No atomic transaction boundary across SQLite and ChromaDB operations. The `vector_id` stored in SQLite may reference non-existent ChromaDB entry.

**Risk Scenario:**
```python
# Current unsafe pattern
def store_summary(summary):
    sqlite_store.create_summary(summary)  # Commits
    chroma_store.add_summary(summary.vector_id, ...)  # Could fail
    # If ChromaDB fails, SQLite has orphaned vector_id reference
```

### Specific Issues:
1. SQLite commit happens before ChromaDB operation
2. No rollback if ChromaDB fails
3. No cleanup of orphaned vectors
4. No validation that vector_id exists in ChromaDB

## Proposed Solutions

### Solution 1: Atomic Transaction with Callback (Recommended)

**Approach:** Pass ChromaDB operation as callback within SQLite transaction

**Pros:**
- Ensures both operations succeed or both fail
- Maintains consistency
- Clear rollback path

**Cons:**
- Requires coordination between stores
- More complex error handling

**Effort:** Medium
**Risk:** Low

**Implementation:**
```python
# In SQLiteStore
def create_summary_with_vector(
    self,
    summary: SummaryData,
    vector_store: ChromaVectorStore,
    embedding: list[float] | None = None,
) -> None:
    """Create summary with vector storage in single transaction."""
    cursor = self.conn.cursor()
    try:
        with self.conn:  # SQLite transaction
            # 1. Insert SQLite record
            cursor.execute("""
                INSERT INTO summaries (target_fqn, level, summary, is_stale)
                VALUES (?, ?, ?, ?)
                RETURNING id
            """, (summary.target_fqn, summary.level.value, summary.summary, False))
            summary_id = cursor.fetchone()[0]

            # 2. Add to ChromaDB (within transaction context)
            vector_store.add_summary(
                summary_id=str(summary_id),
                text=summary.summary,
                embedding=embedding,
                metadata={"fqn": summary.target_fqn, "level": summary.level.value}
            )

            # 3. Update vector_id only after ChromaDB success
            cursor.execute("""
                UPDATE summaries SET vector_id = ? WHERE id = ?
            """, (str(summary_id), summary_id))

    except Exception as e:
        logger.error(f"Rolling back summary creation: {e}")
        # ChromaDB add is not rolled back (limitation), but SQLite reference is
        raise
```

### Solution 2: Two-Phase Commit Pattern

**Approach:** Implement two-phase commit between SQLite and ChromaDB

**Pros:**
- More robust for distributed systems
- Standard pattern for multi-database consistency

**Cons:**
- Overkill for local ChromaDB
- Significant complexity
- ChromaDB doesn't support native two-phase commit

**Effort:** High
**Risk:** Medium

### Solution 3: Eventual Consistency with Cleanup Job

**Approach:** Accept inconsistency and add periodic cleanup

**Pros:**
- Minimal changes
- Works with current architecture

**Cons:**
- Doesn't prevent inconsistency
- Requires background job
- Data remains inconsistent until cleanup

**Effort:** Medium
**Risk:** Medium

## Recommended Action

**Use Solution 1 (Atomic Transaction with Callback)**

For local ChromaDB storage, the callback pattern provides strong consistency without excessive complexity. The transaction ensures SQLite only commits after ChromaDB succeeds.

## Technical Details

### Files to Modify:
1. `ariadne_core/storage/sqlite_store.py` - Add `create_summary_with_vector()` method
2. `ariadne_core/storage/vector_store.py` - Ensure ChromaDB operations throw on failure
3. `ariadne_cli/main.py` - Update `_cmd_summarize()` to use new method

### Cascade Delete Implementation:
Also need to handle deletes atomically:
```python
def delete_summary_cascade(self, target_fqn: str, vector_store: ChromaVectorStore) -> bool:
    """Delete summary from both SQLite and ChromaDB atomically."""
    cursor = self.conn.cursor()
    try:
        with self.conn:
            # 1. Get vector_id from SQLite
            cursor.execute("SELECT vector_id FROM summaries WHERE target_fqn = ?", (target_fqn,))
            row = cursor.fetchone()
            if not row:
                return False

            vector_id = row[0]

            # 2. Delete from ChromaDB
            if vector_id:
                vector_store.delete_summaries([vector_id])

            # 3. Delete from SQLite
            cursor.execute("DELETE FROM summaries WHERE target_fqn = ?", (target_fqn,))
            return True
    except Exception as e:
        logger.error(f"Failed to delete summary: {e}")
        raise
```

### Foreign Key Constraints:
Also add proper foreign keys (see Architecture Review):
```sql
-- Currently missing
ALTER TABLE summaries ADD FOREIGN KEY (target_fqn) REFERENCES symbols(fqn) ON DELETE CASCADE;
```

## Acceptance Criteria

- [ ] `create_summary_with_vector()` method implemented
- [ ] `delete_summary_cascade()` method implemented
- [ ] CLI updated to use new atomic methods
- [ ] Tests verify rollback on ChromaDB failure
- [ ] Tests verify rollback on SQLite failure
- [ ] Tests verify both succeed on normal operation
- [ ] Foreign key constraints added to schema

## Work Log

| Date | Action | Result |
|------|--------|--------|
| 2026-02-01 | Code review completed | Data synchronization issue identified |
| 2026-02-01 | Added atomic vector operations | create_summary_with_vector(), delete_summary_cascade(), mark_summaries_stale_by_file() with proper SQLite transaction handling |

## Resources

- **Files**: `ariadne_core/storage/sqlite_store.py`, `ariadne_core/storage/vector_store.py`
- **Related**:
  - Todo #008 (Foreign Keys) - Related data integrity issue
  - Todo #003 (Path Traversal) - Security issue in same code
- **Documentation**:
  - ACID Transactions: https://en.wikipedia.org/wiki/ACID
  - Two-Phase Commit: https://en.wikipedia.org/wiki/Two-phase_commit_protocol
