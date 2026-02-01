---
status: pending
priority: p2
issue_id: "030"
tags:
  - code-review
  - performance
  - user-experience
dependencies: []
---

# Shadow Rebuild Lacks Incremental Option

## Problem Statement

The shadow rebuild process (`shadow_rebuilder.py`) only supports full rebuilds, which requires re-parsing all Java files and rebuilding the entire database from scratch. For large codebases, this takes 30-60 minutes and blocks all operations.

**Code Location:** `ariadne_core/storage/shadow_rebuilder.py:90-218`

## Why It Matters

1. **Performance**: Full rebuild takes 30-60 seconds for 10K symbols, 5-10 minutes for 100K
2. **Blocking**: No other operations can run during rebuild
3. **Poor UX**: Developers must wait long periods for small changes
4. **Resource Waste**: Re-parsing unchanged files is inefficient

## Findings

### From Performance Review:

> **Severity:** P0
>
> The shadow rebuild creates a complete new database from scratch. At 100K symbols, expected rebuild time is 30-60 minutes.

### Root Cause:

```python
# ariadne_core/storage/shadow_rebuilder.py:90-152
def rebuild_full(self) -> dict[str, Any]:
    """Rebuild the entire database from source code."""
    # Creates entirely new database - no incremental option
    new_store = SQLiteStore(new_db_path, init=True)
    extractor = Extractor(db_path=new_db_path, service_url=self.service_url, init=False)
    result: ExtractionResult = extractor.extract_project(self.project_root)
    # ... processes ALL files
```

### Impact by Project Size:

| Symbol Count | Expected Time | Blocking |
|--------------|---------------|----------|
| 1,000 | ~5 seconds | Acceptable |
| 10,000 | ~30-60 seconds | Frustrating |
| 100,000 | ~5-10 minutes | Unusable |
| 1,000,000 | ~30-60 minutes | Broken |

## Proposed Solutions

### Solution 1: Add Incremental Rebuild (Recommended)

**Approach:** Implement incremental rebuild that only processes changed files.

**Pros:**
- 10-100x faster for small changes
- Non-blocking for unchanged code
- Standard feature in similar tools

**Cons:**
- More complex implementation
- Need to track file changes
- Requires dependency analysis

**Effort:** Medium
**Risk:** Low

