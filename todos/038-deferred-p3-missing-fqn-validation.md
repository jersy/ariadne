---
title: Missing FQN Validation in API Routes
type: code-quality
priority: P3
status: pending
source: pr-review-5
severity: nice-to-have
---

# Missing FQN Validation in API Routes

## Problem

API endpoints don't validate FQN (Fully Qualified Name) format before processing, which could lead to confusing error messages or unexpected behavior.

## Location

**File:** `ariadne_api/routes/tests.py:20-60`

## Current Implementation

```python
@router.get("/knowledge/tests/{fqn:path}")
async def get_test_mapping(fqn: str) -> TestMappingResponse:
    # No validation - any string accepted
    with get_store() as store:
        symbol = store.get_symbol(fqn)
        if not symbol:
            raise HTTPException(status_code=404, detail=f"Symbol not found: {fqn}")
        # ...
```

## Issues

1. **No Format Validation:** Accepts invalid inputs like `../../../etc/passwd`, ``, `   `
2. **Late Error Detection:** Errors only caught after database query
3. **Poor Error Messages:** Generic "not found" instead of specific validation error
4. **Wasted Resources:** Database query for obviously invalid inputs

## Valid FQN Format

**Java FQN pattern:** `com.example.package.ClassName$InnerClass`

- Must start with letter or underscore
- Package segments separated by `.`
- Class name follows PascalCase convention
- May contain inner classes with `$`
- No spaces, special characters (except `.` and `$`)

## Solution

### Add Validation Function

```python
# ariadne_api/utils/validation.py
import re

FQN_PATTERN = re.compile(
    r'^[a-zA-Z_][a-zA-Z0-9_]*'  # First segment
    r'(?:\.[a-zA-Z_][a-zA-Z0-9_]*)*'  # Additional segments
    r'(?:\$[A-Z][a-zA-Z0-9]*)*$'  # Inner classes (optional)
)

def is_valid_fqn(fqn: str) -> bool:
    """Validate FQN format."""
    if not fqn or not fqn.strip():
        return False
    return bool(FQN_PATTERN.match(fqn.strip()))

def validate_fqn(fqn: str) -> str:
    """Validate and normalize FQN, raise HTTPException if invalid."""
    if not is_valid_fqn(fqn):
        raise HTTPException(
            status_code=400,
            detail=f"Invalid FQN format: '{fqn}'. Expected format: 'com.example.ClassName'"
        )
    return fqn.strip()
```

### Update API Routes

```python
from ariadne_api.utils.validation import validate_fqn

@router.get("/knowledge/tests/{fqn:path}")
async def get_test_mapping(fqn: str) -> TestMappingResponse:
    """Get test file mappings for a source symbol."""
    # Validate before database query
    fqn = validate_fqn(fqn)

    with get_store() as store:
        symbol = store.get_symbol(fqn)
        # ...
```

### Add Pydantic Model for Query Parameters

```python
from pydantic import BaseModel, field_validator

class CoverageQuery(BaseModel):
    target: str

    @field_validator('target')
    @classmethod
    def validate_fqn(cls, v: str) -> str:
        if not is_valid_fqn(v):
            raise ValueError(f"Invalid FQN format: '{v}'")
        return v.strip()

@router.get("/knowledge/coverage")
async def get_coverage_analysis(
    target: str = Query(..., description="Target symbol FQN to analyze"),
) -> CoverageAnalysisResponse:
    # Validation via Pydantic
    query = CoverageQuery(target=target)
    # ...
```

## Acceptance Criteria

- [ ] FQN validation function added
- [ ] API routes validate FQN before database query
- [ ] Proper HTTP 400 error for invalid FQN format
- [ ] Unit tests for validation function
- [ ] Integration tests for API validation
- [ ] Error messages include FQN format examples

## References

- **Source:** PR #5 Review - Kieran Python Reviewer Agent
- **Pattern:** Input validation at API boundary
- **Best Practice:** Fail fast with clear error messages
