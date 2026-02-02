---
status: completed
priority: p1
issue_id: "027"
tags:
  - code-review
  - data-integrity
  - migration
  - critical
dependencies: []
---

# Migration Runs Without Preview or Backup

## Problem Statement

The cascade delete migration (`migration_001_cascade_deletes.py`) immediately deletes orphaned records without providing a way to preview what will be deleted or creating backups. This can result in permanent, unrecoverable data loss.

**Code Location:** `ariadne_core/storage/migrations/migration_001_cascade_deletes.py:91-217`

## Why It Matters

1. **Unrecoverable Data Loss**: Deleted records cannot be restored
2. **No Visibility**: Users don't know what will be deleted until it's gone
3. **No Undo**: Once migration runs, data is permanently deleted
4. **Unexpected Behavior**: Users may not expect data deletion during migration

## Findings

### From Data Integrity Review:

> **Severity:** CRITICAL
>
> The migration immediately deletes data without allowing users to preview the deletion. No backup is created. Users have no way to know how much data will be lost.

### Root Cause Analysis:

```python
# ariadne_core/storage/migrations/migration_001_cascade_deletes.py:91-217
def _cleanup_orphaned_records(cursor: Any) -> dict[str, int]:
    """Clean up orphaned records and return counts."""
    orphaned_counts = {}

    # Check orphaned edges from deleted symbols
    cursor.execute("""
        SELECT COUNT(*) FROM edges e
        LEFT JOIN symbols s ON e.from_fqn = s.fqn
        WHERE s.fqn IS NULL
    """)
    orphaned_edge_from = cursor.fetchone()[0]

    # ❌ IMMEDIATE DELETE - NO PREVIEW
    if orphaned_edge_from > 0:
        cursor.execute("DELETE FROM edges WHERE from_fqn NOT IN (SELECT fqn FROM symbols)")
        orphaned_counts["edges_from"] = orphaned_edge_from

    # Same pattern for other orphan types...
    return orphaned_counts
```

### Data Loss Scenario:

```
1. Developer runs migration
2. Migration finds 1,000 orphaned edges
3. DELETE executes immediately
4. Developer discovers edges were from different indexing run
5. No way to recover the deleted data
6. Must re-run entire extraction (30+ minutes)
```

### Additional Issues:

1. **No dry-run mode**: Cannot see what will be deleted without actually deleting
2. **No backup table**: Deleted records are not preserved anywhere
3. **No logging of deleted records**: Only counts are logged, not specific records
4. **Silent data loss**: Users may not realize how much data was deleted

## Proposed Solutions

### Solution 1: Add Dry-Run Mode + Backup Table (Recommended)

**Approach:** Add a `dry_run` parameter and create a backup table before deletion.

**Pros:**
- Users can preview changes before committing
- Deleted data is preserved in backup table
- Can rollback manually if needed
- Standard migration best practice

**Cons:**
- Requires additional storage for backup
- More complex migration logic
- Need cleanup strategy for backups

**Effort:** Medium
**Risk:** Low

