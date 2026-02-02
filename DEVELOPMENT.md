# Ariadne 开发指南

## 环境准备

```bash
# 安装开发依赖
uv pip install -e ".[dev]"

# 运行测试
pytest

# 运行测试（带覆盖率）
pytest --cov=ariadne_core --cov=ariadne_analyzer --cov=ariadne_api

# 格式化代码
ruff format .

# 代码检查
ruff check .

# 类型检查
mypy ariadne_core/
```

## 项目结构

```
ariadne/
├── ariadne_core/          # 核心提取和存储
│   ├── extractors/        # ASM 字节码分析
│   ├── storage/           # SQLite + ChromaDB
│   └── models/            # 数据模型
├── ariadne_analyzer/      # 分析层
│   ├── l1_business/       # L1: 业务层
│   │   ├── summarizer.py              # 摘要生成
│   │   ├── glossary.py                # 术语表提取
│   │   ├── constraints.py             # 约束提取
│   │   ├── parallel_summarizer.py     # 并行处理
│   │   ├── incremental_coordinator.py # 增量更新
│   │   ├── dependency_tracker.py      # 依赖跟踪
│   │   └── cost_tracker.py            # 成本跟踪
│   ├── l2_architecture/   # L2: 架构层
│   └── l3_implementation/ # L3: 实现层
├── ariadne_api/           # FastAPI 服务
│   ├── routes/            # API 端点
│   │   ├── health.py      # 健康检查
│   │   ├── symbol.py      # 符号查询
│   │   ├── glossary.py    # 术语表
│   │   ├── tests.py       # 测试映射
│   │   ├── search.py      # 语义搜索
│   │   ├── impact.py      # 影响分析
│   │   ├── graph.py       # 图查询
│   │   ├── constraints.py # 约束查询
│   │   ├── check.py       # 反模式检查
│   │   ├── rebuild.py     # 图谱重建
│   │   └── jobs.py        # 任务管理
│   ├── schemas/           # Pydantic 模型
│   └── middleware/        # 中间件（限流、追踪）
├── ariadne_llm/           # LLM 客户端
│   ├── client.py          # OpenAI 兼容客户端
│   ├── embedder.py        # 向量嵌入
│   └── config.py          # 配置
├── ariadne_cli/           # 命令行接口
└── tests/                 # 测试套件
    ├── unit/              # 单元测试
    ├── integration/       # 集成测试
    └── api/               # API 测试
```

## 运行测试

```bash
# 所有测试
pytest

# 仅单元测试
pytest tests/unit/

# 仅集成测试
pytest tests/integration/

# 仅 API 测试
pytest tests/api/

# 特定测试文件
pytest tests/unit/test_llm_client.py

# 详细输出
pytest -v

# 遇到第一个失败就停止
pytest -x

# 显示 print 输出
pytest -s
```

## 代码风格

- **格式化工具**: Ruff（兼容 Black）
- **检查工具**: Ruff（兼容 Flake8、isort 等）
- **类型检查**: mypy
- **文档字符串**: Google 风格

## 提交规范

遵循 [Conventional Commits](https://www.conventionalcommits.org/zh-hans/)：

- `feat:` 新功能
- `fix:` Bug 修复
- `docs:` 文档变更
- `refactor:` 代码重构
- `test:` 测试新增/变更
- `chore:` 构建/工具链变更

## 开发工作流

1. 从 `main` 分支创建功能分支
2. 遵循约定格式编写提交消息
3. 运行测试确保通过
4. 运行 linting 并修复问题
5. 提交 Pull Request

## 调试

```bash
# 启用详细日志运行
ARIADNE_LOG_LEVEL=DEBUG ariadne extract --project /path/to/project

# 启用自动重载运行 API 服务器
ARIADNE_RELOAD=true ariadne serve --port 8080

# 检查数据库内容
sqlite3 ariadne.db "SELECT * FROM symbols LIMIT 10"

# 查看测试覆盖率报告
pytest --cov=ariadne_core --cov-report=html
open htmlcov/index.html
```

## 性能分析

```bash
# 分析符号提取
python -m cProfile -o profile.stats ariadne extract --project /path/to/project
python -m pstats profile.stats

# 内存分析
mprof run ariadne extract --project /path/to/project
mprof plot
```

## 测试映射开发

### 本地测试

```bash
# 运行测试映射测试
pytest tests/unit/test_test_mapping.py -v

# 运行覆盖率分析测试
pytest tests/unit/test_test_mapping.py::TestAnalyzeCoverage -v
```

### API 测试

```bash
# 启动 API 服务器
uvicorn ariadne_api.app:app --reload

# 测试测试映射端点
curl "http://localhost:8000/api/v1/knowledge/tests/com.example.UserService"

# 测试批量测试映射
curl -X POST "http://localhost:8000/api/v1/knowledge/tests/batch" \
  -H "Content-Type: application/json" \
  -d '{"fqns": ["com.example.UserService", "com.example.OrderService"]}'

# 测试覆盖率分析
curl "http://localhost:8000/api/v1/knowledge/coverage?target=com.example.PaymentService"
```

## 常见问题

### 数据库锁定

如果遇到 SQLite 锁定错误：
```bash
# 检查是否有其他进程持有数据库连接
lsof ariadne.db

# 关闭其他进程或使用超时
export SQLITE_TIMEOUT=30
```

### ChromaDB 同步失败

如果向量同步失败：
```bash
# 重新同步向量
python -c "
from ariadne_core.storage.sqlite_store import SQLiteStore
store = SQLiteStore('ariadne.db')
store.sync_vectors_to_chroma(force=True)
"
```

### LLM API 限流

如果遇到 API 限流：
```python
# 降低并发数
# 编辑 ariadne_llm/config.py
LLMConfig(max_workers=5)  # 从 10 降低到 5
```

## 添加新功能

### 1. 添加新的 API 端点

```python
# ariadne_api/routes/my_feature.py
from fastapi import APIRouter, HTTPException
from ariadne_api.schemas.my_feature import MyRequest, MyResponse

router = APIRouter()

@router.post("/my-feature", response_model=MyResponse)
async def my_endpoint(request: MyRequest) -> MyResponse:
    """实现我的功能"""
    # ...
    return MyResponse(...)
```

```python
# ariadne_api/app.py
from ariadne_api.routes import my_feature

app.include_router(
    my_feature.router,
    prefix=f"/api/{API_VERSION}",
    tags=["my-feature"]
)
```

### 2. 添加新的存储方法

```python
# ariadne_core/storage/sqlite_store.py
class SQLiteStore:
    def my_new_method(self, param: str) -> dict:
        """新方法的文档字符串"""
        cursor = self.conn.cursor()
        cursor.execute("SELECT ... WHERE ?", (param,))
        return dict(cursor.fetchone())
```

### 3. 编写测试

```python
# tests/unit/test_my_feature.py
import pytest
from ariadne_core.storage.sqlite_store import SQLiteStore

def test_my_new_method():
    store = SQLiteStore(":memory:")
    # 设置测试数据
    # 调用方法
    result = store.my_new_method("test")
    # 断言结果
    assert result["expected"] == "value"
```

## 发布流程

1. 更新版本号（`pyproject.toml`）
2. 更新 `CHANGELOG.md`
3. 创建 git tag
4. 构建 and 发布

```bash
# 更新版本
bumpversion patch  # or minor/major

# 创建 tag
git tag -a v0.4.0 -m "Release v0.4.0"

# 推送 tag
git push origin v0.4.0
```
