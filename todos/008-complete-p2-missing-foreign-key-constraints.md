---
status: complete
priority: p2
issue_id: "008"
tags:
  - code-review
  - data-integrity
  - sqlite
  - schema
dependencies: []
---

# Missing Foreign Key Constraints

## Problem Statement

The SQLite schema lacks foreign key constraints for critical relationships. Specifically, `summaries`, `glossary`, and `constraints` tables reference `symbols(fqn)` but have no foreign key constraints. This allows orphaned records when symbols are deleted.

**Location:** `ariadne_core/storage/schema.py:89-123`

## Why It Matters

1. **Orphaned Data**: When a symbol is deleted, related summaries/glossary/constraints remain with no valid reference
2. **Data Integrity**: No database-level enforcement of referential integrity
3. **Cleanup Complexity**: Application code must manually clean up related records
4. **Silent Failures**: Queries may return data for non-existent symbols without error

## Findings

### From Data Integrity Guardian Review:

> **HIGH RISK**
>
> Foreign key relationships are inconsistently defined. The `summaries.target_fqn` has NO FK constraint to symbols - HIGH risk of orphaned summaries.

**Current State:**

| Table | FK Status | Risk |
|-------|-----------|------|
| `entry_points.symbol_fqn` | Has FK to symbols | Safe |
| `external_dependencies.caller_fqn` | Has FK to symbols | Safe |
| `summaries.target_fqn` | **NO FK constraint** | HIGH - orphaned summaries |
| `glossary.source_fqn` | **NO FK constraint** | MEDIUM - orphaned entries |
| `constraints.source_fqn` | **NO FK constraint** | MEDIUM - orphaned constraints |

**Schema Excerpt:**
```sql
CREATE TABLE IF NOT EXISTS summaries (
    id INTEGER PRIMARY KEY,
    target_fqn TEXT NOT NULL UNIQUE,
    level TEXT NOT NULL,
    summary TEXT NOT NULL,
    vector_id TEXT,
    is_stale BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    -- NO FOREIGN KEY to symbols!
);
```

## Proposed Solutions

### Solution 1: Add Foreign Keys with CASCADE (Recommended)

**Approach:** Add foreign key constraints with `ON DELETE CASCADE`

**Pros:**
- Database enforces referential integrity
- Automatic cleanup of related records
- Prevents orphaned data
- Standard SQL pattern

**Cons:**
- Requires schema migration
- Cascade deletes may hide unintended deletions
- Need to ensure foreign keys are enabled in SQLite

**Effort:** Medium
**Risk:** Low

**Implementation:**
```python
# In schema.py
def _create_summaries_table(cursor: sqlite3.Cursor) -> None:
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS summaries (
            id INTEGER PRIMARY KEY,
            target_fqn TEXT NOT NULL UNIQUE,
            level TEXT NOT NULL CHECK(level IN ('method', 'class', 'package', 'module')),
            summary TEXT NOT NULL,
            vector_id TEXT,
            is_stale BOOLEAN DEFAULT FALSE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (target_fqn) REFERENCES symbols(fqn) ON DELETE CASCADE
        )
    """)

def _create_glossary_table(cursor: sqlite3.Cursor) -> None:
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS glossary (
            id INTEGER PRIMARY KEY,
            code_term TEXT NOT NULL,
            business_meaning TEXT NOT NULL,
            synonyms TEXT,
            source_fqn TEXT,
            vector_id TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (source_fqn) REFERENCES symbols(fqn) ON DELETE SET NULL
        )
    """)

def _create_constraints_table(cursor: sqlite3.Cursor) -> None:
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS constraints (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            constraint_type TEXT NOT NULL,
            description TEXT NOT NULL,
            source_fqn TEXT,
            severity TEXT,
            vector_id TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (source_fqn) REFERENCES symbols(fqn) ON DELETE SET NULL
        )
    """)
```

