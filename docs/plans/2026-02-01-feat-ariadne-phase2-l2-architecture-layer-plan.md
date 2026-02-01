---
title: "feat: Ariadne Phase 2 - L2 Architecture Layer"
type: feat
date: 2026-02-01
status: ready
reference:
  - docs/plans/2026-01-31-feat-ariadne-codebase-knowledge-graph-plan.md
  - /Users/jersyzhang/work/CallGraph (参考实现)
---

# Ariadne Phase 2: L2 架构层实现

## Overview

基于 Phase 1 的 L3 实现层基础，构建 L2 架构层能力：入口点检测、调用链追踪、外部依赖识别、反模式检测。

**核心价值**：让 Agent 能够回答"这个 API 调用了哪些服务？用了 Redis 吗？有事务吗？"

## Problem Statement / Motivation

Phase 1 已完成符号索引和基础调用图，但缺少：
- HTTP API 入口点的结构化存储
- 外部依赖（Redis/MQ/RPC）的识别
- 从入口到数据层的完整调用链
- 反模式检测（如 Controller 直连 DAO）

## Proposed Solution

**最小改动原则**：充分利用 ASM 服务已输出的 Spring 注解信息，扩展 Python 层的处理逻辑。

### 数据流

```
ASM 服务输出 (已有丰富的 Spring 注解信息)
    ↓
extractor.py 扩展 (提取 L2 信息)
    ↓
L2 分析器 (新增模块)
    ↓
SQLite L2 表 (entry_points, external_dependencies, anti_patterns)
```

---

## Technical Approach

### 关键发现：ASM 服务已提供的信息

| 信息类型 | ASM 输出字段 | 用途 |
|---------|-------------|------|
| Spring Bean 类型 | `springBeanType` ("service"/"restController"等) | 组件分类 |
| HTTP 入口 | `isRestEndpoint`, `httpMethod`, `entryPointType` | 入口点检测 |
| 定时任务 | `isScheduled`, `scheduledCron` | 入口点检测 |
| 依赖注入 | `injectionType` ("autowired"/"inject") | Bean 依赖图 |
| 事务 | `isTransactional` | 事务边界 |
| MyBatis 调用 | `isMybatisBaseMapperCall`, `mybatisOperationType` | 数据层识别 |

### 文件结构

```
ariadne/
├── ariadne_core/
│   ├── extractors/
│   │   ├── asm/
│   │   │   └── extractor.py          # 修改: 扩展 _process_classes()
│   │   └── spring/                   # 新增: Spring 分析器
│   │       ├── __init__.py
│   │       ├── entry_detector.py     # 入口点检测
│   │       └── dependency_analyzer.py # 外部依赖分析
│   ├── storage/
│   │   ├── schema.py                 # 已有 L2 表结构
│   │   └── sqlite_store.py           # 修改: 添加 L2 CRUD 方法
│   └── models/
│       └── types.py                  # 修改: 添加 L2 数据类型
│
├── ariadne_analyzer/
│   └── l2_architecture/              # 新增: L2 分析器
│       ├── __init__.py
│       ├── call_chain.py             # 调用链追踪
│       ├── anti_patterns.py          # 反模式检测
│       └── rules/                    # 检测规则
│           └── controller_dao.py
│
└── tests/
    ├── unit/
    │   ├── test_entry_detector.py
    │   ├── test_dependency_analyzer.py
    │   └── test_call_chain.py
    └── integration/
        └── test_l2_mall_project.py
```

---

## Implementation Phases

### Phase 2.1: 入口点检测 (entry_detector.py)

**目标**：从 ASM 输出提取 HTTP API、定时任务入口，存入 `entry_points` 表。

**输入**：ASM 分析结果中的 `methods` 数组

**检测逻辑**：

```python
# ariadne_core/extractors/spring/entry_detector.py

class EntryDetector:
    """从 ASM 输出检测入口点。"""

    def detect_entries(self, classes: list[dict]) -> list[EntryPointData]:
        entries = []
        for class_data in classes:
            # 检查类级别的 @RestController
            is_rest_controller = class_data.get("springBeanType") == "restController"
            class_base_path = class_data.get("classBasePath", "")

            for method in class_data.get("methods", []):
                # HTTP 入口
                if method.get("isRestEndpoint"):
                    entries.append(EntryPointData(
                        symbol_fqn=method["fqn"],
                        entry_type="http_api",
                        http_method=method.get("httpMethod", "GET"),
                        http_path=self._build_path(class_base_path, method),
                    ))

                # 定时任务入口
                if method.get("isScheduled"):
                    entries.append(EntryPointData(
                        symbol_fqn=method["fqn"],
                        entry_type="scheduled",
                        cron_expression=method.get("scheduledCron"),
                    ))

        return entries
```

