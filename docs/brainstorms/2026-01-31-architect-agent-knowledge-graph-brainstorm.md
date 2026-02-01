# Architect Agent Codebase Knowledge Graph (Ariadne)

**Date:** 2026-01-31
**Status:** Brainstorm Complete - Ready for Planning
**Reference:** 架构师 Agent 核心知识底座开发需求规格书 v1.0

## What We're Building

一个多维度代码知识图谱系统（代号 **Ariadne**），作为"架构师 Agent"的智能底座。系统从代码库自动提取语义信息、结构关系及隐式规则，赋予 Agent：

- **全局视野**：理解代码解决的业务问题（L1 业务层）
- **精准规划**：提供技术约束和调用链路（L2 架构层）
- **防遗漏**：精准分析修改的影响范围（L3 实现层）

### 核心特征

| 维度 | 决策 |
|------|------|
| 服务对象 | AI Coding Agent（通过 HTTP API 查询） |
| 目标代码库 | Java + Spring + MyBatis + Quartz（MVP） |
| 存储方式 | 渐进式：SQLite → 可升级至图数据库 |
| 语义检索 | 轻量向量库（ChromaDB/Qdrant） |
| 构建策略 | 离线基线 + 增量更新（< 2 分钟） |
| 实现语言 | Python |

---

## 三层知识架构（对齐规格书）

```
┌─────────────────────────────────────────────────────────────────────┐
│  L1 业务与领域层 (Business & Domain Layer)                           │
│  目标: What & Why                                                    │
│  ├─ 业务能力映射 (Business Capability Mapping)                       │
│  │   - 模块/服务的自然语言摘要 [Must]                                │
│  │   - 入口识别: HTTP API, Cron Jobs, MQ Consumers [Must]           │
│  │   - 关键约束提取: 业务规则 [Should]                               │
│  └─ 领域词汇表 (Ubiquitous Language Glossary)                       │
│      - Code Term ↔ Business Meaning 映射 [Must]                     │
│      - 同义词关联 [Should]                                          │
│  构建方式: LLM 分层摘要 + 向量化存储                                 │
└─────────────────────────────────────────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────┐
│  L2 架构与设计层 (Architecture & Design Layer)                       │
│  目标: Planning & Constraints                                        │
│  ├─ 技术栈与规范库 (Tech Stack & Standards)                          │
│  │   - 框架识别: 解析 pom.xml 等 [Must]                              │
│  │   - 隐式约定挖掘: 高频注解模式、异常处理规范 [Should]              │
│  │   - 反模式检测: 禁止调用路径 [Should]                              │
│  ├─ 核心链路与依赖分析 (Link & Dependency Analysis)                  │
│  │   - 核心调用链追踪: Entry → Controller → Service → DAO [Must]     │
│  │   - 外部依赖拓扑: Redis/MySQL/RPC + 强弱依赖标注 [Must]           │
│  └─ 设计模式识别 (Design Pattern Recognition)                        │
│      - AST 特征匹配: 单例/工厂/策略/观察者 [Could]                   │
│  构建方式: 静态分析 + LLM 总结                                       │
└─────────────────────────────────────────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────┐
│  L3 代码实现与结构层 (Implementation & Structure Layer)              │
│  目标: How & Where                                                   │
│  ├─ 符号索引与全图谱 (Symbol Indexing & Graph)                       │
│  │   - 实体提取: Class, Interface, Function, Variable [Must]        │
│  │   - 关系构建: Inherits, Calls, Instantiates, Reads/Writes [Must] │
│  │   - 性能要求: 图查询 < 500ms                                      │
│  └─ 模块拓扑与测试映射 (Topology & Test Mapping)                     │
│      - 目录职责推断: utils/api/core 等 [Must]                        │
│      - Source ↔ Test 双向映射 [Must]                                │
│  构建方式: 纯静态分析 (tree-sitter + javalang)                       │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Key Decisions

### 1. 存储方案：渐进式升级

**MVP 阶段：**
| 内容类型 | 存储 | 理由 |
|---------|------|------|
| 符号索引、调用关系 | SQLite | 支持 SQL JOIN，可升级 |
| 业务摘要、领域词汇 | SQLite + ChromaDB | 结构化 + 向量检索 |
| 技术规范、约束规则 | JSON 文件 | 人可读、易编辑 |

**升级路径：**
- SQLite 调用图 → Neo4j（当图查询复杂度超出 SQL 表达能力时）
- 架构预留 `GraphStore` 抽象接口，支持无缝切换

### 2. 语义检索：轻量向量库

- 使用 **ChromaDB**（本地部署，无外部依赖）
- 索引内容：L1 业务摘要、L2 技术规范文档
- 查询流程：
  ```
  用户查询 → Embedding → 向量相似度 → 候选节点 → 结构化过滤 → 返回结果
  ```

### 3. 解析工具链

| 解析目标 | 工具 | 优先级 |
|---------|------|--------|
| Java 语法/AST | tree-sitter-java | Must |
| Spring 注解 | 自定义注解扫描器 | Must |
| MyBatis XML | lxml + 自定义解析 | Must |
| Quartz Job | @Scheduled + XML 扫描 | Should |
| pom.xml 依赖 | xml.etree | Must |

### 4. HTTP API 设计（对齐规格书）

```
GET  /knowledge/search?query={natural_language}
     → 混合检索（语义+关键词），返回业务能力节点

