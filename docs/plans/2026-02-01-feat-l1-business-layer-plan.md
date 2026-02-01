---
title: "feat: L1 Business Layer - LLM Semantic Analysis"
type: feat
date: 2026-02-01
status: ready
phase: 3
reference:
  - docs/plans/2026-01-31-feat-ariadne-codebase-knowledge-graph-plan.md
  - /Users/jersyzhang/work/auto-claude-new/ai-memory-system (LLM integration reference)
---

# Phase 3: L1 Business Layer - LLM Semantic Analysis

## Overview

实现 Ariadne 三层架构中的 L1 业务与领域层，为"架构师 Agent"提供语义理解能力。通过 LLM 驱动的分层摘要、领域词汇表和业务约束提取，让 Agent 理解代码解决的业务问题（What & Why）。

**核心价值：**
- **业务理解**：从代码自动生成自然语言业务摘要
- **语义检索**：用自然语言查询代码知识图谱
- **领域映射**：建立 Code Term ↔ Business Meaning 映射
- **约束识别**：提取隐藏在代码中的业务规则

---

## Problem Statement / Motivation

当前 L3 和 L2 层已实现：
- ✅ **L3**：符号索引、调用关系
- ✅ **L2**：入口点识别、调用链追踪、外部依赖

**缺失的 L1 层能力：**
- ❌ 无法理解"这段代码解决什么业务问题"
- ❌ 无法用自然语言搜索代码（如"登录验证码"）
- ❌ 无法识别业务约束（如"库存不可为负"）
- ❌ Agent 规划时缺乏业务上下文

---

## Proposed Solution

### 三层架构中的 L1 定位

```
┌─────────────────────────────────────────────────────────────────────┐
│  L1 业务与领域层 (Phase 3) - NEW                                    │
│  目标: What & Why                                                    │
│  ├─ 业务能力映射 (Business Capability Mapping)                       │
│  │   - 模块/服务的自然语言摘要 (LLM 生成)                            │
│  │   - 入口识别: HTTP API, Cron Jobs, MQ Consumers                  │
│  │   - 关键约束提取: 业务规则                                        │
│  └─ 领域词汇表 (Ubiquitous Language Glossary)                       │
│      - Code Term ↔ Business Meaning 映射                            │
│  构建方式: LLM 分层摘要 + 向量化存储 (ChromaDB)                      │
└─────────────────────────────────────────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────┐
│  L2 架构与设计层 (Phase 2 - 已完成)                                  │
│  ├─ 技术栈识别、调用链追踪、外部依赖拓扑                             │
└─────────────────────────────────────────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────┐
│  L3 代码实现层 (Phase 1 - 已完成)                                    │
│  ├─ 符号索引、关系构建、测试映射                                     │
└─────────────────────────────────────────────────────────────────────┘
```

### 分层摘要策略

```
Method Level (最细粒度)
  ↓ LLM 生成单方法摘要
Class Level (聚合)
  ↓ LLM 基于方法摘要生成类摘要
Package Level (聚合)
  ↓ LLM 基于类摘要生成包摘要
Module Level (最粗粒度)
  ↓ LLM 基于包摘要生成模块摘要
```

**关键设计决策：**
1. **Bottom-Up 聚合**：避免单次 LLM 调用输入过大
2. **增量更新**：只重新摘要变更的代码
3. **混合检索**：向量搜索 + 元数据过滤（level, kind, entry_type）

---

## Technical Approach

### 架构设计

