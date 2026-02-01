---
title: "feat: Ariadne Codebase Knowledge Graph for Architect Agent"
type: feat
date: 2026-01-31
status: ready
reference:
  - docs/brainstorms/2026-01-31-architect-agent-knowledge-graph-brainstorm.md
  - /Users/jersyzhang/work/CallGraph (参考实现)
  - /Users/jersyzhang/work/auto-claude-new/ai-memory-system (语义存储参考)
---

# Ariadne: 架构师 Agent 代码知识图谱系统

## Overview

Ariadne 是一个多维度代码知识图谱系统，为"架构师 Agent"提供智能底座。系统从 Java/Spring 代码库自动提取语义信息、结构关系及隐式规则，通过三层知识架构（业务层、架构层、实现层）赋予 Agent 全局视野和精准规划能力。

**核心价值：**
- **全局视野**：理解代码解决的业务问题（L1）
- **精准规划**：提供技术约束和调用链路（L2）
- **防遗漏**：精准分析修改的影响范围（L3）

---

## Problem Statement / Motivation

传统 RAG 方案在复杂项目分析中存在"只见树木不见森林"的问题：
1. 缺乏代码结构的全局理解
2. 无法追踪跨模块的调用链路
3. 难以识别修改的影响范围
4. 业务语义与代码实现脱节

**现有资源：**
- **CallGraph** 项目已实现 L2/L3 层的核心能力（ASM 字节码分析、调用图、Spring/MyBatis 解析）
- **ai-memory-system** 提供了语义存储和向量检索的参考实现

Ariadne 将参考这些实现，构建一个更完整的三层知识体系。

---

## Proposed Solution

### 三层知识架构

```
┌─────────────────────────────────────────────────────────────────────┐
│  L1 业务与领域层 (Business & Domain Layer) - NEW                     │
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
│  L2 架构与设计层 (参考 CallGraph)                                    │
│  目标: Planning & Constraints                                        │
│  ├─ 技术栈识别 (pom.xml 解析)                                        │
│  ├─ 核心调用链追踪 (Entry → Controller → Service → DAO)             │
│  ├─ 外部依赖拓扑 (Redis/MySQL/RPC)                                   │
│  └─ 反模式检测 (规则引擎)                                            │
│  构建方式: 复用/参考 CallGraph 的 ASM 分析                           │
└─────────────────────────────────────────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────┐
│  L3 代码实现层 (参考 CallGraph)                                      │
│  目标: How & Where                                                   │
│  ├─ 符号索引 (Class, Interface, Method, Field)                      │
│  ├─ 关系构建 (Inherits, Calls, Instantiates)                        │
│  └─ 测试映射 (Source ↔ Test)                                        │
│  构建方式: 复用/参考 CallGraph 的 ASM 分析                           │
└─────────────────────────────────────────────────────────────────────┘
```

### 技术栈选择

| 组件 | 技术选型 | 理由 |
|------|----------|------|
| 语言 | Python 3.12+ | 与 CallGraph/ai-memory-system 一致 |
| 代码解析 | ASM (Java 字节码) | 100% 准确，参考 CallGraph |
| 关系存储 | SQLite | 与 CallGraph 一致，渐进式可升级 |
| 向量存储 | ChromaDB | 轻量、本地部署 |
| HTTP API | FastAPI + Pydantic | 现代 Python API 框架 |
| LLM 接口 | OpenAI-compatible | 支持 DeepSeek/OpenAI 等 |

---

## Technical Approach

### 架构设计