POST /knowledge/graph/query
     → 执行图查询，返回指定深度的调用链/依赖
     Body: { "start": "UserService", "relation": "calls", "depth": 3 }

GET  /knowledge/constraints?context={code_path}
     → 获取指定模块的技术约束和规范

GET  /knowledge/impact?entry_point={api_name}
     → 基于静态图分析改动影响范围

POST /knowledge/rebuild
     → 触发全量/增量重建
     Body: { "mode": "incremental" | "full" }
```

### 5. Java/Spring 特有解析

**入口识别（Entry Points）：**
| 类型 | 识别方式 |
|------|---------|
| HTTP API | `@RestController` + `@RequestMapping` → URL, Method, Handler |
| 定时任务 | `@Scheduled` / Quartz Job 配置 |
| MQ 消费者 | `@RabbitListener` / `@KafkaListener` |

**调用链构建：**
```
Entry Point
    ↓ @RequestMapping
Controller
    ↓ @Autowired
Service
    ↓ @Autowired
Mapper/Repository
    ↓ MyBatis XML
SQL (Table Read/Write)
```

**外部依赖标记：**
| 中间件 | 识别模式 | 标记类型 |
|--------|---------|---------|
| Redis | RedisTemplate.* | cache / external_store |
| MySQL | JdbcTemplate / MyBatis | database |
| MQ | JmsTemplate / RabbitTemplate | async_messaging |
| RPC | RestTemplate / FeignClient | external_service |

---

## Refined Decisions

### 6. 增量更新策略

- **触发方式**：Git Hook + HTTP API 混合
- **更新粒度**：文件级别（git diff 获取变更文件列表）
- **传播逻辑**：
  1. 重解析变更文件的符号
  2. 更新直接引用关系
  3. 标记受影响的 L1/L2 摘要为 stale
  4. 按需重新生成 LLM 摘要
- **性能目标**：单次 commit 增量更新 < 2 分钟

### 7. 多模块处理

- MVP：扁平处理，整个 repo 视为一个分析单元
- 所有 `.java` 文件统一扫描，不区分 Maven 子模块
- 后期可通过解析 pom.xml 的 `<modules>` 添加模块边界感知

### 8. 规范与约束存储

```json
// constraints/anti-patterns.json
{
  "rules": [
    {
      "id": "no-controller-dao",
      "name": "禁止 Controller 直连 DAO",
      "pattern": "Controller.* -> .*Mapper|.*Repository",
      "severity": "error",
      "message": "Controller 层不应直接调用数据访问层，请通过 Service 层中转"
    }
  ]
}
```

### 9. API 安全

- MVP：内网部署，无认证
- 预留 `X-API-Key` header 检查逻辑，通过环境变量控制启用

---

## 验收场景（来自规格书）

### Scenario 1: 规划辅助
**输入**："增加登录验证码"
**期望输出**：
- AuthController 代码位置
- AuthService 依赖列表
- "登录锁定"业务约束

### Scenario 2: 防遗漏
**输入**：修改 UserService 接口
**期望输出**：
- 所有调用 UserService 的 Controller 列表
- 关联的 Test 文件列表
- 未覆盖测试的调用路径警告

### Scenario 3: 规范检查
**输入**：Agent 尝试在 Controller 中写 SQL
**期望输出**：
- 命中反模式规则 "no-controller-dao"
- 返回纠正建议

---

## 非功能需求

| 指标 | 目标 |
|------|------|
| 引用关系准确率 | ≥ 99%（静态类型语言） |
| 图查询响应 | < 500ms |
| 增量更新延迟 | < 2 分钟 |
| 语言支持 | MVP: Java，架构预留插件扩展 |

---

## Next Steps

运行 `/workflows:plan` 生成详细实现计划。

### Plan 阶段关注点

1. **Python 项目结构**：包组织、依赖管理（Poetry/uv）
2. **解析器实现顺序**：
   - Phase 1: L3 符号索引 + 调用图
   - Phase 2: L2 链路追踪 + 外部依赖
   - Phase 3: L1 业务摘要 + 向量检索
3. **存储 Schema 设计**：SQLite 表结构、ChromaDB collection 设计
4. **HTTP API 框架**：FastAPI + Pydantic
5. **测试策略**：用开源 Java 项目（如 Spring PetClinic）做集成测试
