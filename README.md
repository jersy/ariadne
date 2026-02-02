# Ariadne: 架构师 Agent 的代码知识图谱

Ariadne 是一个多维代码知识图谱系统，为"架构师 Agent"提供智能基础设施。它能自动从 Java/Spring 代码库中提取语义信息、结构关系和隐式规则。

## 概览

Ariadne 通过分析 Java 字节码构建三层知识图谱：

- 🧠 **L1 业务层**: 自然语言摘要、领域术语表、业务约束
- 🏗️ **L2 架构层**: 调用链、依赖拓扑、反模式检测
- 🔍 **L3 实现层**: 符号索引、影响分析、测试映射

## 特性

- **符号提取**: 基于 ASM 的 Java 项目字节码分析
- **语义搜索**: 基于 ChromaDB 的向量嵌入搜索
- **影响分析**: 跟踪调用链预测变更影响
- **业务术语表**: LLM 生成的领域词汇（代码术语 → 业务含义）
- **反模式检测**: 识别架构违规和代码异味
- **测试映射**: Maven Surefire 约定的测试文件映射
- **覆盖率分析**: 基于调用图的测试覆盖率分析
- **HTTP API**: 基于 FastAPI 的 RESTful API

## 快速开始

### 安装

```bash
# 克隆仓库
git clone https://github.com/jersy/ariadne.git
cd ariadne

# 使用 uv 安装（推荐）
uv pip install -e .

# 或使用 pip
pip install -e .
```

### 配置

```bash
# 设置 LLM 访问的环境变量
export ARIADNE_DEEPSEEK_API_KEY=your_key_here
# 或
export ARIADNE_OPENAI_API_KEY=your_key_here
```

### 使用方法

```bash
# 启动 API 服务器
uvicorn ariadne_api.app:app --reload --port 8000

# 索引 Java 项目
python -m ariadne_cli extract --project /path/to/java/project

# 通过业务含义搜索代码
curl -X POST "http://localhost:8000/api/v1/search" \
  -H "Content-Type: application/json" \
  -d '{"query": "用户登录验证"}'

# 查看入口点（HTTP API、定时任务）
python -m ariadne_cli entries

# 分析变更影响
curl -X POST "http://localhost:8000/api/v1/impact" \
  -H "Content-Type: application/json" \
  -d '{"target_fqn": "com.example.UserService"}'

# 检查反模式
curl -X POST "http://localhost:8000/api/v1/check" \
  -H "Content-Type: application/json" \
  -d '{"fqn": "com.example"}'
```

## API 端点

### 知识查询
- `GET /api/v1/knowledge/symbol/{fqn}` - 符号详情
- `GET /api/v1/knowledge/glossary` - 领域术语表
- `GET /api/v1/knowledge/glossary/{term}` - 术语定义
- `GET /api/v1/knowledge/constraints/{fqn}` - 业务约束

### 测试映射
- `GET /api/v1/knowledge/tests/{fqn}` - 获取测试文件映射
- `POST /api/v1/knowledge/tests/batch` - 批量测试映射
- `GET /api/v1/knowledge/coverage` - 覆盖率分析
- `POST /api/v1/knowledge/coverage/batch` - 批量覆盖率分析

### 搜索与分析
- `POST /api/v1/search` - 语义代码搜索
- `POST /api/v1/graph/query` - 图遍历查询
- `POST /api/v1/impact` - 变更影响分析
- `POST /api/v1/check` - 反模式检测

### 系统管理
- `GET /health` - 健康检查
- `POST /api/v1/rebuild` - 重建知识图谱
- `GET /api/v1/jobs/{job_id}` - 任务状态查询

## 文档

- [架构文档](ARCHITECTURE.md) - 三层知识架构
- [开发指南](DEVELOPMENT.md) - 环境设置和贡献工作流
- [项目指南](CLAUDE.md) - Claude Code 开发规范
- [变更日志](CHANGELOG.md) - 版本变更记录

## 系统要求

- **Python**: 3.12+
- **Java**: 8+（用于 ASM 字节码服务）
- **依赖**: 见 `pyproject.toml`

## 项目结构

```
ariadne/
├── ariadne_core/          # 核心提取和存储
│   ├── extractors/        # ASM 字节码分析
│   ├── storage/           # SQLite + ChromaDB
│   └── models/            # 数据模型
├── ariadne_analyzer/      # 分析层（L1/L2/L3）
│   ├── l1_business/       # 业务层
│   ├── l2_architecture/   # 架构层
│   └── l3_implementation/ # 实现层
├── ariadne_api/           # FastAPI HTTP 服务
│   ├── routes/            # API 端点
│   ├── schemas/           # Pydantic 模型
│   └── middleware/        # 中间件
├── ariadne_llm/           # LLM 客户端
├── ariadne_cli/           # 命令行接口
└── tests/                 # 测试套件
```

## 测试映射示例

```bash
# 获取测试文件映射
curl "http://localhost:8000/api/v1/knowledge/tests/com.example.UserService"

# 响应示例
{
  "source_fqn": "com.example.UserService",
  "source_file": "src/main/java/com/example/UserService.java",
  "test_mappings": [
    {
      "test_file": "src/test/java/com/example/UserServiceTest.java",
      "test_exists": true,
      "test_pattern": "UserServiceTest.java",
      "test_methods": ["testFindById", "testSave", "testDelete"]
    }
  ]
}

# 获取覆盖率分析
curl "http://localhost:8000/api/v1/knowledge/coverage?target=com.example.PaymentService"

# 响应示例
{
  "target_fqn": "com.example.PaymentService",
  "statistics": {
    "total_callers": 5,
    "tested_callers": 4,
    "coverage_percentage": 80.0
  },
  "warnings": [
    {
      "type": "untested_caller",
      "severity": "medium",
      "message": "PaymentController calls com.example.PaymentService but has no test coverage"
    }
  ]
}
```

## 性能指标

### 并行 LLM 处理

| 场景 | 符号数量 | 预期耗时 | 吞吐量 |
|------|---------|---------|--------|
| 增量更新 | 1,000 | < 2 分钟 | ~8-10 符号/秒 |
| 批量处理 | 100,000 | < 2 小时 | ~14 符号/秒 |

**实际性能取决于：**
- LLM API 响应时间（智谱/DeepSeek 通常 0.5-2 秒/请求）
- 并发数配置（默认 10 workers）
- 网络延迟和 API 速率限制

## 开发

```bash
# 安装开发依赖
uv pip install -e ".[dev]"

# 运行测试
pytest

# 代码格式化
ruff format .
ruff check .

# 类型检查
mypy ariadne_core/
```

## 贡献

欢迎贡献！请查看 [开发指南](DEVELOPMENT.md) 了解详情。

## 许可证

MIT

## 致谢

本项目受以下项目启发并基于其构建：
- [CallGraph](https://github.com/gousiosg/java-callgraph) - Java 调用图分析
- [ai-memory-system](https://github.com/fum2024/ai-memory-system) - AI 记忆架构
