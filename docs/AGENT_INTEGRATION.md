# Ariadne Agent 集成指南

## 概述

Ariadne 为代码知识图谱操作提供了全面的 HTTP API。本文档说明如何将 Ariadne 与您的 AI Agent 集成。

## API 发现

### 基础 URL

```
http://localhost:8080
```

### 发现可用功能

**方法 1: OpenAPI 规范**
```bash
curl http://localhost:8080/openapi.json
```

**方法 2: 交互式文档**
```
http://localhost:8080/docs
```

**方法 3: API 元数据**
```bash
curl http://localhost:8080/
```

返回:
```json
{
  "name": "Ariadne",
  "version": "0.4.0",
  "api_version": "v1",
  "endpoints": [
    {"path": "/api/v1/knowledge/search", "methods": ["GET"]},
    {"path": "/api/v1/knowledge/glossary", "methods": ["GET", "POST"]}
  ]
}
```

## Agent 关键端点

### 1. 语义搜索
```http
GET /api/v1/knowledge/search?query=用户认证
```

通过自然语言查询搜索代码。

**响应示例:**
```json
{
  "query": "用户认证",
  "results": [
    {
      "fqn": "com.example.auth.UserService",
      "kind": "class",
      "name": "UserService",
      "business_meaning": "处理用户认证和授权服务"
    }
  ],
  "total": 1
}
```

### 2. 符号查询
```http
GET /api/v1/knowledge/symbol/{fqn}
```

获取符号的详细信息。

**响应示例:**
```json
{
  "fqn": "com.example.UserService",
  "kind": "class",
  "name": "UserService",
  "file_path": "src/main/java/com/example/auth/UserService.java",
  "business_meaning": "处理用户认证和授权服务",
  "summaries": [
    {
      "level": "class",
      "summary": "用户服务提供登录、注销和权限验证功能"
    }
  ]
}
```

### 3. 影响分析
```http
POST /api/v1/knowledge/impact
Content-Type: application/json

{
  "target_fqn": "com.example.UserService",
  "depth": 5
}
```

分析修改某个符号的影响。

**响应示例:**
```json
{
  "target_fqn": "com.example.UserService",
  "callers": [
    {
      "from_fqn": "com.example.auth.LoginController",
      "relation": "uses"
    }
  ],
  "impact_score": 8
}
```

### 4. 术语表
```http
GET /api/v1/knowledge/glossary
GET /api/v1/knowledge/glossary/search/{query}
```

访问领域词汇和业务术语。

**响应示例:**
```json
{
  "terms": [
    {
      "code_term": "用户认证",
      "business_meaning": "验证用户身份的过程",
      "synonyms": ["身份验证", "登录验证"]
    }
  ]
}
```

### 5. 图查询
```http
POST /api/v1/knowledge/graph/query
Content-Type: application/json

{
  "query_type": "callers",
  "fqn": "com.example.UserService",
  "depth": 3
}
```

查询代码知识图谱。

## 错误处理

### 错误响应格式

所有错误遵循此结构:

```json
{
  "detail": "错误消息"
}
```

**建议改进:** 结构化错误码
```json
{
  "error_code": "symbol_not_found",
  "message": "找不到符号 'com.example.Unknown'",
  "suggestion": "使用 GET /api/v1/knowledge/symbols 列出可用符号"
}
```

### 常见 HTTP 状态码

| 状态码 | 含义 | 建议操作 |
|--------|------|----------|
| 200 | 成功 | 处理响应 |
| 404 | 未找到 | 检查 FQN 或查询 |
| 429 | 速率限制 | 实现退避策略 |
| 500 | 服务器错误 | 使用指数退避重试 |

## 速率限制

Ariadne 实现了速率限制:

| 时间窗口 | 限制 |
|----------|------|
| 每秒 | 10 次请求 |
| 每分钟 | 60 次请求 |
| 每小时 | 1000 次请求 |

**速率限制响应:**
```http
HTTP/1.1 429 Too Many Requests
X-RateLimit-Limit: 60
X-RateLimit-Remaining: 0
X-RateLimit-Reset: 1641234567
```

