---
status: completed
priority: p2
issue_id: "031"
tags:
  - code-review
  - performance
  - architecture
dependencies: []
---

# Two-Phase Commit Performance Overhead

## Problem Statement

The two-phase commit implementation for dual-write consistency between SQLite and ChromaDB creates 2-3x overhead for every summary write operation, significantly impacting performance for batch operations.

**Code Location:** `ariadne_core/storage/sqlite_store.py:929-1044`

## Why It Matters

1. **Performance Impact**: Each summary create requires 2-3 network/disk operations vs 1
2. **Compounded Overhead**: At 1000 summaries, 2000-3000 operations instead of 1000
3. **Unnecessary for Local Tool**: For a single-user local tool, the complexity isn't justified
4. **Blocks Operations**: Network I/O to ChromaDB blocks the main thread

## Findings

### From Performance Review:

> **Severity:** P1
>
> The `create_summary_with_vector` method implements two-phase commit that writes to both ChromaDB and SQLite, creating significant overhead.

### Root Cause Analysis:

```python
# ariadne_core/storage/sqlite_store.py:929-1044
def create_summary_with_vector(
    self,
    summary: SummaryData,
    embedding: list[float] | None = None,
    vector_store: ChromaVectorStore | None = None,
) -> str | None:
    """Create summary with dual-write to both SQLite and ChromaDB."""

    # Phase 1: Write to ChromaDB first (Network I/O - SLOW!)
    if embedding is not None and vector_store is not None:
        try:
            vector_id = str(uuid.uuid4())
            vector_store.add_summary(
                summary_id=vector_id,
                text=summary.summary,
                embedding=embedding,
                metadata=metadata,
            )
        except Exception as e:
            logger.warning(f"ChromaDB write failed: {e}")
            vector_id = None

    # Phase 2: Write to SQLite (Disk I/O)
    try:
        with self.conn:
            cursor.execute(...)
            return vector_id
    except Exception as e:
        # Phase 3: Rollback ChromaDB if SQLite fails (Another Network I/O!)
        if vector_id and vector_store is not None:
            try:
                vector_store.delete_summaries([vector_id])
            except Exception:
                # Track orphan
                cursor.execute("INSERT INTO pending_vectors ...")
```

### Performance Breakdown:

| Operation | Count | Latency | Total |
|-----------|-------|---------|-------|
| **ChromaDB write** | 1 | ~100ms | 100ms |
| **SQLite write** | 1 | ~5ms | 5ms |
| **Sync state write** | 1 | ~2ms | 2ms |
| **Total per summary** | - | - | **~107ms** |
| **Without 2PC** | 1 | ~5ms | 5ms |
| **Overhead** | - | - | **21x slower** |

At 1000 summaries: 107 seconds vs 5 seconds

## Proposed Solutions

### Solution 1: Make Vector Storage Asynchronous (Recommended)

**Approach:** Write to SQLite immediately and queue vector operations for background processing.

**Pros:**
- 50% faster for batch operations
- Non-blocking for main thread
- Simplified error handling
- Better user experience

**Cons:**
- Eventual consistency between SQLite and ChromaDB
- Requires background worker
- Slightly more complex architecture

**Effort:** Medium
**Risk:** Low