**Implementation:**
```python
def rebuild_incremental(
    self,
    changed_files: list[str] | None = None,
    force: bool = False
) -> dict[str, Any]:
    """Rebuild only changed files incrementally.

    Args:
        changed_files: List of modified file paths. If None, detects changes via git/mtime.
        force: If True, force rebuild of changed files even if symbols unchanged

    Returns:
        Rebuild statistics
    """
    import time
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler

    start_time = time.time()

    # Detect changed files if not provided
    if changed_files is None:
        changed_files = self._detect_changed_files()

    if not changed_files:
        logger.info("No changes detected, skipping rebuild")
        return {
            "status": "skipped",
            "reason": "no_changes",
            "duration_seconds": 0,
        }

    logger.info(
        f"Incremental rebuild starting with {len(changed_files)} changed files",
        extra={"event": "incremental_rebuild_start", "file_count": len(changed_files)}
    )

    # Analyze dependencies to find affected symbols
    affected_fqns = self._get_affected_symbols(changed_files)

    # Copy current database to new location
    new_db_path = self._get_new_db_path()
    shutil.copy2(self.db_path, new_db_path)

    # Open databases
    current_store = SQLiteStore(self.db_path, init=False)
    new_store = SQLiteStore(new_db_path, init=False)

    try:
        # Delete symbols from changed files
        deleted_count = self._delete_symbols_for_files(new_store, changed_files)

        # Extract symbols from changed files only
        extractor = Extractor(db_path=new_db_path, service_url=self.service_url, init=False)
        extraction_result = extractor.extract_files(changed_files)

        # Re-run L1 analysis for affected symbols
        affected_fqns.update(extraction_result.symbols)
        self._regenerate_summaries_for_fqns(new_store, list(affected_fqns))

        # Verify integrity
        self._verify_incremental_rebuild(new_store, current_store, changed_files)

        # Atomic swap
        self._atomic_swap_databases(self.db_path, new_db_path, "_backup")

        duration = time.time() - start_time

        stats = {
            "status": "success",
            "type": "incremental",
            "changed_files": len(changed_files),
            "symbols_deleted": deleted_count,
            "symbols_added": len(extraction_result.symbols),
            "summaries_regenerated": len(affected_fqns),
            "duration_seconds": duration,
        }

        logger.info(
            f"Incremental rebuild completed in {duration:.2f}s",
            extra={"event": "incremental_rebuild_complete", "stats": stats}
        )

        return stats

    except Exception as e:
        logger.error(f"Incremental rebuild failed: {e}")
        # Clean up failed rebuild
        if os.path.exists(new_db_path):
            os.remove(new_db_path)
        raise RebuildFailedError(f"Incremental rebuild failed: {e}") from e

def _detect_changed_files(self) -> list[str]:
    """Detect changed files since last rebuild.

    Uses git if available, otherwise falls back to file modification times.
    """
    import subprocess

    # Try git first (most reliable)
    try:
        result = subprocess.run(
            ["git", "diff", "--name-only", "HEAD"],
            cwd=self.project_root,
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0:
            changed = [
                os.path.join(self.project_root, f)
                for f in result.stdout.strip().split('\n')
                if f and f.endswith('.java')
            ]
            logger.info(f"Detected {len(changed)} changed files via git")
            return changed
    except Exception as e:
        logger.debug(f"Git detection failed: {e}")

    # Fallback to mtime comparison
    last_rebuild_time = self._get_last_rebuild_timestamp()
    changed = []
    for java_file in Path(self.project_root).rglob("*.java"):
        if os.path.getmtime(java_file) > last_rebuild_time:
            changed.append(str(java_file))

    logger.info(f"Detected {len(changed)} changed files via mtime")
    return changed

def _get_affected_symbols(self, changed_files: list[str]) -> set[str]:
    """Get all symbols affected by changes to these files.

    Includes:
    - Symbols defined in changed files
    - Symbols that depend on symbols in changed files
    - Symbols that changed symbols depend on (callers)
    """
    affected = set()

    # Get symbols from changed files
    with self._get_store() as store:
        for file_path in changed_files:
            symbols = store.get_symbols_by_file_path(file_path)
            affected.update(s["fqn"] for s in symbols)

        # Get callers of affected symbols (reverse dependencies)
        for fqn in list(affected):
            callers = self._get_callers_of(store, fqn)
            affected.update(callers)

        logger.info(f"Found {len(affected)} affected symbols for {len(changed_files)} changed files")

    return affected
```

### Solution 2: Use SQLite Backup API

**Approach:** Use SQLite's online backup API instead of re-extraction.

**Pros:**
- Much faster (2-5 seconds vs 30+ seconds)
- Simpler than incremental
- Reliable and well-tested

**Cons:**
- Doesn't solve stale data issue
- Still requires rebuild for schema changes
- No re-analysis

**Effort:** Low
**Risk:** Low

**Implementation:**
```python
def _fast_copy_database(self, source: str, target: str) -> None:
    """Use SQLite backup API for fast database copy.

    Much faster than re-extraction for simple copies.
    """
    import sqlite3

    source_conn = sqlite3.connect(source)
    target_conn = sqlite3.connect(target)

    # Online backup - blocks other writers but not readers
    source_conn.backup(target_conn)

    source_conn.close()
    target_conn.close()
```

### Solution 3: Background Rebuild with Progress

**Approach:** Run rebuild in background thread/worker with progress reporting.

**Pros:**
- Doesn't block main operations
- User can see progress
- Can cancel mid-rebuild

**Cons:**
- More complex architecture
- Potential for inconsistent state
- Requires async API

**Effort:** Medium
**Risk:** Medium

