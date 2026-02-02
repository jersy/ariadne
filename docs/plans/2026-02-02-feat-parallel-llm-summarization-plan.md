---
title: "feat: Parallel LLM Summarization with Dependency Tracking"
type: feat
date: 2026-02-02
status: ready
reference:
  - todos/020-pending-p2-llm-api-bottleneck-summary-generation.md
  - docs/solutions/code-quality/async-sync-mixing-in-batch-operations.md
  - docs/solutions/resource-management/threadpool-executor-leak-in-llm-client.md
  - docs/solutions/performance-issues/p2-code-review-fixes-phase1-infrastructure.md
---

# Parallel LLM Summarization with Dependency Tracking

## Overview

通过并行处理和选择性重新摘要化，解决 LLM API 调用瓶颈问题。使用 ThreadPoolExecutor（而非 async/await）实现并发处理，配合 1-hop 依赖跟踪实现增量更新。

**核心价值：**
- ⚡ **性能提升**：100K 方法从 13.8 小时 → ~2 分钟（增量更新）
- 💰 **成本优化**：选择性重摘要化减少 API 调用
- 🔒 **稳定性**：遵循现有 ThreadPoolExecutor 模式，避免 async/sync 混用
- 📊 **可观测性**：成本跟踪和进度报告

---

## Problem Statement / Motivation

### 当前问题

1. **顺序处理瓶颈**：`summarizer.py` 的 `generate_incremental_summaries()` 逐个处理符号
2. **批量处理不足**：现有 `batch_generate_summaries()` 仅支持 5 并发
3. **无选择性更新**：所有变更触发全量重摘要化
4. **无依赖跟踪**：无法识别受影响的直接依赖项

### 性能分析

| 场景 | 符号数量 | 当前耗时 | 目标耗时 |
|------|---------|---------|---------|
| 全量重建 | 100K 方法 | 13.8 小时 | 2 小时 |
| 批量处理（5并发） | 100K 方法 | ~42 分钟 | 10 分钟 |
| **增量更新** | **1K 变更** | **~5 分钟** | **< 2 分钟** |

### 为什么重要

1. **NFR 合规**：增量更新 < 2 分钟目标是硬性要求
2. **开发体验**：快速反馈循环对于本地开发工具至关重要
3. **成本控制**：第三方 LLM API（智谱/DeepSeek）按 token 计费
4. **可扩展性**：支持更大规模的代码库分析

---

## Proposed Solution

### 架构设计

```
                    ┌─────────────────────────────────────┐
                    │   IncrementalSummarizerCoordinator   │
                    │  (协调器：增量更新入口)              │
                    └─────────────────┬───────────────────┘
                                      │
              ┌───────────────────────┼───────────────────────┐
              │                       │                       │
              ▼                       ▼                       ▼
    ┌─────────────────┐   ┌───────────────────┐   ┌─────────────────┐
    │ DependencyTracker│   │ ParallelSummarizer│   │   CostTracker   │
    │  (依赖跟踪)      │   │  (并行处理)       │   │  (成本跟踪)     │
    └─────────────────┘   └─────────┬─────────┘   └─────────────────┘
                                   │
                    ┌──────────────┼──────────────┐
                    │              │              │
                    ▼              ▼              ▼
           ┌─────────────┐ ┌─────────────┐ ┌─────────────┐
           │ LLMClient   │ │ SQLiteStore │ │   Cache     │
           │ (ThreadPool)│ │ (批量操作)  │ │ (摘要缓存)  │
           └─────────────┘ └─────────────┘ └─────────────┘
```

### 核心组件

#### 1. ParallelSummarizer（并行摘要器）

使用 **ThreadPoolExecutor**（而非 asyncio）遵循现有代码库模式：