```
ariadne/
├── ariadne_core/                    # 核心解析层
│   ├── extractors/                  # 代码提取器
│   │   ├── asm/                     # ASM 字节码分析 (参考 CallGraph)
│   │   │   ├── client.py            # ASM Service 客户端
│   │   │   ├── extractor.py         # 主提取逻辑
│   │   │   └── symbol_indexer.py    # 符号索引
│   │   ├── spring/                  # Spring 框架分析
│   │   │   ├── bean_scanner.py      # @Component/@Service/@Repository
│   │   │   ├── aop_analyzer.py      # @Aspect/@Transactional
│   │   │   └── entry_detector.py    # @RestController 入口
│   │   └── mybatis/                 # MyBatis 映射分析
│   │       ├── mapper_parser.py     # Mapper 接口解析
│   │       └── xml_parser.py        # XML SQL 解析
│   ├── storage/                     # 存储层
│   │   ├── sqlite_store.py          # SQLite 图存储
│   │   ├── vector_store.py          # ChromaDB 向量存储
│   │   └── schema.py                # 数据库 Schema
│   └── models/                      # 数据模型
│       └── types.py                 # ClassData, MethodData, EdgeData 等
│
├── ariadne_analyzer/                # 分析层
│   ├── l1_business/                 # L1 业务层分析
│   │   ├── summarizer.py            # LLM 分层摘要
│   │   ├── glossary.py              # 领域词汇表
│   │   └── constraints.py           # 业务约束提取
│   ├── l2_architecture/             # L2 架构层分析
│   │   ├── call_chain.py            # 调用链追踪
│   │   ├── dependency_graph.py      # 依赖拓扑
│   │   └── anti_patterns.py         # 反模式检测
│   └── l3_implementation/           # L3 实现层分析
│       ├── impact_analyzer.py       # 影响范围分析
│       └── test_mapper.py           # 测试映射
│
├── ariadne_api/                     # API 服务层
│   ├── server.py                    # FastAPI 主入口
│   ├── routes/                      # API 路由
│   │   ├── search.py                # /knowledge/search
│   │   ├── graph.py                 # /knowledge/graph/query
│   │   ├── constraints.py           # /knowledge/constraints
│   │   ├── impact.py                # /knowledge/impact
│   │   └── rebuild.py               # /knowledge/rebuild
│   └── schemas/                     # Pydantic 模型
│
├── asm-analysis-service/            # Java ASM 服务 (参考 CallGraph)
│   └── (从 CallGraph 复制/简化)
│
├── tests/                           # 测试
│   ├── unit/
│   ├── integration/
│   └── fixtures/                    # 测试用 Java 项目
│
└── pyproject.toml                   # 项目配置
```

### 实现阶段

#### Phase 1: 基础设施 + L3 实现层

**目标**：搭建项目骨架，实现符号索引和调用图。

**任务清单**：

- [ ] **1.1 项目初始化**
  - 创建 `pyproject.toml` (Poetry/uv)
  - 配置 pytest、ruff、mypy
  - 创建目录结构

- [ ] **1.2 ASM 服务集成**
  - 从 CallGraph 复制/简化 `asm-analysis-service/`
  - 实现 `ariadne_core/extractors/asm/client.py`
  - 验证字节码分析工作

- [ ] **1.3 SQLite 存储层**
  - 设计 Schema（见下方详细设计）
  - 实现 `sqlite_store.py`
  - 支持符号索引 CRUD

- [ ] **1.4 符号提取器**
  - 实现 Class/Interface/Method/Field 提取
  - 构建 Inherits/Implements/Calls 关系
  - 支持增量更新（基于文件 hash）

**验收标准**：
```bash
# 能够提取 Java 项目的符号和调用关系
ariadne extract --project /path/to/java-project
# 输出: ariadne.db (SQLite)
```

#### Phase 2: L2 架构层

**目标**：实现调用链追踪、外部依赖识别、Spring 注入分析。

**任务清单**：

- [ ] **2.1 Spring 组件扫描**
  - 实现 `bean_scanner.py` 识别 @Component/@Service 等
  - 解析 @Autowired 依赖关系
  - 识别 @RestController 入口点

- [ ] **2.2 调用链追踪**
  - 实现 `call_chain.py`
  - 从 Entry Point 正向遍历到 DAO/DB
  - 支持指定深度限制

- [ ] **2.3 外部依赖识别**
  - 识别 RedisTemplate/JmsTemplate/RestTemplate 调用
  - 标记为 external_dependency 节点
  - 区分强依赖/弱依赖

- [ ] **2.4 MyBatis 集成**
  - 解析 Mapper 接口 → XML 映射
  - 提取 SQL 语句和操作类型
  - 建立 Service → Mapper → Table 链路

**验收标准**：
```bash
# 能够追踪 API 入口的完整调用链
ariadne trace --entry "POST /api/orders"
# 输出: OrderController → OrderService → OrderMapper → t_orders
```

#### Phase 3: L1 业务层 + 向量检索

**目标**：实现 LLM 摘要生成、领域词汇表、语义检索。

**任务清单**：

- [ ] **3.1 ChromaDB 集成**
  - 实现 `vector_store.py`
  - 定义 Collection 结构（summaries, glossary）
  - 支持混合检索（向量 + 关键词）

- [ ] **3.2 LLM 摘要生成**
  - 实现分层摘要策略：Method → Class → Package → Module
  - 设计 Prompt 模板
  - 支持增量摘要（只重新生成变更部分）

