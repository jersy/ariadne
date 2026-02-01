---
status: pending
priority: p1
issue_id: "018"
tags:
  - code-review
  - data-integrity
  - database
  - critical
dependencies: []
---

# Missing Cascade Delete Rules: Orphaned Edges Risk

## Problem Statement

The database schema defines foreign key constraints but **lacks critical cascade behaviors**. When symbols are deleted, edges referencing them become **orphaned**, causing query inconsistencies and graph corruption.

**Current Schema (from plan):**
```sql
CREATE TABLE edges (
    id INTEGER PRIMARY KEY,
    from_fqn TEXT NOT NULL,
    to_fqn TEXT NOT NULL,
    relation TEXT NOT NULL,
    metadata TEXT,
    FOREIGN KEY (from_fqn) REFERENCES symbols(fqn),
    FOREIGN KEY (to_fqn) REFERENCES symbols(fqn)
);
```

**Missing Safeguards:**
- No `ON DELETE CASCADE` - edges remain when symbols deleted
- No `ON UPDATE CASCADE` - edges break if FQNs change
- No soft delete pattern - graph history lost

**Failure Scenario:**
```
Time 1: Symbol "com.example.OldService" exists with 100 edges
Time 2: Class renamed during refactoring
Time 3: Symbol deleted and replaced with "com.example.NewService"
Time 4: 100 edges now reference non-existent FQNs
Time 5: Graph queries return incomplete/incorrect results
```

## Why It Matters

1. **Graph Corruption**: Orphaned edges pollute the call graph
2. **Query Errors**: Traversals hit missing nodes, return incomplete results
3. **Silent Failure**: No error raised, just wrong data
4. **Impact Analysis Broken**: Can't trace true call paths
5. **Data Quality Degrades**: Accumulates over time

## Findings

### From Data Integrity Guardian Review:

> **Severity:** CRITICAL
>
> Foreign key constraints are defined but lack cascade behaviors. If a symbol is deleted, edges referencing it become orphaned. No cleanup mechanism exists.

### From Implementation Review:

> **Observation:** Impact analyzer may fail or return incorrect results when traversing orphaned edges.

### Affected Schema Elements:

| Table | Foreign Key | Missing Behavior |
|-------|-------------|------------------|
| `edges` | `from_fqn → symbols.fqn` | ON DELETE CASCADE |
| `edges` | `to_fqn → symbols.fqn` | ON DELETE CASCADE |
| `entry_points` | `symbol_fqn → symbols.fqn` | ON DELETE CASCADE |
| `external_dependencies` | `caller_fqn → symbols.fqn` | ON DELETE CASCADE |
| `summaries` | `target_fqn → symbols.fqn` | ON DELETE CASCADE |
| `glossary` | `source_fqn → symbols.fqn` | ON DELETE CASCADE |
| `constraints` | `source_fqn → symbols.fqn` | ON DELETE CASCADE |

### Orphan Detection Query:

```sql
-- Current orphaned edges (should return 0, but likely returns many)
SELECT e.id, e.from_fqn, e.to_fqn, e.relation
FROM edges e
LEFT JOIN symbols s_from ON e.from_fqn = s_from.fqn
LEFT JOIN symbols s_to ON e.to_fqn = s_to.fqn
WHERE s_from.fqn IS NULL OR s_to.fqn IS NULL;
```

## Proposed Solutions

### Solution 1: Add ON DELETE CASCADE (Recommended for Production)

**Approach:** Modify foreign keys to automatically clean up dependent records.

**Pros:**
- Automatic cleanup
- Database-enforced integrity
- Simple and reliable

**Cons:**
- Loses historical data (edges deleted with symbol)
- May need application logic to preserve history

**Effort:** Low
**Risk:** Low