```python
from concurrent.futures import ThreadPoolExecutor, as_completed
from tqdm import tqdm

class ParallelSummarizer:
    """并行摘要生成器，使用 ThreadPoolExecutor"""

    def __init__(self, llm_client: LLMClient, max_workers: int = 10):
        self.llm_client = llm_client
        self.max_workers = max_workers
        self.stats = {
            "total": 0,
            "success": 0,
            "failed": 0,
            "cached": 0,
            "skipped": 0
        }

    def summarize_symbols_batch(
        self,
        symbols: List[SymbolData],
        show_progress: bool = True
    ) -> Dict[str, str]:
        """批量并行摘要化符号"""

        results = {}
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # 提交所有任务
            futures = {
                executor.submit(self._summarize_single, symbol): symbol
                for symbol in symbols
            }

            # 收集结果（带进度条）
            if show_progress:
                with tqdm(total=len(symbols), desc="Summarizing") as pbar:
                    for future in as_completed(futures):
                        symbol = futures[future]
                        try:
                            result = future.result(timeout=30)
                            results[symbol.fqn] = result
                        except Exception as e:
                            logger.error(f"Failed to summarize {symbol.fqn}: {e}")
                            results[symbol.fqn] = self._fallback_summary(symbol)
                        finally:
                            pbar.update(1)
            else:
                for future in as_completed(futures):
                    symbol = futures[future]
                    try:
                        results[symbol.fqn] = future.result(timeout=30)
                    except Exception as e:
                        results[symbol.fqn] = self._fallback_summary(symbol)

        self.stats["total"] = len(symbols)
        return results

    def _summarize_single(self, symbol: SymbolData) -> str:
        """单个符号摘要化（在 worker 线程中执行）"""
        # 检查缓存
        cached = self.store.get_cached_summary(symbol.fqn)
        if cached and not cached.is_stale:
            self.stats["cached"] += 1
            return cached.summary_text

        # 生成新摘要
        summary = self.llm_client.generate_summary(
            code=symbol.code,
            context=symbol.context
        )

        # 保存到数据库
        self.store.update_summary(symbol.fqn, summary)
        self.stats["success"] += 1
        return summary
```

#### 2. DependencyTracker（依赖跟踪器）

跟踪 1-hop 依赖关系，实现选择性重摘要化：

```python
class DependencyTracker:
    """1-hop 依赖跟踪器"""

    def __init__(self, store: SQLiteStore):
        self.store = store

    def get_affected_symbols(
        self,
        changed_fqns: List[str]
    ) -> AffectedSymbols:
        """获取受影响的符号（变更符号 + 1-hop 依赖）"""

        affected = set(changed_fqns)

        for fqn in changed_fqns:
            # 1. 获取直接调用者 (CALLS 关系)
            callers = self.store.get_related_symbols(
                fqn,
                relation="CALLS",
                direction="incoming"
            )
            affected.update(c.fqn for c in callers)

            # 2. 获取被包含的父符号 (CONTAINS 关系)
            symbol = self.store.get_symbol(fqn)
            if symbol and symbol.parent_fqn:
                affected.add(symbol.parent_fqn)

            # 3. 标记为过期
            self.store.mark_summary_stale(fqn)

        return AffectedSymbols(
            changed=changed_fqns,
            dependents=list(affected - set(changed_fqns)),
            total=len(affected)
        )
```

#### 3. IncrementalSummarizerCoordinator（协调器）

协调增量更新流程：

```python
class IncrementalSummarizerCoordinator:
    """增量摘要化协调器"""

    def __init__(
        self,
        llm_client: LLMClient,
        store: SQLiteStore,
        config: SummarizerConfig
    ):
        self.llm_client = llm_client
        self.store = store
        self.config = config
        self.parallel = ParallelSummarizer(llm_client, config.max_workers)
        self.tracker = DependencyTracker(store)
        self.cost_tracker = LLMCostTracker()

    def regenerate_incremental(
        self,
        changed_symbols: List[str]
    ) -> IncrementalResult:
        """增量更新摘要"""

        start_time = time.time()

        # 1. 获取受影响的符号
        affected = self.tracker.get_affected_symbols(changed_symbols)
        logger.info(f"Incremental update: {affected.total} symbols to regenerate")

        # 2. 加载符号数据
        symbols_data = self.store.get_symbols_by_fqn(list(affected.total_set))

        # 3. 并行摘要化
        summaries = self.parallel.summarize_symbols_batch(symbols_data)

        # 4. 批量更新数据库
        self.store.batch_update_summaries(summaries)

        # 5. 返回结果
        return IncrementalResult(
            regenerated_count=len(summaries),
            skipped_cached=self.parallel.stats["cached"],
            duration_seconds=time.time() - start_time,
            cost_report=self.cost_tracker.get_report()
        )
```

---

## Technical Approach

### 实现阶段

#### Phase 1: 并行摘要器（MVP）