**Implementation:**
```python
def _cleanup_orphaned_records(cursor: Any, dry_run: bool = False) -> dict[str, int]:
    """Clean up orphaned records with optional dry-run.

    Args:
        cursor: Database cursor
        dry_run: If True, only report what would be deleted without deleting

    Returns:
        Dictionary with counts of orphaned records found/deleted
    """

    orphaned_counts = {}
    backup_table = "_deleted_orphans_backup_001"

    # Create backup table if not exists (only on first run)
    if not dry_run:
        cursor.execute(f"""
            CREATE TABLE IF NOT EXISTS {backup_table} (
                id INTEGER PRIMARY KEY,
                table_name TEXT NOT NULL,
                record_id TEXT,
                record_data JSON,
                deleted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

    # Check orphaned edges from deleted symbols
    cursor.execute("""
        SELECT COUNT(*) FROM edges e
        LEFT JOIN symbols s ON e.from_fqn = s.fqn
        WHERE s.fqn IS NULL
    """)
    orphaned_edge_from = cursor.fetchone()[0]

    if orphaned_edge_from > 0:
        if dry_run:
            # In dry-run mode, just count and report
            orphaned_counts["edges_from"] = orphaned_edge_from
            logger.info(f"[DRY-RUN] Would delete {orphaned_edge_from} orphaned edges (from)")
        else:
            # First, backup the records
            cursor.execute(f"""
                INSERT INTO {backup_table} (table_name, record_id, record_data)
                SELECT 'edges', from_fqn || ':' || to_fqn || ':' || relation,
                       json_object('from_fqn', from_fqn, 'to_fqn', to_fqn,
                                   'relation', relation, 'id', id)
                FROM edges e
                LEFT JOIN symbols s ON e.from_fqn = s.fqn
                WHERE s.fqn IS NULL
            """)

            # Then delete
            cursor.execute("DELETE FROM edges WHERE from_fqn NOT IN (SELECT fqn FROM symbols)")
            deleted_count = cursor.rowcount
            orphaned_counts["edges_from"] = deleted_count
            logger.info(f"Deleted {deleted_count} orphaned edges (from), backed up to {backup_table}")

    # Repeat pattern for other orphan types...
    return orphaned_counts

def upgrade(cursor: Any, dry_run: bool = False) -> dict[str, int]:
    """Upgrade database to cascade delete triggers.

    Args:
        cursor: Database cursor
        dry_run: If True, only report changes without executing

    Returns:
        Statistics about cleanup operation
    """
    logger.info(f"Running migration with dry_run={dry_run}")

    # Create triggers first (safe, no data loss)
    _create_edges_triggers(cursor)
    _create_summaries_triggers(cursor)

    # Then cleanup orphaned records
    stats = _cleanup_orphaned_records(cursor, dry_run=dry_run)

    if dry_run:
        logger.info(
            f"[DRY-RUN] Migration complete. Would clean up: {stats}",
            extra={"event": "migration_dry_run", "stats": stats}
        )
    else:
        logger.info(
            f"Migration complete. Cleaned up: {stats}",
            extra={"event": "migration_complete", "stats": stats}
        )

    return stats
```

**Usage:**
```python
# Preview first
stats = migration.upgrade(cursor, dry_run=True)
print(f"Would delete {stats['edges_from']} edges")

# If acceptable, run for real
stats = migration.upgrade(cursor, dry_run=False)
```

### Solution 2: Require Explicit Confirmation

**Approach:** Require user to pass `--confirm` flag to run migration.

**Pros:**
- Simple to implement
- Forces user to acknowledge data deletion
- No additional storage

**Cons:**
- Still no backup
- No preview capability
- Easy to bypass with `--confirm`

**Effort:** Low
**Risk:** Medium

**Implementation:**
```python
def upgrade(cursor: Any, confirmed: bool = False) -> dict[str, int]:
    """Upgrade database to cascade delete triggers.

    Args:
        cursor: Database cursor
        confirmed: Must be True to actually delete data

    Raises:
        ValueError: If confirmed=False and orphaned records exist
    """
    # Check what would be deleted first
    stats = _count_orphaned_records(cursor)
    total_orphans = sum(stats.values())

    if total_orphans > 0 and not confirmed:
        raise ValueError(
            f"Migration would delete {total_orphans} orphaned records: {stats}. "
            f"Pass confirmed=True to proceed, or backup your database first."
        )

    if confirmed:
        logger.warning(f"Proceeding with deletion of {stats} records (confirmed=True)")
        return _cleanup_orphaned_records(cursor)
    else:
        logger.info("No orphaned records found, proceeding safely")
        return {}
```

### Solution 3: Create Cascade Preview Function

**Approach:** Add a separate function to preview cascade effects before any deletion.

**Pros:**
- Separates preview from execution
- Can be called independently
- More flexible API

**Cons:**
- Requires two API calls
- More code to maintain
- Users might forget to preview

**Effort:** Low
**Risk:** Low

