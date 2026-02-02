---
title: feat: Add Test-to-Source Mapping and Coverage Analysis
type: feat
date: 2026-02-02
tags:
  - acceptance-criteria
  - l3-implementation
  - testing
  - api
---

# feat: 添加测试映射和覆盖分析功能

## 概述

为实现头脑风暴文档中的 **Scenario 2: 防遗漏** 验收场景，需要补充 Test ↔ Source 双向映射和测试覆盖分析功能。

**验收场景需求：**
- 输入：修改 UserService 接口
- 期望输出：
  1. 所有调用 UserService 的 Controller 列表
  2. 关联的 Test 文件列表
  3. 未覆盖测试的调用路径警告

## 问题陈述

当前 Ariadne 实现约 **85%** 满足验收场景，主要缺失：

| 缺失功能 | 优先级 | 影响 |
|---------|--------|------|
| Test ↔ Source 双向映射 | P0 | 无法找到测试文件 |
| 测试覆盖警告分析 | P0 | 无法识别未测试路径 |

**现有实现：**
- ✅ 查找调用者：`POST /api/v1/knowledge/graph/query`
- ✅ 影响分析：`POST /api/v1/knowledge/impact`
- ❌ Test 映射：无 API
- ❌ 覆盖分析：无 API

## 技术方案

### 1. Test ↔ Source 双向映射

#### 设计思路

基于 Java 标准测试约定（Maven Surefire）：

| 模式 | 说明 | 示例 |
|------|------|------|
| `**/Test*.java` | 测试类以 Test 开头 | `TestUserService.java` |
| `**/*Test.java` | 测试类以 Test 结尾（推荐） | `UserServiceTest.java` |
| `**/*Tests.java` | 测试类以 Tests 结尾 | `UserServiceTests.java` |
| `**/*IT.java` | 集成测试 | `UserServiceIT.java` |

**映射算法：**
1. 给定源 FQN：`com.example.service.UserService`
2. 提取文件路径：`src/main/java/com/example/service/UserService.java`
3. 转换为测试路径：`src/test/java/com/example/service/UserServiceTest.java`
4. 检查文件是否存在
5. 尝试多个变体（Test, Tests, IT）

#### API 设计

```http
GET /api/v1/knowledge/tests/{fqn}
```

**响应：**
```json
{
  "source_fqn": "com.example.service.UserService",
  "source_file": "src/main/java/com/example/service/UserService.java",
  "test_mappings": [
    {
      "test_file": "src/test/java/com/example/service/UserServiceTest.java",
      "test_exists": true,
      "test_methods": ["testCreateUser", "testDeleteUser", "testFindByUsername"]
    },
    {
      "test_file": "src/test/java/com/example/service/UserServiceIT.java",
      "test_exists": false,
      "test_methods": []
    }
  ]
}
```

### 2. 测试覆盖警告分析

#### 设计思路

利用现有的 `edges` 表数据，分析调用路径的测试覆盖：

1. 获取目标符号的所有调用者（from edges 表）
2. 识别哪些调用者位于测试文件中
3. 计算覆盖率：已测试调用者 / 总调用者
4. 生成未覆盖警告

#### API 设计

```http
GET /api/v1/knowledge/coverage?target={fqn}
```

**响应：**
```json
{
  "target_fqn": "com.example.service.UserService",
  "statistics": {
    "total_callers": 5,
    "tested_callers": 3,
    "coverage_percentage": 60.0
  },
  "callers": [
    {
      "caller_fqn": "com.example.controller.UserController",
      "caller_file": "src/main/java/com/example/controller/UserController.java",
      "is_test_file": false,
      "is_covered": false
    },
    {
      "caller_fqn": "com.example.service.UserServiceTest",
      "caller_file": "src/test/java/com/example/service/UserServiceTest.java",
      "is_test_file": true,
      "is_covered": true
    }
  ],
  "warnings": [
    {
      "type": "untested_caller",
      "severity": "medium",
      "message": "UserController 调用了 UserService 但无测试覆盖",
      "caller_fqn": "com.example.controller.UserController"
    }
  ]
}
```

## 实现计划

### Phase 1: 数据模型扩展

**文件：** `ariadne_core/storage/sqlite_store.py`

添加方法：

```python
def get_test_mapping(self, fqn: str) -> dict[str, Any]
    """Get test file mappings for a source symbol."""

def analyze_coverage(self, fqn: str) -> dict[str, Any]
    """Analyze test coverage for a target symbol."""
```

### Phase 2: API 端点实现

**文件：** `ariadne_api/routes/tests.py` (新建)

创建新的路由文件，包含两个端点：

```python
@router.get("/knowledge/tests/{fqn}")
async def get_test_mapping(fqn: str)

@router.get("/knowledge/coverage")
async def get_coverage_analysis(target: str = Query(...))
```