**目标：** 实现基于 ThreadPoolExecutor 的并行处理

**任务清单：**

- [x] **1.1 创建 ParallelSummarizer 类**
  - 新文件：`ariadne_analyzer/l1_business/parallel_summarizer.py`
  - 实现 `summarize_symbols_batch()` 方法
  - 使用 ThreadPoolExecutor 替代 async/await
  - 添加进度条支持（tqdm）

- [x] **1.2 扩展 LLMClient 配置**
  - 文件：`ariadne_llm/config.py`
  - 添加 `max_workers: int = 10` 配置项
  - 添加 `request_timeout: float = 30.0` 配置项
  - 添加批量操作相关配置

- [x] **1.3 增强 LLMClient**
  - 文件：`ariadne_llm/client.py`
  - 增加 `batch_generate_summaries()` 的 `max_workers` 参数
  - 现有：5 workers → 新：可配置（默认 10）
  - 添加超时处理

- [x] **1.4 错误处理与重试**
  - 单个符号失败不阻塞其他处理
  - 使用 `as_completed()` 处理部分失败
  - 添加 fallback 摘要（基于签名）

- [x] **1.5 测试并行摘要器**
  - 新文件：`tests/unit/test_parallel_summarizer.py`
  - 测试并发处理（mock LLM 调用）
  - 测试错误隔离
  - 测试进度报告

**验收标准：**
```python
# 测试 1000 个符号的并行处理
symbols = generate_test_symbols(1000)
summarizer = ParallelSummarizer(llm_client, max_workers=10)

start = time.time()
summaries = summarizer.summarize_symbols_batch(symbols)
duration = time.time() - start

assert len(summaries) == 1000
assert duration < 60  # < 1 分钟（假设每次 500ms，10 并发）
```

#### Phase 2: 依赖跟踪

**目标：** 实现 1-hop 依赖跟踪

**任务清单：**

- [x] **2.1 扩展数据库查询**
  - 文件：`ariadne_core/storage/sqlite_store.py`
  - 添加 `get_related_symbols(fqn, relation, direction)` 方法
  - 添加 `mark_summaries_stale(fqns)` 批量方法
  - 利用现有 `edges` 表的索引

- [x] **2.2 创建 DependencyTracker**
  - 新文件：`ariadne_analyzer/l1_business/dependency_tracker.py`
  - 实现 `get_affected_symbols(changed_fqns)` 方法
  - 支持 CALLS 和 CONTAINS 关系

- [x] **2.3 集成到 Summarizer**
  - 文件：`ariadne_analyzer/l1_business/summarizer.py`
  - 修改 `generate_incremental_summaries()` 使用依赖跟踪
  - 只处理受影响的符号

- [x] **2.4 测试依赖跟踪**
  - 测试 1-hop 依赖识别
  - 测试过期标记
  - 测试边界情况（无依赖、循环依赖）

**验收标准：**
```python
# 测试依赖跟踪
changed = ["com.example.ClassA.method()"]
affected = tracker.get_affected_symbols(changed)

assert "com.example.ClassA.method()" in affected.changed
# 假设 ClassB.method() 调用了 ClassA.method()
assert any("ClassB" in fqn for fqn in affected.dependents)
# ClassA 应该被标记为过期
assert store.is_summary_stale("com.example.ClassA")
```

#### Phase 3: 增量更新协调器

**目标：** 整合并行处理和依赖跟踪

**任务清单：**

- [x] **3.1 创建协调器**
  - 新文件：`ariadne_analyzer/l1_business/incremental_coordinator.py`
  - 实现 `regenerate_incremental()` 方法
  - 整合 ParallelSummarizer 和 DependencyTracker

- [x] **3.2 成本跟踪**
  - 新文件：`ariadne_analyzer/l1_business/cost_tracker.py`
  - 跟踪 token 使用和 API 成本
  - 生成成本报告

- [x] **3.3 缓存优化**
  - 利用现有 `summaries.is_stale` 标志
  - 跳过未过期的缓存摘要

- [x] **3.4 集成测试**
  - 测试完整增量更新流程
  - 性能基准测试

**验收标准：**
```python
# 测试增量更新性能
changed = ["com.example.ClassA.method()"] * 100  # 100 个变更
result = coordinator.regenerate_incremental(changed)

assert result.regenerated_count <= 200  # 100 变更 + ~100 依赖
assert result.duration_seconds < 120  # < 2 分钟
```

