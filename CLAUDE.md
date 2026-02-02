# Ariadne 项目指南

## 项目概述

Ariadne 是一个**本地开发工具**，为架构师 Agent 提供代码知识图谱功能。

**关键特点**：
- 本地开发工具，单用户环境
- 无外部网络暴露
- 容器化本地部署
- 不用于生产环境

---

## 代码审查指南

### ⚠️ 本地开发安全例外

以下安全配置**是可接受的**，不应在代码审查中标记为问题：

| 问题 | 状态 | 原因 |
|------|------|------|
| CORS: `allow_origins=["*"]` | ✅ 可接受 | 仅本地访问，无外部暴露 |
| 无身份认证 | ✅ 可接受 | 单开发者环境 |
| 默认绑定 `0.0.0.0` | ✅ 可接受 | 容器内使用，无外部网络 |
| X-Forwarded-For 信任 | ✅ 可接受 | 无反向代理 |

### 应该关注的安全问题

仍然需要审查的**真正安全问题**：

| 问题类型 | 示例 | 严重性 |
|----------|------|--------|
| SQL 注入 | 动态 SQL 拼接 | 🔴 严重 |
| 路径遍历 | 文件操作未验证 `..` | 🔴 严重 |
| 命令注入 | Shell 命令拼接 | 🔴 严重 |
| 输入验证 | 参数长度、类型验证 | 🟡 重要 |
| 密钥管理 | API 密钥硬编码 | 🟡 重要 |
| N+1 查询 | 循环中查询数据库 | 🟡 重要 |
| 线程安全 | 竞态条件 | 🟡 重要 |
| 内存泄漏 | 资源未释放 | 🟡 重要 |

---

## 技术栈

| 组件 | 技术 | 版本要求 |
|------|------|----------|
| 语言 | Python | 3.12+ |
| HTTP API | FastAPI + Pydantic | latest |
| 存储 | SQLite | 3.x |
| 向量存储 | ChromaDB | 0.5+ |
| LLM | OpenAI-compatible API | - |

---

## 目录结构

```
ariadne/
├── ariadne_core/          # 核心解析层
│   ├── extractors/        # ASM 字节码分析
│   ├── storage/           # SQLite + ChromaDB
│   └── models/            # 数据模型
├── ariadne_analyzer/      # 分析层
│   ├── l1_business/       # L1 业务层
│   ├── l2_architecture/   # L2 架构层
│   └── l3_implementation/ # L3 实现层
├── ariadne_api/           # FastAPI 服务
├── ariadne_llm/           # LLM 客户端
└── tests/                 # 测试
```

---

## 开发规范

### Python 代码风格

- 使用 **ruff** 进行格式化和 linting
- 使用 **mypy** 进行类型检查
- 函数使用类型注解
- 使用 **async/await** 处理 I/O 操作

### 测试

- 单元测试：`pytest tests/unit/`
- 集成测试：`pytest tests/integration/`
- 测试覆盖率目标：> 80%

### 提交规范

使用 Conventional Commits：
- `feat:` 新功能
- `fix:` 修复 bug
- `docs:` 文档更新
- `refactor:` 代码重构
- `test:` 测试相关
- `chore:` 构建/工具链

---

## 常用命令

```bash
# 运行服务
uvicorn ariadne_api.app:app --reload

# 运行测试
pytest

# 代码格式化
ruff format .
ruff check .

# 类型检查
mypy ariadne_core/
```

---

## 并行 LLM 摘要化

### 性能预期

| 场景 | 符号数量 | 预期耗时 | 吞吐量 |
|------|---------|---------|--------|
| 增量更新 | 1,000 符号 | < 2 分钟 | ~8-10 符号/秒 |
| 批量处理 | 100,000 符号 | < 2 小时 | ~14 符号/秒 |

**实际性能取决于：**
- LLM API 响应时间（智谱/DeepSeek 通常 0.5-2 秒/请求）
- 并发数配置（默认 10 workers）
- 网络延迟和 API 速率限制

### 配置

```python
# ariadne_llm/config.py
@dataclass
class LLMConfig:
    # 并发配置
    max_workers: int = 10           # 最大并发 LLM 调用数
    request_timeout: float = 30.0  # 单个请求超时时间（秒）

    # API 配置
    api_key: str = ""
    api_base: str = ""
    model: str = "glm-4-flash"
```