**Schema Migration:**
```sql
-- SQLite doesn't support ALTER CONSTRAINT directly
-- Need to recreate tables

-- 1. Create new edges table with CASCADE
CREATE TABLE edges_new (
    id INTEGER PRIMARY KEY,
    from_fqn TEXT NOT NULL,
    to_fqn TEXT NOT NULL,
    relation TEXT NOT NULL,
    metadata TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (from_fqn) REFERENCES symbols(fqn) ON DELETE CASCADE,
    FOREIGN KEY (to_fqn) REFERENCES symbols(fqn) ON DELETE CASCADE
);

CREATE INDEX idx_edges_new_from ON edges_new(from_fqn);
CREATE INDEX idx_edges_new_to ON edges_new(to_fqn);
CREATE INDEX idx_edges_new_relation ON edges_new(relation);

-- 2. Copy existing data (filtering orphans)
INSERT INTO edges_new (id, from_fqn, to_fqn, relation, metadata)
SELECT e.id, e.from_fqn, e.to_fqn, e.relation, e.metadata
FROM edges e
INNER JOIN symbols s_from ON e.from_fqn = s_from.fqn
INNER JOIN symbols s_to ON e.to_fqn = s_to.fqn;

-- 3. Drop old table and rename
DROP TABLE edges;
ALTER TABLE edges_new RENAME TO edges;

-- 4. Repeat for other tables
-- entry_points, external_dependencies, summaries, glossary, constraints
```

### Solution 2: Soft Delete with History Preservation

**Approach:** Add `deleted_at` column instead of deleting, preserve graph history.

**Pros:**
- Preserves historical graph structure
- Can analyze code evolution over time
- No data loss

**Cons:**
- More complex queries (always filter WHERE deleted_at IS NULL)
- Larger database size
- Need cleanup policy for old records

**Effort:** Medium
**Risk:** Medium

**Schema Changes:**
```sql
-- Add soft delete column
ALTER TABLE symbols ADD COLUMN deleted_at TIMESTAMP;

-- Update indexes to include deleted filter
CREATE INDEX idx_symbols_active ON symbols(fqn) WHERE deleted_at IS NULL;

-- Update queries to filter deleted
-- All queries must include: WHERE deleted_at IS NULL
```

### Solution 3: Application-Level Cascade with Triggers

**Approach:** Use database triggers to log deletions and clean up manually.

**Pros:**
- Full control over cascade behavior
- Can log before deletion
- Can implement custom business logic

**Cons:**
- More complex implementation
- Performance overhead
- Trigger maintenance burden

**Effort:** High
**Risk:** Medium

## Recommended Action

**Use Solution 1 (ON DELETE CASCADE) with Solution 2 (Soft Delete) for Migration Period**

1. **Immediate**: Add CASCADE to prevent further orphan accumulation
2. **Short-term**: Implement soft delete for audit trail
3. **Long-term**: Consider separate `graph_history` table for archival

## Technical Details

### Migration Script:

```python
# migrations/002_add_cascade_deletes.py
def upgrade():
    """Add ON DELETE CASCADE to all foreign keys"""

    with sqlite_store.transaction():
        # Migrate edges table
        _migrate_table_with_cascade(
            table_name="edges",
            foreign_keys=[
                ("from_fqn", "symbols(fqn)", "CASCADE"),
                ("to_fqn", "symbols(fqn)", "CASCADE")
            ]
        )

        # Migrate entry_points table
        _migrate_table_with_cascade(
            table_name="entry_points",
            foreign_keys=[
                ("symbol_fqn", "symbols(fqn)", "CASCADE")
            ]
        )

        # Migrate external_dependencies table
        _migrate_table_with_cascade(
            table_name="external_dependencies",
            foreign_keys=[
                ("caller_fqn", "symbols(fqn)", "CASCADE")
            ]
        )

        # Migrate summaries, glossary, constraints tables
        # ... similar pattern

def _migrate_table_with_cascade(table_name, foreign_keys):
    """Recreate table with CASCADE foreign keys"""

    # 1. Get existing schema
    existing_schema = _get_table_schema(table_name)

    # 2. Create new table with CASCADE
    new_table_name = f"{table_name}_new"
    create_sql = _generate_create_sql_with_cascade(
        new_table_name,
        existing_schema,
        foreign_keys
    )
    execute(create_sql)

    # 3. Copy valid data (no orphans)
    copy_sql = _generate_copy_sql(table_name, new_table_name, foreign_keys)
    execute(copy_sql)

    # 4. Report orphaned count
    orphaned_count = _count_orphaned(table_name, new_table_name)
    if orphaned_count > 0:
        logger.warning(f"Removed {orphaned_count} orphaned records from {table_name}")

    # 5. Atomic swap
    execute(f"DROP TABLE {table_name}")
    execute(f"ALTER TABLE {new_table_name} RENAME TO {table_name}")
```

