---
status: completed
priority: p2
issue_id: "020"
tags:
  - code-review
  - performance
  - llm
  - architecture
dependencies: []
---

# LLM API Bottleneck in Summary Generation

## Problem Statement

The plan calls for hierarchical summarization (Method → Class → Package → Module). For large projects, the sequential LLM API calls create a **massive bottleneck** that violates the < 2 minute incremental update target.

**Current Approach (from plan Phase 3.2):**
- Summarize each method individually
- Aggregate into class summary
- Aggregate into package summary
- Aggregate into module summary

**Performance Calculation:**
```
10K class project:
- ~100K methods
- 500ms per LLM call
- Sequential: 100,000 × 0.5s = 13.8 hours
- Even with batching (20/batch): ~42 minutes

Target: < 2 minutes for incremental updates
Current: 40+ minutes for full rebuild
```

## Why It Matters

1. **NFR Violation**: < 2 minute incremental target impossible
2. **Cost Prohibitive**: LLM API costs scale linearly
3. **User Experience**: Long rebuild times discourage use
4. **Developer Workflow**: Waiting 40+ minutes for rebuild is unacceptable

## Findings

### From Performance Oracle Review:

> **Severity:** HIGH
>
> The hierarchical summarization approach is fundamentally flawed for large projects. Even with parallel processing, the LLM call volume is prohibitive.

### From Implementation Review:

> **Observation:** The actual implementation uses single-level summarization, not the 4-level hierarchy specified in the plan. This is a pragmatic deviation but not documented.

### From Code Quality Review:

> **Concern:** Broad exception handling in summarizer catches all LLM errors and returns fallback, potentially hiding issues.

### Affected Code Locations:

| File | Issue |
|------|-------|
| `ariadne_analyzer/l1_business/summarizer.py` | Sequential LLM calls |
| Plan Phase 3.2 | Hierarchical strategy not implemented |

## Proposed Solutions

### Solution 1: Parallel Processing with Concurrency Limit (Recommended)

**Approach:** Use asyncio to process multiple summaries in parallel with rate limiting.