**调整建议：**
- 速率限制问题：降低 `max_workers` (建议 5-8)
- API 较慢：增加 `request_timeout`
- 内存不足：降低 `max_workers`

### 使用方式

**增量更新（推荐）：**
```python
from ariadne_analyzer.l1_business import IncrementalSummarizerCoordinator

coordinator = IncrementalSummarizerCoordinator(llm_client, store, max_workers=10)
result = coordinator.regenerate_incremental(changed_fqns)

print(f"Regenerated: {result.regenerated_count}")
print(f"Cached: {result.skipped_cached}")
print(f"Duration: {result.duration_seconds:.2f}s")
print(result.cost_report)
```

**批量处理：**
```python
from ariadne_analyzer.l1_business import ParallelSummarizer

summarizer = ParallelSummarizer(llm_client, max_workers=10)
summaries = summarizer.summarize_symbols_batch(symbols, show_progress=True)
```

### 性能监控

`IncrementalResult` 包含详细的性能指标：
- `dependency_analysis_time`: 依赖分析耗时
- `symbol_load_time`: 符号加载耗时
- `summarization_time`: 摘要生成耗时
- `database_update_time`: 数据库更新耗时
- `throughput_per_second`: 每秒处理符号数

**日志输出示例：**
```
INFO: Starting incremental update (changed_count: 100, max_workers: 10)
INFO: Incremental update: 250 symbols to regenerate (100 changed + 150 dependents)
INFO: dependency_analysis_complete in 0.12s
INFO: Filtered 250 symbols to process, 50 cached
INFO: Generated 200 summaries in 18.5s (10.8 summaries/sec)
INFO: Incremental update complete: 200 regenerated, 50 cached, 19.2s total
```

---

## 相关文档

- **计划文档**: `docs/plans/2026-01-31-feat-ariadne-codebase-knowledge-graph-plan.md`
- **审查指南**: `docs/reviews/review-guidelines.md`
- **本地开发安全例外**: `docs/solutions/development-workflows/local-dev-security-exceptions.md`

---

## Git Worktree 开发

### Claude Settings 自动同步

项目使用 Git `post-worktree` 钩子自动同步 Claude Code 的 LLM API 配置到新 worktree。

**一次性设置：**
```bash
# 运行设置脚本
./scripts/setup-claude-settings.sh
```

设置脚本会：
1. 创建 `~/.claude-template/settings.json` 模板
2. 创建 `.githooks/post-worktree` 钩子
3. 配置 `git config core.hooksPath .githooks`

**使用方法：**
```bash
# 新建 worktree（使用 wrapper 脚本）
./scripts/worktree-add.sh ../feature-x -b feature/x

# 注意：Apple Git 不支持 post-worktree hook，必须使用 wrapper 脚本
# 如果使用标准 git worktree add，配置不会自动同步

# 查看现有 worktree
git worktree list

# 手动同步现有 worktree
cp ~/.claude-template/settings.json <worktree-path>/.claude/
```

**故障排查：**
- **问题**: 新 worktree 没有 settings.json
  - **解决**: 检查模板是否存在 `ls ~/.claude-template/settings.json`
  - **重新运行设置脚本

- **问题**: 使用 `git worktree add` 后配置没有同步
  - **原因**: Apple Git 2.39.5 不支持 `post-worktree` hook
  - **解决**: 使用 `./scripts/worktree-add.sh` 代替 `git worktree add`

- **问题**: JSON 验证失败
  - **解决**: 检查模板 JSON 格式 `jq empty ~/.claude-template/settings.json`
  - 从当前配置重建 `cp .claude/settings.json ~/.claude-template/settings.json`

- **问题**: 钩子未执行
  - **解决**: 检查 Git 钩子配置 `git config core.hooksPath`
  - 应该返回 `.githooks`

**平台兼容性：**
- ✅ macOS (Darwin)
- ✅ Linux
- ✅ Windows Git Bash
- ✅ WSL (Windows Subsystem for Linux)

---

## 重要提醒

⚠️ **这是一个本地开发工具，不是生产 SaaS 产品。**

在审查代码时，请记住：
1. 某些安全限制（认证、CORS）对本地工具来说是不必要的
2. 专注于真正的代码质量问题（SQL 注入、N+1 查询、线程安全等）
3. 优先考虑正确性、性能和可维护性
4. 避免过度工程化