### Phase 3: Pydantic Schema

**文件：** `ariadne_api/schemas/tests.py` (新建)

```python
class TestMapping(BaseModel):
    source_fqn: str
    test_mappings: list[TestMappingEntry]

class CoverageAnalysis(BaseModel):
    target_fqn: str
    statistics: CoverageStats
    callers: list[CallerInfo]
    warnings: list[Warning]
```

### Phase 4: 集成

**文件：** `ariadne_api/app.py`

将新路由注册到 FastAPI 应用：

```python
from ariadne_api.routes import tests

app.include_router(tests.router, prefix="/api/v1/knowledge")
```

## 数据库 Schema（可选）

**优化方案：** 缓存 test_mappings 关系

```sql
CREATE TABLE IF NOT EXISTS test_mappings (
    id INTEGER PRIMARY KEY,
    source_fqn TEXT NOT NULL,
    test_file_path TEXT NOT NULL,
    test_exists BOOLEAN DEFAULT TRUE,
    last_checked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (source_fqn) REFERENCES symbols(fqn)
);

CREATE INDEX IF NOT EXISTS idx_test_mappings_source ON test_mappings(source_fqn);
```

## API 端点汇总

| 端点 | 方法 | 功能 | 优先级 |
|------|------|------|--------|
| `/api/v1/knowledge/tests/{fqn}` | GET | 获取测试映射 | P0 |
| `/api/v1/knowledge/coverage?target={fqn}` | GET | 分析测试覆盖 | P0 |

## 验收标准

### 功能验收

- [x] `GET /api/v1/knowledge/tests/{fqn}` 返回源符号的所有测试文件映射
- [x] 正确识别标准测试命名模式（Test, Tests, IT）
- [x] 返回测试文件是否存在状态
- [x] `GET /api/v1/knowledge/coverage?target={fqn}` 返回覆盖率统计
- [x] 正确识别调用者是否为测试文件
- [x] 对未覆盖的调用者生成警告

### 非功能验收

- [x] 图查询响应 < 500ms
- [ ] 支持批量查询多个 FQN（未来增强）
- [x] 错误处理完善（404, 500）

### 测试验收

- [x] 单元测试覆盖新建方法（15 个测试用例全部通过）
- [x] 集成测试验证 API 响应格式
- [x] 性能测试验证响应时间

## 相关文件

### 修改文件

1. **ariadne_core/storage/sqlite_store.py**
   - 添加 `get_test_mapping()` 方法
   - 添加 `analyze_coverage()` 方法

2. **ariadne_api/routes/tests.py** (新建)
   - 实现 `/tests/{fqn}` 端点
   - 实现 `/coverage` 端点

3. **ariadne_api/schemas/tests.py** (新建)
   - `TestMappingResponse` schema
   - `CoverageAnalysisResponse` schema

4. **ariadne_api/app.py**
   - 注册 tests 路由

### 参考实现

**现有参考代码：**
- `ariadne_analyzer/l3_implementation/test_mapper.py` - 已有测试映射逻辑
- `ariadne_api/routes/impact.py` - 影响分析端点参考

## 风险评估

| 风险 | 影响 | 缓解措施 |
|------|------|----------|
| 测试文件发现不准确 | 假阴性/假阳性 | 支持多种命名模式，用户可配置 |
| 性能影响（大量调用者） | 响应缓慢 | 缓存结果集，限制递归深度 |
| 文件系统扫描开销 | 构建时间增加 | 按需扫描，增量更新 |

## 时间估算

| 阶段 | 预计时间 |
|------|----------|
| Phase 1: 数据模型扩展 | 1-2 小时 |
| Phase 2: API 端点实现 | 2-3 小时 |
| Phase 3: Schema 创建 | 0.5 小时 |
| Phase 4: 集成测试 | 1-2 小时 |
| **总计** | **5-8 小时** |

## 依赖项

- [ ] 确认测试映射命名约定（与团队对齐）
- [ ] 确认是否需要数据库 schema 变更
- [ ] 确认 API 版本控制策略

## 成功指标

| 指标 | 目标 |
|------|------|
| 验收场景 2 满足度 | 100% (从 70% 提升) |
| API 响应时间 | < 500ms |
| 测试发现准确率 | > 95% |
| 单元测试覆盖率 | > 80% |

## 参考资料

- **头脑风暴文档:** `docs/brainstorms/2026-01-31-architect-agent-knowledge-graph-brainstorm.md`
- **Maven Surefire 测试发现模式:** https://maven.apache.org/surefire/maven-surefire-plugin/examples/inclusion-exclusion.html
- **Java 测试最佳实践:** https://www.baeldung.com/java-unit-testing-best-practices
- **现有测试映射实现:** `ariadne_analyzer/l3_implementation/test_mapper.py`
