---
status: pending
priority: p2
issue_id: "012"
tags:
  - code-review
  - data-integrity
  - sqlite
  - schema
dependencies: []
---

# Missing Foreign Key on anti_patterns Table

## Problem Statement

The `anti_patterns` table references `from_fqn` and `to_fqn` (which should reference symbols) but has no foreign key constraints. This allows orphaned records when symbols are deleted, and permits invalid FQNs to be inserted.

**Location:** `ariadne_core/storage/schema.py:75-83`

## Why It Matters

1. **Orphaned Records**: Anti-pattern records remain after symbols are deleted
2. **Invalid References**: Can insert anti-patterns for non-existent symbols
3. **Data Inconsistency**: Query results may reference deleted symbols
4. **Navigation Errors**: UI attempts to navigate to non-existent symbols

## Findings

### From Data Integrity Guardian Review:

> **HIGH RISK**
>
> The `anti_patterns` table references `from_fqn` and `to_fqn` (which should be symbols) but has no foreign key constraints.

**Current Schema:**
```sql
-- Current (unsafe)
CREATE TABLE IF NOT EXISTS anti_patterns (
    id INTEGER PRIMARY KEY,
    rule_id TEXT NOT NULL,
    from_fqn TEXT NOT NULL,
    to_fqn TEXT,
    severity TEXT NOT NULL,
    message TEXT NOT NULL,
    detected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    -- NO FOREIGN KEYS!
);
```

**Comparison with Other Tables:**
| Table | FK Status | Risk |
|-------|-----------|------|
| `entry_points.symbol_fqn` | Has FK to symbols | Safe |
| `external_dependencies.caller_fqn` | Has FK to symbols | Safe |
| `summaries.target_fqn` | Has FK to symbols (FIXED) | Safe |
| `anti_patterns.from_fqn` | **NO FK constraint** | HIGH - orphaned records |
| `anti_patterns.to_fqn` | **NO FK constraint** | HIGH - orphaned records |

**Data Loss Scenario:**
1. Anti-pattern detected for `com.example.OrderService.process()`
2. `from_fqn = "com.example.OrderService.process"` stored in anti_patterns
3. Symbol `com.example.OrderService.process` deleted during refactoring
4. Anti-pattern record remains with orphaned reference
5. UI shows anti-pattern for non-existent symbol
6. Attempt to navigate to symbol fails
7. Data cleanup becomes manual process

## Proposed Solutions

### Solution 1: Add Foreign Keys with CASCADE (Recommended)

**Approach:** Add foreign key constraints to anti_patterns table

**Pros:**
- Database enforces referential integrity
- Automatic cleanup of related records
- Prevents orphaned data
- Standard SQL pattern

**Cons:**
- Requires schema migration
- May need to handle existing data

**Effort:** Medium
**Risk:** Low

**Implementation:**
```sql
CREATE TABLE IF NOT EXISTS anti_patterns (
    id INTEGER PRIMARY KEY,
    rule_id TEXT NOT NULL,
    from_fqn TEXT NOT NULL,
    to_fqn TEXT,
    severity TEXT NOT NULL CHECK(severity IN ('error', 'warning', 'info')),
    message TEXT NOT NULL,
    detected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (from_fqn) REFERENCES symbols(fqn) ON DELETE CASCADE,
    FOREIGN KEY (to_fqn) REFERENCES symbols(fqn) ON DELETE SET NULL
);
```

**Why CASCADE/SET NULL:**
- `from_fqn`: CASCADE - Anti-pattern is about the "from" symbol, so if it's deleted, remove the record
- `to_fqn`: SET NULL - The "to" symbol is optional context; keep the record but clear the reference

### Solution 2: Add Foreign Keys with RESTRICT

**Approach:** Add FK constraints that block deletes

**Pros:**
- Prevents accidental deletion
- Forces explicit cleanup

**Cons:**
- Blocks refactoring workflow
- Manual cleanup required before symbol deletion

**Effort:** Medium
**Risk:** Medium

### Solution 3: Application-Level Enforcement

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

## Recommended Action

**Use Solution 1 (Add Foreign Keys with CASCADE)**

Foreign keys are the standard SQL solution for referential integrity. The cascade behavior ensures automatic cleanup when symbols are deleted.

## Technical Details

### Files to Modify:
1. `ariadne_core/storage/schema.py` - Update `SCHEMA_L2` anti_patterns table definition
2. Create migration script for existing databases

### Migration Script:
```python
def migrate_add_anti_patterns_fks(db_path: str) -> None:
    """Add foreign key constraints to anti_patterns table."""
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON")

    # SQLite doesn't support ALTER TABLE ADD CONSTRAINT
    # Need to recreate table
    cursor = conn.cursor()

    # 1. Rename old table
    cursor.execute("ALTER TABLE anti_patterns RENAME TO anti_patterns_old")

    # 2. Create new table with FK
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS anti_patterns (
            id INTEGER PRIMARY KEY,
            rule_id TEXT NOT NULL,
            from_fqn TEXT NOT NULL,
            to_fqn TEXT,
            severity TEXT NOT NULL CHECK(severity IN ('error', 'warning', 'info')),
            message TEXT NOT NULL,
            detected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (from_fqn) REFERENCES symbols(fqn) ON DELETE CASCADE,
            FOREIGN KEY (to_fqn) REFERENCES symbols(fqn) ON DELETE SET NULL
        )
    """)

    # 3. Copy data (only valid references will be inserted)
    cursor.execute("""
        INSERT INTO anti_patterns
        SELECT * FROM anti_patterns_old
    """)

    # 4. Drop old table
    cursor.execute("DROP TABLE anti_patterns_old")

    conn.commit()
    conn.close()
```

### Also Add CHECK Constraint:
```sql
severity TEXT NOT NULL CHECK(severity IN ('error', 'warning', 'info'))
```

## Acceptance Criteria

- [ ] Foreign key constraints added to anti_patterns table
- [ ] CHECK constraint added for severity
- [ ] Migration script created and tested
- [ ] Tests verify cascade delete works
- [ ] Tests verify constraint violations raise errors
- [ ] Documentation updated with migration instructions

## Work Log

| Date | Action | Result |
|------|--------|--------|
| 2026-02-01 | Code review completed | Missing foreign keys on anti_patterns identified |

## Resources

- **Files**: `ariadne_core/storage/schema.py`
- **Related**:
  - Todo #008 (Foreign Keys) - Similar issue for L1 tables
  - Todo #011 (INSERT OR REPLACE) - Related data integrity issue
- **Documentation**:
  - SQLite Foreign Keys: https://www.sqlite.org/foreignkeys.html
  - ALTER TABLE limitations: https://www.sqlite.org/lang_altertable.html