- [ ] **3.3 领域词汇表**
  - 从类名、方法名、注释中提取术语
  - LLM 生成 Code Term → Business Meaning 映射
  - 支持同义词关联

- [ ] **3.4 业务约束提取**
  - 从注释、Assert 语句中提取规则
  - LLM 识别隐式约束
  - 存储到 constraints 表

**验收标准**：
```bash
# 自然语言查询
ariadne search "登录验证码"
# 输出: AuthController, AuthService, 相关约束
```

#### Phase 4: HTTP API + 规范检测

**目标**：实现 HTTP API 服务、影响范围分析、反模式检测。

**任务清单**：

- [ ] **4.1 FastAPI 服务**
  - 实现 `/knowledge/search` 混合检索
  - 实现 `/knowledge/graph/query` 图查询
  - 实现 `/knowledge/impact` 影响分析
  - 实现 `/knowledge/constraints` 约束查询
  - 实现 `/knowledge/rebuild` 重建触发

- [ ] **4.2 影响范围分析**
  - 反向遍历调用图
  - 映射到 Entry Points 和 Tests
  - 输出影响清单

- [ ] **4.3 反模式检测**
  - 实现规则引擎（JSON 配置）
  - 内置规则：Controller 直连 DAO、循环依赖等
  - 支持自定义规则

- [ ] **4.4 增量更新**
  - Git Hook 集成
  - 文件级别变更检测
  - 级联更新受影响节点

**验收标准**：
```bash
# API 服务运行
ariadne serve --port 8080

# 查询影响范围
curl "http://localhost:8080/knowledge/impact?entry_point=UserService"
# 输出: 受影响的 Controller、Test、Entry Point 列表
```

---

## 存储 Schema 设计

### SQLite 表结构

```sql
-- ============== L3 实现层 ==============

-- 符号节点
CREATE TABLE symbols (
    id INTEGER PRIMARY KEY,
    fqn TEXT NOT NULL UNIQUE,           -- 全限定名 com.example.UserService
    kind TEXT NOT NULL,                  -- class, interface, method, field
    name TEXT NOT NULL,                  -- 简称 UserService
    file_path TEXT,                      -- 源文件路径
    line_number INTEGER,
    modifiers TEXT,                      -- public, static, etc. (JSON array)
    signature TEXT,                      -- 方法签名
    parent_fqn TEXT,                     -- 父类/所属类 FQN
    annotations TEXT,                    -- 注解列表 (JSON array)
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_symbols_fqn ON symbols(fqn);
CREATE INDEX idx_symbols_kind ON symbols(kind);
CREATE INDEX idx_symbols_file ON symbols(file_path);

-- 关系边
CREATE TABLE edges (
    id INTEGER PRIMARY KEY,
    from_fqn TEXT NOT NULL,
    to_fqn TEXT NOT NULL,
    relation TEXT NOT NULL,              -- calls, inherits, implements, instantiates, injects
    metadata TEXT,                       -- 额外信息 (JSON)
    FOREIGN KEY (from_fqn) REFERENCES symbols(fqn),
    FOREIGN KEY (to_fqn) REFERENCES symbols(fqn)
);

CREATE INDEX idx_edges_from ON edges(from_fqn);
CREATE INDEX idx_edges_to ON edges(to_fqn);
CREATE INDEX idx_edges_relation ON edges(relation);

-- ============== L2 架构层 ==============

-- 入口点
CREATE TABLE entry_points (
    id INTEGER PRIMARY KEY,
    symbol_fqn TEXT NOT NULL,            -- 指向 symbols.fqn
    entry_type TEXT NOT NULL,            -- http_api, scheduled, mq_consumer
    http_method TEXT,                    -- GET, POST, etc.
    http_path TEXT,                      -- /api/users
    cron_expression TEXT,                -- Quartz cron
    mq_queue TEXT,                       -- 队列名
    FOREIGN KEY (symbol_fqn) REFERENCES symbols(fqn)
);

-- 外部依赖
CREATE TABLE external_dependencies (
    id INTEGER PRIMARY KEY,
    caller_fqn TEXT NOT NULL,
    dependency_type TEXT NOT NULL,       -- redis, mysql, mq, rpc
    target TEXT,                         -- 目标地址/表名/队列名
    strength TEXT DEFAULT 'strong',      -- strong, weak
    FOREIGN KEY (caller_fqn) REFERENCES symbols(fqn)
);

-- 反模式检测结果
CREATE TABLE anti_patterns (
    id INTEGER PRIMARY KEY,
    rule_id TEXT NOT NULL,
    from_fqn TEXT NOT NULL,
    to_fqn TEXT,
    severity TEXT NOT NULL,              -- error, warning, info
    message TEXT NOT NULL,
    detected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ============== L1 业务层 ==============

-- 业务摘要 (存 SQLite，向量存 ChromaDB)
CREATE TABLE summaries (
    id INTEGER PRIMARY KEY,
    target_fqn TEXT NOT NULL,            -- 被摘要的符号 FQN
    level TEXT NOT NULL,                 -- method, class, package, module
    summary TEXT NOT NULL,               -- 自然语言摘要
    vector_id TEXT,                      -- ChromaDB 中的向量 ID
    is_stale BOOLEAN DEFAULT FALSE,      -- 是否需要重新生成
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 领域词汇表
CREATE TABLE glossary (
    id INTEGER PRIMARY KEY,
    code_term TEXT NOT NULL,             -- 代码术语 (类名/方法名)
    business_meaning TEXT NOT NULL,      -- 业务含义
    synonyms TEXT,                       -- 同义词 (JSON array)
    source_fqn TEXT,                     -- 来源符号 FQN
    vector_id TEXT                       -- ChromaDB 向量 ID
);

-- 业务约束
CREATE TABLE constraints (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT NOT NULL,
    source_fqn TEXT,                     -- 来源符号
    source_line INTEGER,
    constraint_type TEXT,                -- validation, business_rule, invariant
    vector_id TEXT
);

-- ============== 元数据 ==============

CREATE TABLE index_metadata (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
-- 存储: last_indexed_commit, schema_version, etc.
```