**数据类型** (types.py 新增)：

```python
@dataclass
class EntryPointData:
    symbol_fqn: str
    entry_type: str          # http_api | scheduled | mq_consumer
    http_method: str | None = None
    http_path: str | None = None
    cron_expression: str | None = None
    mq_queue: str | None = None

    def to_row(self) -> tuple:
        return (self.symbol_fqn, self.entry_type, self.http_method,
                self.http_path, self.cron_expression, self.mq_queue)
```

**存储层** (sqlite_store.py 新增)：

```python
def insert_entry_points(self, entries: list[EntryPointData]) -> int:
    """插入入口点。"""
    cursor = self.conn.cursor()
    cursor.executemany(
        """INSERT OR REPLACE INTO entry_points
           (symbol_fqn, entry_type, http_method, http_path, cron_expression, mq_queue)
           VALUES (?, ?, ?, ?, ?, ?)""",
        [e.to_row() for e in entries],
    )
    self.conn.commit()
    return len(entries)

def get_entry_points(self, entry_type: str | None = None) -> list[dict]:
    """查询入口点。"""
    cursor = self.conn.cursor()
    if entry_type:
        cursor.execute("SELECT * FROM entry_points WHERE entry_type = ?", (entry_type,))
    else:
        cursor.execute("SELECT * FROM entry_points")
    return [dict(row) for row in cursor.fetchall()]
```

**验收标准**：
```bash
# 从 mall 项目提取入口点
ariadne extract --project /path/to/mall
ariadne entries --type http_api
# 输出: POST /api/orders → OmsPortalOrderController.generateOrder
```

---

### Phase 2.2: 外部依赖识别 (dependency_analyzer.py)

**目标**：识别 Redis/MQ/RPC/HTTP 客户端调用，存入 `external_dependencies` 表。

**检测模式**：

| 依赖类型 | 识别模式 | 强度 |
|---------|---------|------|
| Redis | `RedisTemplate.*`, `StringRedisTemplate.*` | strong |
| MySQL | MyBatis Mapper 调用 (`isMybatisBaseMapperCall=true`) | strong |
| RabbitMQ | `AmqpTemplate.*`, `RabbitTemplate.*` | strong |
| Kafka | `KafkaTemplate.*` | strong |
| HTTP | `RestTemplate.*`, `WebClient.*` | weak |
| RPC | Dubbo/gRPC 注解 | strong |

**实现**：

```python
# ariadne_core/extractors/spring/dependency_analyzer.py

class ExternalDependencyAnalyzer:
    """识别外部依赖调用。"""

    # 外部依赖模式
    PATTERNS = {
        "redis": [
            "org.springframework.data.redis.core.RedisTemplate",
            "org.springframework.data.redis.core.StringRedisTemplate",
            "org.springframework.data.redis.core.ValueOperations",
        ],
        "mq": [
            "org.springframework.amqp.core.AmqpTemplate",
            "org.springframework.amqp.rabbit.core.RabbitTemplate",
            "org.springframework.kafka.core.KafkaTemplate",
        ],
        "http": [
            "org.springframework.web.client.RestTemplate",
            "org.springframework.web.reactive.function.client.WebClient",
        ],
        "mysql": [],  # 通过 isMybatisBaseMapperCall 识别
    }

    def analyze(self, classes: list[dict]) -> list[ExternalDependencyData]:
        deps = []
        for class_data in classes:
            for method in class_data.get("methods", []):
                for call in method.get("calls", []):
                    # MyBatis 调用
                    if call.get("isMybatisBaseMapperCall"):
                        deps.append(ExternalDependencyData(
                            caller_fqn=method["fqn"],
                            dependency_type="mysql",
                            target=call["toFqn"],
                            strength="strong",
                        ))
                    else:
                        # 其他外部依赖
                        dep_type = self._match_pattern(call["toFqn"])
                        if dep_type:
                            deps.append(ExternalDependencyData(
                                caller_fqn=method["fqn"],
                                dependency_type=dep_type,
                                target=call["toFqn"],
                                strength="strong" if dep_type != "http" else "weak",
                            ))
        return deps

    def _match_pattern(self, fqn: str) -> str | None:
        for dep_type, patterns in self.PATTERNS.items():
            for pattern in patterns:
                if fqn.startswith(pattern):
                    return dep_type
        return None
```

**验收标准**：
```bash
ariadne deps --caller "OrderServiceImpl"
# 输出:
# - mysql: OrderMapper.selectById (strong)
# - redis: RedisTemplate.opsForValue (strong)
# - mq: AmqpTemplate.convertAndSend (strong)
```

---

### Phase 2.3: 调用链追踪 (call_chain.py)

**目标**：从入口点正向追踪到数据层，支持 `ariadne trace` 命令。