**Pros:**
- Dramatically reduces total time (10x+)
- Respects LLM provider rate limits
- Fault isolation (one failure doesn't block others)

**Cons:**
- More complex error handling
- Need to track concurrent operations

**Effort:** Medium
**Risk:** Low

**Implementation:**
```python
import asyncio
from asyncio import Semaphore

class ParallelSummarizer:
    def __init__(self, llm_client, concurrency: int = 10):
        self.llm_client = llm_client
        self.semaphore = Semaphore(concurrency)
        self.stats = {
            "total": 0,
            "success": 0,
            "failed": 0,
            "cached": 0
        }

    async def summarize_symbols_batch(
        self,
        symbols: List[SymbolData],
        show_progress: bool = True
    ) -> Dict[str, str]:
        """Summarize multiple symbols in parallel"""

        tasks = []
        for symbol in symbols:
            task = self._summarize_with_limit(symbol)
            tasks.append(task)

        if show_progress:
            from tqdm.asyncio import tqdm
            results = await tqdm.gather(*tasks, desc="Summarizing")
        else:
            results = await asyncio.gather(*tasks, return_exceptions=True)

        # Process results
        summaries = {}
        for symbol, result in zip(symbols, results):
            self.stats["total"] += 1

            if isinstance(result, Exception):
                logger.error(f"Failed to summarize {symbol.fqn}: {result}")
                self.stats["failed"] += 1
                summaries[symbol.fqn] = self._fallback_summary(symbol)
            elif result is None:
                # Cache hit
                self.stats["cached"] += 1
            else:
                self.stats["success"] += 1
                summaries[symbol.fqn] = result

        logger.info(f"Summarization stats: {self.stats}")
        return summaries

    async def _summarize_with_limit(self, symbol: SymbolData) -> Optional[str]:
        """Summarize with concurrency limiting"""

        async with self.semaphore:
            # Check cache first
            cached = await self._get_cached_summary(symbol)
            if cached:
                return None  # Signal cache hit

            # Generate summary
            try:
                summary = await self.llm_client.generate_summary(symbol)
                await self._cache_summary(symbol, summary)
                return summary

            except Exception as e:
                logger.error(f"LLM error for {symbol.fqn}: {e}")
                raise  # Re-raise for outer handler
```

### Solution 2: Selective Re-summarization (1-Hop)

**Approach:** Only regenerate summaries for changed symbols and their direct dependents.

**Pros:**
- Dramatically reduces LLM calls for incremental updates
- Matches typical developer workflow
- Enables < 2 minute incremental target

**Cons:**
- Transitive dependencies may miss semantic changes
- Need full rebuild periodically

**Effort:** Medium
**Risk:** Low

**Implementation:**
```python
class IncrementalSummarizer:
    def regenerate_incremental(
        self,
        changed_symbols: List[str],
        store: SQLiteStore
    ) -> IncrementalResult:
        """Regenerate only affected summaries"""

        # 1. Mark changed symbols as stale
        for fqn in changed_symbols:
            store.mark_summary_stale(fqn)

        # 2. Find 1-hop dependents
        dependents = set()
        for fqn in changed_symbols:
            deps = store.get_direct_dependents(fqn, max_hops=1)
            dependents.update(deps)

        # 3. Only regenerate changed + dependents
        to_regenerate = dependents | set(changed_symbols)

        logger.info(f"Incremental update: {len(to_regenerate)} symbols to regenerate")

        # 4. Parallel regeneration
        summarizer = ParallelSummarizer(self.llm_client)
        summaries = asyncio.run(summarizer.summarize_symbols_batch(to_regenerate))

        # 5. Update summaries in store
        store.update_summaries(summaries)

        return IncrementalResult(
            regenerated_count=len(summaries),
            skipped_cached=summarizer.stats["cached"],
            duration_seconds=summarizer.stats["duration"]
        )
```

### Solution 3: Tiered Summary Strategy

**Approach:** Different strategies for different levels.

**Pros:**
- Reduces LLM calls significantly
- Appropriate granularity for each level

**Cons:**
- More complex implementation
- May lose some semantic detail

**Effort:** High
**Risk:** Medium

**Strategy:**
```python
TIERED_STRATEGY = {
    "method": {
        "strategy": "cache_only",  # Only generate on explicit request
        "fallback": "signature_based"  # Use method signature as summary
    },
    "class": {
        "strategy": "llm_incremental",  # Generate LLM summary, cache aggressively
        "regeneration": "on_change_only"  # Only when methods change
    },
    "package": {
        "strategy": "aggregate",  # Aggregate from class summaries
        "llm": "synthesize_only"  # Synthesize from existing summaries
    },
    "module": {
        "strategy": "aggregate",  # Pure aggregation, no LLM call
        "source": "package_summaries"
    }
}
```

## Recommended Action

**Use Solution 1 (Parallel Processing) + Solution 2 (Selective Re-summarization)**

This combination achieves the < 2 minute incremental target while maintaining summary quality.

## Technical Details

### Performance Projections:

| Strategy | Time for 100K methods | Cost (assuming $0.001/1K tokens) |
|----------|----------------------|----------------------------------|
| Sequential | 13.8 hours | ~$50 |
| Parallel (10 concurrent) | 1.4 hours | ~$50 |
| Parallel + Selective (1K changed) | ~2 minutes | ~$0.50 |
| Tiered (10K classes only) | ~5 minutes | ~$5 |

### Concurrency Configuration:

```python
# ariadne_llm/config.py
@dataclass
class LLMConfig:
    provider: str = "openai"
    api_key: str = ""
    model: str = "gpt-4"

    # Concurrency settings
    max_concurrent_requests: int = 10  # Respect rate limits
    request_timeout: float = 30.0
    batch_size: int = 20

    # Rate limiting (requests per minute)
    rate_limit_rpm: int = 100
    rate_limit_tpm: int = 50000  # Tokens per minute

    # Caching
    enable_cache: bool = True
    cache_ttl_hours: int = 24 * 7  # 1 week
```

### Summary Invalidation Strategy:

```python
class SummaryDependencyTracker:
    def mark_dependent_stale(self, changed_fqn: str) -> List[str]:
        """Mark all summaries affected by a change"""

        affected = []

        # 1. Mark own summary stale
        self.store.mark_summary_stale(changed_fqn)
        affected.append(changed_fqn)

        # 2. Find direct callers (1-hop)
        callers = self.store.get_callers(changed_fqn, max_depth=1)
        for caller in callers:
            self.store.mark_summary_stale(caller.fqn)
            affected.append(caller.fqn)

        # 3. Find containing class/package
        symbol = self.store.get_symbol(changed_fqn)
        if symbol:
            if symbol.kind == "method":
                # Mark class summary stale
                class_fqn = symbol.parent_fqn
                self.store.mark_summary_stale(class_fqn)
                affected.append(class_fqn)

        return affected
```

### Files to Modify:

1. **`ariadne_analyzer/l1_business/summarizer.py`** - Add parallel processing
2. **`ariadne_llm/client.py`** - Add async methods
3. **`ariadne_llm/config.py`** - Add concurrency settings
4. **`ariadne_core/storage/sqlite_store.py`** - Add dependency tracking
5. **`tests/unit/test_summarizer.py`** - Test parallel scenarios

### Cost Tracking:

```python
class LLMCostTracker:
    """Track LLM API usage and costs"""

    def __init__(self):
        self.usage = {
            "total_tokens": 0,
            "total_cost_usd": 0.0,
            "requests_count": 0,
            "cached_count": 0
        }

    def record_request(
        self,
        input_tokens: int,
        output_tokens: int,
        model: str,
        cached: bool = False
    ):
        cost_per_1k = MODEL_COSTS.get(model, 0.001)
        cost = (input_tokens + output_tokens) / 1000 * cost_per_1k

        self.usage["total_tokens"] += input_tokens + output_tokens
        self.usage["total_cost_usd"] += cost
        self.usage["requests_count"] += 1
        if cached:
            self.usage["cached_count"] += 1

    def get_report(self) -> str:
        return (
            f"LLM Usage:\n"
            f"  Requests: {self.usage['requests_count']}\n"
            f"  Cached: {self.usage['cached_count']}\n"
            f"  Tokens: {self.usage['total_tokens']:,}\n"
            f"  Cost: ${self.usage['total_cost_usd']:.4f}"
        )
```

## Acceptance Criteria

- [ ] Parallel summarizer implemented with asyncio
- [ ] Concurrency limit configurable (default: 10)
- [ ] Selective re-summarization for incremental updates
- [ ] 1-hop dependency tracking
- [ ] Performance: < 2 minutes for 1000 changed symbols
- [ ] Cost tracking implemented
- [ ] LLM cache with TTL
- [ ] Progress reporting (tqdm or similar)
- [ ] Error handling with retries
- [ ] Documentation updated with performance expectations

## Work Log

| Date | Action | Result |
|------|--------|--------|
| 2026-02-02 | Plan review completed | LLM bottleneck identified |
| 2026-02-02 | Code verified | ParallelSummarizer already implements parallel processing |
| 2026-02-02 | Verified complete | Issue already fixed by PR #4 |
| | | |

## Resources

- **Affected Files**:
  - `ariadne_analyzer/l1_business/summarizer.py`
  - `ariadne_llm/client.py`
- **Plan Reference**: Phase 3.2 - LLM 摘要生成
- **Related Issues**:
  - Performance NFR: < 2 minute incremental update
- **Documentation**:
  - Plan Section: "非功能需求"
  - OpenAI Rate Limits: https://platform.openai.com/docs/guides/rate-limits
