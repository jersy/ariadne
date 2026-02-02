---
title: N+1 Query Pattern in Coverage Analysis
type: performance
priority: P2
status: pending
source: pr-review-5
severity: important
---

# N+1 Query Pattern in Coverage Analysis

## Problem

The `analyze_coverage()` method in `ariadne_core/storage/sqlite_store.py` contains an N+1 query pattern where `get_test_mapping()` is called inside a loop over caller symbols.

## Location

**File:** `ariadne_core/storage/sqlite_store.py:420-480`

## Current Implementation

```python
def analyze_coverage(self, fqn: str) -> dict[str, Any]:
    callers = self.get_callers(fqn)  # 1 query

    for caller in callers:
        # This is called for EACH caller - N queries!
        test_mapping = self.get_test_mapping(caller["caller_fqn"])
        # Process test_mapping...
```

## Performance Impact

- **Small projects (10 callers):** ~10-20x slower than optimized
- **Medium projects (100 callers):** Unacceptable latency
- **Large projects (1000+ callers):** May timeout or cause API failure

## Solution

### Option 1: Batch Query (Recommended)

Query all test mappings in a single database query:

```python
def analyze_coverage(self, fqn: str) -> dict[str, Any]:
    callers = self.get_callers(fqn)

    # Get all caller FQNs
    caller_fqns = [c["caller_fqn"] for c in callers]

    # Batch query all symbols at once
    symbols = self.get_symbols_by_fqns(caller_fqns)

    # Build lookup dict
    symbol_map = {s.fqn: s for s in symbols}

    # Process without additional queries
    for caller in callers:
        symbol = symbol_map.get(caller["caller_fqn"])
        is_test = self._is_test_file(symbol.file_path) if symbol else False
        # ...
```

### Option 2: Remove Redundant Calls

Since `get_callers()` already returns `file_path`, we can directly check:

```python
def analyze_coverage(self, fqn: str) -> dict[str, Any]:
    callers = self.get_callers(fqn)

    for caller in callers:
        # Direct check without additional query
        is_test = self._is_test_file(caller.get("file_path", ""))
        # ...
```

## Acceptance Criteria

- [ ] Single database query for coverage analysis regardless of caller count
- [ ] Response time < 500ms for 100 callers
- [ ] Response time < 2s for 1000 callers
- [ ] Unit tests added for batch query behavior
- [ ] Existing tests still pass

## References

- **Source:** PR #5 Review - Performance Oracle Agent
- **Related:** P2 #019 - N+1 Query Pattern in Impact Analyzer
- **Pattern:** docs/solutions/performance/n-plus-1-query-pattern.md
