---
status: pending
priority: p2
issue_id: "040"
tags:
  - code-review
  - performance
  - n-plus-one
  - database
dependencies: []
---

# N+1 Query in Incremental Coordinator

## Problem Statement

**N+1 query pattern in incremental coordinator database update loop** causes unnecessary database round-trips when updating multiple summaries.

## What's Broken

**Location:** `ariadne_analyzer/l1_business/incremental_coordinator.py` lines 268-296

```python
for fqn, summary_text in summaries.items():
    existing = self.store.get_summary(fqn)  # <-- N+1 QUERY!
```

**Impact:**
- For n summaries: n+1 individual SELECT queries
- At 100 summaries: ~101 database round-trips
- Estimated additional latency: 50-200ms

## Proposed Solution

Batch fetch all existing summaries before loop:

```python
# Single batch query
placeholders = ",".join("?" * len(summaries))
existing_summaries = cursor.execute(
    f"SELECT target_fqn, is_stale FROM summaries WHERE target_fqn IN ({placeholders})",
    list(summaries.keys())
).fetchall()

# Build lookup dict for O(1) access
fresh_summaries = {row[0]: row[1] for row in existing_summaries if not row[1]}
```

**Effort:** Small (30 minutes)

**Performance Gain:**
- 100 summaries: ~48-198ms saved
- 1000 summaries: ~498-1998ms saved

## Technical Details

**Affected Files:**
- `ariadne_analyzer/l1_business/incremental_coordinator.py`

**Database Changes:** None

## Acceptance Criteria

- [ ] Single batch query fetches all existing summaries
- [ ] O(1) in-memory lookup for each FQN
- [ ] Performance test shows < 10ms for 100 summaries

## Work Log

### 2026-02-02

**Issue discovered during:** Performance Oracle Review

**Pattern identified:** Classic N+1 anti-pattern in loop

**Status:** Pending