**Implementation:**
```python
import threading
from queue import Queue

class RebuildWorker:
    def __init__(self, rebuilder: ShadowRebuilder):
        self.rebuilder = rebuilder
        self.thread = None
        self.progress_queue = Queue()
        self._stop_event = threading.Event()

    def rebuild_async(self) -> str:
        """Start rebuild in background, returns job ID."""
        job_id = str(uuid.uuid4())

        def rebuild_worker():
            try:
                # Emit progress updates
                for progress in self._rebuild_with_progress():
                    self.progress_queue.put({
                        "job_id": job_id,
                        "progress": progress,
                    })

                self.progress_queue.put({
                    "job_id": job_id,
                    "status": "complete",
                })
            except Exception as e:
                self.progress_queue.put({
                    "job_id": job_id,
                    "status": "failed",
                    "error": str(e),
                })

        self.thread = threading.Thread(target=rebuild_worker)
        self.thread.start()

        return job_id

    def get_progress(self, job_id: str) -> dict:
        """Get current progress of rebuild job."""
        # Check queue for updates
        pass
```

## Recommended Action

**Implement Solution 1 (Incremental Rebuild)** with **Solution 3 (Background Processing)**

For the best user experience:
1. Default to incremental rebuild (10-100x faster)
2. Fall back to full rebuild when needed
3. Run in background with progress reporting
4. Allow cancellation

## Technical Details

### Files to Modify:

1. **`ariadne_core/storage/shadow_rebuilder.py`**
   - Add `rebuild_incremental()` method
   - Add `_detect_changed_files()` helper
   - Add `_get_affected_symbols()` helper
   - Add progress tracking

2. **`ariadne_api/routes/rebuild.py`**
   - Add async rebuild endpoint
   - Add progress query endpoint
   - Add cancel endpoint

3. **`ariadne_api/schemas/rebuild.py`** (NEW)
   - Progress response schema
   - Job status schema

### New API Endpoints:

```python
@router.post("/rebuild/incremental")
async def rebuild_incremental(
    changed_files: list[str] | None = None,
    force: bool = False,
    run_async: bool = True
):
    """Trigger incremental rebuild."""

@router.get("/rebuild/status/{job_id}")
async def get_rebuild_status(job_id: str):
    """Get rebuild job status and progress."""

@router.post("/rebuild/cancel/{job_id}")
async def cancel_rebuild(job_id: str):
    """Cancel running rebuild job."""
```

### Testing Requirements:

```python
# tests/unit/test_shadow_rebuilder.py
def test_incremental_rebuild_faster_than_full():
    """Verify incremental rebuild is faster than full."""
    # Create database with 1000 symbols
    # Modify 10 files
    # Incremental rebuild should take < 1 second
    # Full rebuild would take > 5 seconds

def test_incremental_rebuild_correctness():
    """Verify incremental rebuild produces same result as full."""
    # Create database
    # Modify files
    # Do incremental rebuild
    # Do full rebuild in separate DB
    # Compare results - should be identical

def test_detect_changed_files():
    """Test changed file detection."""
    # Modify files
    # Run detection
    # Verify correct files detected

def test_affected_symbols_calculation():
    """Test dependency tracking for affected symbols."""
    # Create symbol dependencies
    # Change one symbol
    # Verify all dependents included
```

## Acceptance Criteria

- [ ] Incremental rebuild implemented with < 5 second target for 10 changed files
- [ ] Changed file detection works via git or mtime
- [ ] Dependency tracking includes callers and callees
- [ ] Background rebuild with progress reporting
- [ ] API endpoints for async rebuild
- [ ] Unit tests for incremental vs full rebuild equivalence
- [ ] Performance benchmarks showing improvement

## Work Log

| Date | Action | Result |
|------|--------|--------|
| 2026-02-02 | Code review completed | Performance issue identified |
| | | |

## Resources

- **Affected Files:**
  - `ariadne_core/storage/shadow_rebuilder.py:90-218`
- **Related Issues:**
  - Performance Review: Finding #1 - Shadow Rebuild Performance
- **References:**
  - Incremental build patterns
  - SQLite backup API
  - Watchdog file monitoring library