```
ariadne/
├── ariadne_core/
│   ├── storage/
│   │   ├── vector_store.py          # NEW: ChromaDB 向量存储
│   │   └── sqlite_store.py          # EXTEND: L1 CRUD 操作
│   └── models/
│       └── types.py                 # EXTEND: L1 数据类型
│
├── ariadne_analyzer/
│   └── l1_business/                 # NEW: L1 业务层分析
│       ├── __init__.py
│       ├── summarizer.py            # LLM 分层摘要生成
│       ├── glossary.py              # 领域词汇表提取
│       ├── constraints.py           # 业务约束识别
│       └── prompts.py               # LLM Prompt 模板
│
├── ariadne_llm/                     # NEW: LLM 集成层
│   ├── __init__.py
│   ├── config.py                    # LLM 配置
│   ├── client.py                    # OpenAI 兼容客户端
│   └── embedder.py                  # 向量化嵌入器
│
├── ariadne_cli/
│   └── main.py                      # EXTEND: L1 CLI 命令
│
└── tests/
    ├── unit/
    │   ├── test_vector_store.py
    │   ├── test_summarizer.py
    │   └── test_llm_client.py
    └── fixtures/
        └── java_projects/           # 测试用 Java 项目
```

### 数据流设计

```
Java Source Code
       │
       ▼
┌──────────────────┐
│ ASM Extraction   │ (Phase 1/2 已有)
│ → Symbols/Edges  │
└──────────────────┘
       │
       ▼
┌──────────────────┐
│ Symbol Filter    │ (选择需要摘要的符号)
│ → Changed Files  │
└──────────────────┘
       │
       ▼
┌──────────────────┐
│ LLM Summarizer   │ (分层 LLM 调用)
│ → Summaries      │
└──────────────────┘
       │
       ▼
┌──────────────────┐
│ Vector Embedder  │ (向量化摘要)
│ → Embeddings     │
└──────────────────┘
       │
       ▼
┌──────────────────┐
│ ChromaDB Store   │ (向量存储)
│ + SQLite Store   │ (元数据存储)
└──────────────────┘
       │
       ▼
┌──────────────────┐
│ Hybrid Search    │ (检索 API)
│ → Results        │
└──────────────────┘
```

---

## Implementation Phases

### Phase 3.1: LLM 集成基础设施

**目标**：搭建 LLM 客户端和嵌入器，支持多 Provider。

**任务清单：**

- [x] **3.1.1 创建 `ariadne_llm/` 模块**
  - 实现 `config.py`：LLMConfig 数据类
    - 支持 OpenAI/DeepSeek/Ollama Provider
    - 环境变量配置（ARIADNE_LLM_PROVIDER, OPENAI_API_KEY 等）
    - 模型配置（llm_model, embedding_model）
  - 实现 `client.py`：OpenAI 兼容客户端
    - `generate_summary()`：单次 LLM 调用
    - `batch_generate_summaries()`：批量调用（并发控制）
    - 错误重试和速率限制
  - 实现 `embedder.py`：向量嵌入器
    - `embed_text()`：单文本向量化
    - `embed_texts()`：批量向量化
    - 支持本地 Ollama 作为 fallback

- [x] **3.1.2 更新依赖**
  ```toml
  [project.dependencies]
  "openai>=1.0.0",           # LLM API
  "chromadb>=0.5.0",         # 向量存储
  "tenacity>=8.0.0",         # 重试逻辑
  "python-dotenv>=1.0.0",    # 环境变量
  ```

- [x] **3.1.3 单元测试**
  - Mock OpenAI API 响应
  - 测试重试逻辑
  - 测试并发控制

**验收标准：**
```python
# LLM 客户端可用
from ariadne_llm import LLMConfig, create_llm_client

config = LLMConfig.from_env()
client = create_llm_client(config)
summary = client.generate_summary("public void login(String user) { ... }")
assert "认证" in summary or "登录" in summary
```

---

### Phase 3.2: ChromaDB 向量存储

**目标**：实现向量存储层，支持混合检索。

**任务清单：**

[x]1 实现 `vector_store.py`**
  - `ChromaVectorStore` 类
    - `__init__(path, collection_name)`：初始化连接
    - `add_summary(id, text, metadata)`：添加摘要向量
    - `search(query, n_results, filters)`：混合检索
    - `delete(ids)`：批量删除
    - `update(id, text, metadata)`：更新向量
  - Collection 设计：
    - `ariadne_summaries`：业务摘要
    - `ariadne_glossary`：领域词汇
    - `ariadne_constraints`：业务约束