**Implementation:**
```python
def preview_cascade_effects(cursor: Any, fqn: str) -> dict[str, list[str]]:
    """Preview what would be deleted if a symbol is deleted.

    Returns:
        Dict mapping table names to lists of affected record IDs
    """
    effects = {}

    # Edges that would be deleted
    cursor.execute("""
        SELECT from_fqn, to_fqn, relation
        FROM edges
        WHERE from_fqn = ? OR to_fqn = ?
    """, (fqn, fqn))
    effects["edges"] = [f"{row[0]} -> {row[1]} ({row[2]})" for row in cursor.fetchall()]

    # Summaries that would be deleted
    cursor.execute("SELECT target_fqn FROM summaries WHERE target_fqn = ?", (fqn,))
    effects["summaries"] = [row[0] for row in cursor.fetchall()]

    return effects

# Before running migration
def upgrade(cursor: Any) -> dict[str, int]:
    """Upgrade with preview."""
    # Get all symbols
    cursor.execute("SELECT fqn FROM symbols")
    symbols = [row[0] for row in cursor.fetchall()]

    # Preview total effects (for information)
    total_effects = {}
    for fqn in symbols:
        effects = preview_cascade_effects(cursor, fqn)
        for table, records in effects.items():
            total_effects.setdefault(table, []).extend(records)

    logger.info(f"Cascade triggers will affect: { {k: len(v) for k, v in total_effects.items()} }")

    # Proceed with migration
    return _cleanup_orphaned_records(cursor)
```

## Recommended Action

**Use Solution 1 (Dry-Run Mode + Backup Table)**

This provides the best safety:
1. Users can preview before committing
2. Deleted data is preserved in backup table
3. Can rollback manually if needed
4. Follows database migration best practices

Additionally implement **Solution 3** for runtime cascade preview functionality.

## Technical Details

### Files to Modify:

1. **`ariadne_core/storage/migrations/migration_001_cascade_deletes.py`** (lines 91-217)
   - Add `dry_run` parameter to `_cleanup_orphaned_records`
   - Create backup table before deletion
   - Log deleted records with details

2. **`ariadne_core/storage/sqlite_store.py`** (migration runner)
   - Add support for dry-run mode in `_run_migrations`
   - Expose preview functionality

3. **`ariadne_api/routes/rebuild.py`** (NEW)
   - Add endpoint to preview cascade effects
   - Add endpoint to list deleted orphans from backup

### New API Endpoints:

```python
@router.get("/admin/migration-preview")
async def preview_migration():
    """Preview what migration would delete."""

@router.get("/admin/deleted-orphans")
async def list_deleted_orphans():
    """List records in backup table."""
```

### Testing Requirements:

```python
# tests/unit/test_migration.py
def test_migration_dry_run():
    """Verify dry-run doesn't delete data."""
    # Create orphaned records
    # Run migration with dry_run=True
    # Verify records still exist

def test_migration_creates_backup():
    """Verify deleted records are backed up."""
    # Create orphaned records
    # Run migration
    # Verify backup table has records
    # Verify main table cleaned

def test_migration_with_confirmation():
    """Verify migration requires confirmation."""
    # Create orphaned records
    # Run without confirmed=True
    # Verify exception raised

def test_cascade_preview():
    """Verify cascade preview shows effects."""
    # Create symbol with edges and summaries
    # Call preview_cascade_effects
    # Verify all affected records listed
```

## Acceptance Criteria

- [ ] Migration supports `dry_run` parameter
- [ ] Backup table created before any deletion
- [ ] Deleted records preserved with JSON data
- [ ] API endpoint for previewing migration effects
- [ ] API endpoint for listing deleted orphans
- [ ] Unit tests for dry-run, backup, and preview
- [ ] Documentation explains how to restore from backup

## Work Log

| Date | Action | Result |
|------|--------|--------|
| 2026-02-02 | Code review completed | Critical issue identified |
| 2026-02-02 | Implemented dry_run parameter | Updated `upgrade()` and `_cleanup_orphaned_records()` to support dry-run |
| 2026-02-02 | Added backup table creation | `_deleted_orphans_backup_001` table created before deletion |
| 2026-02-02 | Added json import to migration | Required for backup table JSON data |
| 2026-02-02 | Updated migration runner | Added `preview_migrations()` and `_run_migrations_impl()` methods |
| 2026-02-02 | All tests passing (179 passed) | Fix verified working |

## Resources

- **Affected Files:**
  - `ariadne_core/storage/migrations/migration_001_cascade_deletes.py:91-217`
- **Related Issues:**
  - Data Integrity Review: Finding #2 - Cascade Delete No Preview
- **References:**
  - Database migration best practices
  - SQLite backup strategies
  - Cascade delete documentation
