---
status: pending
priority: p3
issue_id: "041"
tags:
  - code-review
  - simplicity
  - dead-code
  - cleanup
dependencies: []
---

# Dead Code in sqlite_store.py

## Problem Statement

**Dead code found in sqlite_store.py** - unreachable lines after method end that duplicate existing functionality.

## What's Broken

**Location:** `ariadne_core/storage/sqlite_store.py` lines 988-990

```python
# Lines 988-990 - DEAD CODE (unreachable)
cursor = self.conn.cursor()
cursor.execute("SELECT COUNT(*) FROM glossary")
return cursor.fetchone()[0]
```

**Issue:** These lines appear after the method ends and are never executed. They duplicate the existing `get_glossary_count()` method.

## Impact

| Aspect | Impact |
|--------|--------|
| Code size | +3 LOC unnecessary |
| Maintenance | Confusing for readers |
| Correctness | None (unreachable) |

## Proposed Solution

Delete lines 988-990 from `sqlite_store.py`.

**Effort:** Trivial (2 minutes)

**Risk:** None

## Technical Details

**Affected Files:**
- `ariadne_core/storage/sqlite_store.py` lines 988-990

## Acceptance Criteria

- [ ] Lines 988-990 deleted
- [ ] All tests still pass

## Work Log

### 2026-02-02

**Issue discovered during:** Code Simplicity Reviewer

**Root cause:** Copy-paste error during development

**Status:** Pending