### ChromaDB Collection 设计

```python
# Collection: ariadne_summaries
{
    "ids": ["summary_001"],
    "documents": ["UserService 负责用户注册、登录、权限验证"],
    "metadatas": [{"fqn": "com.example.UserService", "level": "class"}],
    "embeddings": [[0.123, -0.456, ...]]
}

# Collection: ariadne_glossary
{
    "ids": ["term_001"],
    "documents": ["Sku - 商品库存单位，唯一标识一个可售卖的商品规格"],
    "metadatas": [{"code_term": "Sku", "source_fqn": "com.example.Sku"}],
    "embeddings": [[...]]
}

# Collection: ariadne_constraints
{
    "ids": ["constraint_001"],
    "documents": ["库存数量不可为负"],
    "metadatas": [{"source_fqn": "com.example.InventoryService", "type": "business_rule"}],
    "embeddings": [[...]]
}
```

---

## HTTP API 设计

### 端点定义

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

# POST /knowledge/graph/query
# 图查询
Request:
  start: string               # 起始节点 FQN
  relation: string            # calls, inherits, depends_on
  direction: string = "outgoing"  # outgoing, incoming, both
  depth: int = 3
  filters:
    kind: string[]
Response:
  nodes: [...]
  edges: [...]

# GET /knowledge/impact?target={fqn}
# 影响范围分析
Request:
  target: string              # 被修改的符号 FQN
Response:
  affected_entry_points: [...]
  affected_tests: [...]
  call_paths: [...]           # 从 Entry Point 到 target 的路径

# GET /knowledge/constraints?context={path}
# 获取约束
Request:
  context: string             # 代码路径或 FQN
Response:
  constraints: [...]
  anti_patterns: [...]

# POST /knowledge/rebuild
# 触发重建
Request:
  mode: string = "incremental"  # incremental, full
  target_paths: string[]        # 可选，指定路径
Response:
  status: string
  stats:
    symbols_updated: int
    summaries_regenerated: int
