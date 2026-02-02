---
status: completed
priority: p1
issue_id: "021"
tags:
  - code-review
  - thread-safety
  - critical
dependencies: []
---

# Thread Safety: Shared Mutable State Race Conditions

## Problem Statement

The parallel LLM summarization code contains **critical thread safety violations** where multiple threads modify shared mutable state without synchronization. This causes:

1. **Lost updates**: Counter increments are lost due to read-modify-write race conditions
2. **Incorrect statistics**: Success/failure counts don't reflect actual results
3. **Data corruption**: Dictionary can become corrupted under concurrent access
4. **Silent failures**: Issues are not immediately apparent in single-threaded testing

## Findings

### 1. ParallelSummarizer.stats Race Condition

**File**: `ariadne_analyzer/l1_business/parallel_summarizer.py:38-43, 101, 118`

**Problem**: The `stats` dictionary is mutated from multiple ThreadPoolExecutor workers without locks:

```python
self.stats: dict[str, int] = {
    "total": 0,
    "success": 0,
    "failed": 0,
    "skipped": 0,
}

# Line 101 & 118: Concurrent updates without lock
self.stats["failed"] += 1  # Race condition!
```

**Impact**: With `max_workers=10`, multiple workers update `stats` concurrently. The `+=` operation is not atomic, causing:
- Lost counter increments
- Incorrect final counts
- Dictionary corruption risk

### 2. LLMCostTracker.usage Race Condition

**File**: `ariadne_analyzer/l1_business/cost_tracker.py:40-82`

**Problem**: The `usage` dictionary is mutated from multiple threads without synchronization:

```python
# Lines 70-82: Multiple concurrent updates without locking
self.usage["total_tokens"] += total_tokens
self.usage["total_cost_usd"] += cost
self.usage["requests_count"] += 1
self.usage["model_costs"][model]["tokens"] += total_tokens
```

**Impact**: Cost tracking data is corrupted under concurrent load, making:
- Token counts inaccurate
- Cost calculations wrong
- Budget tracking unreliable

### 3. SQLite Connection Thread Safety

**File**: `ariadne_core/storage/sqlite_store.py:34`

**Problem**: Single SQLite connection shared across threads:

```python
self.conn = sqlite3.connect(db_path)  # Single connection
```

**Impact**: SQLite connections are NOT thread-safe by default. Multiple threads calling `create_summary()` simultaneously will cause:
- "database is locked" errors
- Connection corruption risk
- Performance degradation due to lock contention

### 4. IncrementalSummarizerCoordinator Stats Read Race

**File**: `ariadne_analyzer/l1_business/incremental_coordinator.py:203-209`

**Problem**: Direct access to `parallel.stats` during concurrent updates:

```python
stats={
    "success": self.parallel.stats["success"],  # Read during concurrent updates!
    "failed": self.parallel.stats["failed"],    # Read during concurrent updates!
}
```

**Impact**: Torn reads produce inconsistent statistics.

## Technical Details

**Affected Files**:
- `ariadne_analyzer/l1_business/parallel_summarizer.py`
- `ariadne_analyzer/l1_business/cost_tracker.py`
- `ariadne_core/storage/sqlite_store.py`
- `ariadne_analyzer/l1_business/incremental_coordinator.py`

**Components**:
- `ParallelSummarizer` - ThreadPoolExecutor-based parallel processing
- `LLMCostTracker` - Token/cost tracking
- `SQLiteStore` - Database operations

## Proposed Solutions

### Solution 1: Add Locking to ParallelSummarizer (RECOMMENDED)

**Effort**: Small
**Risk**: Low
**Benefits**: Simple, effective, minimal code changes

```python
from threading import Lock

class ParallelSummarizer:
    def __init__(self, llm_client: LLMClient, max_workers: int = 10) -> None:
        self.llm_client = llm_client
        self.max_workers = max_workers
        self.stats: dict[str, int] = {...}
        self._stats_lock = Lock()

    def _increment_failed(self):
        with self._stats_lock:
            self.stats["failed"] += 1

    def _increment_success(self):
        with self._stats_lock:
            self.stats["success"] += 1
```

### Solution 2: Add Locking to LLMCostTracker

**Effort**: Small
**Risk**: Low

```python
from threading import Lock
from dataclasses import dataclass, field

@dataclass
class LLMCostTracker:
    usage: dict[str, Any] = field(default_factory=...)
    _lock: Lock = field(default_factory=Lock)

    def record_request(self, model: str, input_tokens: int, output_tokens: int, cached: bool = False):
        with self._lock:
            self.usage["total_tokens"] += total_tokens
            self.usage["total_cost_usd"] += cost
            # ...
```

### Solution 3: Thread-Local SQLite Connections

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
            # ... setup code ...
        return self._local.conn
```

### Solution 4: Thread-Safe Stats Getter

**Effort**: Small
**Risk**: Low

```python
def get_stats_snapshot(self) -> dict[str, int]:
    """Get a thread-safe snapshot of current statistics."""
    with self._stats_lock:
        return self.stats.copy()
```

## Acceptance Criteria

- [ ] All shared mutable state is protected by locks
- [ ] Thread safety tests pass with 10 concurrent workers
- [ ] No lost counter increments under load
- [ ] SQLite operations work correctly with multiple threads
- [ ] Cost tracking produces accurate counts under concurrent load

## Work Log

| Date | Action | Result |
|------|--------|--------|
| 2026-02-02 | Code review completed | Thread safety issues identified |
| 2026-02-02 | ParallelSummarizer locking | Already has _stats_lock with thread-safe methods |
| 2026-02-02 | LLMCostTracker locking | Already has _lock for all usage updates |
| 2026-02-02 | Thread-local SQLite connections | Already uses threading.local() per thread |
| 2026-02-02 | incremental_coordinator fixed | NOW uses get_stats() instead of direct access |
| 2026-02-02 | All tests passing | 14 thread safety tests pass |
| 2026-02-02 | Committed | fix(analyzer): Use thread-safe stats access in incremental coordinator |

## Resources

- **Related Issue**: PR #4 - Parallel LLM Summarization
- **Learning**: `docs/solutions/security-issues/hardcoded-api-keys-in-tests.md` - Security patterns
- **Similar Pattern**: Thread pool resource leak (previously documented)
