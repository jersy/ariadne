# 在您的代码库中使用 Compound 工作流

## 快速回答

**是的，compound 可以完全独立使用！** 不需要按照 brainstorm→plan→review→work 的顺序执行。

## 前置条件

只需要满足：
1. ✅ 您刚刚解决了一个问题
2. ✅ 解决方案已经验证有效
3. ✅ 这是一个值得记录的非平凡问题（不是简单的拼写错误）

**不需要**：
- ❌ 先运行 /workflows:plan
- ❌ 先运行 /workflows:review
- ❌ 按照特定的工作流顺序

## 如何在您的代码库中启用

### 方法一：自动设置（推荐）

```bash
# 在这个 plugin 仓库运行
cd /Users/jersyzhang/work/claude/compound-engineering-plugin
./setup-compound-for-your-repo.sh /path/to/your/project

# 例如：
./setup-compound-for-your-repo.sh ~/my-rails-app
```

这会自动创建：
- `docs/solutions/` 目录结构（13个分类目录）
- `schema.yaml` 配置文件
- `assets/resolution-template.md` 模板
- `references/yaml-schema.md` 参考文档
- `README.md` 使用说明

### 方法二：手动设置

1. **创建目录结构**：
```bash
cd /path/to/your/project
mkdir -p docs/solutions/{build-errors,test-failures,runtime-errors,performance-issues,database-issues,security-issues,ui-bugs,integration-issues,logic-errors,developer-experience,workflow-issue,best-practice,documentation-gap}
```

2. **复制配置文件**：
```bash
# 从这个 plugin 仓库复制
cp plugins/compound-engineering/skills/compound-docs/schema.yaml \
   /path/to/your/project/docs/solutions/

cp -r plugins/compound-engineering/skills/compound-docs/assets \
   /path/to/your/project/docs/solutions/

cp -r plugins/compound-engineering/skills/compound-docs/references \
   /path/to/your/project/docs/solutions/
```

3. **定制 schema.yaml**：

编辑 `docs/solutions/schema.yaml`，将 `component` enum 改成您项目的实际模块：

```yaml
component:
  type: enum
  values:
    # 改成您的项目模块，例如：
    - user_authentication    # 用户认证模块
    - payment_processing     # 支付处理
    - order_management       # 订单管理
    - notification_service   # 通知服务
    # ... 您的其他模块
```

## 使用方式

### 触发 1：自动触发（推荐）

当您解决问题后，只需说：
- "that worked"
- "it's fixed"
- "working now"
- "problem solved"

Claude Code 会自动检测并启动 compound 工作流。

### 触发 2：手动触发

直接运行命令：
```bash
claude /workflows:compound
```

或者提供上下文提示：
```bash
claude /workflows:compound "刚修复了 N+1 查询问题"
```

## 工作流程

Compound 会自动完成：

1. **提取上下文**：从对话历史中提取问题和解决方案
2. **分类问题**：根据 schema.yaml 自动分类
3. **生成文档**：使用 YAML frontmatter + markdown 格式
4. **保存文件**：到 `docs/solutions/[category]/[filename].md`
5. **交互选项**：询问您是否需要进一步操作

## 示例场景

### 场景 1：修复性能问题

```
You: 我发现首页加载很慢，有大量数据库查询
Claude: [帮助调查] 发现是 N+1 查询问题
Claude: [建议修复] 添加 includes(:comments) 预加载
You: 测试了一下，页面现在只需要 200ms，完美！that worked!

Claude: ✓ 自动触发 compound 工作流
        [自动提取] 问题：N+1 查询导致首页慢
        [自动分类] performance-issues
        [生成文档] docs/solutions/performance-issues/n-plus-one-homepage-20260131.md

        What's next?
        1. Continue workflow (recommended)
        2. Add to Required Reading
        3. Link related issues
        4-7. [其他选项]
```

### 场景 2：解决测试失败

```
You: 运行测试时出错：NoMethodError: undefined method 'email'
Claude: [帮助调试] 发现是 factory 缺少关联
You: 加了 association :user 后测试通过了

You: /workflows:compound  # 手动触发

Claude: [生成文档] docs/solutions/test-failures/factory-missing-association-20260131.md
```

## 生成的文档格式

每个文档包含：

