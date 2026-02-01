---
status: pending
priority: p1
issue_id: "017"
tags:
  - code-review
  - data-integrity
  - architecture
  - critical
dependencies: []
---

# Rebuild Operation Data Loss Risk

## Problem Statement

The `/knowledge/rebuild` endpoint has **no safety mechanism for interruption**. If the rebuild process crashes or is interrupted, the system is left in a **permanently incomplete state** with no way to resume.

**Current Implementation:**
```python
# From plan: Phase 4.4 - Incremental Update
POST /knowledge/rebuild
mode: "incremental" | "full"
```

**Failure Scenario:**
```
Time 0: User POST /knowledge/rebuild?mode=full
Time 1: System drops all tables: DROP TABLE symbols; DROP TABLE edges;
Time 2: System starts indexing 10,000 files
Time 3: Process crashes (OOM, killed, Ctrl+C) at file 5,000

Result:
- 50% of data missing
- No way to resume from checkpoint
- No backup of previous state
- API returns incomplete results until manual intervention
```

## Why It Matters

1. **Complete Data Loss**: Full rebuild destroys existing data with no backup
2. **No Recovery**: Interrupted rebuild leaves system unusable
3. **User Experience**: Long-running operation with no progress indication
4. **Production Risk**: No rollback mechanism for failed rebuilds

## Findings

### From Data Integrity Guardian Review:

> **Severity:** CRITICAL
>
> The rebuild process has no safety mechanism. If the process crashes after dropping tables but before completing indexing, there's complete data loss with no recovery path.

### From Architecture Strategist Review:

> **Severity:** HIGH
>
> The plan mentions "file-level change detection" and "cascade update affected nodes" but doesn't address atomicity of the rebuild operation itself.

### From Code Quality Review:

> **Observation:** The job queue system exists but rebuild operation doesn't use checkpointing or recovery.

### Affected Code Locations:

| File | Issue |
|------|-------|
| `ariadne_api/routes/rebuild.py` | No backup/restore logic |
| `ariadne_core/storage/sqlite_store.py` | No atomic rebuild method |
| `ariadne_core/storage/job_queue.py` | No checkpoint mechanism |

## Proposed Solutions

### Solution 1: Shadow Rebuild with Atomic Swap (Recommended)

**Approach:** Build new index in separate database file, then atomically swap.

**Pros:**
- Zero downtime during rebuild
- Instant rollback on failure
- Previous state always available
- Can verify new index before going live

**Cons:**
- Requires 2x disk space during rebuild
- Slightly more complex file management

**Effort:** Medium
**Risk:** Low

**Implementation:**
```python
class IndexRebuilder:
    def rebuild_full(self) -> RebuildResult:
        """Build new index in separate database, then atomically swap"""

        # 1. Create backup schema
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_suffix = f"_backup_{timestamp}"
        new_db_path = f"ariadne_new_{timestamp}.db"

        try:
            # 2. Build new index in separate file
            logger.info(f"Building new index at {new_db_path}")
            new_store = SQLiteStore(new_db_path, init=True)

            # Extract and index all data
            stats = self._build_index_from_scratch(new_store)

            # 3. Verify integrity of new index
            if not self._verify_index(new_store):
                raise IntegrityError("Built index failed verification")

            # 4. Atomic swap
            logger.info("Atomic database swap")
            self._atomic_swap_databases(
                current="ariadne.db",
                new=new_db_path,
                backup_suffix=backup_suffix
            )

            # 5. Clean up old backup (async)
            self._schedule_old_backup_cleanup(backup_suffix)

            return RebuildResult(
                status="success",
                symbols_indexed=stats.symbols_count,
                edges_created=stats.edges_count,
                duration=stats.duration
            )

        except Exception as e:
            # 6. Rollback: Clean up failed rebuild
            logger.error(f"Rebuild failed, keeping current database: {e}")

            # Delete incomplete new database
            if os.path.exists(new_db_path):
                os.remove(new_db_path)

            raise RebuildFailedError(f"Rebuild failed: {e}")

    def _atomic_swap_databases(self, current: str, new: str, backup_suffix: str):
        """Atomically swap database files"""

        # 1. Rename current to backup
        if os.path.exists(current):
            os.rename(current, f"{current}{backup_suffix}")

        # 2. Rename new to current
        os.rename(new, current)

        # 3. Verify swap succeeded
        if not os.path.exists(current):
            # Rollback: restore backup
            if os.path.exists(f"{current}{backup_suffix}"):
                os.rename(f"{current}{backup_suffix}", current)
            raise IOError("Database swap failed, rolled back")

    def _verify_index(self, store: SQLiteStore) -> bool:
        """Verify built index meets integrity criteria"""
        checks = [
            self._check_symbol_count(store),
            self._check_edge_integrity(store),
            self._check_no_orphaned_edges(store),
            self._check_foreign_keys(store)
        ]
        return all(checks)
```

### Solution 2: Transactional Rebuild with Staging Tables

