---
status: complete
priority: p2
issue_id: "004"
tags:
  - code-review
  - python
  - async
  - performance
dependencies: []
---

# Async/Sync Mixing in batch_generate_summaries

## Problem Statement

The `batch_generate_summaries()` method in `LLMClient` has a confusing mix of synchronous and asynchronous patterns. It's a public synchronous method that internally uses `asyncio.run()` to execute async code, wrapping synchronous operations in an async context.

**Location:** `ariadne_llm/client.py:207-242`

```python
def batch_generate_summaries(
    self,
    items: list[dict[str, Any]],
    concurrent_limit: int = 5,
) -> list[str]:
    results = ["N/A"] * len(items)
    semaphore = asyncio.Semaphore(concurrent_limit)

    async def generate_one(index: int, item: dict[str, Any]) -> None:
        async with semaphore:
            loop = asyncio.get_event_loop()
            summary = await loop.run_in_executor(
                self._executor,
                self.generate_summary,
                item["code"],
                item.get("context"),
            )
            results[index] = summary

    async def generate_all() -> None:
        tasks = [
            generate_one(i, item) for i, item in enumerate(items)
        ]
        await asyncio.gather(*tasks)

    asyncio.run(generate_all())  # Blocking call from sync method
    return results
```

## Why It Matters

1. **Paradigm Confusion**: The API is sync but implementation is async, making it hard to understand
2. **Event Loop Creation**: `asyncio.run()` creates a new event loop each call, which is inefficient
3. **Testing Difficulty**: Mixed paradigms make mocking and testing more complex
4. **Unnecessary Complexity**: The current use case doesn't require async at all

## Findings

### From Kieran Python Reviewer:

> **HIGH PRIORITY ISSUE**
>
> **Problems:**
> 1. **Mixing paradigms**: Public API is sync, implementation is async
> 2. **Confusing intent**: Why not make the method async?
> 3. **Event loop creation**: `asyncio.run()` creates new event loop each call
>
> **Recommendation:** Choose ONE paradigm - either fully async or use thread pool

## Proposed Solutions

### Solution 1: Pure Thread Pool Implementation (Recommended)

**Approach:** Use `concurrent.futures.ThreadPoolExecutor` directly without async

**Pros:**
- Simpler, more straightforward
- No event loop overhead
- Easier to test and debug
- Consistent with rest of codebase (sync everywhere else)

**Cons:**
- Slightly less efficient than true async for I/O-bound work

**Effort:** Low
**Risk:** Low

**Implementation:**
```python
from concurrent.futures import ThreadPoolExecutor, as_completed

def batch_generate_summaries(
    self,
    items: list[dict[str, Any]],
    concurrent_limit: int = 5,
) -> list[str]:
    """Generate summaries for multiple items concurrently using thread pool."""
    if not items:
        return []

    results = {}

    with ThreadPoolExecutor(max_workers=concurrent_limit) as executor:
        # Submit all tasks
        futures = {
            executor.submit(
                self.generate_summary,
                item["code"],
                item.get("context"),
            ): i
            for i, item in enumerate(items)
        }

        # Collect results as they complete
        for future in as_completed(futures):
            index = futures[future]
            try:
                results[index] = future.result()
            except Exception as e:
                logger.error(f"Failed to generate summary for item {index}: {e}")
                results[index] = "N/A"

    # Return results in original order
    return [results.get(i, "N/A") for i in range(len(items))]
```

### Solution 2: Fully Async Implementation

**Approach:** Make the method async and expose async API

**Pros:**
- More efficient for I/O-bound operations
- Modern Python async pattern
- Better resource utilization

**Cons:**
- Requires async throughout the call chain
- More complex to use
- Inconsistent with rest of codebase (CLI is sync)

**Effort:** High
**Risk:** Medium

**Implementation:**
```python
async def batch_generate_summaries_async(
    self,
    items: list[dict[str, Any]],
    concurrent_limit: int = 5,
) -> list[str]:
    """Async version of batch_generate_summaries."""
    results = ["N/A"] * len(items)
    semaphore = asyncio.Semaphore(concurrent_limit)

    async def generate_one(index: int, item: dict[str, Any]) -> None:
        async with semaphore:
            # Call async LLM API
            summary = await self._generate_summary_async(...)
            results[index] = summary

    await asyncio.gather(*[generate_one(i, item) for i, item in enumerate(items)])
    return results

# Sync wrapper for backward compatibility
def batch_generate_summaries(self, items: list[dict[str, Any]], ...) -> list[str]:
    return asyncio.run(self.batch_generate_summaries_async(items, ...))
```

### Solution 3: Keep Current but Add Documentation

**Approach:** Document the async/sync bridge pattern explicitly

**Pros:**
- Minimal code changes
- Maintains current behavior

**Cons:**
- Doesn't address complexity
- Still confusing for users

**Effort:** Very Low
**Risk:** Low

## Recommended Action

**Use Solution 1 (Pure Thread Pool)**

The current use case doesn't require async. The LLM API calls are synchronous (`self.client.chat.completions.create`), so wrapping them in async is unnecessary complexity. A pure thread pool implementation is simpler, more testable, and more maintainable.

## Technical Details

### Files to Modify:
1. `ariadne_llm/client.py` - Rewrite `batch_generate_summaries()` to use thread pool
2. `tests/test_llm_client.py` - Update tests accordingly

### Current vs New Complexity:
- **Current**: ~35 lines with async/sync bridge
- **New**: ~25 lines with pure thread pool

### Performance Considerations:
- Thread pool overhead: ~1ms per thread
- Async overhead: ~0.1ms per coroutine
- For this use case (network I/O), difference is negligible

### Backward Compatibility:
- Function signature unchanged
- Return value unchanged
- Existing code will work without modification

## Acceptance Criteria

- [ ] `batch_generate_summaries()` rewritten with pure thread pool
- [ ] `asyncio` imports removed if no longer needed
- [ ] Tests updated to test concurrent behavior
- [ ] Tests verify error handling for individual failures
- [ ] Tests verify results returned in correct order
- [ ] Performance not degraded (verify with benchmarks)

## Work Log

| Date | Action | Result |
|------|--------|--------|
| 2026-02-01 | Code review completed | Async/sync mixing identified |
| 2026-02-01 | Rewrote batch_generate_summaries | Replaced asyncio with pure ThreadPoolExecutor for cleaner, more efficient concurrent processing |Async/sync mixing identified |

## Resources

- **Files**: `ariadne_llm/client.py`
- **Related**: Todo #002 (Resource Leak) - ThreadPoolExecutor also involved
- **Documentation**:
  - concurrent.futures: https://docs.python.org/3/library/concurrent.futures.html
  - asyncio vs threading: https://docs.python.org/3/library/asyncio.html
- **Discussion**: Python community generally advises against mixing async and sync without clear boundaries
