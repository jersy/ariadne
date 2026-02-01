---
status: pending
priority: p2
issue_id: "013"
tags:
  - code-review
  - python
  - bug
  - llm-client
dependencies: []
---

# Static Method Missing @staticmethod Decorator

## Problem Statement

The `_should_retry()` method in `LLMClient` is defined as an instance method but called as a static method in the retry decorator. This will fail at runtime.

**Location:** `ariadne_llm/client.py:103`

## Why It Matters

1. **Runtime Failure**: Method is called as static but defined as instance method
2. **Incorrect Binding**: `self` parameter will receive the exception instead of being bound
3. **Silent Bug**: May not be caught until retry logic is actually triggered
4. **Test Coverage Gap**: Tests may not exercise retry paths

## Findings

### From Kieran Python Reviewer:

> **CRITICAL ISSUE**
>
> Static method missing @staticmethod decorator. Defined as instance method but called as static method in retry decorator. This will fail at runtime.

**Current Code:**
```python
# Line 103 - Missing @staticmethod!
def _should_retry(exception: Exception) -> bool:
    """Check if exception should trigger retry."""
    if isinstance(exception, RateLimitError):
        return True
    if isinstance(exception, (APIError, APIConnectionError)):
        return True
    return False
```

**How It's Called (incorrectly):**
```python
# Line 124-129 - retry decorator uses it as if it were static
@retry(
    stop=stop_after_attempt(MAX_RETRIES),
    wait=wait_exponential(multiplier=1, min=MIN_WAIT_SECONDS, max=MAX_WAIT_SECONDS),
    retry=retry_if_exception_type(Exception),
    reraise=True,
)
def _call_llm(self, prompt, system_prompt, max_tokens, temperature):
```

**Note:** Actually, the retry decorator uses `retry_if_exception_type(Exception)` which doesn't directly call `_should_retry()`. The method appears to be unused entirely. However, if it were used, it would need the decorator.

## Proposed Solutions

### Solution 1: Add @staticmethod Decorator (Recommended)

**Approach:** Make it a proper static method

**Pros:**
- Correct Python pattern
- Can be called without instance
- Clear intent

**Cons:**
- None

**Effort:** Very Low
**Risk:** Low

**Implementation:**
```python
@staticmethod
def _should_retry(exception: Exception) -> bool:
    """Check if exception should trigger retry."""
    if isinstance(exception, RateLimitError):
        return True
    if isinstance(exception, (APIError, APIConnectionError)):
        return True
    return False
```

### Solution 2: Make it a Class Method

**Approach:** Use @classmethod instead

**Pros:**
- Has access to class
- Can be overridden

**Cons:**
- Not needed for this use case
- Unnecessary complexity

**Effort:** Very Low
**Risk:** Low

### Solution 3: Remove Unused Method (Alternative)

**Approach:** Remove the method since it's not actually used

**Pros:**
- Removes dead code
- Cleaner codebase

**Cons:**
- May be intended for future use
- Loses retry customization capability

**Effort:** Very Low
**Risk:** Low

## Recommended Action

**Use Solution 1 (Add @staticmethod Decorator)**

Since the method is defined and may be used for custom retry logic in the future, add the decorator to make it correct. Alternatively, remove it if it's truly unused.

## Technical Details

### Files to Modify:
1. `ariadne_llm/client.py` - Add `@staticmethod` decorator to `_should_retry()`

### Lines Affected:
- Line 103: `def _should_retry(exception: Exception) -> bool:`

### Testing Required:
1. Verify method is actually used somewhere
2. If used, test retry behavior with different exception types
3. If unused, consider removal

## Acceptance Criteria

- [ ] `@staticmethod` decorator added to `_should_retry()`
- [ ] Test verifies method works correctly
- [ ] OR: Method removed if confirmed unused
- [ ] Code review verifies no other similar issues

## Work Log

| Date | Action | Result |
|------|--------|--------|
| 2026-02-01 | Code review completed | Static method missing decorator identified |

## Resources

- **Files**: `ariadne_llm/client.py`
- **Related**: None
- **Documentation**:
  - Python staticmethod: https://docs.python.org/3/library/functions.html#staticmethod
