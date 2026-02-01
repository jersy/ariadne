# ASM Analysis Service (Spring Boot)

Java 字节码分析服务，基于 ASM 库和 Spring Boot 3。

---

## 📋 功能

- ✅ **符号索引**：分析 .class 文件，提取类、方法、字段信息
- ✅ **调用关系**：分析方法调用、继承关系、成员关系
- ✅ **注解提取**：提取 `@Override`, `@Transactional` 等注解信息
- ✅ **REST API**：提供 HTTP 接口供 Python 客户端调用
- ✅ **行号追踪**：记录方法定义和调用的行号

---

## 🛠️ 技术栈

- **Java**: 17+
- **Spring Boot**: 3.2.3
- **ASM**: 9.x (字节码操作框架)
- **Maven**: 构建工具

---

## 🚀 快速启动

### 方式 1：使用启动脚本（推荐）

**Linux/Mac:**
```bash
./run.sh
```

**Windows:**
```bash
run.bat
```

### 方式 2：使用 Maven

```bash
# 开发模式（自动重新编译）
mvn spring-boot:run

# 生产模式（打包后运行）
mvn clean package
java -jar target/asm-analysis-service-spring-1.0.0.jar
```

### 验证服务已启动

```bash
# 检查健康状态
curl http://localhost:8766/health

# 预期输出
{"status":"UP","service":"ASM Analysis Service","version":"1.0.0"}
```

服务默认监听端口：**8766**

---

## 📡 API 端点

### 1. 健康检查

```bash
GET /health
```

**响应示例:**
```json
{
  "status": "UP",
  "service": "ASM Analysis Service",
  "version": "1.0.0"
}
```

### 2. 符号索引

提取类和方法的符号信息（FQN、类型、行号等）。

```bash
POST /index
Content-Type: application/json

{
  "classFiles": [
    {
      "path": "/path/to/MyClass.class",
      "content": "base64-encoded-bytes"
    }
  ]
}
```

**响应示例:**
```json
{
  "symbols": [
    {
      "fqn": "com.example.MyClass",
      "nodeType": "class",
      "line": 10
    },
    {
      "fqn": "com.example.MyClass.myMethod",
      "nodeType": "method",
      "line": 25
    }
  ]
}
```

### 3. 调用图分析

分析类的调用关系、继承关系等。

```bash
POST /analyze
Content-Type: application/json

{
  "classFiles": [
    {
      "path": "/path/to/MyClass.class",
      "content": "base64-encoded-bytes"
    }
  ]
}
```

**响应示例:**
```json
{
  "nodes": [...],
  "edges": [...],
  "metadata": {...}
}
```

### 4. 关闭服务

```bash
POST /shutdown
```

---

## 🏗️ 构建说明

### 构建 JAR 包

```bash
mvn clean package

# 输出位置
# target/asm-analysis-service-spring-1.0.0.jar
```

### 运行测试

```bash
mvn test
```

### 清理构建产物

```bash
mvn clean
```

---

## 🔧 配置

### 端口配置

默认端口：8766

修改端口：编辑 `src/main/resources/application.properties`

```properties
server.port=8766
```

或通过环境变量：

```bash
SERVER_PORT=9000 java -jar target/asm-analysis-service-spring-1.0.0.jar
```

### 日志配置

日志输出到：
- 控制台（INFO 级别）
- `service.log` 文件（所有级别）

修改日志级别：编辑 `src/main/resources/application.properties`

```properties
logging.level.com.callgraph=DEBUG
```

---

## 📦 Python 客户端

Python 客户端位于主项目的 `callgraph_core.extractors.asm` 模块。

### 使用示例

```python
from callgraph_core.extractors.asm.extractor import ASMExtractor

# 创建提取器（自动连接到 Java 服务）
extractor = ASMExtractor(
    db_path=".callgraph.db",
    service_url="http://localhost:8766"
)

# 构建符号索引
extractor.build_symbol_index(packages)

# 提取调用图
extractor.extract(packages)
```

**注意**：使用前需要先启动此 Java 服务！

---

## 🐛 故障排除

### 服务无法启动

**问题**: 端口 8766 已被占用

**解决**:
```bash
# 查找占用端口的进程
lsof -i :8766  # Mac/Linux
netstat -ano | findstr :8766  # Windows

# 杀死进程或更改服务端口
```

### 编译失败

**问题**: Java 版本不兼容

**解决**:
```bash
# 检查 Java 版本（需要 17+）
java -version

# 如果版本过低，升级 Java
# Mac: brew install openjdk@17
# Linux: sudo apt install openjdk-17-jdk
```

### 内存不足

**问题**: 分析大型项目时 OutOfMemoryError

**解决**:
```bash
# 增加 JVM 堆内存
java -Xmx4g -jar target/asm-analysis-service-spring-1.0.0.jar
```

---

## 📚 项目结构

```
asm-analysis-service/
├── pom.xml                         # Maven 配置
├── run.sh                          # Linux/Mac 启动脚本
├── run.bat                         # Windows 启动脚本
├── src/
│   ├── main/
│   │   ├── java/                   # Java 源代码
│   │   │   └── com/callgraph/
│   │   │       ├── service/        # Spring Boot 服务
│   │   │       ├── analyzer/       # ASM 分析器
│   │   │       └── model/          # 数据模型
│   │   └── resources/
│   │       └── application.properties
│   └── test/
│       └── java/                   # 测试代码
└── target/                         # 构建输出（不提交到 git）
```

---

## 📖 相关文档

- [ASM 官方文档](https://asm.ow2.io/)
- [Spring Boot 文档](https://spring.io/projects/spring-boot)
- [CallGraph 主项目 README](../README.md)

---

## 📄 许可证

与主项目相同 (MIT)

---

## 🔗 集成关系

```
┌─────────────────────────────────────┐
│  Python 层                           │
│  ┌─────────────────────────────┐    │
│  │ callgraph_core              │    │
│  │  └─ extractors/asm/         │    │
│  │      └─ extractor.py        │────┼──► HTTP REST API
│  └─────────────────────────────┘    │
└─────────────────────────────────────┘
                 │
                 │ HTTP (port 8766)
                 ▼
┌─────────────────────────────────────┐
│  Java 层                             │
│  ┌─────────────────────────────┐    │
│  │ asm-analysis-service        │    │
│  │  (Spring Boot 3)            │    │
│  │  └─ ASM Bytecode Analyzer   │    │
│  └─────────────────────────────┘    │
└─────────────────────────────────────┘
```

**通信方式**: Python 通过 HTTP REST API 调用 Java 服务

**部署方式**: 独立部署，Python 和 Java 可以在不同机器上运行