**Approach:** Use staging tables within same database, then atomic rename.

**Pros:**
- No separate file management
- Uses existing transaction infrastructure

**Cons:**
- Database locked during final swap
- Still requires 2x space during rebuild
- Single database file corruption risk

**Effort:** Medium
**Risk:** Medium

### Solution 3: Incremental Checkpoint-Based Rebuild

**Approach:** Process in batches with checkpoint after each batch.

**Pros:**
- Resumable on failure
- Progress tracking
- Can continue from last checkpoint

**Cons:**
- Slower (checkpoint overhead)
- More complex state management
- Still affects production database

**Effort:** High
**Risk:** Medium

## Recommended Action

**Use Solution 1 (Shadow Rebuild with Atomic Swap)**

This provides the strongest safety guarantees with minimal downtime. The atomic swap ensures users always have a complete database available.

## Technical Details

### API Changes Required:

```python
# ariadne_api/routes/rebuild.py
@router.post("/rebuild")
async def trigger_rebuild(
    mode: RebuildMode = RebuildMode.INCREMENTAL,
    background_tasks: BackgroundTasks = None
) -> JobResponse:
    """
    Trigger knowledge graph rebuild.

    Modes:
    - incremental: Update changed files only (fast)
    - full: Complete rebuild from scratch (uses shadow database)
    """
    job_id = str(uuid.uuid4())

    if mode == RebuildMode.FULL:
        # Shadow rebuild: safe, no downtime
        rebuilder = ShadowIndexRebuilder(store, vector_store)
        background_tasks.add_task(rebuilder.rebuild_full, job_id)
    else:
        # Incremental: fast, minimal disruption
        rebuilder = IncrementalIndexer(store, vector_store)
        background_tasks.add_task(rebuilder.rebuild_incremental, job_id)

    return JobResponse(job_id=job_id, status="queued")
```

### Files to Modify:

1. **`ariadne_api/routes/rebuild.py`** - Add shadow rebuild option
2. **`ariadne_core/storage/sqlite_store.py`** - Add `atomic_swap()` method
3. **`ariadne_core/storage/schema.py`** - Add verification queries
4. **`tests/integration/test_rebuild.py`** - Test crash scenarios
5. **NEW** `ariadne_core/storage/shadow_rebuilder.py` - Shadow rebuild logic

### Integrity Checks:

```python
def _verify_index(self, store: SQLiteStore) -> bool:
    """Run comprehensive integrity checks"""

    # 1. Check minimum data expectations
    symbol_count = store.conn.execute(
        "SELECT COUNT(*) FROM symbols"
    ).fetchone()[0]

    if symbol_count == 0:
        raise IntegrityError("No symbols indexed")

    # 2. Check for orphaned edges
    orphaned = store.conn.execute("""
        SELECT COUNT(*) FROM edges e
        LEFT JOIN symbols s ON e.from_fqn = s.fqn
        WHERE s.fqn IS NULL
    """).fetchone()[0]

    if orphaned > 0:
        raise IntegrityError(f"{orphaned} orphaned edges detected")

    # 3. Check foreign key integrity
    try:
        store.conn.execute("PRAGMA foreign_key_check")
    except sqlite3.IntegrityError as e:
        raise IntegrityError(f"Foreign key violation: {e}")

    # 4. Check summary consistency
    summaries_without_vectors = store.conn.execute("""
        SELECT COUNT(*) FROM summaries
        WHERE vector_id IS NULL AND is_stale = FALSE
    """).fetchone()[0]

    # Allow some stale summaries, but warn
    if summaries_without_vectors > 100:
        logger.warning(f"{summaries_without_vectors} summaries without vectors")

    return True
```

## Acceptance Criteria

- [ ] Shadow rebuild implementation completed
- [ ] Atomic database swap implemented and tested
- [ ] Integrity verification suite created
- [ ] Rebuild crash scenario tested (50% completion)
- [ ] Rebuild OOM scenario tested
- [ ] Rollback on failure verified
- [ ] Previous database preserved as backup
- [ ] API returns 503 during brief swap moment (< 1s)
- [ ] Background cleanup of old backups
- [ ] Test coverage for all failure modes
- [ ] Documentation updated with rebuild safety guarantees

## Work Log

| Date | Action | Result |
|------|--------|--------|
| 2026-02-02 | Plan review completed | Critical rebuild safety issue identified |
| | | |

## Resources

- **Affected Files**:
  - `ariadne_api/routes/rebuild.py`
  - `ariadne_core/storage/sqlite_store.py`
  - `ariadne_core/storage/job_queue.py`
- **Plan Reference**: Phase 4.4 - 增量更新
- **Related Issues**:
  - Issue 016: Dual-Write Consistency (related data integrity)
- **Documentation**:
  - Plan Section: "验收场景 - Scenario 2: 防遗漏"
  - SQLite ATOMIC COMMIT: https://www.sqlite.org/atomiccommit.html