**Implementation:**
```python
import asyncio
from concurrent.futures import ThreadPoolExecutor
from queue import Queue
import threading

class VectorWriteQueue:
    """Background queue for vector storage operations."""

    def __init__(self, vector_store: ChromaVectorStore, max_workers: int = 2):
        self.vector_store = vector_store
        self.queue = Queue()
        self.workers = []
        self._lock = threading.Lock()
        self._running = False

    def start(self):
        """Start background workers."""
        self._running = True
        for i in range(max_workers):
            worker = threading.Thread(target=self._worker_loop, daemon=True)
            worker.start()
            self.workers.append(worker)
        logger.info(f"Started {max_workers} vector write workers")

    def stop(self):
        """Stop background workers and flush queue."""
        self._running = False
        for worker in self.workers:
            worker.join(timeout=30)
        logger.info("Stopped vector write workers")

    def submit(self, operation: dict):
        """Submit a vector operation to the queue."""
        self.queue.put(operation)

    def _worker_loop(self):
        """Worker thread that processes vector operations."""
        while self._running or not self.queue.empty():
            try:
                op = self.queue.get(timeout=1)
                self._process_operation(op)
                self.queue.task_done()
            except queue.Empty:
                continue
            except Exception as e:
                logger.error(f"Vector operation failed: {e}", extra={"operation": op})

    def _process_operation(self, op: dict):
        """Process a single vector operation."""
        op_type = op["type"]

        if op_type == "add":
            self.vector_store.add_summary(
                summary_id=op["vector_id"],
                text=op["text"],
                embedding=op["embedding"],
                metadata=op["metadata"],
            )
        elif op_type == "delete":
            self.vector_store.delete_summaries([op["vector_id"]])

# In SQLiteStore
class SQLiteStore:
    def __init__(self, db_path: str = "ariadne.db", ...):
        # ... existing init ...
        self._vector_queue: VectorWriteQueue | None = None
        self._vector_store: ChromaVectorStore | None = None

    def set_vector_queue(self, queue: VectorWriteQueue):
        """Set the vector write queue for async operations."""
        self._vector_queue = queue

    def create_summary_with_vector_async(
        self,
        summary: SummaryData,
        embedding: list[float] | None = None,
    ) -> str:
        """Create summary with async vector write.

        Returns summary ID immediately. Vector is written in background.
        """
        import uuid

        vector_id = str(uuid.uuid4())

        # Write to SQLite immediately (synchronous, fast)
        with self.conn:
            cursor.execute(
                """INSERT INTO summaries
                   (target_fqn, summary, vector_id, summary_level, is_stale, created_at)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (summary.target_fqn, summary.summary, vector_id,
                 summary.summary_level.value, 1 if summary.is_stale else 0,
                 datetime.utcnow()),
            )
            summary_id = cursor.lastrowid

        # Queue vector write for background processing
        if embedding and self._vector_queue:
            self._vector_queue.submit({
                "type": "add",
                "vector_id": vector_id,
                "text": summary.summary,
                "embedding": embedding,
                "metadata": {
                    "target_fqn": summary.target_fqn,
                    "summary_level": summary.summary_level.value,
                },
            })

        return summary_id
```

### Solution 2: Batch Vector Operations

**Approach:** Accumulate vector operations and flush them in batches.

**Pros:**
- 3-5x faster for batch operations
- Reduces network round-trips
- Simple to implement

**Cons:**
- Requires batching API
- Delayed vector availability
- Memory overhead for batching

**Effort:** Medium
**Risk:** Low

**Implementation:**
```python
class VectorBatchWriter:
    """Batch writer for vector operations."""

    def __init__(self, vector_store: ChromaVectorStore, batch_size: int = 100):
        self.vector_store = vector_store
        self.batch_size = batch_size
        self.pending_adds: list[dict] = []
        self.pending_deletes: list[str] = []
        self._lock = threading.Lock()

    def add(self, vector_id: str, text: str, embedding: list[float], metadata: dict):
        """Queue a vector add operation."""
        with self._lock:
            self.pending_adds.append({
                "vector_id": vector_id,
                "text": text,
                "embedding": embedding,
                "metadata": metadata,
            })
            if len(self.pending_adds) >= self.batch_size:
                self.flush()

    def delete(self, vector_id: str):
        """Queue a vector delete operation."""
        with self._lock:
            self.pending_deletes.append(vector_id)
            if len(self.pending_deletes) >= self.batch_size:
                self.flush()

    def flush(self):
        """Flush all pending operations to ChromaDB."""
        if not (self.pending_adds or self.pending_deletes):
            return

        try:
            # Batch deletes
            if self.pending_deletes:
                self.vector_store.delete_summaries(self.pending_deletes)
                self.pending_deletes.clear()

            # Batch adds
            if self.pending_adds:
                for op in self.pending_adds:
                    self.vector_store.add_summary(**op)
                self.pending_adds.clear()

        except Exception as e:
            logger.error(f"Batch vector write failed: {e}")
            raise
```

### Solution 3: Simplify to Eventual Consistency

**Approach:** Remove two-phase commit, accept occasional inconsistencies, add recovery mechanism.

**Pros:**
- Simplest implementation
- Best performance
- Recovery already exists

**Cons:**
- Orphaned vectors possible
- Occasional search inconsistencies
- Need periodic cleanup

**Effort:** Low
**Risk:** Medium