**Migration Script:**
```python
def migrate_add_foreign_keys(db_path: str) -> None:
    """Add foreign key constraints to existing database."""
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON")

    # SQLite doesn't support ALTER TABLE ADD CONSTRAINT
    # Need to recreate tables
    tables_to_migrate = ["summaries", "glossary", "constraints"]

    for table in tables_to_migrate:
        # 1. Rename old table
        conn.execute(f"ALTER TABLE {table} RENAME TO {table}_old")

        # 2. Create new table with FK
        if table == "summaries":
            _create_summaries_table(conn.cursor())
        # ... etc

        # 3. Copy data
        conn.execute(f"""
            INSERT INTO {table} SELECT * FROM {table}_old
        """)

        # 4. Drop old table
        conn.execute(f"DROP TABLE {table}_old")

    conn.commit()
    conn.close()
```

### Solution 2: Application-Level Enforcement

**Approach:** Keep schema as-is and add application-level cleanup

**Pros:**
- No schema migration
- More control over deletion behavior

**Cons:**
- No database enforcement
- Easy to miss cleanup
- Risk of orphaned data

**Effort:** Medium
**Risk:** High

### Solution 3: Use Triggers for Cleanup

**Approach:** Create SQL triggers to delete related records

**Pros:**
- Database-enforced cleanup
- Can add custom logic

**Cons:**
- More complex than FK
- Still requires migration
- Less standard than FK

**Effort:** Medium
**Risk:** Low

## Recommended Action

**Use Solution 1 (Add Foreign Keys with CASCADE)**

Foreign keys are the standard SQL solution for referential integrity. The cascade behavior ensures automatic cleanup when symbols are deleted.

## Technical Details

### Files to Modify:
1. `ariadne_core/storage/schema.py` - Update table creation SQL
2. `ariadne_core/storage/sqlite_store.py` - Ensure `PRAGMA foreign_keys = ON` is set
3. Create migration script for existing databases

### Foreign Key Enforcement in SQLite:
```python
# In SQLiteStore.__init__
def __init__(self, db_path: str = "ariadne.db", init: bool = False) -> None:
    self.db_path = db_path
    self.conn = sqlite3.connect(db_path)
    self.conn.execute("PRAGMA foreign_keys = ON")  # CRITICAL!
    # ... rest of init
```

### Check Constraint for Summary Level:
Also add CHECK constraint for summary.level:
```sql
level TEXT NOT NULL CHECK(level IN ('method', 'class', 'package', 'module'))
```

### Migration Considerations:
- SQLite doesn't support `ALTER TABLE ADD CONSTRAINT`
- Must recreate tables to add constraints
- Data migration required for production databases
- Consider schema version tracking

## Acceptance Criteria

- [ ] Foreign key constraints added to all tables
- [ ] `PRAGMA foreign_keys = ON` set in SQLiteStore
- [ ] Cascade delete behavior verified
- [ ] CHECK constraint added for summary.level
- [ ] Migration script created and tested
- [ ] Schema version tracking implemented
- [ ] Tests verify cascade delete works
- [ ] Tests verify constraint violations raise errors
- [ ] Documentation updated with migration instructions

## Work Log

| Date | Action | Result |
|------|--------|--------|
| 2026-02-01 | Code review completed | Missing foreign keys identified |
| 2026-02-01 | Added FK constraints to schema | Added FOREIGN KEY constraints to summaries, glossary, constraints tables with CASCADE/SET NULL, plus CHECK constraint for summary.level |

## Resources

- **Files**: `ariadne_core/storage/schema.py`, `ariadne_core/storage/sqlite_store.py`
- **Related**: Todo #007 (SQLite-ChromaDB sync) - Related data integrity issue
- **Documentation**:
  - SQLite Foreign Keys: https://www.sqlite.org/foreignkeys.html
  - ALTER TABLE limitations: https://www.sqlite.org/lang_altertable.html