**退避策略:**
```python
import time

def make_request_with_backoff(url, max_retries=3):
    for attempt in range(max_retries):
        response = requests.get(url)
        if response.status_code == 429:
            # 指数退避
            wait_time = 2 ** attempt
            time.sleep(wait_time)
            continue
        response.raise_for_status()
        return response
    raise Exception("超过最大重试次数")
```

## 性能优化

### 批量操作

处理多个符号时:

**❌ 不要这样:**
```python
for fqn in symbol_list:
    response = requests.get(f"/api/v1/knowledge/symbol/{fqn}")
```

**✅ 要这样:** (批量端点实现后)
```python
response = requests.post(
    "/api/v1/knowledge/symbols/batch",
    json={"fqns": symbol_list}
)
```

### 并行请求

对独立操作使用异步请求:

```python
import asyncio
import aiohttp

async def fetch_symbols(session, fqns):
    tasks = [
        session.get(f"http://localhost:8080/api/v1/knowledge/symbol/{fqn}")
        for fqn in fqns
    ]
    responses = await asyncio.gather(*tasks)
    return await asyncio.gather(*[r.json() for r in responses])
```

## 完整 Agent 工作流

### 示例: 重构助手

```python
import requests
import time
from typing import Dict, List

class AriadneClient:
    """Ariadne API 客户端，用于 Agent 集成。"""

    def __init__(self, base_url: str = "http://localhost:8080"):
        self.base_url = base_url

    def analyze_refactoring_risk(self, fqn: str) -> Dict:
        """分析重构符号的风险。

        Args:
            fqn: 符号的完全限定名

        Returns:
            包含风险评分和建议的字典
        """

        # 步骤 1: 获取符号详情
        symbol = self.get_symbol(fqn)
        if not symbol:
            return {"error": "找不到符号"}

        # 步骤 2: 获取影响分析
        impact = self.get_impact(fqn, depth=3)

        # 步骤 3: 获取调用者（下游依赖）
        callers = impact.get("callers", [])

        # 步骤 4: 获取受影响符号的测试
        caller_fqns = [c.get("from_fqn") for c in callers if c.get("from_fqn")]
        test_coverage = self.get_tests_for_symbols(caller_fqns)

        # 步骤 5: 计算风险评分
        risk_score = self._calculate_risk(impact, test_coverage)

        return {
            "symbol": fqn,
            "risk_score": risk_score,
            "affected_symbols": len(callers),
            "test_coverage": len(test_coverage),
            "recommendation": self._get_recommendation(risk_score)
        }

    def get_symbol(self, fqn: str) -> Dict | None:
        """获取符号详情。"""
        try:
            response = requests.get(f"{self.base_url}/api/v1/knowledge/symbol/{fqn}")
            response.raise_for_status()
            return response.json()
        except requests.HTTPError as e:
            if e.response.status_code == 404:
                return None
            raise

    def get_impact(self, fqn: str, depth: int = 5) -> Dict:
        """获取影响分析。"""
        response = requests.post(
            f"{self.base_url}/api/v1/knowledge/impact",
            json={"target_fqn": fqn, "depth": depth}
        )
        response.raise_for_status()
        return response.json()

    def search(self, query: str, limit: int = 10) -> List[Dict]:
        """语义搜索。"""
        response = requests.get(
            f"{self.base_url}/api/v1/knowledge/search",
            params={"query": query, "limit": limit}
        )
        response.raise_for_status()
        return response.json().get("results", [])

    def get_glossary_term(self, code_term: str) -> Dict | None:
        """获取术语表条目。"""
        try:
            response = requests.get(f"{self.base_url}/api/v1/knowledge/glossary/{code_term}")
            response.raise_for_status()
            return response.json()
        except requests.HTTPError as e:
            if e.response.status_code == 404:
                return None
            raise

    def get_tests_for_symbols(self, fqns: List[str]) -> List[Dict]:
        """获取符号的测试。"""
        # TODO: 实现测试查询逻辑
        return []

    def _calculate_risk(self, impact: Dict, tests: List) -> int:
        """从影响和测试计算风险评分 (0-100)。"""
        caller_count = len(impact.get("callers", []))
        test_count = len(tests)

        # 更多调用者 = 更高风险
        risk = min(caller_count * 10, 70)

        # 测试降低风险
        risk -= min(test_count * 5, 30)

        return max(0, risk)

    def _get_recommendation(self, risk_score: int) -> str:
        """根据风险评分获取建议。"""
        if risk_score < 20:
            return "安全重构"
        elif risk_score < 50:
            return "谨慎重构 - 先添加测试"
        else:
            return "高风险 - 需要仔细规划"


# 使用示例
if __name__ == "__main__":
    client = AriadneClient()

    # 搜索相关符号
    results = client.search("用户认证")
    print(f"找到 {len(results)} 个结果")

    # 分析重构风险
    if results:
        fqn = results[0]["fqn"]
        risk_analysis = client.analyze_refactoring_risk(fqn)
        print(f"风险分析: {risk_analysis}")
```