### Orphan Cleanup Query (Before Migration):

```sql
-- Identify all orphaned records across all tables

-- Orphaned edges (from side)
SELECT 'edge_from' as type, COUNT(*) as count
FROM edges e
LEFT JOIN symbols s ON e.from_fqn = s.fqn
WHERE s.fqn IS NULL
UNION ALL
-- Orphaned edges (to side)
SELECT 'edge_to', COUNT(*)
FROM edges e
LEFT JOIN symbols s ON e.to_fqn = s.fqn
WHERE s.fqn IS NULL
UNION ALL
-- Orphaned entry_points
SELECT 'entry_point', COUNT(*)
FROM entry_points ep
LEFT JOIN symbols s ON ep.symbol_fqn = s.fqn
WHERE s.fqn IS NULL
UNION ALL
-- Orphaned external_dependencies
SELECT 'external_dep', COUNT(*)
FROM external_dependencies ed
LEFT JOIN symbols s ON ed.caller_fqn = s.fqn
WHERE s.fqn IS NULL
UNION ALL
-- Orphaned summaries
SELECT 'summary', COUNT(*)
FROM summaries sum
LEFT JOIN symbols s ON sum.target_fqn = s.fqn
WHERE s.fqn IS NULL
UNION ALL
-- Orphaned glossary
SELECT 'glossary', COUNT(*)
FROM glossary g
LEFT JOIN symbols s ON g.source_fqn = s.fqn
WHERE s.fqn IS NULL
UNION ALL
-- Orphaned constraints
SELECT 'constraint', COUNT(*)
FROM constraints c
LEFT JOIN symbols s ON c.source_fqn = s.fqn
WHERE s.fqn IS NULL;
```

### Files to Modify:

1. **`ariadne_core/storage/schema.py`** - Update CREATE TABLE statements
2. **`migrations/`** - NEW: Add migration directory
3. **`migrations/002_add_cascade_deletes.py`** - NEW: Migration script
4. **`tests/unit/test_schema.py`** - NEW: Test cascade behavior
5. **`tests/integration/test_deletion.py`** - NEW: Test deletion scenarios

## Acceptance Criteria

- [ ] Migration script created and tested
- [ ] All foreign keys have ON DELETE CASCADE
- [ ] Existing orphaned records cleaned up
- [ ] Test: Deleting symbol removes all dependent records
- [ ] Test: Renaming symbol (delete + insert) works cleanly
- [ ] Test: Foreign key violation raised for invalid references
- [ ] Documentation updated with deletion behavior
- [ ] Performance impact of cascade measured (< 100ms for 1K edges)

## Work Log

| Date | Action | Result |
|------|--------|--------|
| 2026-02-02 | Plan review completed | Missing cascade deletes identified |
| | | |

## Resources

- **Affected Files**:
  - `ariadne_core/storage/schema.py`
  - Plan document Section: "存储 Schema 设计"
- **Related Issues**:
  - Issue 016: Dual-Write Consistency (related data integrity)
  - Issue 017: Rebuild Data Loss Risk
- **SQLite Documentation**:
  - Foreign Key Constraints: https://www.sqlite.org/foreignkeys.html
  - ON DELETE CASCADE: https://www.sqlite.org/lang_createtable.html#fk_def_action
- **Documentation**:
  - Plan Section: SQLite 表结构 (lines 296-413)
