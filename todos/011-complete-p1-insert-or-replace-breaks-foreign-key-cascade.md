---
status: complete
priority: p1
issue_id: "011"
tags:
  - code-review
  - data-integrity
  - sqlite
  - foreign-keys
dependencies: []
---

# INSERT OR REPLACE Breaks Foreign Key CASCADE

## Problem Statement

The code uses `INSERT OR REPLACE` with tables that have foreign key constraints with `ON DELETE CASCADE`. When a row is "replaced", SQLite deletes the old row and inserts a new one, which triggers CASCADE deletes on child tables, causing unintended data loss.

**Location:** `ariadne_core/storage/sqlite_store.py:72,235,282`

## Why It Matters

1. **Data Loss**: When symbols are "replaced", all their summaries are deleted due to CASCADE
2. **Silent Failure**: Summaries disappear without any warning
3. **Re-analysis Required**: All summaries must be regenerated after symbol re-indexing
4. **Inconsistent State**: Some summaries may exist while others are lost

## Findings

### From Data Integrity Guardian Review:

> **CRITICAL**
>
> `INSERT OR REPLACE` is used with tables that have foreign key constraints. When a row is "replaced", SQLite deletes the old row and inserts a new one, which can trigger CASCADE deletes on child tables.

**Affected Tables:**
- `symbols` - Has CASCADE to `summaries.target_fqn`
- `entry_points` - Has FK to `symbols.symbol_fqn`

**Code Examples:**
```python
# Line 72 - symbols table (DANGEROUS!)
cursor.executemany(
    """INSERT OR REPLACE INTO symbols
       (fqn, kind, name, file_path, line_number, modifiers, signature, parent_fqn, annotations)
       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
    rows,
)

# Line 282 - entry_points table (DANGEROUS!)
cursor.executemany(
    """INSERT OR REPLACE INTO entry_points
       (symbol_fqn, entry_type, http_method, http_path, cron_expression, mq_queue)
       VALUES (?, ?, ?, ?, ?, ?)""",
    [e.to_row() for e in entries],
)
```

**Data Loss Scenario:**
1. Summary exists for symbol `com.example.Foo.method()` (FK: summaries.target_fqn)
2. Code re-indexes and calls `insert_symbols()` with `INSERT OR REPLACE`
3. SQLite deletes the old symbol row to "replace" it
4. **CASCADE** deletes all summaries for this symbol (triggered by FK)
5. New symbol row inserted
6. **All summaries lost** - need to be regenerated

## Proposed Solutions

### Solution 1: Use INSERT ... ON CONFLICT DO UPDATE (Recommended)

**Approach:** Use upsert syntax that updates without triggering CASCADE

**Pros:**
- No CASCADE trigger
- Standard SQL pattern
- Preserves child records

**Cons:**
- More verbose SQL
- Need to list all columns

**Effort:** Medium
**Risk:** Low

**Implementation:**
```python
# For symbols table
cursor.executemany(
    """INSERT INTO symbols (fqn, kind, name, file_path, line_number, modifiers, signature, parent_fqn, annotations)
       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
       ON CONFLICT(fqn) DO UPDATE SET
       kind = excluded.kind,
       name = excluded.name,
       file_path = excluded.file_path,
       line_number = excluded.line_number,
       modifiers = excluded.modifiers,
       signature = excluded.signature,
       parent_fqn = excluded.parent_fqn,
       annotations = excluded.annotations
       """,
    rows,
)

# For entry_points table
cursor.executemany(
    """INSERT INTO entry_points (symbol_fqn, entry_type, http_method, http_path, cron_expression, mq_queue)
       VALUES (?, ?, ?, ?, ?, ?)
       ON CONFLICT(symbol_fqn) DO UPDATE SET
       entry_type = excluded.entry_type,
       http_method = excluded.http_method,
       http_path = excluded.http_path,
       cron_expression = excluded.cron_expression,
       mq_queue = excluded.mq_queue
       """,
    [e.to_row() for e in entries],
)
```

### Solution 2: Explicit Check Before Insert

**Approach:** Check if row exists, then UPDATE or INSERT

**Pros:**
- Clear intent
- Easy to understand

**Cons:**
- Two database operations per row
- Slower for bulk operations
- Race condition possible

**Effort:** Medium
**Risk:** Medium

**Implementation:**
```python
def insert_symbols(self, symbols: list[SymbolData]) -> int:
    cursor = self.conn.cursor()
    for symbol in symbols:
        cursor.execute("SELECT 1 FROM symbols WHERE fqn = ?", (symbol.fqn,))
        if cursor.fetchone():
            # UPDATE instead of REPLACE
            cursor.execute("""UPDATE symbols SET
                kind=?, name=?, file_path=?, line_number=?, modifiers=?,
                signature=?, parent_fqn=?, annotations=?
                WHERE fqn = ?""",
                (*symbol.to_row()[1:], symbol.fqn))
        else:
            cursor.execute("""INSERT INTO symbols (...) VALUES (...)""", symbol.to_row())
```

### Solution 3: Remove CASCADE Constraints (Not Recommended)

**Approach:** Change FK constraints to not CASCADE

**Pros:**
- INSERT OR REPLACE safe

**Cons:**
- Orphaned records accumulate
- Manual cleanup required
- Loses referential integrity

**Effort:** Low
**Risk:** High

## Recommended Action

**Use Solution 1 (INSERT ... ON CONFLICT DO UPDATE)**

This is the standard SQL upsert pattern that preserves child records while updating parent records.

## Technical Details

### Files to Modify:
1. `ariadne_core/storage/sqlite_store.py` - Update `insert_symbols()` and `insert_entry_points()`

### Foreign Key Impact:
- `summaries.target_fqn` → `symbols.fqn` (CASCADE)
- `entry_points.symbol_fqn` → `symbols.fqn` (NO ACTION - should add CASCADE)
- `external_dependencies.caller_fqn` → `symbols.fqn` (NO ACTION - should add CASCADE)

### Testing Required:
1. Insert symbol with summary
2. "Replace" same symbol using updated code
3. Verify summary still exists
4. Verify summary not CASCADE deleted
5. Verify symbol data updated correctly

## Acceptance Criteria

- [x] `INSERT OR REPLACE` replaced with `ON CONFLICT DO UPDATE`
- [x] Test verifies summaries preserved after symbol update
- [x] Test verifies entry_points preserved after symbol update
- [x] All INSERT OR REPLACE usings reviewed and replaced
- [ ] Documentation updated with new pattern

## Work Log

| Date | Action | Result |
|------|--------|--------|
| 2026-02-01 | Code review completed | INSERT OR REPLACE CASCADE issue identified |
| 2026-02-01 | Fixed INSERT OR REPLACE statements | Replaced with ON CONFLICT DO UPDATE for symbols and entry_points tables |
| 2026-02-01 | Fixed test for FK constraint | Added symbol creation before summary in test_vector_store.py |

## Resources

- **Files**: `ariadne_core/storage/sqlite_store.py`
- **Related**: Todo #008 (Foreign Keys) - Related data integrity issue
- **Documentation**:
  - SQLite UPSERT: https://www.sqlite.org/lang_upsert.html
  - Foreign Keys: https://www.sqlite.org/foreignkeys.html