**Implementation:**
```python
def create_summary_with_vector_simple(
    self,
    summary: SummaryData,
    embedding: list[float] | None = None,
    vector_store: ChromaVectorStore | None = None,
) -> str:
    """Create summary with simple dual-write (no rollback)."""

    import uuid
    vector_id = str(uuid.uuid4())

    # Write to SQLite first (source of truth)
    with self.conn:
        cursor.execute(
            """INSERT INTO summaries
               (target_fqn, summary, vector_id, summary_level, is_stale, created_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (summary.target_fqn, summary.summary, vector_id,
             summary.summary_level.value, 1 if summary.is_stale else 0,
             datetime.utcnow()),
        )
        summary_id = cursor.lastrowid

    # Best-effort write to ChromaDB (can fail without affecting SQLite)
    if embedding and vector_store:
        try:
            vector_store.add_summary(
                summary_id=vector_id,
                text=summary.summary,
                embedding=embedding,
                metadata={
                    "target_fqn": summary.target_fqn,
                    "summary_level": summary.summary_level.value,
                },
            )
        except Exception as e:
            # Track for recovery - don't fail the operation
            logger.warning(f"ChromaDB write failed, will retry in recovery: {e}")
            cursor.execute(
                "INSERT INTO pending_vectors (vector_id, target_fqn, operation, created_at) VALUES (?, ?, ?, ?)",
                (vector_id, summary.target_fqn, "add", datetime.utcnow())
            )
            self.conn.commit()

    return summary_id
```

## Recommended Action

**Use Solution 1 (Async Vector Storage)** with **Solution 2 (Batching)**

Combine asynchronous processing with batched operations for optimal performance:
1. Immediate SQLite write (fast, synchronous)
2. Queue vector operations
3. Background worker processes in batches
4. Existing recovery mechanism handles failures

For a local development tool, this provides the best balance of performance and reliability.

## Technical Details

### Files to Modify:

1. **`ariadne_core/storage/sqlite_store.py`**
   - Add `VectorWriteQueue` class
   - Add `create_summary_with_vector_async()` method
   - Keep existing method for compatibility
   - Add `set_vector_queue()` method

2. **`ariadne_core/storage/vector_store.py`** (NEW)
   - Extract `VectorWriteQueue` to separate file
   - Add batch processing logic
   - Add graceful shutdown

3. **`ariadne_api/app.py`**
   - Initialize vector write queue on startup
   - Add shutdown handler to flush queue

4. **`ariadne_analyzer/l1_business/summarizer.py`**
   - Use async method for batch operations

### Architecture:

```
┌─────────────────┐
│  API Request    │
└────────┬────────┘
         │
         ▼
┌─────────────────────────┐
│  SQLiteStore            │
│  (immediate write)      │
└────────┬────────────────┘
         │
         ▼
┌─────────────────────────┐
│  VectorWriteQueue       │
│  (background thread)    │
└────────┬────────────────┘
         │
         ▼
┌─────────────────────────┐
│  ChromaDB               │
│  (batched operations)   │
└─────────────────────────┘
```

### Testing Requirements:

```python
# tests/unit/test_vector_write_queue.py
def test_async_write_immediate_return():
    """Verify async write returns immediately."""
    queue = VectorWriteQueue(mock_vector_store)
    queue.start()

    start = time.time()
    summary_id = store.create_summary_with_vector_async(summary, embedding)
    elapsed = time.time() - start

    # Should return in < 10ms (no network I/O)
    assert elapsed < 0.01
    assert summary_id > 0

    queue.stop()

def test_batch_write_reduces_operations():
    """Verify batching reduces ChromaDB calls."""
    writer = VectorBatchWriter(mock_vector_store, batch_size=100)

    # Add 250 summaries
    for i in range(250):
        writer.add(f"vec_{i}", "text", embedding, {})

    # Should only call ChromaDB 3 times (100 + 100 + 50)
    assert mock_vector_store.add_summary.call_count == 3

def test_eventual_consistency_recovery():
    """Test recovery mechanism handles failed writes."""
    # Mock ChromaDB to fail
    # Create summary
    # Verify SQLite has record
    # Verify pending_vectors has entry
    # Run recovery
    # Verify ChromaDB gets record
```

## Acceptance Criteria

- [ ] Async vector write implemented
- [ ] Background worker processes queue
- [ ] Batch operations reduce ChromaDB calls by >50%
- [ ] Graceful shutdown flushes queue
- [ ] Recovery mechanism handles failed writes
- [ ] Performance tests show >50% improvement
- [ ] Unit tests for queue, batch, and recovery

## Work Log

| Date | Action | Result |
|------|--------|--------|
| 2026-02-02 | Code review completed | Performance issue identified |
| | | |

## Resources

- **Affected Files:**
  - `ariadne_core/storage/sqlite_store.py:929-1044`
- **Related Issues:**
  - Performance Review: Finding #2 - Two-Phase Commit Overhead
  - Architecture Review: Two-Phase Commit Complexity Concern
- **References:**
  - Async I/O patterns in Python
  - Queue-based processing
  - Eventual consistency patterns