#### Phase 4: 性能优化与监控

**目标：** 进一步优化和可观测性

**任务清单：**

- [ ] **4.1 批量数据库操作**
  - 扩展 `sqlite_store.py` 的 `batch_update_summaries()`
  - 使用事务批量更新

- [ ] **4.2 性能监控**
  - 添加性能指标收集
  - 添加结构化日志

- [ ] **4.3 文档更新**
  - 更新 `CLAUDE.md` 性能预期
  - 添加配置说明

---

## Technical Considerations

### 设计决策

| 决策 | 选择 | 理由 |
|------|------|------|
| 并发模型 | ThreadPoolExecutor | 遵循现有模式，避免 async/sync 混用 |
| 并发数 | 10 (可配置) | 平衡性能和速率限制 |
| 依赖深度 | 1-hop | 平衡准确性和性能 |
| 缓存策略 | TTL + 过期标志 | 简单有效，利用现有 `is_stale` |
| 错误处理 | Fallback + 继续处理 | 单个失败不阻塞批量操作 |

### 速率限制

```python
# ariadne_llm/config.py
@dataclass
class LLMConfig:
    # 现有配置...

    # 并发配置
    max_workers: int = 10
    request_timeout: float = 30.0

    # 速率限制（智谱 API）
    rate_limit_rpm: int = 100  # 每分钟请求数
    rate_limit_tpm: int = 50000  # 每分钟 token 数
```

### 成本跟踪

```python
# ariadne_llm/client.py
class LLMCostTracker:
    """LLM API 成本跟踪器"""

    MODEL_COSTS = {
        "glm-4-flash": 0.0001,  # 每 1K tokens
        "glm-4-plus": 0.0005,
        "deepseek-chat": 0.0001,
    }

    def record_request(
        self,
        model: str,
        input_tokens: int,
        output_tokens: int
    ):
        cost_per_1k = self.MODEL_COSTS.get(model, 0.0001)
        cost = (input_tokens + output_tokens) / 1000 * cost_per_1k

        self.usage["total_cost_usd"] += cost
        self.usage["total_tokens"] += input_tokens + output_tokens
        self.usage["requests_count"] += 1

    def get_report(self) -> str:
        return (
            f"LLM Usage Report:\n"
            f"  Requests: {self.usage['requests_count']}\n"
            f"  Tokens: {self.usage['total_tokens']:,}\n"
            f"  Cost: ${self.usage['total_cost_usd']:.4f}"
        )
```

### 安全考虑

| 风险 | 缓解措施 |
|------|----------|
| API 密钥泄露 | 环境变量，不提交到仓库 |
| 资源泄漏 | 使用 context manager 管理 ThreadPoolExecutor |
| 级联失败 | 单个符号失败不阻塞，使用 fallback |
| 数据库死锁 | 批量操作使用事务，超时保护 |

---

## Acceptance Criteria

### 功能需求

- [ ] **AC1**: 并行摘要器支持可配置并发数（默认 10）
- [ ] **AC2**: 依赖跟踪识别 1-hop 依赖（CALLS, CONTAINS）
- [ ] **AC3**: 增量更新只处理受影响的符号
- [ ] **AC4**: 单个符号失败不阻塞其他处理
- [ ] **AC5**: 进度条显示处理进度
- [ ] **AC6**: 成本跟踪生成报告

### 非功能需求

- [ ] **NFR1**: 1000 个符号增量更新 < 2 分钟
- [ ] **NFR2**: 100K 符号全量更新 < 2 小时（10 并发）
- [ ] **NFR3**: ThreadPoolExecutor 正确关闭（无资源泄漏）
- [ ] **NFR4**: 测试覆盖率 > 80%
- [ ] **NFR5**: 遵循现有代码风格（ruff, mypy）

### 质量标准

- [ ] **Test Coverage**: 并行处理、错误处理、依赖跟踪有完整测试
- [ ] **Documentation**: 配置说明、性能预期、故障排查
- [ ] **Code Quality**: 通过 shellcheck、ruff、mypy 检查

---

## Dependencies & Risks

### 依赖项

| 依赖 | 版本要求 | 用途 |
|------|----------|------|
| Python | 3.12+ | ThreadPoolExecutor |
| tqdm | latest | 进度条 |
| pytest | latest | 测试 |

