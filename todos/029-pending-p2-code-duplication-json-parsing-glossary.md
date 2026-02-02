---
status: completed
priority: p2
issue_id: "029"
tags:
  - code-review
  - code-quality
  - dry-violation
dependencies: []
---

# Code Duplication: JSON Parsing in Glossary API

## Problem Statement

The same JSON parsing logic for synonyms is duplicated 4 times in the glossary API routes, violating DRY (Don't Repeat Yourself) principle and making maintenance error-prone.

**Code Location:** `ariadne_api/routes/glossary.py` (lines 46-49, 91-94, 150-153, 177-180)

## Why It Matters

1. **Maintenance Burden**: Changes must be made in 4 places
2. **Bug Risk**: Fixes might be applied inconsistently
3. **Code Bloat**: Same logic repeated unnecessarily
4. **Poor Performance**: `import json` inside loops (atrocious)

## Findings

### From Pattern Recognition Review:

> **Severity:** MEDIUM
>
> The same JSON parsing logic is duplicated 4 times across the file, with `import json` appearing inside the loop.

### Root Cause:

```python
# ariadne_api/routes/glossary.py:46-49 (first occurrence)
try:
    import json  # ❌ Import inside loop!
    synonyms = json.loads(synonyms_json) if isinstance(synonyms_json, str) else synonyms_json
except Exception:
    synonyms = []

# Lines 91-94 (second occurrence)
try:
    import json  # ❌ Duplicated!
    synonyms = json.loads(synonyms_json) if isinstance(synonyms_json, str) else synonyms_json
except Exception:
    synonyms = []

# Lines 150-153 (third occurrence)
# Lines 177-180 (fourth occurrence)
# Same code repeated...
```

### Issues:

1. **Import inside loop**: `import json` executed on every request
2. **Bare except**: Swallows ALL errors including system errors
3. **Type confusion**: Doesn't validate result is actually a list
4. **4x duplication**: Same code in 4 different endpoints

## Proposed Solutions

### Solution 1: Extract Helper Function (Recommended)

**Approach:** Create a `parse_synonyms()` helper function.

**Pros:**
- Single source of truth
- Proper error handling
- Type-safe
- Testable in isolation

**Cons:**
- Adds one more function to file
- Minimal additional code

**Effort:** Low
**Risk:** Low

**Implementation:**
```python
# Add at top of file with other imports
import json
from typing import Any

def parse_synonyms(synonyms_json: Any) -> list[str]:
    """Parse synonyms from JSON storage.

    Handles both string JSON and pre-parsed lists.
    Returns empty list on any error or if input is None.

    Args:
        synonyms_json: Either a JSON string or a list

    Returns:
        List of synonym strings, empty list on error
    """
    # Handle None/empty input
    if not synonyms_json:
        return []

    # If already a list, validate and return
    if isinstance(synonyms_json, list):
        return synonyms_json if all(isinstance(s, str) for s in synonyms_json) else []

    # If string, try to parse JSON
    if isinstance(synonyms_json, str):
        try:
            parsed = json.loads(synonyms_json)
            if isinstance(parsed, list):
                return parsed if all(isinstance(s, str) for s in parsed) else []
        except (json.JSONDecodeError, TypeError, ValueError):
            pass

    # Fallback for any other type
    return []

# Then replace all 4 occurrences:
# OLD CODE:
# synonyms = []
# if synonyms_json:
#     try:
#         import json
#         synonyms = json.loads(synonyms_json) if isinstance(synonyms_json, str) else synonyms_json
#     except Exception:
#         synonyms = []

# NEW CODE:
synonyms = parse_synonyms(term_data.get("synonyms"))
```

### Solution 2: Handle in Domain Model

**Approach:** Move parsing logic to the `GlossaryTerm` domain model.

**Pros:**
- Parsing logic lives with data model
- API routes become simpler
- Reusable across different contexts

**Cons:**
- Requires model changes
- May not fit current architecture

**Effort:** Low
**Risk:** Low

**Implementation:**
```python
# ariadne_core/models/types.py
from dataclasses import dataclass
from typing import Any
import json

@dataclass
class GlossaryEntry:
    """Domain model for glossary entries."""
    code_term: str
    business_meaning: str
    synonyms: list[str]
    source_fqn: str | None = None
    examples: list[str] | None = None
    created_at: str | None = None

    @classmethod
    def from_db_row(cls, row: dict[str, Any]) -> "GlossaryEntry":
        """Create GlossaryEntry from database row."""
        # Parse synonyms from JSON
        synonyms = cls._parse_synonyms(row.get("synonyms"))

        return cls(
            code_term=row["code_term"],
            business_meaning=row["business_meaning"],
            synonyms=synonyms,
            source_fqn=row.get("source_fqn"),
            examples=[],  # Parse if needed
            created_at=row.get("created_at"),
        )

    @staticmethod
    def _parse_synonyms(synonyms_json: Any) -> list[str]:
        """Parse synonyms from JSON storage."""
        if not synonyms_json:
            return []
        if isinstance(synonyms_json, list):
            return synonyms_json
        if isinstance(synonyms_json, str):
            try:
                parsed = json.loads(synonyms_json)
                return parsed if isinstance(parsed, list) else []
            except (json.JSONDecodeError, TypeError):
                pass
        return []

# In API route
@router.get("/{code_term}")
async def get_glossary_term(code_term: str):
    term_data = store.get_glossary_term(code_term)
    if not term_data:
        raise HTTPException(status_code=404, detail=f"Term '{code_term}' not found")

    # Parse using domain model
    entry = GlossaryEntry.from_db_row(term_data)
    return GlossaryTerm(
        code_term=entry.code_term,
        business_meaning=entry.business_meaning,
        synonyms=entry.synonyms,
        # ...
    )
```

### Solution 3: Store as JSON in Pydantic Model

**Approach:** Use Pydantic's built-in JSON handling.

**Pros:**
- Leverages Pydantic validation
- Automatic parsing
- Type-safe

**Cons:**
- Requires schema changes
- May need database migration

**Effort:** Medium
**Risk:** Low

**Implementation:**
```python
# ariadne_api/schemas/glossary.py
from pydantic import BaseModel, Field
from typing import List

class GlossaryTerm(BaseModel):
    code_term: str
    business_meaning: str
    synonyms: List[str] = Field(default_factory=list)
    # ...

# In route, let Pydantic handle it
@router.get("/{code_term}")
async def get_glossary_term(code_term: str):
    term_data = store.get_glossary_term(code_term)
    if not term_data:
        raise HTTPException(status_code=404)

    # Pydantic automatically parses JSON
    return GlossaryTerm(**term_data)
```

## Recommended Action

**Use Solution 1 (Extract Helper Function)**

This is the simplest fix that immediately addresses the duplication. The helper function can be added to the glossary routes file and used in all 4 locations.

**Consider Solution 2** for a more architectural fix as part of a larger refactoring.

## Technical Details

### Files to Modify:

1. **`ariadne_api/routes/glossary.py`**
   - Add `parse_synonyms()` function at top of file
   - Replace all 4 occurrences of duplicated code
   - Move `import json` to top with other imports
   - Update all affected endpoints

### Code Changes:

**Locations to update:**
- Line 46-49: `list_glossary_terms()`
- Line 91-94: `get_glossary_term()`
- Line 150-153: `search_glossary()` (first result processing)
- Line 177-180: `search_glossary()` (second result processing)

### Testing Requirements:

```python
# tests/api/test_glossary.py
def test_parse_synonyms_from_json_string():
    """Test parsing JSON string of synonyms."""
    result = parse_synonyms('["synonym1", "synonym2"]')
    assert result == ["synonym1", "synonym2"]

def test_parse_synonyms_from_list():
    """Test parsing list of synonyms."""
    result = parse_synonyms(["synonym1", "synonym2"])
    assert result == ["synonym1", "synonym2"]

def test_parse_synonyms_invalid_json():
    """Test parsing invalid JSON returns empty list."""
    result = parse_synonyms('invalid json')
    assert result == []

def test_parse_synonyms_none():
    """Test parsing None returns empty list."""
    result = parse_synonyms(None)
    assert result == []

def test_parse_synonyms_non_list_json():
    """Test parsing JSON that's not a list returns empty list."""
    result = parse_synonyms('{"key": "value"}')
    assert result == []

def test_glossary_endpoints_use_helper():
    """Test all endpoints use the helper correctly."""
    # Create term with various synonym formats
    # Verify all endpoints parse correctly
```

## Acceptance Criteria

- [ ] `parse_synonyms()` helper function created
- [ ] All 4 occurrences of duplicated code replaced
- [ ] `import json` moved to top of file
- [ ] Unit tests for helper function
- [ ] All existing glossary API tests still pass
- [ ] No bare `except` clauses remain

## Work Log

| Date | Action | Result |
|------|--------|--------|
| 2026-02-02 | Code review completed | Duplication issue identified |
| | | |

## Resources

- **Affected Files:**
  - `ariadne_api/routes/glossary.py:46-49, 91-94, 150-153, 177-180`
- **Related Issues:**
  - Pattern Recognition Review: Finding #1 - JSON Parsing Duplication
  - Kieran Python Review: Finding #3 - Raw JSON Parsing
- **References:**
  - DRY principle documentation
  - Python import best practices