```yaml
---
module: 您的模块名
date: 2026-01-31
problem_type: performance_issue  # 自动分类
component: rails_model
symptoms:
  - "首页加载超过 5 秒"
  - "数据库执行了 100+ 条查询"
root_cause: missing_include
severity: high
tags: [n-plus-one, eager-loading, performance]
---

# Troubleshooting: 首页 N+1 查询问题

## Problem
首页加载缓慢，数据库日志显示每个评论都执行了单独的查询...

## Symptoms
- 页面加载时间超过 5 秒
- 控制台显示 100+ 条 SELECT 查询

## What Didn't Work
**尝试 1：添加缓存**
- 为什么失败：没有解决根本问题，只是隐藏了症状

## Solution
添加预加载：
```ruby
# Before
@posts = Post.all

# After
@posts = Post.includes(:comments, :user)
```

## Why This Works
Rails 的 includes 方法使用 eager loading，一次查询加载所有关联数据...

## Prevention
- 开发时启用 bullet gem 检测 N+1 查询
- Code review 检查所有 .each 循环中的关联调用
```

## 复利效应

### 第一次遇到问题
- 研究、调试：30 分钟
- 记录文档：5 分钟
- **总计：35 分钟**

### 第二次遇到类似问题
- 搜索文档：`grep -r "N+1" docs/solutions/`
- 找到答案：2 分钟
- **节省：28 分钟**

### 团队效应
- 5 个开发者 × 每人遇到 3 次 = 15 次
- 节省：28 分钟 × 14 次 = **392 分钟（6.5 小时）**

**这就是"复利工程"：每次解决问题都让未来的工作更容易。**

## 自定义选项

### 修改问题分类

编辑 `schema.yaml` 中的 `problem_type`:

```yaml
problem_type:
  type: enum
  values:
    - build_error
    - performance_issue
    - your_custom_type    # 添加您的类型
```

### 修改严重程度级别

```yaml
severity:
  type: enum
  values:
    - p0_critical    # 自定义级别
    - p1_high
    - p2_medium
    - p3_low
```

### 添加自定义字段

```yaml
optional_fields:
  jira_ticket:
    type: string
    description: "关联的 JIRA ticket 号"

  assignee:
    type: string
    description: "负责人"
```

## 最佳实践

### ✅ 应该记录的问题

- 调试花费了 10+ 分钟
- 解决方案不明显
- 其他团队成员可能遇到相同问题
- 涉及框架的特殊用法
- 需要多次尝试才找到解决方案

### ❌ 不需要记录的问题

- 简单的拼写错误
- 明显的语法错误
- IDE 自动提示就能解决的问题
- 一次性的、不会再出现的问题

## 常见问题

### Q: compound 依赖其他工作流吗？
**A: 不依赖。** 可以独立使用，只要对话历史中有问题和解决方案的上下文即可。

### Q: 我可以在任何项目中使用吗？
**A: 可以。** 只需：
1. 安装 compound-engineering plugin
2. 在项目中创建 docs/solutions/ 结构
3. 定制 schema.yaml 适配您的项目

### Q: 如果我用的不是 Rails 怎么办？
**A: 完全可以。** 修改 schema.yaml：
- 把 `rails_model`, `rails_controller` 改成您的技术栈
- 把 `component` enum 改成您的项目模块
- 例如：`react_component`, `express_route`, `django_view`

### Q: 生成的文档可以手动编辑吗？
**A: 当然可以。** 文档是标准的 markdown 文件，随时可以编辑补充。

### Q: 如何搜索已有的解决方案？
**A: 多种方式：**
```bash
# 按错误消息搜索
grep -r "NoMethodError" docs/solutions/

# 按标签搜索
grep -r "tags:.*n-plus-one" docs/solutions/

# 按分类浏览
ls docs/solutions/performance-issues/
```

## 进阶用法

### 结合 Claude Code 的其他功能

```bash
# 解决问题后生成文档
claude /workflows:compound

# 创建相关的代码审查检查点
claude agent kieran-rails-reviewer "review the fix"

# 添加测试覆盖
claude agent cora-test-reviewer "add tests for this scenario"
```

### 团队协作

1. **提交到 Git**：将 `docs/solutions/` 提交到版本控制
2. **Code Review**：审查文档质量和准确性
3. **定期回顾**：每月回顾常见问题，提升预防措施
4. **入职培训**：新成员可以搜索历史问题快速上手

## 总结

Compound 工作流：
- ✅ 可以完全独立使用
- ✅ 不依赖其他工作流（brainstorm/plan/review/work）
- ✅ 适用于任何语言/框架（只需定制 schema）
- ✅ 自动化文档生成（节省时间）
- ✅ 创建可搜索的知识库（复利效应）

**立即开始：**
```bash
./setup-compound-for-your-repo.sh /path/to/your/project
```

然后在下次解决问题时，只需说 "that worked!" 🚀
