---
title: "P1 #027 - Migration Runs Without Preview or Backup"
category: database-issues
severity: P1
date_created: 2026-02-02
related_issues:
  - "027-pending-p1-migration-preview-and-backup.md"
  - "018-pending-p1-cascade-delete-orphaned-edges.md"
tags:
  - database-migration
  - data-loss
  - dry-run
  - backup
  - orphaned-records
---

## Problem

The cascade delete migration (migration 001) immediately deleted orphaned records without providing a preview mechanism or creating backups, causing potentially unrecoverable data loss.

### Symptom

**File**: `ariadne_core/storage/migrations/migration_001_cascade_deletes.py`

The original `upgrade()` function had no `dry_run` parameter and deleted records immediately:

```python
# Original buggy implementation (simplified)
def upgrade(conn: Any) -> dict[str, int]:
    """Apply migration to add cascade delete behavior."""
    cursor = conn.cursor()

    # 1. Add cascade delete triggers (safe, no data loss)
    _create_edges_triggers(cursor)

    # 2. Clean up orphaned records (DELETES DATA IMMEDIATELY)
    _cleanup_orphaned_records(cursor)  # No preview, no backup

    # 3. Ensure foreign keys have CASCADE
    _ensure_cascade_constraints(cursor)

    conn.commit()
    return orphaned_counts
```

### Impact

1. **No Preview**: Users couldn't see what would be deleted before running migration
2. **No Backup**: Deleted records were lost forever
3. **Unrecoverable**: No way to restore accidentally deleted records
4. **Unexpected Behavior**: Users might not expect migrations to delete data

---

## Root Cause Analysis

### Why This Was Missed

1. **Developer Mindset**: Migrations were seen as "internal operations" not requiring user control
2. **No Migration Policy**: No established pattern for safe data deletion in migrations
3. **Testing Gap**: Tests only verified migration succeeded, not data preservation
4. **Documentation Gap**: Migration description didn't warn about data deletion

### The Orphaned Records Problem

Orphaned records occur when:
- A symbol is deleted
- Related records (edges, summaries, etc.) remain
- Foreign key relationships are broken

The migration was intended to clean these up, but without proper safeguards.

---

## Solution

The fix adds three critical safety features:

1. **`dry_run` parameter** for previewing deletions
2. **Backup table** (`_deleted_orphans_backup_001`) for recovery
3. **`preview_migrations()` method** in SQLiteStore

### Part 1: Dry-Run Support

**File**: `ariadne_core/storage/migrations/migration_001_cascade_deletes.py` (lines 28-95)

```python
def upgrade(conn: Any, dry_run: bool = False) -> dict[str, int]:
    """Apply migration to add cascade delete behavior.

    IMPORTANT: Run with dry_run=True first to preview what will be deleted.
    Deleted records are backed up to _deleted_orphans_backup_001 table.

    Args:
        conn: SQLite connection object
        dry_run: If True, only report what would be deleted without deleting

    Returns:
        Dictionary with counts of orphaned records found/deleted
    """
    cursor = conn.cursor()

    logger.info(
        f"Running migration {version} with dry_run={dry_run}",
        extra={"migration": version, "dry_run": dry_run}
    )

    # Enable foreign keys
    cursor.execute("PRAGMA foreign_keys = ON")

    # 1. Add cascade delete triggers for edges table (safe, no data loss)
    _create_edges_triggers(cursor)

    # 2. Clean up orphaned records (with dry-run support)
    orphaned_counts = _cleanup_orphaned_records(cursor, dry_run=dry_run)

    # 3. Ensure foreign keys have CASCADE for L2/L1 tables
    _ensure_cascade_constraints(cursor)

    # Only commit if not in dry-run mode
    if not dry_run:
        conn.commit()
    else:
        conn.rollback()  # Explicit rollback to make intent clear

    # Log results
    if orphaned_counts:
        total_orphans = sum(orphaned_counts.values())
        if dry_run:
            logger.info(
                f"[DRY-RUN] Migration {version}: would delete {total_orphans} orphaned records",
                extra={
                    "migration": version,
                    "dry_run": True,
                    "would_delete": total_orphans,
                    "orphaned_counts": orphaned_counts,
                }
            )
        else:
            logger.info(
                f"Migration {version} completed: deleted {total_orphans} orphaned records",
                extra={
                    "migration": version,
                    "deleted": total_orphans,
                    "orphaned_counts": orphaned_counts,
                }
            )

    return orphaned_counts
```