**实现**：基于 Phase 1 的 `get_call_chain()` 递归 CTE，增强入口识别。

```python
# ariadne_analyzer/l2_architecture/call_chain.py

class CallChainTracer:
    """从入口点追踪完整调用链。"""

    def __init__(self, store: SQLiteStore):
        self.store = store

    def trace_from_entry(
        self,
        entry_pattern: str,  # "POST /api/orders" 或 method FQN
        max_depth: int = 10,
    ) -> CallChainResult:
        """追踪入口点的完整调用链。"""

        # 1. 解析入口模式
        entry = self._resolve_entry(entry_pattern)
        if not entry:
            raise ValueError(f"Entry not found: {entry_pattern}")

        # 2. 获取调用链
        chain = self.store.get_call_chain(entry["symbol_fqn"], max_depth)

        # 3. 标注层级
        annotated = self._annotate_layers(chain)

        # 4. 提取外部依赖
        deps = self._extract_dependencies(chain)

        return CallChainResult(
            entry=entry,
            chain=annotated,
            external_deps=deps,
            depth=max(c["depth"] for c in chain) if chain else 0,
        )

    def _resolve_entry(self, pattern: str) -> dict | None:
        """解析入口模式（支持 HTTP 路径或 FQN）。"""
        if pattern.startswith(("GET ", "POST ", "PUT ", "DELETE ")):
            method, path = pattern.split(" ", 1)
            entries = self.store.get_entry_points("http_api")
            for e in entries:
                if e["http_method"] == method and e["http_path"] == path:
                    return e
        else:
            return self.store.get_symbol(pattern)
        return None

    def _annotate_layers(self, chain: list[dict]) -> list[dict]:
        """为调用链标注层级（Controller/Service/Repository）。"""
        for item in chain:
            symbol = self.store.get_symbol(item["to_fqn"])
            if symbol:
                annotations = json.loads(symbol.get("annotations") or "[]")
                if "@RestController" in annotations or "@Controller" in annotations:
                    item["layer"] = "controller"
                elif "@Service" in annotations:
                    item["layer"] = "service"
                elif "@Repository" in annotations or "Mapper" in symbol["name"]:
                    item["layer"] = "repository"
                else:
                    item["layer"] = "unknown"
        return chain
```

**CLI 集成** (ariadne_cli/main.py)：

```python
@app.command()
def trace(
    entry: str = typer.Argument(..., help="入口点 (如 'POST /api/orders')"),
    depth: int = typer.Option(10, help="最大追踪深度"),
):
    """追踪入口点的完整调用链。"""
    tracer = CallChainTracer(store)
    result = tracer.trace_from_entry(entry, depth)

    # 格式化输出
    print(f"Entry: {result.entry['symbol_fqn']}")
    print(f"Depth: {result.depth}")
    print("\nCall Chain:")
    for item in result.chain:
        indent = "  " * item["depth"]
        layer = f"[{item['layer']}]" if item.get("layer") else ""
        print(f"{indent}→ {item['to_fqn']} {layer}")

    print("\nExternal Dependencies:")
    for dep in result.external_deps:
        print(f"  - {dep['dependency_type']}: {dep['target']}")
```

**验收标准**：
```bash
ariadne trace "POST /api/orders"
# 输出:
# Entry: OmsPortalOrderController.generateOrder
# Depth: 4
#
# Call Chain:
# → OmsPortalOrderController.generateOrder [controller]
#   → OmsPortalOrderServiceImpl.generateOrder [service]
#     → UmsMemberService.getCurrentMember [service]
#     → OmsCartItemService.listPromotion [service]
#     → OrderMapper.insert [repository]
#     → CancelOrderSender.sendMessage [service]
#
# External Dependencies:
#   - mysql: OrderMapper.insert (strong)
#   - redis: RedisTemplate.set (strong)
#   - mq: AmqpTemplate.convertAndSend (strong)
```

---

### Phase 2.4: 反模式检测 (anti_patterns.py)

**目标**：检测违反架构规范的代码模式。

**内置规则**：

| 规则 ID | 描述 | 严重性 |
|--------|------|--------|
| `controller-dao` | Controller 直接调用 DAO/Mapper | error |
| `circular-dep` | 循环依赖 | error |
| `service-controller` | Service 调用 Controller | warning |
| `no-transaction` | 写操作无 @Transactional | warning |

**实现**：