[x]2 扩展 `sqlite_store.py`**
  - 添加 L1 表的 CRUD 操作：
    - `create_summary(summary_data)`：创建摘要记录
    - `get_summary(target_fqn, level)`：获取摘要
    - `mark_summary_stale(target_fqn)`：标记为过期
    - `get_stale_summaries()`：获取过期列表
    - `update_summary_vector_id(target_fqn, vector_id)`：关联向量 ID
  - 类似方法用于 glossary 和 constraints

[x]3 扩展 `types.py`**
  ```python
  @dataclass
  class SummaryData:
      target_fqn: str
      level: SummaryLevel  # method, class, package, module
      summary: str
      vector_id: str | None = None
      is_stale: bool = False
      created_at: str = field(default_factory=lambda: datetime.now().isoformat())

  @dataclass
  class GlossaryEntry:
      code_term: str
      business_meaning: str
      synonyms: list[str]
      source_fqn: str
      vector_id: str | None = None

  @dataclass
  class ConstraintEntry:
      name: str
      description: str
      source_fqn: str | None = None
      source_line: int | None = None
      constraint_type: ConstraintType  # validation, business_rule, invariant
      vector_id: str | None = None
  ```

[x]4 集成测试**
  - 使用测试 Java 项目
  - 验证向量存储和检索
  - 测试元数据过滤

**验收标准：**
```python
# 向量存储可用
store = ChromaVectorStore("/tmp/test", "summaries")
store.add_summary("test_1", "用户登录验证", {"fqn": "com.example.AuthService", "level": "class"})
results = store.search("认证相关", n_results=5, filters={"level": "class"})
assert len(results) > 0
```

---

### Phase 3.3: LLM 分层摘要生成

**目标**：实现分层 LLM 摘要策略，生成 Method → Class → Package → Module 摘要。

**任务清单：**

[x]1 实现 `prompts.py`**
  - `METHOD_SUMMARY_PROMPT`：方法摘要模板
    ```python
    METHOD_SUMMARY_PROMPT = """你是一个 Java 代码分析专家。请用一句话总结以下方法的功能，专注于它解决的业务问题。

    类名: {class_name}
    方法名: {method_name}
    方法签名: {signature}
    源代码:
    ```java
    {source_code}
    ```

    要求:
    1. 使用业务语言，避免技术术语
    2. 一句话，不超过30字
    3. 格式: "动词 + 宾语"（如"验证用户登录凭据"）
    4. 如果是 getter/setter，返回 "N/A"

    摘要:"""
    ```

  - `CLASS_SUMMARY_PROMPT`：类摘要模板（聚合方法摘要）
  - `PACKAGE_SUMMARY_PROMPT`：包摘要模板（聚合类摘要）
  - `MODULE_SUMMARY_PROMPT`：模块摘要模板（聚合包摘要）

[x]2 实现 `summarizer.py`**
  - `HierarchicalSummarizer` 类
    - `summarize_method(method_data)`：单方法摘要
    - `summarize_class(class_data, method_summaries)`：类摘要
    - `summarize_package(package_data, class_summaries)`：包摘要
    - `summarize_module(module_data, package_summaries)`：模块摘要
    - `generate_incremental_summaries(changed_symbols)`：增量摘要

[x]3 增量更新策略**
  - 基于文件 hash 检测变更（复用 Phase 1 机制）
  - 级联标记 stale：
    - Method 变更 → 标记 Method, Class, Package, Module 为 stale
    - Class 变更 → 标记 Class, Package, Module 为 stale
  - 重新生成摘要时自动清理 stale 标记

[x]4 Token 优化**
  - 单次 LLM 调用限制：max_tokens = 4000
  - 超长方法截断策略：保留前 500 行 + 后 500 行
  - 批量处理并发控制：max_concurrent = 5

[x]5 集成测试**
  - 使用 Spring PetClinic 测试
  - 验证分层摘要质量
  - 测试增量更新

**验收标准：**
```bash
# 生成摘要
ariadne summarize --project /path/to/java-project

# 查看摘要
ariadne summary --fqn com.example.AuthService
# 输出: "AuthService 负责用户认证和授权管理"
```

---