### Part 2: Backup Before Delete

**File**: `ariadne_core/storage/migrations/migration_001_cascade_deletes.py` (lines 127-204)

```python
def _cleanup_orphaned_records(cursor: Any, dry_run: bool = False) -> dict[str, int]:
    """Clean up orphaned records across all tables.

    IMPORTANT: This will DELETE data. Run with dry_run=True first to preview.

    Args:
        cursor: SQLite cursor
        dry_run: If True, only report what would be deleted without deleting

    Returns:
        Dictionary with table names and orphaned counts
    """
    orphaned_counts = {}
    backup_table = "_deleted_orphans_backup_001"

    # Create backup table if not exists (only when not in dry-run mode)
    if not dry_run:
        cursor.execute(f"""
            CREATE TABLE IF NOT EXISTS {backup_table} (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                table_name TEXT NOT NULL,
                record_id TEXT NOT NULL,
                record_data JSON,
                deleted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        logger.info(f"Created backup table: {backup_table}")

    # Helper function to backup and delete orphaned records
    def _backup_and_delete_orphans(
        table_name: str,
        id_column: str,
        where_clause: str,
        count_query: str,
        data_query: str,
    ) -> int:
        """Backup and delete orphaned records for a table.

        Args:
            table_name: Name of the table
            id_column: Primary key column name
            where_clause: WHERE clause to find orphans
            count_query: Query to count orphans
            data_query: Query to select orphan data for backup

        Returns:
            Number of orphans deleted (or would be deleted in dry-run)
        """
        # Count orphans
        cursor.execute(count_query)
        orphan_count = cursor.fetchone()[0]

        if orphan_count == 0:
            return 0

        if dry_run:
            logger.info(f"[DRY-RUN] Would delete {orphan_count} orphaned records from {table_name}")
            return orphan_count

        # Backup the records
        cursor.execute(f"""
            INSERT INTO {backup_table} (table_name, record_id, record_data, deleted_at)
            SELECT '{table_name}',
                   {id_column},
                   json_object('data', json({data_query})),
                   datetime('now')
            FROM ({data_query}) AS orphan_data
        """)

        # Delete the records
        cursor.execute(f"DELETE FROM {table_name} WHERE {where_clause}")
        deleted_count = cursor.rowcount

        logger.info(f"Deleted {deleted_count} orphaned records from {table_name}, backed up to {backup_table}")
        return deleted_count

    # Check and clean orphaned edges (from side)
    orphaned_counts["edges_from"] = _backup_and_delete_orphans(
        table_name="edges",
        id_column="'from_fqn' || ':' || 'to_fqn' || ':' || relation",
        where_clause="from_fqn NOT IN (SELECT fqn FROM symbols)",
        count_query="""
            SELECT COUNT(*) FROM edges e
            LEFT JOIN symbols s ON e.from_fqn = s.fqn
            WHERE s.fqn IS NULL
        """,
        data_query="""
            SELECT from_fqn, to_fqn, relation, id
            FROM edges e
            LEFT JOIN symbols s ON e.from_fqn = s.fqn
            WHERE s.fqn IS NULL
        """,
    )

    # Similar cleanup for other tables...
    # (edges_to, entry_points, external_dependencies, summaries, glossary, constraints, anti_patterns)

    return orphaned_counts
```

### Part 3: Preview Migrations API

**File**: `ariadne_core/storage/sqlite_store.py` (lines 143-153)

```python
def _run_migrations(self) -> None:
    """Run pending database migrations."""
    self._run_migrations_impl(dry_run=False)

def preview_migrations(self) -> dict[str, Any]:
    """Preview pending migrations without applying them.

    Returns:
        Dictionary with migration results for each pending migration
    """
    return self._run_migrations_impl(dry_run=True)
```

