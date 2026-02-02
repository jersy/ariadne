# Ariadne 架构文档

## 三层知识架构

Ariadne 将代码知识组织为三个不同的层次，每层服务于不同的分析需求：

### L1: 业务与领域层

**目的**: 将技术代码与业务含义连接起来

- **自然语言摘要**: LLM 生成的代码功能描述
- **领域术语表**: 代码术语 → 业务含义映射（如 "Sku" → "库存保有单位"）
- **业务约束**: 从代码中提取的规则和不变式

**组件**:
- `ariadne_analyzer/l1_business/summarizer.py` - 摘要生成
- `ariadne_analyzer/l1_business/glossary.py` - 领域词汇提取
- `ariadne_analyzer/l1_business/constraints.py` - 业务规则提取
- `ariadne_analyzer/l1_business/parallel_summarizer.py` - 并行摘要处理
- `ariadne_analyzer/l1_business/incremental_coordinator.py` - 增量更新协调
- `ariadne_analyzer/l1_business/dependency_tracker.py` - 依赖关系跟踪
- `ariadne_analyzer/l1_business/cost_tracker.py` - LLM 成本跟踪

### L2: 架构与设计层

**目的**: 理解系统结构和设计关系

- **调用链追踪**: 跨方法跟踪执行路径
- **外部依赖拓扑**: 数据库、Redis、MQ、RPC 依赖
- **反模式检测**: 识别架构违规

**组件**:
- `ariadne_analyzer/l2_architecture/call_chain.py` - 调用图分析
- `ariadne_analyzer/l2_architecture/dependency_tracker.py` - 依赖映射
- `ariadne_analyzer/l2_architecture/anti_patterns.py` - 违规检测

### L3: 实现层

**目的**: 底层代码事实和关系

- **符号索引**: 基于 ASM 字节码的类、方法、字段分析
- **关系图谱**: 基于 SQLite 的边存储（调用、继承、使用）
- **测试映射**: 连接生产代码与测试代码
- **覆盖率分析**: 测试覆盖率分析

**组件**:
- `ariadne_core/extractors/asm/` - 字节码分析
- `ariadne_core/storage/sqlite_store.py` - 图存储
- `ariadne_core/storage/test_mapping.py` - 测试映射功能

## 技术栈

| 组件 | 技术 | 版本 |
|------|------|------|
| 语言 | Python | 3.12+ |
| HTTP API | FastAPI + Pydantic | latest |
| 存储 | SQLite | 3.x |
| 向量存储 | ChromaDB | 0.5+ |
| 代码分析 | ASM | Java 字节码 |
| LLM | OpenAI/DeepSeek/Ollama | - |

## 数据流

```
Java 源代码
       ↓
   ASM 字节码分析
       ↓
   符号提取 (L3)
       ↓
   ┌─────────┬─────────┬─────────┐
   ↓         ↓         ↓         ↓
L3 存储  L2 分析  L1 LLM 摘要
   ↓         ↓         ↓
   └─────────┴─────────┴────→ API 层
```

## 存储架构

### SQLite 表结构

| 表名 | 用途 | 关键字段 |
|------|------|----------|
| `symbols` | 代码符号 | fqn, kind, name, file_path |
| `edges` | 关系边 | from_fqn, to_fqn, edge_type |
| `summaries` | 业务摘要 | fqn, summary, category |
| `glossary` | 领域术语 | term, definition, context |
| `constraints` | 业务约束 | constraint_type, description |
| `entry_points` | 入口点 | entry_type (HTTP/SCHEDULED) |
| `anti_patterns` | 反模式 | pattern_type, severity |
| `vector_sync_state` | 向量同步状态 | collection_name, last_synced_at |

**设计要点**:
- `ON DELETE CASCADE`: 自动清理孤儿边
- 索引优化: `symbols_fqn_idx`, `edges_from_idx`, `edges_to_idx`
- 两阶段提交: SQLite + ChromaDB 双写一致性

### ChromaDB 集合

- `summaries` - 摘要向量嵌入
- `glossary` - 术语向量嵌入

**同步策略**:
- 影子重建 + 原子交换
- 自动恢复孤儿记录
- 批量操作优化

## API 端点

### 健康检查
- `GET /health` - 服务健康检查

### 知识查询
- `GET /api/v1/knowledge/symbol/{fqn:path}` - 符号详情
- `GET /api/v1/knowledge/glossary` - 领域术语表
- `GET /api/v1/knowledge/glossary/{term}` - 术语定义
- `GET /api/v1/knowledge/constraints/{fqn:path}` - 业务约束

### 搜索与图谱
- `POST /api/v1/search` - 语义代码搜索
- `POST /api/v1/graph/query` - 图遍历查询

### 影响分析
- `POST /api/v1/impact` - 变更影响分析

### 测试映射（新增）
- `GET /api/v1/knowledge/tests/{fqn:path}` - 获取测试文件映射
- `POST /api/v1/knowledge/tests/batch` - 批量测试映射
- `GET /api/v1/knowledge/coverage` - 覆盖率分析
- `POST /api/v1/knowledge/coverage/batch` - 批量覆盖率分析

### 代码检查
- `POST /api/v1/check` - 反模式检测

### 系统管理
- `POST /api/v1/rebuild` - 重建知识图谱
- `GET /api/v1/jobs/{job_id}` - 任务状态查询

## 性能优化

### 并行 LLM 处理

**配置参数**:
```python
@dataclass
class LLMConfig:
    max_workers: int = 10           # 最大并发 LLM 调用
    request_timeout: float = 30.0   # 请求超时（秒）
```

**性能指标**:
| 场景 | 符号数量 | 预期耗时 | 吞吐量 |
|------|---------|---------|--------|
| 增量更新 | 1,000 | < 2 分钟 | ~8-10 符号/秒 |
| 批量处理 | 100,000 | < 2 小时 | ~14 符号/秒 |

### 数据库优化

- **批量操作**: `batch_update_summaries()`, `batch_get_symbols()`
- **索引优化**: 关键查询字段建立索引
- **N+1 查询修复**: 单次查询获取调用者信息
- **正则缓存**: 类级别常量预编译

### 线程安全

- **线程本地连接**: 每线程独立 SQLite 连接
- **锁保护**: `ParallelSummarizer.stats`, `LLMCostTracker.usage`
- **原子操作**: CAS 更新陈旧标记

## 测试映射特性

### Maven Surefire 约定

支持的测试文件命名模式：
- `Test*.java` (如 `TestUserService.java`)
- `*Test.java` (如 `UserServiceTest.java`) - **推荐**
- `*Tests.java` (如 `UserServiceTests.java`)
- `*IT.java` (如 `UserServiceIT.java` - 集成测试)

### 目录结构映射

```
src/main/java/.../Foo.java  →  src/test/java/.../FooTest.java
```

### 覆盖率分析

基于调用图分析测试覆盖率：
- 识别所有调用者（incoming edges）
- 检测测试文件（路径包含 `/test/` 或匹配命名模式）
- 计算覆盖率百分比
- 生成未覆盖调用者警告

## 安全性

### 本地开发例外

作为本地开发工具，以下配置是可接受的：
- CORS: `allow_origins=["*"]`
- 无身份认证
- 默认绑定 `0.0.0.0`

### 仍需关注的安全问题

- SQL 注入防护
- 路径遍历验证
- 命令注入防护
- 输入验证
- 密钥管理
