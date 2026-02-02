---
title: Uncached Regex Compilation in Test Mapper
type: performance
priority: P2
status: pending
source: pr-review-5
severity: important
---

# Uncached Regex Compilation in Test Mapper

## Problem

Regular expression patterns are recompiled on every method call instead of being cached as class constants. This causes unnecessary CPU overhead.

## Location

**File:** `ariadne_core/storage/sqlite_store.py:520-560`

## Current Implementation

```python
def _extract_test_methods(self, test_file: Path) -> list[str]:
    if not test_file.exists():
        return []

    # Pattern recompiled on EVERY call
    pattern = re.compile(r'@Test\s*\(\s*\)|^\s*(public|private|protected)?\s*+\s*\w+\s+test\w+\s*\(')

    # ... rest of method
```

## Performance Impact

- **Per-call overhead:** ~2-5x slower than cached version
- **Impact:** Compounds with N+1 query issue
- **Cumulative effect:** Significant for large test files

## Solution

Pre-compile regex patterns as class-level constants:

```python
class SQLiteStore:
    """SQLite storage backend with cached regex patterns."""

    # Pre-compiled regex patterns (class constants)
    _TEST_METHOD_PATTERN = re.compile(
        r'@Test\s*\(\s*\)|^\s*(public|private|protected)?\s*+\s*\w+\s+test\w+\s*\('
    )
    _PACKAGE_PATTERN = re.compile(r'^package\s+([\w.]+);')
    _CLASS_PATTERN = re.compile(r'^\s*(public\s+)?(class|interface|enum)\s+(\w+)')

    def _extract_test_methods(self, test_file: Path) -> list[str]:
        if not test_file.exists():
            return []

        # Use cached pattern
        content = test_file.read_text(encoding='utf-8')
        matches = self._TEST_METHOD_PATTERN.findall(content)

        return [self._extract_method_name(line) for line in matches]
```

## Acceptance Criteria

- [ ] All regex patterns defined as class constants
- [ ] Benchmark shows 2-5x performance improvement
- [ ] Existing tests still pass
- [ ] No functional changes to behavior

## References

- **Source:** PR #5 Review - Performance Oracle Agent
- **Best Practice:** Python regex compilation caching
- **Related:** docs/solutions/performance/regex-pattern-caching.md