```python
# ariadne_analyzer/l2_architecture/anti_patterns.py

class AntiPatternDetector:
    """反模式检测器。"""

    def __init__(self, store: SQLiteStore):
        self.store = store
        self.rules = [
            ControllerDaoRule(),
            CircularDepRule(),
            ServiceControllerRule(),
            NoTransactionRule(),
        ]

    def detect_all(self) -> list[AntiPatternData]:
        """运行所有规则。"""
        results = []
        for rule in self.rules:
            results.extend(rule.detect(self.store))
        return results

# ariadne_analyzer/l2_architecture/rules/controller_dao.py

class ControllerDaoRule:
    """检测 Controller 直接调用 DAO 的反模式。"""

    RULE_ID = "controller-dao"
    SEVERITY = "error"

    def detect(self, store: SQLiteStore) -> list[AntiPatternData]:
        results = []

        # 获取所有 Controller
        controllers = [s for s in store.get_symbols_by_kind("class")
                      if "@RestController" in (s.get("annotations") or "")]

        for controller in controllers:
            # 获取 Controller 中的方法
            methods = store.get_symbols_by_parent(controller["fqn"])

            for method in methods:
                if method["kind"] != "method":
                    continue

                # 获取方法调用
                calls = store.get_edges_from(method["fqn"], "calls")

                for call in calls:
                    target = store.get_symbol(call["to_fqn"])
                    if target and self._is_dao(target):
                        results.append(AntiPatternData(
                            rule_id=self.RULE_ID,
                            from_fqn=method["fqn"],
                            to_fqn=call["to_fqn"],
                            severity=self.SEVERITY,
                            message=f"Controller 直接调用 DAO，请通过 Service 层中转",
                        ))

        return results

    def _is_dao(self, symbol: dict) -> bool:
        name = symbol.get("name", "")
        annotations = symbol.get("annotations", "")
        return (
            "Mapper" in name or
            "Dao" in name or
            "@Repository" in annotations
        )
```

**验收标准**：
```bash
ariadne check
# 输出:
# [ERROR] controller-dao: OrderController.list → OrderMapper.selectAll
#         Controller 直接调用 DAO，请通过 Service 层中转
#
# Found 1 error, 0 warnings
```

---

## Acceptance Criteria

### 功能验收

- [x] `ariadne entries` 能列出所有 HTTP API 和定时任务入口
- [x] `ariadne deps` 能识别 Redis/MySQL/MQ 外部依赖
- [x] `ariadne trace "POST /api/orders"` 能输出完整调用链
- [x] `ariadne check` 能检测 controller-dao 反模式

### 测试验收

- [x] 单元测试覆盖：entry_detector, dependency_analyzer, call_chain, anti_patterns
- [x] 集成测试：在 mall 项目上验证完整流程
- [ ] 性能测试：mall 项目（4000+ symbols）的追踪响应 < 500ms

### 数据验收（mall 项目）

| 指标 | 预期值 |
|------|--------|
| HTTP API 入口 | ~50 个 |
| 定时任务入口 | ~5 个 |
| Redis 依赖 | ~20 个调用点 |
| MyBatis 依赖 | ~200 个调用点 |
| MQ 依赖 | ~10 个调用点 |

---

## Dependencies & Prerequisites

### 已完成 (Phase 1)

- [x] ASM 服务运行正常
- [x] SQLite 存储层 + L2 表结构
- [x] `get_call_chain()` 递归遍历
- [x] mall 项目测试数据

### 需要修改的文件

| 文件 | 修改类型 | 内容 |
|------|---------|------|
| `ariadne_core/models/types.py` | 新增 | EntryPointData, ExternalDependencyData, AntiPatternData |
| `ariadne_core/storage/sqlite_store.py` | 扩展 | L2 表 CRUD 方法 |
| `ariadne_core/extractors/asm/extractor.py` | 扩展 | 集成 L2 分析器 |
| `ariadne_core/extractors/spring/` | 新增目录 | entry_detector.py, dependency_analyzer.py |
| `ariadne_analyzer/l2_architecture/` | 新增目录 | call_chain.py, anti_patterns.py |
| `ariadne_cli/main.py` | 扩展 | entries, deps, trace, check 命令 |

---

## References & Research

### Internal References

- Phase 1 实现: `ariadne_core/extractors/asm/extractor.py`
- L2 表结构: `ariadne_core/storage/schema.py:51-84`
- 图遍历: `ariadne_core/storage/sqlite_store.py:162-209`

### CallGraph 参考

- Spring Bean 分析: `/Users/jersyzhang/work/CallGraph/callgraph_core/extractors/spring/bean_analyzer.py`
- 入口点检测: `/Users/jersyzhang/work/CallGraph/callgraph_core/extractors/spring/quartz_analyzer.py`
- MyBatis 检测: `/Users/jersyzhang/work/CallGraph/callgraph_core/extractors/mybatis/detector.py`
- 字段工具: `/Users/jersyzhang/work/CallGraph/callgraph_core/utils/field_utils.py`

### 测试项目

- mall: `/Users/jersyzhang/work/claude/mall` (47 Controller, 76 Mapper, Redis + RabbitMQ)
