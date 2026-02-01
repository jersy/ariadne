---
category: data-integrity
module: storage
symptoms:
  - Orphaned records when symbols deleted
  - No database-level referential integrity
  - Manual cleanup required
tags:
  - data-integrity
  - sqlite
  - schema
  - foreign-keys
---

# Missing Foreign Key Constraints

## Problem

The SQLite schema lacked foreign key constraints for critical relationships. Tables `summaries`, `glossary`, and `constraints` referenced `symbols(fqn)` but had no foreign key constraints, allowing orphaned records when symbols were deleted.

## Detection

```sql
-- ariadne_core/storage/schema.py (before)
CREATE TABLE IF NOT EXISTS summaries (
    id INTEGER PRIMARY KEY,
    target_fqn TEXT NOT NULL UNIQUE,
    level TEXT NOT NULL,
    summary TEXT NOT NULL,
    vector_id TEXT,
    is_stale BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    -- NO FOREIGN KEY to symbols!
);
```

## Risk Matrix

| Table | FK Status | Risk |
|-------|-----------|------|
| `entry_points.symbol_fqn` | Has FK to symbols | Safe |
| `external_dependencies.caller_fqn` | Has FK to symbols | Safe |
| `summaries.target_fqn` | **NO FK constraint** | HIGH - orphaned summaries |
| `glossary.source_fqn` | **NO FK constraint** | MEDIUM - orphaned entries |
| `constraints.source_fqn` | **NO FK constraint** | MEDIUM - orphaned constraints |

## Solution

### 1. Add Foreign Key Constraints

```sql
-- ariadne_core/storage/schema.py (after)
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
);

CREATE TABLE IF NOT EXISTS glossary (
    id INTEGER PRIMARY KEY,
    code_term TEXT NOT NULL UNIQUE,
    business_meaning TEXT NOT NULL,
    synonyms TEXT,
    source_fqn TEXT,
    vector_id TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (source_fqn) REFERENCES symbols(fqn) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS constraints (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    description TEXT NOT NULL,
    source_fqn TEXT,
    source_line INTEGER,
    constraint_type TEXT,
    vector_id TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (source_fqn) REFERENCES symbols(fqn) ON DELETE SET NULL
);
```

### 2. Enable Foreign Keys in SQLite

```python
# ariadne_core/storage/sqlite_store.py
def __init__(self, db_path: str = "ariadne.db", init: bool = False) -> None:
    self.db_path = db_path
    self.conn = sqlite3.connect(db_path)
    self.conn.execute("PRAGMA foreign_keys = ON")  # CRITICAL!
    # ... rest of init
```

### 3. Add CHECK Constraints

Also enforce valid values for `summary.level`:

```sql
level TEXT NOT NULL CHECK(level IN ('method', 'class', 'package', 'module'))
```

## Cascade Behavior

- **CASCADE** (`summaries.target_fqn`): Auto-delete summaries when symbol is deleted
- **SET NULL** (`glossary.source_fqn`, `constraints.source_fqn`): Clear reference but keep record

## Migration Notes

For existing databases, a migration script is required since SQLite doesn't support `ALTER TABLE ADD CONSTRAINT`:

```python
def migrate_add_foreign_keys(db_path: str) -> None:
    """Add foreign key constraints to existing database."""
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON")

    tables_to_migrate = ["summaries", "glossary", "constraints"]

    for table in tables_to_migrate:
        # 1. Rename old table
        conn.execute(f"ALTER TABLE {table} RENAME TO {table}_old")

        # 2. Create new table with FK
        # ... (use new schema)

        # 3. Copy data (only valid references)
        conn.execute(f"""
            INSERT INTO {table} SELECT * FROM {table}_old
        """)

        # 4. Drop old table
        conn.execute(f"DROP TABLE {table}_old")

    conn.commit()
    conn.close()
```

## Why This Matters

- **Orphaned data prevention**: Database enforces referential integrity
- **Automatic cleanup**: CASCADE deletes related records
- **Data quality**: CHECK constraints ensure valid enum values
- **Standard SQL**: Follows relational database best practices

## Files Changed

- `ariadne_core/storage/schema.py` - Added FOREIGN KEY constraints to SCHEMA_L1
- `ariadne_core/storage/sqlite_store.py` - Ensure `PRAGMA foreign_keys = ON` is set

## Related

- Todo #008: Missing foreign key constraints
- Todo #007: SQLite-ChromaDB synchronization (related)
- SQLite Foreign Keys: https://www.sqlite.org/foreignkeys.html
