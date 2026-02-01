---
status: pending
priority: p3
issue_id: "006"
tags:
  - code-review
  - performance
  - vector-search
dependencies: []
---

# Zero Vector Fallback in embed_texts()

## Problem Statement

When empty text is passed to `embed_texts()`, the method returns zero vectors (`[0.0, 0.0, ...]`). These zero vectors pollute the semantic search space and may cause unexpected search results.

**Location:** `ariadne_llm/embedder.py:188-195`

```python
# Build final results in original order
final_results: list[list[float]] = []
for i, text in enumerate(texts):
    if not text or not text.strip():
        final_results.append([0.0] * dimension)  # Zero vector!
```

## Why It Matters

1. **Semantic Pollution**: Zero vectors don't represent any semantic meaning
2. **Search Quality Degradation**: Empty text will match ANYTHING in vector search with distance equal to vector magnitude
3. **Silent Failures**: Callers get results but they're semantically meaningless
4. **Mathematically Incorrect**: A zero vector has no direction, making cosine similarity undefined

## Findings

### From Kieran Python Reviewer:

> **MEDIUM PRIORITY ISSUE**
>
> Returning zero vectors for empty text is semantically incorrect. This will make empty text match ANYTHING in vector search.

### From Performance Oracle Review:

> Empty text handling returns zero vectors, but no validation of dimension consistency.

### Mathematical Issue:
- Cosine similarity: `similarity(A, B) = (A · B) / (||A|| ||B||)`
- If A is zero vector: `similarity(zero, B) = 0 / (0 * ||B||) = undefined`
- Most vector stores return 0 similarity for zero vectors, but this is misleading

## Proposed Solutions

### Solution 1: Reject Empty Texts (Recommended)

**Approach:** Raise an error if empty texts are provided

**Pros:**
- Fails fast
- Prevents silent data corruption
- Clear error message

**Cons:**
- Requires caller to filter empty texts
- Breaking change if callers rely on current behavior

**Effort:** Low
**Risk:** Low

**Implementation:**
```python
def embed_texts(self, texts: list[str], batch_size: int = 100) -> list[list[float]]:
    """Generate embeddings for multiple texts.

    Raises:
        ValueError: If any text is empty or contains only whitespace
    """
    if not texts:
        return []

    # Validate no empty texts
    empty_indices = [i for i, t in enumerate(texts) if not t or not t.strip()]
    if empty_indices:
        raise ValueError(
            f"Cannot embed empty strings at indices {empty_indices}. "
            f"Filter empty texts before calling embed_texts()."
        )

    # Proceed with embedding...
```

### Solution 2: Skip Empty Texts with Warning

**Approach:** Skip empty texts and log a warning

**Pros:**
- Non-breaking change
- Handles edge cases gracefully
- Alerts caller to the issue

**Cons:**
- Returns fewer results than inputs
- Caller must handle mismatched lengths
- Still pollutes if not used carefully

**Effort:** Low
**Risk:** Medium

**Implementation:**
```python
def embed_texts(self, texts: list[str], batch_size: int = 100) -> list[list[float]]:
    if not texts:
        return []

    # Filter empty texts with warning
    non_empty_texts = [(i, t) for i, t in enumerate(texts) if t and t.strip()]

    if len(non_empty_texts) < len(texts):
        empty_count = len(texts) - len(non_empty_texts)
        logger.warning(f"Skipped {empty_count} empty texts")

    # Process only non-empty texts...
    # Note: Returns fewer results than input length
```

### Solution 3: Return Special Sentinel Value

**Approach:** Use `None` for empty texts

**Pros:**
- Explicit indication of missing embedding
- Preserves result length
- Caller can handle explicitly

**Cons:**
- Changes return type to `list[list[float] | None]`
- More complex for caller to handle

**Effort:** Low
**Risk:** Medium

## Recommended Action

**Use Solution 1 (Reject Empty Texts)**

Empty texts should be filtered at the input validation stage. It's better to fail explicitly with a clear error message than to return meaningless results.

## Technical Details

### Files to Modify:
1. `ariadne_llm/embedder.py` - Update `embed_texts()` and `embed_text()`
2. `tests/test_llm_integration.py` - Update tests that might use empty texts

### Current Call Sites:
Check if any code relies on the current zero-vector behavior:
- `ariadne_cli/main.py` - Search command uses embeddings
- `ariadne_core/storage/vector_store.py` - Vector store operations

### Migration Path:
1. Add validation that raises error
2. Update call sites to filter empty texts before calling
3. Add tests for empty text rejection

## Acceptance Criteria

- [ ] `embed_texts()` raises `ValueError` for empty texts
- [ ] `embed_text()` raises `ValueError` for empty text
- [ ] Error message is clear and actionable
- [ ] Tests verify error is raised for empty texts
- [ ] Tests verify normal texts still work
- [ ] All call sites updated to filter empty texts

## Work Log

| Date | Action | Result |
|------|--------|--------|
| 2026-02-01 | Code review completed | Zero vector fallback identified |

## Resources

- **Files**: `ariadne_llm/embedder.py`
- **Related**: Todo #007 (Vector Store warnings) - related vector issues
- **Documentation**:
  - Word Embeddings: https://en.wikipedia.org/wiki/Word_embedding
  - Cosine Similarity: https://en.wikipedia.org/wiki/Cosine_similarity
