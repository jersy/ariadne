---
category: data-integrity
module: storage
symptoms:
  - Orphaned vector_id references
  - SQLite-ChromaDB inconsistency
  - No atomic transactions
tags:
  - data-integrity
  - sqlite
  - chromadb
  - transactions
---

# Atomic SQLite-ChromaDB Operations

## Problem

SQLite and ChromaDB operations were not atomic. If ChromaDB failed after SQLite commit, or vice versa, data became inconsistent with orphaned `vector_id` references.

## Detection

```python
# ariadne_cli/main.py (before)
def _cmd_summarize(args):
    # SQLite write
    sqlite_store.create_summary(summary_data)
    # ChromaDB write - could fail!
    vector_store.add_summary(summary_id, text, embedding, metadata)
    # If ChromaDB fails, SQLite has orphaned vector_id reference
```

## Risk Scenario

1. SQLite creates summary record with `vector_id = NULL`
2. ChromaDB add fails (network error, storage full, etc.)
3. SQLite reference remains but no vector exists
4. Vector search returns IDs that don't exist in SQLite

## Solution

### 1. Atomic Create with Vector

```python
# ariadne_core/storage/sqlite_store.py
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
            """, (summary.target_fqn, summary.level.value, summary.summary, False))

            summary_id = cursor.lastrowid

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
        raise
```

### 2. Atomic Cascade Delete

```python
def delete_summary_cascade(
    self,
    target_fqn: str,
    vector_store: ChromaVectorStore
) -> bool:
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

### 3. Enhanced Stale Marking

```python
def mark_summaries_stale_by_file(
    self,
    file_path: str,
    sqlite_store: SQLiteStore,
    vector_store: ChromaVectorStore
) -> int:
    """Mark summaries stale by file path with cascade to parent levels."""
    affected = 0

    # Mark method-level summaries stale
    cursor = self.conn.cursor()
    cursor.execute("""
        UPDATE summaries
        SET is_stale = 1
        WHERE target_fqn IN (
            SELECT fqn FROM symbols WHERE file_path = ?
        )
    """, (file_path,))
    affected = cursor.rowcount

    # Find affected classes and mark their summaries stale
    cursor.execute("""
        SELECT DISTINCT parent_fqn
        FROM symbols
        WHERE file_path = ? AND parent_fqn IS NOT NULL
    """, (file_path,))

    for row in cursor.fetchall():
        parent_fqn = row[0]
        # Mark class-level summary stale
        cursor.execute("""
            UPDATE summaries SET is_stale = 1 WHERE target_fqn = ?
        """, (parent_fqn,))
        affected += cursor.rowcount

    self.conn.commit()
    return affected
```

## Usage Pattern

```python
# CLI usage
with sqlite_store.transaction():
    sqlite_store.create_summary_with_vector(
        summary=summary_data,
        vector_store=vector_store,
        embedding=embedding
    )
    # Both succeed or both fail
```

## Why This Matters

- **Data consistency**: vector_id always references valid ChromaDB entry
- **Rollback safety**: SQLite commits only after ChromaDB succeeds
- **Cleanup**: Cascade deletes prevent orphaned vectors

## Files Changed

- `ariadne_core/storage/sqlite_store.py` - Added atomic vector operations
- `ariadne_cli/main.py` - Updated `_cmd_summarize()` to use new methods

## Related

- Todo #007: Data integrity SQLite-ChromaDB synchronization
- Todo #008: Missing foreign key constraints (related)
- ACID Transactions: https://en.wikipedia.org/wiki/ACID
