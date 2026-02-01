---
title: "Claude Settings Worktree Sync Solution"
date: 2026-02-02
status: brainstorm
type: improvement
---

# Claude Settings Worktree 同步方案

## What We're Building

解决 `.claude/settings.json` 在 Git worktree 新建时不会自动同步的问题，确保每个 worktree 都能获得正确的 LLM API 配置（第三方便宜 provider）。

## Problem Context

### 当前问题

1. `.gitignore` 忽略了 `.claude/` 目录
2. `settings.json` 包含第三方 LLM API key 和 URL
3. 新建 worktree 时，配置文件不会带过去
4. 系统环境变量有官方 key（成本高），settings.json 有便宜 key

### 约束条件

- **安全性**：第三方 API key 绝不能提交到 GitHub
- **自动化**：希望新建 worktree 时自动获得配置
- **非侵入**：不影响现有工作流

## Solution Approach: Git Post-Worktree Hook

### 方案概述

使用 Git 的 `post-worktree` 钩子，在新建 worktree 时自动从安全位置复制 `settings.json`。

### 架构设计

```
~/.claude-template/settings.json    # 安全位置：用户目录模板
              ↓ (post-worktree 钩子)
/path/to/worktree/.claude/settings.json
```

### Why This Approach

**优势：**
- ✅ **安全**：个人配置在用户目录 `~/`，不在仓库中
- ✅ **自动化**：新建 worktree 时自动同步
- ✅ **可维护**：单一真实来源，修改模板即可
- ✅ **团队友好**：每个人用自己的模板，互不干扰
- ✅ **回退友好**：删除 worktree 不影响源文件

**劣势：**
- ⚠️ 需要首次设置（创建模板和钩子）
- ⚠️ 如果修改模板，需要手动更新已有 worktree

## Implementation Design

### 1. 创建模板文件

```bash
# 创建用户目录模板
mkdir -p ~/.claude-template

# 复制当前 settings.json 作为模板
cp /path/to/ariadne/.claude/settings.json ~/.claude-template/settings.json
```

### 2. 创建 Git 钩子

```bash
# 在项目 .git/hooks/ 目录创建 post-worktree 钩子
cat > .git/hooks/post-worktree << 'EOF'
#!/bin/bash
# Git post-worktree hook: 自动同步 Claude settings

# 模板文件位置
TEMPLATE_SETTINGS="$HOME/.claude-template/settings.json"

# 新 worktree 位置（Git 传递的参数）
WORKTREE_DIR="$1"

# 目标位置
DEST_SETTINGS="$WORKTREE_DIR/.claude/settings.json"

# 检查模板是否存在
if [ ! -f "$TEMPLATE_SETTINGS" ]; then
    echo "Warning: Claude settings template not found at $TEMPLATE_SETTINGS"
    echo "Run: mkdir -p ~/.claude-template && cp .claude/settings.json ~/.claude-template/"
    exit 0
fi

# 创建 .claude 目录
mkdir -p "$WORKTREE_DIR/.claude"

# 复制配置文件
cp "$TEMPLATE_SETTINGS" "$DEST_SETTINGS"

echo "✓ Claude settings synced to $WORKTREE_DIR"
EOF

# 添加执行权限
chmod +x .git/hooks/post-worktree
```

### 3. 提交钩子到仓库（可选）

```bash
# 将钩子移至可追踪位置
mkdir -p .githooks
mv .git/hooks/post-worktree .githooks/post-worktree

# 配置 Git 使用项目钩子
git config core.hooksPath .githooks

# 提交到仓库
git add .githooks/post-worktree
git commit -m "feat: add post-worktree hook for Claude settings sync"
```

### 4. 初始化脚本（一次性设置）

```bash
#!/bin/bash
# setup-claude-settings.sh - 首次设置脚本

set -e

echo "Setting up Claude settings template..."

# 1. 创建模板目录
mkdir -p ~/.claude-template

# 2. 复制当前配置
if [ -f ".claude/settings.json" ]; then
    cp .claude/settings.json ~/.claude-template/settings.json
    echo "✓ Template created at ~/.claude-template/settings.json"
else
    echo "Warning: .claude/settings.json not found"
fi

# 3. 设置 Git 钩子
git config core.hooksPath .githooks
echo "✓ Git hooks configured"

echo ""
echo "Setup complete! Future worktrees will automatically receive Claude settings."
echo "To update existing worktrees, run: cp ~/.claude-template/settings.json <worktree>/.claude/"
```

## Key Decisions

### 决策 1: 使用 `~/.claude-template/` 而非项目目录

**原因：**
- 用户目录不在仓库中，无泄露风险
- 多个项目可以共享同一模板
- 符合 XDG 配置目录惯例

### 决策 2: 使用 `post-worktree` 而非 `pre-worktree`

**原因：**
- `post-worktree` 在 worktree 创建后执行，目录已存在
- `pre-worktree` 无法知道目标路径
- 可以在钩子中验证创建结果

### 决策 3: 复制而非符号链接

**原因：**
- 符号链接在不同系统上可能有兼容性问题
- 每个 worktree 独立，删除不影响其他
- 可以针对特定 worktree 修改配置

### 决策 4: 可选的钩子提交

**原因：**
- 提交到仓库：团队成员可以自动使用
- 不提交：个人配置，不强制团队使用

## Open Questions

| 问题 | 待讨论 |
|------|--------|
| Q1 | 模板文件更新后，如何通知已有 worktree？ |
| Q2 | 是否需要 `update-existing-worktrees` 命令？ |
| Q3 | 多个项目使用同一模板时，如何处理差异？ |

## Alternative Approaches Considered

### 方案 A: Skip-Worktree 模板模式

```bash
# 提交 settings.json.template
git add .claude/settings.json.template

# 本地使用真实文件
git update-index --skip-worktree .claude/settings.json
```

**未选择原因：**
- 需要维护模板和真实文件的同步
- 新手容易搞混 skip-worktree 和 assume-unchanged

### 方案 B: 符号链接

```bash
# 所有 worktree 链接到同一文件
ln -s ~/.claude-global/settings.json .claude/settings.json
```

**未选择原因：**
- 符号链接在不同系统上行为不一致
- Windows 支持需要特殊处理

### 方案 C: 环境变量统一

**未选择原因：**
- settings.json 是 Claude Code 特有的，与项目 .env 是两套系统
- 用户明确表示不想用 .env 方案

## Next Steps

### 立即行动

1. 创建 `~/.claude-template/settings.json`
2. 创建 `.githooks/post-worktree` 钩子
3. 运行设置脚本
4. 测试：新建 worktree 验证配置同步

### 未来增强

1. 添加 `update-all-worktrees` 命令
2. 支持多项目配置差异
3. 添加配置验证（检查 API key 有效性）