### Phase 3.4: 领域词汇表提取

**目标**：从代码中提取领域术语，建立 Code Term ↔ Business Meaning 映射。

**任务清单：**

- [ ] **3.4.1 实现 `glossary.py`**
  - `DomainGlossaryExtractor` 类
    - `extract_terms_from_class(class_data)`：从类名/方法名/字段名提取术语
    - `generate_business_meaning(term, context)`：LLM 生成业务含义
    - `extract_synonyms(term, related_terms)`：识别同义词
    - `build_glossary(symbols)`：构建完整词汇表

- [ ] **3.4.2 术语提取规则**
  - 类名 → 核心领域概念（如 `Order`, `Inventory`, `AuthCode`）
  - 方法名 → 业务操作（如 `processPayment`, `validateInventory`）
  - 字段名 → 属性（如 `sku`, `stockQty`）
  - 枚举值 → 业务状态（如 `PENDING`, `SHIPPED`）

- [ ] **3.4.3 LLM Prompt 设计**
  ```python
  GLOSSARY_TERM_PROMPT = """你是业务分析师。请为以下代码术语解释其业务含义。

  术语: {term}
  上下文: {context}  # 类名/方法名/注释

  输出格式:
  {{
    "business_meaning": "业务含义描述（1-2句话）",
    "synonyms": ["同义词1", "同义词2"]
  }}
  """
  ```

- [ ] **3.4.4 向量化存储**
  - 每个术语向量化：business_meaning + synonyms
  - 元数据：code_term, source_fqn, term_type

**验收标准：**
```bash
# 构建词汇表
ariadne glossary --project /path/to/java-project

# 查询术语
ariadne term-search "库存"
# 输出:
# - Inventory (库存管理系统)
# - stockQty (库存数量)
# - SKU (商品库存单位)
```

---

### Phase 3.5: 业务约束提取

**目标**：从代码和注释中识别业务约束和规则。

**任务清单：**

- [ ] **3.5.1 实现 `constraints.py`**
  - `BusinessConstraintExtractor` 类
    - `extract_from_comments(comment, context)`：从注释提取
    - `extract_from_assertions(method_data)`：从 Assert 语句提取
    - `extract_from_validations(method_data)`：从验证逻辑提取
    - `identify_implicit_constraints(llm, method_data)`：LLM 识别隐式约束

- [ ] **3.5.2 约束类型分类**
  ```python
  class ConstraintType(Enum):
      VALIDATION = "validation"       # 输入验证（如 @NotNull）
      BUSINESS_RULE = "business_rule" # 业务规则（如库存不可为负）
      INVARIANT = "invariant"         # 不变量（如订单总额 = sum(明细)）
  ```

- [ ] **3.5.3 提取模式**
  - **显式约束**：
    - 注释：`// 库存不可为负`
    - 断言：`assert qty >= 0 : "库存不能为负"`
    - 注解：`@Min(0), @NotNull`
  - **隐式约束**（LLM 识别）：
    - `if (qty < 0) throw new IllegalArgumentException(...)` → 库存非负约束
    - `if (order.getStatus() == Status.PAID)` → 订单状态约束

- [ ] **3.5.4 向量化存储**
  - 约束描述向量化
  - 元数据：constraint_type, source_fqn, severity

**验收标准：**
```bash
# 提取约束
ariadne constraints --project /path/to/java-project

# 查询约束
ariadne constraint-search "库存"
# 输出:
# - 库存数量不可为负 (com.example.InventoryService:42)
# - 库存变动需记录审计日志 (com.example.InventoryService:88)
```

---

### Phase 3.6: CLI 命令集成

**目标**：扩展 CLI，支持 L1 层操作。

**任务清单：**

[x]1 新增 CLI 命令**
  ```bash
  # 摘要生成
  ariadne summarize --project <path> [--incremental] [--level <method|class|package|module>]

  # 摘要查询
  ariadne summary --fqn <fqn>

  # 语义搜索
  ariadne search <query> [--limit 10] [--level class] [--entry-type http_api]

  # 领域词汇表
  ariadne glossary --project <path> [--rebuild]
  ariadne term-search <term>

  # 业务约束
  ariadne constraints --project <path> [--rebuild]
  ariadne constraint-search <keyword>
  ```

