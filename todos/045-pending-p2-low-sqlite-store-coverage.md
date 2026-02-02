---
status: pending
priority: p2
issue_id: "045"
tags:
  - code-review
  - test-coverage
  - database
  - sqlite-store
dependencies: []
---

# P2: Low Test Coverage on sqlite_store (27%)

## Problem Statement

**sqlite_store.py has only 27% test coverage** - Critical database layer with 319/439 lines untested.

## What's Missing

**File:** `ariadne_core/storage/sqlite_store.py` (439 lines)

**Coverage:** 27.33% (129/439 lines covered)

**Uncovered Areas (from coverage report):**
- Lines 50, 97, 166, 192, 202-204, 226, 241, 259, 364, 381, 395-396, 404, 409-411, 420, 439, 448-454, 459-461, 469-479, 487-499, 503-508, 515, 518, 553-562, 570-575, 589, 612-627, 638-643, 652-657, 668-670, 674-676, 688-699, 710-713, 724-731, 742-744, 753-758, 762-764, 776-788, 799-802, 813-815, 826-828, 839-846, 855-860, 864-866, 896-933, 949-974, 987-1015, 1037-1071, 1085-1109, 1122-1138, 1152-1207, 1231-1250

**Specific Missing Tests:**
- `batch_create_summaries()` method (lines 600-628) - Phase 4.1 feature
- `get_summary()` with level parameter
- `mark_summary_stale()` method
- `mark_summaries_stale()` batch method
- `get_stale_summaries()` method
- `update_summary_vector_id()` method
- Glossary-related methods
- Job queue operations
- Vector sync state methods

## Impact

| Aspect | Impact |
|--------|--------|
| Risk | High - core database operations untested |
| Regression | Cannot detect bugs in database layer |
| Confidence | Low in database operations |
| Coverage | sqlite_store.py only 27% covered |

## Proposed Solutions

### Solution A: Add targeted tests for missing methods

Add tests to `tests/unit/test_sqlite_store.py` for each uncovered method:

```python
class TestBatchCreateSummaries:
    # Tests for batch_create_summaries()

class TestSummaryOperations:
    def test_get_summary_with_level(self)
    def test_mark_summary_stale(self)
    def test_mark_summaries_stale_batch(self)
    def test_get_stale_summaries(self)
    def test_update_summary_vector_id(self)

class TestGlossaryOperations:
    # Tests for glossary methods

class TestJobQueueOperations:
    # Tests for job queue methods

class TestVectorSync:
    # Tests for vector_sync_state methods
```

**Pros:**
- Targeted improvement
- Focuses on high-risk areas
- Incremental progress

**Cons:**
- Still leaves some gaps
- Requires prioritization

**Effort:** Medium (2-3 hours)

**Risk:** None

### Solution B: Run pytest with --cov to generate full report

```bash
pytest --cov=ariadne_core.storage.sqlite_store --cov-report=html
```

Then systematically add tests for all uncovered lines.

**Pros:**
- Comprehensive coverage
- Clear visibility into gaps

**Cons:**
- More time-consuming
- May test implementation details

**Effort:** Large (4-6 hours)

**Risk:** None

## Affected Files

- `ariadne_core/storage/sqlite_store.py` - 439 lines, 27% coverage
- `tests/unit/test_sqlite_store.py` - needs more tests

## Acceptance Criteria

- [ ] Coverage increased to at least 60%
- [ ] All public methods have at least one test
- [ ] All Phase 4.1 methods tested (batch_create_summaries)
- [ ] All critical database operations tested
- [ ] No regressions in existing tests

## Work Log

### 2026-02-02

**Issue discovered during:** Test coverage review

**Root cause:** Tests not kept up with code additions

**Status:** Pending test implementation