**File**: `ariadne_core/storage/sqlite_store.py` (lines 155-243)

```python
def _run_migrations_impl(self, dry_run: bool = False) -> dict[str, Any]:
    """Run or preview pending database migrations.

    Args:
        dry_run: If True, only report what would happen without applying changes

    Returns:
        Dictionary with results from each migration (only when dry_run=True)
    """
    cursor = self.conn.cursor()

    # Create migrations table if it doesn't exist
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS _migrations (
            version TEXT PRIMARY KEY,
            applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Get applied migrations
    cursor.execute("SELECT version FROM _migrations ORDER BY version")
    applied = {row[0] for row in cursor.fetchall()}

    results = {}

    # Run pending migrations
    for migration in migrations.ALL_MIGRATIONS:
        if migration["version"] not in applied:
            logger.info(
                f"{'[DRY-RUN] ' if dry_run else ''}Running migration {migration['version']}: {migration['name']}",
                extra={
                    "event": "migration_start",
                    "version": migration["version"],
                    "migration_name": migration["name"],
                    "dry_run": dry_run,
                }
            )
            try:
                # Call upgrade with dry_run parameter
                migration_result = migration["upgrade"](self.conn, dry_run=dry_run)

                # Record migration (only if not dry_run)
                if not dry_run:
                    cursor.execute(
                        "INSERT INTO _migrations (version) VALUES (?)",
                        (migration["version"],)
                    )
                    self.conn.commit()
                else:
                    # In dry-run mode, return the results
                    results[migration["version"]] = migration_result

            except Exception as e:
                if not dry_run:
                    self.conn.rollback()
                    logger.error(
                        f"Migration {migration['version']} failed: {e}",
                        extra={
                            "event": "migration_failed",
                            "version": migration["version"],
                            "error": str(e),
                        }
                    )
                    raise
                else:
                    # In dry-run mode, just record the error and continue
                    results[migration["version"]] = {
                        "error": str(e),
                        "status": "failed"
                    }
                    logger.warning(
                        f"[DRY-RUN] Migration {migration['version']} would fail: {e}",
                        extra={
                            "event": "migration_dry_run_failed",
                            "version": migration["version"],
                            "error": str(e),
                        }
                    )

    return results
```

---

## Key Insights

### 1. Dry-Run Pattern for Destructive Operations

Always provide a preview capability for operations that delete data:

```python
# DON'T: Delete immediately
def delete_orphans(cursor):
    cursor.execute("DELETE FROM edges WHERE ...")
    return cursor.rowcount

# DO: Support dry-run
def delete_orphans(cursor, dry_run=False):
    if dry_run:
        cursor.execute("SELECT COUNT(*) FROM edges WHERE ...")
        return cursor.fetchone()[0]  # Report would-be count
    else:
        cursor.execute("DELETE FROM edges WHERE ...")
        return cursor.rowcount
```

### 2. Backup Before Delete Pattern

Create backups before deletion for potential recovery:

```python
def backup_and_delete(cursor, table_name, where_clause, dry_run=False):
    # 1. Create backup table if needed
    if not dry_run:
        cursor.execute(f"""
            CREATE TABLE IF NOT EXISTS {table_name}_backup (
                ...
            )
        """)

    # 2. Backup records
    if not dry_run:
        cursor.execute(f"""
            INSERT INTO {table_name}_backup
            SELECT * FROM {table_name} WHERE {where_clause}
        """)

    # 3. Delete records
    if not dry_run:
        cursor.execute(f"DELETE FROM {table_name} WHERE {where_clause}")
```

### 3. Transparent Logging

Log all destructive operations with clear context:

```python
logger.info(
    f"[DRY-RUN] Would delete {count} orphaned records from {table_name}",
    extra={
        "migration": version,
        "dry_run": True,
        "would_delete": count,
        "table": table_name,
    }
)
```

---

## API Usage Examples

### Previewing Migrations

