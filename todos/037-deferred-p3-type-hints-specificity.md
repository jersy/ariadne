---
title: Type Hints Lack Specificity
type: code-quality
priority: P3
status: pending
source: pr-review-5
severity: nice-to-have
---

# Type Hints Lack Specificity

## Problem

Return type annotations use generic `dict[str, Any]` instead of specific TypedDict or dataclass types, reducing type safety and IDE autocomplete quality.

## Location

**File:** `ariadne_core/storage/sqlite_store.py:380-450`

## Current Implementation

```python
def get_test_mapping(self, fqn: str) -> dict[str, Any]:
    """Get test file mappings for a source symbol."""
    # What fields are in this dict? Unknown without reading code.
    return {
        "source_fqn": fqn,
        "source_file": "...",
        "test_mappings": [...]
    }
```

## Impact

1. **No IDE Autocomplete:** Editors don't know what fields exist
2. **No Type Checking:** mypy can't verify correct field access
3. **Hidden Errors:** Typos in field names only caught at runtime
4. **Poor Documentation:** Must read code to understand structure

## Solution

### Option 1: TypedDict (Recommended)

```python
from typing import TypedDict

class TestMappingEntry(TypedDict):
    test_file: str
    test_exists: bool
    test_pattern: str
    test_methods: list[str]

class TestMappingResult(TypedDict):
    source_fqn: str
    source_file: str | None
    test_mappings: list[TestMappingEntry]

def get_test_mapping(self, fqn: str) -> TestMappingResult:
    """Get test file mappings for a source symbol."""
    # Now we have type safety!
    result: TestMappingResult = {
        "source_fqn": fqn,
        "source_file": symbol.file_path,
        "test_mappings": [...]
    }
    return result
```

### Option 2: Pydantic Model

```python
from pydantic import BaseModel

class TestMappingEntry(BaseModel):
    test_file: str
    test_exists: bool
    test_pattern: str
    test_methods: list[str]

class TestMappingResult(BaseModel):
    source_fqn: str
    source_file: str | None
    test_mappings: list[TestMappingEntry]

def get_test_mapping(self, fqn: str) -> TestMappingResult:
    """Get test file mappings for a source symbol."""
    return TestMappingResult(
        source_fqn=fqn,
        source_file=symbol.file_path,
        test_mappings=[...]
    )
```

### Option 3: Reuse API Schemas

```python
from ariadne_api.schemas.tests import TestMappingResponse

def get_test_mapping(self, fqn: str) -> TestMappingResponse:
    """Get test file mappings for a source symbol."""
    # Reuse existing schema!
    return TestMappingResponse(...)
```

## Acceptance Criteria

- [ ] Replace `dict[str, Any]` with TypedDict or Pydantic models
- [ ] All return types have specific type hints
- [ ] mypy type checking passes
- [ ] IDE autocomplete works for all fields
- [ ] No functional changes

## References

- **Source:** PR #5 Review - Kieran Python Reviewer Agent
- **Best Practice:** Python Type Hints - PEP 589 (TypedDict)
- **Related:** docs/solutions/python/type-hints-best-practices.md
