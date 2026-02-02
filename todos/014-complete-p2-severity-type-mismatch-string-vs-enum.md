---
status: completed
priority: p2
issue_id: "014"
tags:
  - code-review
  - python
  - type-safety
  - anti-patterns
dependencies: []
---

# Severity Type Mismatch - String vs Enum

## Problem Statement

The `ControllerDaoRule.severity` property returns a string literal `"error"` but `AntiPatternData.severity` expects a `Severity` enum. This type mismatch will cause runtime errors or data inconsistencies.

**Location:** `ariadne_analyzer/l2_architecture/rules/controller_dao.py:25`

## Why It Matters

1. **Type Inconsistency**: Property declares `str` return type but should return `Severity`
2. **Runtime Errors**: Code expecting `Severity` enum may fail when receiving string
3. **Data Validation**: Can't validate severity values at type level
4. **Refactoring Risk**: Changing Severity enum values won't be caught

## Findings

### From Kieran Python Reviewer:

> **CRITICAL ISSUE**
>
> Type mismatch between string and Enum. `severity` property returns string literal but `AntiPatternData` expects `Severity` enum type.

**Current Code:**
```python
# controller_dao.py:25
@property
def severity(self) -> str:  # Returns string, but should return Severity
    return "error"

# But AntiPatternData expects:
# ariadne_core/models/types.py
@dataclass
class AntiPatternData:
    rule_id: str
    from_fqn: str
    to_fqn: str | None
    severity: Severity  # Enum type!
    message: str
    detected_at: str
```

**Severity Enum Definition:**
```python
class Severity(str, Enum):
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"
```

## Proposed Solutions

### Solution 1: Return Severity Enum (Recommended)

**Approach:** Change property to return `Severity` enum value

**Pros:**
- Type-safe
- Consistent with data model
- Validates values at type level

**Cons:**
- None

**Effort:** Very Low
**Risk:** Low

**Implementation:**
```python
# In controller_dao.py
from ariadne_core.models.types import Severity

class ControllerDaoRule(AntiPatternRule):
    @property
    def severity(self) -> Severity:
        return Severity.ERROR

# Or if severity should vary:
    @property
    def severity(self) -> Severity:
        return Severity.ERROR  # Or Severity.WARNING, etc.
```

### Solution 2: Change AntiPatternData to Accept String

**Approach:** Change data model to accept `str` instead of `Severity`

**Pros:**
- More flexible
- Allows custom severity values

**Cons:**
- Loses type safety
- Can't validate at type level
- Inconsistent with enum usage elsewhere

**Effort:** Medium
**Risk:** Medium

### Solution 3: Use String with Validation

**Approach:** Keep string but add validation in dataclass

**Pros:**
- Flexible but validated
- Backward compatible

**Cons:**
- More complex
- Still not type-safe

**Effort:** Medium
**Risk:** Low

## Recommended Action

**Use Solution 1 (Return Severity Enum)**

This maintains type safety and consistency with the data model. All anti-pattern rules should return `Severity` enum values.

## Technical Details

### Files to Modify:
1. `ariadne_analyzer/l2_architecture/rules/controller_dao.py` - Update `severity` property
2. Check other rule implementations for same issue

### Import Required:
```python
from ariadne_core.models.types import Severity
```

### All Rules Should Return Severity Enum:
- `ControllerDaoRule.severity` → `Severity.ERROR`
- Any other rules → Appropriate `Severity` value

### Testing Required:
1. Test rule detection returns correct data
2. Test severity value is `Severity` enum
3. Test enum can be compared and serialized correctly

## Acceptance Criteria

- [ ] `severity` property returns `Severity` enum
- [ ] Import added for `Severity` type
- [ ] All rules checked for same issue
- [ ] Tests verify type consistency
- [ ] Tests verify enum values work correctly

## Work Log

| Date | Action | Result |
|------|--------|--------|
| 2026-02-01 | Code review completed | Severity type mismatch identified |
| 2026-02-02 | Code verified | severity property already returns Severity.ERROR enum |
| 2026-02-02 | Verified complete | Issue already fixed |

## Resources

- **Files**: `ariadne_analyzer/l2_architecture/rules/controller_dao.py`, `ariadne_core/models/types.py`
- **Related**: None
- **Documentation**:
  - Python Enums: https://docs.python.org/3/library/enum.html
