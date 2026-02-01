---
category: resource-management
module: llm-client
symptoms:
  - ThreadPoolExecutor not closed
  - Resource leak in long-running processes
  - No cleanup mechanism
tags:
  - resource-leak
  - threadpool
  - llm
  - context-manager
---

# ThreadPoolExecutor Leak in LLMClient

## Problem

`LLMClient` created a `ThreadPoolExecutor` in `__init__` but never closed it. In long-running processes or repeated instantiations, this caused thread pool accumulation and resource leaks.

## Detection

```python
# ariadne_llm/client.py (before)
class LLMClient:
    def __init__(self, ...):
        self._executor = ThreadPoolExecutor(max_workers=5)
    # No close() method!
    # No context manager support!
```

## Solution

### 1. Add Close Method

```python
class LLMClient:
    def __init__(self, ...):
        self._executor = ThreadPoolExecutor(max_workers=5)

    def close(self) -> None:
        """Clean up resources."""
        if self._executor:
            self._executor.shutdown(wait=True)
```

### 2. Add Context Manager Support

```python
def __enter__(self) -> "LLMClient":
    return self

def __exit__(self, *args: Any) -> None:
    self.close()
```

### 3. Apply to HierarchicalSummarizer

Same pattern for `HierarchicalSummarizer` in `ariadne_analyzer/l1_business/summarizer.py`.

## Usage

### Before (Leaky)

```python
client = LLMClient(provider=LLMProvider.DEEPSEEK, api_key="...")
client.generate_summary(code, context)
# Executor never closed!
```

### After (Clean)

```python
# Option 1: Context manager (recommended)
with LLMClient(provider=LLMProvider.DEEPSEEK, api_key="...") as client:
    client.generate_summary(code, context)
# Executor automatically closed

# Option 2: Manual cleanup
client = LLMClient(provider=LLMProvider.DEEPSEEK, api_key="...")
try:
    client.generate_summary(code, context)
finally:
    client.close()
```

## Why This Matters

- **Thread exhaustion**: Unclosed executors accumulate threads
- **Memory leak**: Each thread holds stack memory
- **FD exhaustion**: Threads hold file descriptors
- **Clean shutdown**: Ensures proper process termination

## Testing

```python
def test_context_manager_cleanup():
    with LLMClient(provider=LLMProvider.DEEPSEEK, api_key="test") as client:
        assert client._executor is not None
    # Executor should be shut down after context
    assert client._executor._shutdown is True
```

## Files Changed

- `ariadne_llm/client.py` - Added `close()`, `__enter__()`, `__exit__()`
- `ariadne_analyzer/l1_business/summarizer.py` - Same pattern for HierarchicalSummarizer

## Related

- Todo #002: ThreadPoolExecutor resource leak
- PEP 343: The "with" Statement
- Resource Management: Context managers pattern