```python
from ariadne_core.storage.sqlite_store import SQLiteStore

store = SQLiteStore("ariadne.db")

# Preview what migrations would do
results = store.preview_migrations()

for version, result in results.items():
    print(f"Migration {version}:")
    if "error" in result:
        print(f"  ERROR: {result['error']}")
    else:
        print(f"  Would delete orphans:")
        for table, count in result.items():
            print(f"    {table}: {count}")
```

### Running Migrations

```python
# After preview, run actual migrations
store = SQLiteStore("ariadne.db")
# Migrations run automatically in __init__
```

### Recovering from Backup

```python
# Restore deleted records from backup
cursor = conn.cursor()
cursor.execute("""
    SELECT table_name, record_id, record_data
    FROM _deleted_orphans_backup_001
    WHERE table_name = 'edges'
""")

for row in cursor.fetchall():
    table_name, record_id, record_data = row
    data = json.loads(record_data)
    # Restore logic...
```

---

## Prevention Strategies

### 1. Migration Checklist

Before writing any migration that deletes data:

- [ ] Add `dry_run` parameter to `upgrade()` function
- [ ] Create backup table for deleted records
- [ ] Log all operations with `[DRRY-RUN]` prefix when previewing
- [ ] Document what will be deleted in migration docstring
- [ ] Add preview method to storage class
- [ ] Test both dry-run and actual execution

### 2. Migration Template

```python
def upgrade(conn: Any, dry_run: bool = False) -> dict[str, int]:
    """Apply migration with dry-run support.

    IMPORTANT: This migration may DELETE data. Run with dry_run=True first.

    Args:
        conn: SQLite connection
        dry_run: If True, only report what would happen

    Returns:
        Dictionary with counts of affected records
    """
    cursor = conn.cursor()
    results = {}

    # 1. Preview/report counts
    cursor.execute("SELECT COUNT(*) FROM table WHERE condition")
    count = cursor.fetchone()[0]
    results["table"] = count

    if dry_run:
        logger.info(f"[DRY-RUN] Would delete {count} records from table")
        conn.rollback()
        return results

    # 2. Create backup
    cursor.execute("CREATE TABLE IF NOT EXISTS backup_table ...")

    # 3. Backup before delete
    cursor.execute("INSERT INTO backup_table SELECT * FROM table WHERE condition")

    # 4. Delete
    cursor.execute("DELETE FROM table WHERE condition")

    conn.commit()
    return results
```

### 3. Testing Strategy

```python
def test_migration_dry_run():
    """Test that dry-run doesn't delete data."""
    conn = sqlite3.connect(":memory:")

    # Create test data with orphans
    # ...

    # Preview migration
    results = upgrade(conn, dry_run=True)

    # Verify no deletions
    assert results["edges"] == 5  # Would delete 5
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM edges")
    assert cursor.fetchone()[0] == 10  # Still 10 (not deleted)

def test_migration_with_backup():
    """Test that deleted records are backed up."""
    conn = sqlite3.connect(":memory:")

    # Create test data with orphans
    # ...

    # Run migration
    results = upgrade(conn, dry_run=False)

    # Verify backup exists
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM _deleted_orphans_backup_001")
    assert cursor.fetchone()[0] == 5  # 5 backed up

    # Verify deletion
    cursor.execute("SELECT COUNT(*) FROM edges")
    assert cursor.fetchone()[0] == 5  # 5 remaining
```

---

## Related Documentation

- **Issue Analysis**: `docs/issues/027-pending-p1-migration-preview-and-backup.md`
- **Migration System**: `ariadne_core/storage/migrations/`
- **Related**: `docs/solutions/database-issues/p025-two-phase-commit-rollback-tracking-failure.md`

---

## Verification

After implementing this fix, verify:

1. **Dry-Run**: Run `preview_migrations()` and verify no data is deleted
2. **Backup**: Run actual migration and verify backup table is created
3. **Recovery**: Test restoring records from backup table
4. **Logging**: Verify `[DRY-RUN]` prefix appears in logs

```sql
-- Verify backup table exists
SELECT * FROM _deleted_orphans_backup_001;

-- Check what would be deleted (in dry-run mode)
-- (Check logs for "[DRY-RUN] Would delete X orphaned records")
```