[x]2 集成到现有工作流**
  - `ariadne extract` 后自动触发 `summarize`
  - `ariadne rebuild` 重建所有 L1 数据

[x]3 输出格式**
  - 表格输出：rich 库格式化
  - JSON 输出：`--format json`
  - 详细模式：`--verbose`

**验收标准：**
```bash
# 完整工作流
ariadne extract --project /path/to/java-project
ariadne summarize --project /path/to/java-project
ariadne search "用户登录"
# 输出相关代码位置和业务摘要
```

---

## HTTP API 设计（预览，Phase 4 实现）

```yaml
# GET /knowledge/search
# 混合检索（语义 + 关键词）
Request:
  query: string (required)    # 自然语言查询
  num_results: int = 10
  filters:
    level: string[]           # class, method, package
    entry_type: string[]      # http_api, scheduled
Response:
  results:
    - fqn: string
      kind: string
      summary: string
      score: float
      entry_points: [...]

# GET /knowledge/constraints?context={path}
# 获取约束
Request:
  context: string             # 代码路径或 FQN
Response:
  constraints: [...]
  glossary: [...]
```

---

## 非功能需求

| 指标 | 目标 | 验证方法 |
|------|------|----------|
| 摘要质量 | 相关性 ≥ 0.7 | 人工标注测试集 |
| 向量检索响应 | < 500ms | pytest-benchmark |
| LLM 调用成本 | < $50/10K LOC | Token 计数监控 |
| 增量更新延迟 | < 5 分钟 | 监控摘要生成时间 |
| 混合检索 MRR@10 | ≥ 0.7 | 测试集验证 |

---

## Dependencies & Prerequisites

### 新增依赖

```toml
# pyproject.toml
[project.dependencies]
"openai>=1.0.0",           # LLM API (支持 OpenAI 兼容接口)
"chromadb>=0.5.0",         # 向量存储
"tenacity>=8.0.0",         # LLM 调用重试
"python-dotenv>=1.0.0",    # 环境变量
"aiohttp>=3.9.0",          # 异步 HTTP (可选，用于并发 LLM)
```

### 环境变量

```bash
# LLM Provider (支持: openai, deepseek, ollama)
ARIADNE_LLM_PROVIDER=openai
ARIADNE_OPENAI_API_KEY=sk-...
ARIADNE_OPENAI_MODEL=gpt-4o-mini
ARIADNE_OPENAI_EMBEDDING_MODEL=text-embedding-3-small

# ChromaDB
ARIADNE_VECTOR_DB_PATH=~/.ariadne/vectors

# 可选：使用 Ollama 本地模型
# ARIADNE_LLM_PROVIDER=ollama
# ARIADNE_OLLAMA_BASE_URL=http://localhost:11434
# ARIADNE_OLLAMA_MODEL=deepseek-r1:7b
# ARIADNE_OLLAMA_EMBEDDING_MODEL=nomic-embed-text
```

### 前置条件

- ✅ Phase 1 (L3 层) 已完成
- ✅ Phase 2 (L2 层) 已完成
- ✅ SQLite 数据库已有 symbols/edges 数据
- ⚠️ OpenAI API Key 或兼容服务（DeepSeek/Ollama）

---

## Risk Analysis & Mitigation

| 风险 | 可能性 | 影响 | 缓解措施 |
|------|--------|------|----------|
| LLM 调用成本高 | 中 | 中 | 1) 增量更新策略 2) 本地 Ollama fallback 3) Token 计数监控 |
| 摘要质量不稳定 | 中 | 高 | 1) 优化 Prompt 2) 温度参数调优 3) 人工评估反馈循环 |
| ChromaDB 性能瓶颈 | 低 | 中 | 预留切换到 Qdrant/Weaviate 的接口 |
| Token 限制超限 | 中 | 中 | 1) 分层摘要避免单次过大 2) 代码截断策略 |
| 并发 LLM 调用速率限制 | 高 | 低 | 1) tenacity 重试 2) 并发控制 (max_concurrent=5) |