```

---

## 验收场景

### Scenario 1: 规划辅助

**输入**："增加登录验证码"

**期望输出**：
```json
{
  "related_symbols": [
    {"fqn": "com.example.AuthController", "summary": "处理用户认证相关 HTTP 请求"},
    {"fqn": "com.example.AuthService", "summary": "认证业务逻辑，包括登录、注销、token 管理"}
  ],
  "entry_points": [
    {"path": "POST /api/auth/login", "handler": "AuthController.login"}
  ],
  "constraints": [
    {"name": "登录锁定", "description": "连续失败5次后锁定账户30分钟"}
  ],
  "dependencies": [
    {"type": "redis", "usage": "存储验证码和登录失败计数"}
  ]
}
```

### Scenario 2: 防遗漏

**输入**：修改 UserService.updateProfile() 接口

**期望输出**：
```json
{
  "affected_entry_points": [
    "PUT /api/users/profile",
    "PUT /api/admin/users/{id}"
  ],
  "affected_callers": [
    "UserController.updateProfile",
    "AdminController.updateUser"
  ],
  "related_tests": [
    "UserServiceTest.testUpdateProfile",
    "UserControllerTest.testUpdateProfileApi"
  ],
  "missing_test_coverage": [
    "AdminController.updateUser -> UserService.updateProfile (无测试覆盖)"
  ]
}
```

### Scenario 3: 规范检查

**输入**：Agent 在 Controller 中写 SQL

**期望输出**：
```json
{
  "anti_patterns": [
    {
      "rule_id": "no-controller-dao",
      "severity": "error",
      "from": "OrderController.listOrders",
      "to": "JdbcTemplate.query",
      "message": "Controller 层不应直接调用数据访问层，请通过 Service 层中转",
      "suggestion": "将数据库操作移至 OrderService"
    }
  ]
}
```

---

## 非功能需求

| 指标 | 目标 | 验证方法 |
|------|------|----------|
| 引用关系准确率 | ≥ 99% | 与 CallGraph 对比验证 |
| 图查询响应 | < 500ms | pytest-benchmark |
| 增量更新延迟 | < 2 分钟 | 监控单次 commit 处理时间 |
| 自然语言检索相关性 | MRR@10 ≥ 0.7 | 人工标注测试集 |

---

## Dependencies & Prerequisites

### 外部依赖

```toml
# pyproject.toml
[project]
dependencies = [
    "fastapi>=0.115.0",
    "uvicorn>=0.34.0",
    "pydantic>=2.0",
    "httpx>=0.27.0",           # ASM Service 通信
    "chromadb>=0.5.0",         # 向量存储
    "openai>=1.0.0",           # LLM API
    "tqdm>=4.65.0",
    "python-dotenv>=1.0.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0.0",
    "pytest-asyncio>=0.24.0",
    "ruff>=0.6.0",
    "mypy>=1.11.0",
]
```

### CallGraph 依赖

- 需要 Java 17+ 环境运行 ASM Analysis Service
- 可从 CallGraph 复制 `asm-analysis-service/` 目录

---

## Risk Analysis & Mitigation

| 风险 | 可能性 | 影响 | 缓解措施 |
|------|--------|------|----------|
| ASM 服务启动慢 | 中 | 低 | 支持预热、保持常驻 |
| LLM 调用成本高 | 中 | 中 | 增量摘要、缓存、批量处理 |
| ChromaDB 性能瓶颈 | 低 | 中 | 预留切换到 Qdrant 的接口 |
| SQLite 图查询复杂度 | 中 | 中 | 递归 CTE 深度限制、预留 Neo4j 升级路径 |

---

## 测试策略

### 单元测试

- 每个 Extractor、Analyzer 独立测试
- Mock ASM Service 响应

### 集成测试

- 使用 Spring PetClinic 项目作为测试 fixture
- 验证完整的提取 → 存储 → 查询流程

### E2E 测试

- 启动 FastAPI 服务
- 通过 HTTP 调用验证所有端点

---

## References & Research

### Internal References

- CallGraph 项目：`/Users/jersyzhang/work/CallGraph`
  - ASM 服务：`asm-analysis-service/`
  - 核心提取器：`callgraph_core/extractors/`
  - 存储层：`callgraph_core/storage/`
- ai-memory-system：`/Users/jersyzhang/work/auto-claude-new/ai-memory-system`
  - Graphiti 集成：`src/memory/graphiti/`
  - 多 Provider 支持：`src/memory/providers_pkg/`

### External References

- [tree-sitter-java PyPI](https://pypi.org/project/tree-sitter-java/) - Python 0.25.2 / Java grammar 0.23.5
- [ChromaDB Documentation](https://docs.trychroma.com/)
- [Joern Code Property Graph](https://joern.io/)
- [SCIP (Sourcegraph)](https://sourcegraph.com/blog/announcing-scip)
- [SQLite Recursive CTEs](https://sqlite.org/lang_with.html)
- [sqlite-graph Extension](https://github.com/agentflare-ai/sqlite-graph)

### Research Findings

1. **ASM 字节码分析优于 tree-sitter**：CallGraph 实践证明 ASM 分析 100% 准确
2. **分层摘要策略**：File level 用全代码，Module level 用聚合摘要
3. **SQLite 递归 CTE**：支持 10-20 层深度的调用链遍历，超过需考虑 Neo4j
4. **Spring @Autowired 解析**：需构建 Bean Registry，按类型 → Qualifier → 名称解析