### 风险分析

| 风险 | 可能性 | 影响 | 缓解措施 |
|------|--------|------|----------|
| 速率限制触发 | 中 | 中 | 可配置并发数，添加退避 |
| 数据库锁竞争 | 低 | 中 | 批量操作使用事务 |
| 内存压力 | 低 | 低 | 流式处理，及时写入 |
| 依赖跟踪不准确 | 中 | 高 | 充分测试，添加验证 |

---

## Success Metrics

| 指标 | 目标 | 测量方法 |
|------|------|----------|
| 增量更新时间 | < 2 分钟 (1000 符号) | 基准测试 |
| 全量更新时间 | < 2 小时 (100K 符号) | 基准测试 |
| API 成本降低 | > 80% (增量 vs 全量) | 成本跟踪报告 |
| 测试覆盖率 | > 80% | pytest --cov |
| 资源泄漏 | 0 | 资源监控测试 |

---

## Implementation Details

### 目录结构

```
ariadne/
├── ariadne_analyzer/
│   └── l1_business/
│       ├── parallel_summarizer.py       # 新增：并行摘要器
│       ├── dependency_tracker.py        # 新增：依赖跟踪器
│       ├── incremental_coordinator.py   # 新增：增量协调器
│       ├── cost_tracker.py              # 新增：成本跟踪器
│       └── summarizer.py                # 修改：集成协调器
├── ariadne_llm/
│   ├── client.py                        # 修改：增加并发配置
│   └── config.py                        # 修改：添加配置项
├── ariadne_core/
│   └── storage/
│       └── sqlite_store.py              # 修改：批量操作、依赖查询
├── tests/
│   ├── unit/
│   │   ├── test_parallel_summarizer.py  # 新增
│   │   ├── test_dependency_tracker.py   # 新增
│   │   └── test_incremental_coordinator.py  # 新增
│   └── benchmarks/
│       └── test_summarizer_performance.py  # 新增：性能基准测试
```

### 性能基准测试

```python
# tests/benchmarks/test_summarizer_performance.py
import pytest
import time

@pytest.mark.benchmark
class TestSummarizerPerformance:

    def test_incremental_update_1000_symbols(self, coordinator):
        """测试 1000 个符号的增量更新"""
        symbols = generate_test_symbols(1000)
        changed = [s.fqn for s in symbols[:100]]

        start = time.time()
        result = coordinator.regenerate_incremental(changed)
        duration = time.time() - start

        assert result.duration_seconds < 120  # < 2 分钟
        assert result.regenerated_count <= 200  # 100 变更 + ~100 依赖

    def test_full_rebuild_100k_symbols(self, coordinator):
        """测试 100K 符号的全量重建"""
        symbols = generate_test_symbols(100_000)

        start = time.time()
        result = coordinator.parallel.summarize_symbols_batch(symbols)
        duration = time.time() - start

        assert duration < 7200  # < 2 小时（10 并发）
        assert len(result) == 100_000
```

---

## References & Research

### Internal References

- **Todo Item**: `todos/020-pending-p2-llm-api-bottleneck-summary-generation.md`
- **Code Review Findings**: `docs/reviews/2026-02-02-ariadne-knowledge-graph-plan-review.md`
- **Learnings**:
  - `docs/solutions/code-quality/async-sync-mixing-in-batch-operations.md` - 使用 ThreadPoolExecutor 而非 async/await
  - `docs/solutions/resource-management/threadpool-executor-leak-in-llm-client.md` - 资源管理
  - `docs/solutions/performance-issues/p2-code-review-fixes-phase1-infrastructure.md` - 性能优化模式

### External References

- [Python ThreadPoolExecutor Documentation](https://docs.python.org/3/library/concurrent.futures.html)
- [智谱 API 速率限制](https://open.bigmodel.cn/dev/api#rate-limit)
- [tqdm 进度条文档](https://tqdm.github.io/)

### Related Files

- `ariadne_analyzer/l1_business/summarizer.py:191-247` - 当前顺序处理逻辑
- `ariadne_llm/client.py:282-324` - 现有批量处理方法
- `ariadne_core/storage/sqlite_store.py:435-452` - 摘要创建方法
- `ariadne_core/storage/schema.py:110-120` - summaries 表结构