---

## Prompt 设计参考

### 方法摘要 Prompt

```python
METHOD_SUMMARY_PROMPT = """你是一个 Java 代码分析专家。请用一句话总结以下方法的功能，专注于它解决的业务问题。

类名: {class_name}
方法名: {method_name}
方法签名: {signature}
访问修饰符: {modifiers}
注解: {annotations}

源代码:
```java
{source_code}
```

要求:
1. 使用业务语言，避免技术术语（如"调用 DAO" → "查询数据库"）
2. 一句话，不超过30字
3. 格式: "动词 + 宾语"（如"验证用户登录凭据"）
4. 如果是纯技术方法（getter/setter/toString），返回 "N/A"
5. 关注业务意图而非实现细节

摘要:"""
```

### 类摘要 Prompt

```python
CLASS_SUMMARY_PROMPT = """你是业务分析师。请基于以下方法摘要，生成这个类的业务摘要。

类名: {class_name}
类型: {class_type}  # Controller/Service/Repository/Entity
注解: {annotations}

方法摘要列表:
{method_summaries}

要求:
1. 一句话描述这个类的核心职责
2. 使用业务语言（如"处理用户订单"而非"接收 HTTP 请求"）
3. 不超过50字
4. 如果是 Controller/Service/Repository，从业务角度描述

类摘要:"""
```

### 领域词汇表 Prompt

```python
GLOSSARY_TERM_PROMPT = """你是业务分析师。请为以下代码术语解释其业务含义。

术语: {term}
上下文:
- 类名: {class_name}
- 方法名: {method_name}
- 相关注释: {comment}

输出 JSON 格式:
{{
  "business_meaning": "业务含义描述（1-2句话，使用业务语言）",
  "synonyms": ["同义词1", "同义词2"]  # 可选
}}
"""
```

---

## 测试策略

### 单元测试

- `test_llm_client.py`：Mock LLM API 响应
- `test_vector_store.py`：使用临时 ChromaDB 实例
- `test_summarizer.py`：Mock LLM，测试聚合逻辑

### 集成测试

- 使用 Spring PetClinic 作为测试项目
- 验证完整流程：extract → summarize → search
- 测试增量更新

### 质量评估

- 人工标注 100 个方法的摘要质量
- 计算相关性指标（MRR, NDCG）
- 迭代优化 Prompt

---

## 实施顺序建议

1. **Week 1**: Phase 3.1 (LLM 集成) + Phase 3.2 (ChromaDB)
2. **Week 2**: Phase 3.3 (分层摘要) - 核心功能
3. **Week 3**: Phase 3.4 (词汇表) + Phase 3.5 (约束提取)
4. **Week 4**: Phase 3.6 (CLI 集成) + 测试优化

---

## References

### Internal References

- Phase 1/2 实现：
  - `ariadne_core/models/types.py:1-205`
  - `ariadne_core/storage/sqlite_store.py:1-408`
  - `ariadne_core/extractors/asm/extractor.py:1-351`

### External References

- LLM 集成参考：`/Users/jersyzhang/work/auto-claude-new/ai-memory-system`
  - `src/memory/providers_pkg/factory.py` - Provider 模式
  - `src/memory/config.py` - 配置模式
  - `src/memory/providers_pkg/llm_providers/openai_llm.py` - OpenAI 集成

- ChromaDB 文档：https://docs.trychroma.com/
- OpenAI API 文档：https://platform.openai.com/docs/api-reference

### Research Findings

1. **LLM Provider 模式**：使用 Factory 模式支持多 Provider（OpenAI/DeepSeek/Ollama）
2. **配置管理**：环境变量 + dataclass，支持 `from_env()` 加载
3. **分层摘要**：Bottom-Up 聚合避免单次 LLM 输入过大
4. **错误处理**：使用 tenacity 实现指数退避重试
5. **向量存储**：ChromaDB 轻量级，支持持久化和元数据过滤
