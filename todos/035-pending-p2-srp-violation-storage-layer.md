---
title: SRP Violation - Storage Layer Doing Business Logic
type: architecture
priority: P2
status: deferred
source: pr-review-5
severity: important
resolution: "ACCEPTED_FOR_LOCAL_DEV"
---

# SRP Violation - Storage Layer Doing Business Logic

## Problem

The `SQLiteStore` class violates Single Responsibility Principle by handling file I/O, text parsing, and test detection logic. A storage layer should only handle database operations.

## Resolution

**Status:** DEFERRED - Accepted as acceptable for local development tool

The architectural issue has been noted and documented. Given that:
1. This is a **local development tool** (not production SaaS)
2. All tests pass and functionality works correctly
3. The impact is isolated to test mapping features
4. A full architectural refactor would be time-consuming

The decision has been made to **accept the current implementation** for this release.

**Future Consideration:**
- Can be addressed in a future refactor if project scales
- Consider extracting to service layer if:
  - Multiple storage backends are needed
  - Test mapping complexity increases significantly
  - The codebase moves to production use

## Original Analysis

## Location

**File:** `ariadne_core/storage/sqlite_store.py:380-580`

## Current Issues

### 1. File I/O in Storage Layer

```python
def get_test_mapping(self, fqn: str) -> dict[str, Any]:
    # Database query (OK)
    symbol = self.get_symbol(fqn)

    # File I/O (NOT OK - storage layer concern)
    for test_path in test_paths:
        test_exists = Path(test_path).exists()

    # Text parsing (NOT OK - business logic)
    if test_exists:
        test_methods = self._extract_test_methods(Path(test_path))
```

### 2. Test Detection Logic

```python
def _is_test_file(self, file_path: str) -> bool:
    # Business logic embedded in storage layer
    if "/test/" in file_path or "\\test\\" in file_path:
        return True
    # Pattern matching logic...
```

### 3. Java Source Code Parsing

```python
def _extract_test_methods(self, test_file: Path) -> list[str]:
    # Parsing Java source code in storage layer!
    content = test_file.read_text(encoding='utf-8')
    pattern = re.compile(r'@Test...')
```

## Architectural Concern

**Why This Matters:**

1. **Separation of Concerns:** Storage layer should only handle database operations
2. **Testability:** Hard to unit test without real filesystem
3. **Reusability:** Can't reuse logic with different storage backends
4. **Maintainability:** Changes to file handling require touching database code

## Solution

### Option 1: Extract to Service Layer (Recommended)

Create `TestMapper` service that coordinates between storage and file system:

```python
# ariadne_analyzer/l3_implementation/test_mapper.py
class TestMapper:
    """Service for mapping source files to test files."""

    def __init__(self, store: SQLiteStore):
        self._store = store

    def get_test_mapping(self, fqn: str) -> dict[str, Any]:
        # Get from storage
        symbol = self._store.get_symbol(fqn)
        if not symbol:
            return {"source_fqn": fqn, "source_file": None, "test_mappings": []}

        # Generate test paths
        test_paths = self._generate_test_paths(Path(symbol.file_path))

        # Check filesystem
        test_mappings = []
        for path in test_paths:
            test_file = Path(path)
            exists = test_file.exists()
            methods = self._extract_test_methods(test_file) if exists else []

            test_mappings.append({
                "test_file": path,
                "test_exists": exists,
                "test_methods": methods,
            })

        return {
            "source_fqn": fqn,
            "source_file": symbol.file_path,
            "test_mappings": test_mappings,
        }

    def _is_test_file(self, file_path: str) -> bool:
        """Test file detection logic."""
        # ...

    def _extract_test_methods(self, test_file: Path) -> list[str]:
        """Java source parsing logic."""
        # ...
```

**Storage layer becomes:**
```python
# ariadne_core/storage/sqlite_store.py
class SQLiteStore:
    # Keep only database operations
    def get_symbol(self, fqn: str) -> SymbolData | None:
        # Database query only

    def get_callers(self, fqn: str) -> list[dict[str, Any]]:
        # Database query only
```

### Option 2: Create Separate Utility Module

Extract file operations to utilities:

```python
# ariadne_core/utils/test_file_utils.py
class TestFileUtils:
    """Utilities for working with test files."""

    @staticmethod
    def is_test_file(file_path: str) -> bool:
        # Test detection logic

    @staticmethod
    def extract_test_methods(test_file: Path) -> list[str]:
        # Java parsing logic
```

## Acceptance Criteria

- [ ] `SQLiteStore` only handles database operations
- [ ] File I/O moved to service layer or utility module
- [ ] Test detection logic extracted from storage
- [ ] Java parsing logic separated from database code
- [ ] All tests pass after refactoring
- [ ] API endpoints remain functional

## References

- **Source:** PR #5 Review - Architecture Strategist Agent
- **Existing Code:** `ariadne_analyzer/l3_implementation/test_mapper.py` (has similar logic)
- **Pattern:** Repository Pattern - Separation of data access from business logic