## CLI 与 API 映射

| CLI 命令 | API 端点 | 说明 |
|----------|----------|------|
| `ariadne search <query>` | `GET /api/v1/knowledge/search` | 相同行为 |
| `ariadne extract` | `POST /api/v1/knowledge/rebuild` | API 有异步选项 |
| `ariadne glossary` | `GET /api/v1/knowledge/glossary` | CLI 返回"未实现" |
| `ariadne trace <fqn>` | `POST /api/v1/knowledge/graph/query` | 相同结果 |

## 版本控制

API 使用 URL 路径进行语义化版本控制:
- 当前版本: `/api/v1/*`
- 未来版本: `/api/v2/*`

重大变更将增加主版本号。次版本号添加新功能。

## 故障排除

### 连接被拒绝
```
Error: Connection refused
```
**解决方案:** 启动 Ariadne 服务器: `ariadne serve`

### 空结果
```
搜索返回空结果
```
**解决方案:** 先运行提取: `POST /api/v1/knowledge/rebuild`

### 响应缓慢
```
API 响应时间 > 1 秒
```
**解决方案:** 检查数据库大小，考虑添加索引或使用过滤器

## 最佳实践

### 1. 缓存元数据

缓存不常变化的数据:
```python
class CachedAriadneClient(AriadneClient):
    def __init__(self, base_url: str = "http://localhost:8080"):
        super().__init__(base_url)
        self._cache = {}

    def get_symbol(self, fqn: str, use_cache: bool = True):
        if use_cache and fqn in self._cache:
            return self._cache[fqn]

        result = super().get_symbol(fqn)
        if result:
            self._cache[fqn] = result
        return result
```

### 2. 批量查询优化

减少网络往返:
```python
def batch_get_symbols(client: AriadneClient, fqns: List[str]):
    # 使用语义搜索批量查找
    unique_prefixes = set(fqn.split('.')[0] for fqn in fqns)

    results = {}
    for prefix in unique_prefixes:
        matching = client.search(prefix, limit=100)
        for item in matching:
            if item["fqn"] in fqns:
                results[item["fqn"]] = item

    return results
```

### 3. 优雅的错误处理

```python
def safe_api_call(func, *args, **kwargs):
    """带重试和退避的 API 调用包装器。"""
    max_retries = 3
    base_delay = 1.0

    for attempt in range(max_retries):
        try:
            return func(*args, **kwargs)
        except requests.HTTPError as e:
            if e.response.status_code == 429:
                # 速率限制 - 指数退避
                delay = base_delay * (2 ** attempt)
                time.sleep(delay)
            elif e.response.status_code >= 500:
                # 服务器错误 - 重试
                if attempt < max_retries - 1:
                    time.sleep(base_delay)
            else:
                # 客户端错误 - 不重试
                raise

    raise Exception(f"{func.__name__} 失败: 超过最大重试次数")
```

## 支持

- GitHub Issues: https://github.com/jersy/ariadne/issues
- 文档: https://github.com/jersy/ariadne/blob/main/README.md
- OpenAPI 规范: http://localhost:8080/openapi.json
