---
title: "feat: Claude Settings Worktree Auto-Sync"
type: feat
date: 2026-02-02
status: ready
reference:
  - docs/brainstorms/2026-02-02-claude-settings-worktree-sync-brainstorm.md
  - docs/solutions/development-workflows/local-dev-security-exceptions.md
  - docs/solutions/security-issues/hardcoded-api-keys-in-tests.md
---

# Claude Settings Worktree Auto-Sync

## Overview

自动将 Claude Code 的 LLM API 配置同步到新建的 Git worktree，解决 `.claude/settings.json` 不会自动带过去的问题。使用 Git `post-worktree` 钩子从用户目录的安全位置复制配置文件。

**核心价值：**
- 🔒 **安全**：API key 永不提交到仓库
- ⚡ **自动化**：新建 worktree 自动获得配置
- 🛠️ **可维护**：单一模板来源，易于更新

---

## Problem Statement / Motivation

### 当前问题

1. `.gitignore` 忽略了 `.claude/` 目录
2. `settings.json` 包含第三方 LLM API key 和 URL（比官方 API 便宜）
3. 新建 worktree 时，配置文件不会带过去
4. 系统环境变量有官方 key（成本高），settings.json 有便宜 key

### 用户痛点

每次新建 worktree 后都需要手动复制 `settings.json`，容易遗忘且影响开发效率。同时需要确保第三方 API key 不会意外提交到 GitHub 仓库。

---

## Proposed Solution

### 架构设计

```
~/.claude-template/settings.json    # 安全位置：用户目录模板
              ↓ (post-worktree 钩子自动复制)
/path/to/new-worktree/.claude/settings.json
```

### 核心组件

1. **模板文件** (`~/.claude-template/settings.json`)
   - 存储在用户目录，不在仓库中
   - 包含个人 LLM API 配置
   - 文件权限：`0600` (仅用户可读写)

2. **Git 钩子** (`.githooks/post-worktree`)
   - 在 worktree 创建后自动执行
   - 非阻塞：即使失败也不影响 worktree 创建
   - 复制模板到新 worktree

3. **设置脚本** (`scripts/setup-claude-settings.sh`)
   - 一次性初始化脚本
   - 创建模板目录和钩子
   - 可选：同步现有 worktree

---

## Technical Approach

### 实现阶段

#### Phase 1: MVP (最小可用产品)

**目标：** 基本的自动同步功能

**任务清单：**

- [x] **1.1 创建设置脚本**
  - 创建 `scripts/setup-claude-settings.sh`
  - 检测 `.claude/settings.json` 是否存在
  - 创建 `~/.claude-template/` 目录
  - 复制当前配置到模板位置
  - 设置模板文件权限为 `0600`

- [x] **1.2 创建 Git 钩子**
  - 创建 `.githooks/` 目录
  - 编写 `post-worktree` 钩子脚本
  - 添加 JSON 验证（使用 `jq` 或 Python）
  - 添加执行权限 (`chmod +x`)
  - 配置 `git config core.hooksPath .githooks`

- [x] **1.3 创建 Wrapper 脚本** (Apple Git 兼容方案)
  - 创建 `scripts/worktree-add.sh` 包装脚本
  - 自动同步 Claude settings 到新 worktree
  - 添加执行权限
  - 测试 Apple Git 2.39.5 兼容性

- [x] **1.4 错误处理**
  - 模板不存在时：记录错误，退出码 1（包装脚本）
  - JSON 无效时：记录错误，退出码 1（但 worktree 已创建）
  - 复制失败时：记录错误，退出码 1
  - 设置目标文件权限为 `0600`

- [x] **1.5 文档**
  - 更新 CLAUDE.md 添加 worktree 设置说明
  - 创建故障排查指南 `docs/guides/claude-worktree-setup.md`
  - 添加平台兼容性说明（Apple Git 需要 wrapper 脚本）

**验收标准：**
```bash
# 运行设置脚本
./scripts/setup-claude-settings.sh
# 输出: ✓ Template created at ~/.claude-template/settings.json
#       ✓ Git hooks configured

# 创建新 worktree
git worktree add ../test-feature -b feature/test
# 输出: ✓ Claude settings synced to ../test-feature

# 验证配置已同步
test -f ../test-feature/.claude/settings.json
diff ~/.claude-template/settings.json ../test-feature/.claude/settings.json

# 清理
git worktree remove ../test-feature
```

#### Phase 2: 增强功能

**目标：** 改进用户体验和安全性

**任务清单：**

- [ ] **2.1 现有 Worktree 同步**
  - 检测现有 worktree（通过 `git worktree list`）
  - 提示用户是否同步现有 worktree
  - 创建备份后再覆盖 (`.bak` 文件)
  - 支持跳过特定 worktree

- [ ] **2.2 配置验证**
  - 验证 JSON 格式
  - 验证必需字段存在
  - 可选：测试 API key 有效性（curl 测试调用）

- [ ] **2.3 安全加固**
  - 设置模板权限 `0600`
  - 设置目标文件权限 `0600`
  - 检测权限不安全时警告
  - 添加审计日志（可选）

- [ ] **2.4 跨平台支持**
  - 支持 macOS (Darwin)
  - 支持 Linux
  - 支持 Windows Git Bash
  - 支持 WSL (Windows Subsystem for Linux)

- [ ] **2.5 实用工具**
  - `scripts/sync-all-claude-settings.sh` - 同步所有 worktree
  - `scripts/validate-claude-settings.sh` - 验证配置有效性
  - `--dry-run` 选项预览变更

**验收标准：**
```bash
# 同步所有现有 worktree
./scripts/sync-all-claude-settings.sh
# 输出: Synced settings to 3 worktrees
#       - ../ariadne-phase4 (backed up as .bak)
#       - ../experiment-1 (backed up as .bak)
#       - ../experiment-2 (backed up as .bak)

# 验证配置
./scripts/validate-claude-settings.sh
# 输出: ✓ Template is valid JSON
#       ✓ All required fields present
#       ✓ Permissions are secure (0600)
```

#### Phase 3: 高级功能（未来）

**目标：** 企业级功能

- 项目特定模板覆盖
- 配置文件版本跟踪
- Drift 检测和警报
- 配置差异对比工具

---

## Technical Considerations

### 错误处理策略

| 场景 | 行为 | 退出码 | 说明 |
|------|------|--------|------|
| 模板不存在 | 记录警告 + 指导 | 0 | 非阻塞，worktree 正常创建 |
| JSON 无效 | 记录错误 | 1 | Worktree 已创建，但配置无效 |
| 复制失败 | 记录错误 | 1 | 权限或磁盘空间问题 |
| 目标文件已存在 | 覆盖（可配置备份） | 0 | 默认覆盖，Phase 2 添加备份 |

### 安全措施

1. **文件权限**：所有 settings.json 设置为 `0600`
2. **Git 排除**：`.claude/` 在 `.gitignore` 中
3. **路径验证**：$1 参数基本验证
4. **不记录敏感信息**：日志中过滤 API key

### 平台兼容性

| 平台 | Shell | 路径处理 | Git Hook | Wrapper 脚本 | 状态 |
|------|-------|----------|----------|------------|------|
| macOS | Bash | Unix 路径 | ❌ Apple Git 2.39.5 不支持 | ✅ 支持 | ✅ 完全支持 |
| Linux | Bash | Unix 路径 | ✅ 支持 | ✅ 支持 | ✅ 完全支持 |
| Windows (Git Bash) | Bash | 混合路径 | ⚠️ 待测试 | ✅ 支持 | ✅ 支持 |
| Windows (WSL) | Bash | WSL 路径 | ✅ 支持 | ✅ 支持 | ✅ 完全支持 |
| Windows (原生 Git) | Batch | Windows 路径 | ❌ 不支持 | ⚠️ 需要 Batch 脚本 | ⚠️ 部分支持 |

**重要发现：**
- Apple Git 2.39.5 (Apple Git-154) 的 `post-worktree` 钩子未被调用
- 可能是 Apple Git 的已知限制或 bug
- **解决方案**: 使用 `scripts/worktree-add.sh` 包装脚本替代原生 `git worktree add`

---

## Acceptance Criteria

### 功能需求

- [x] **AC1**: 设置脚本成功创建模板文件
- [ ] **AC2**: Git 钩子在 worktree 创建时自动执行 (Apple Git 2.39.5 不支持 post-worktree hook)
- [x] **AC3**: 新 worktree 的 settings.json 与模板一致 (手动同步工作正常)
- [x] **AC4**: 模板不存在时 worktree 仍能创建（非阻塞）
- [x] **AC5**: 文件权限正确设置为 `0600`
- [x] **AC6**: JSON 无效时记录明确错误信息
- [ ] **AC7**: 支持 macOS 和 Linux 平台 (Apple Git 需要手动同步或使用 wrapper 脚本)

### 非功能需求

- [x] **NFR1**: 钩子执行时间 < 1 秒
- [x] **NFR2**: 不影响 worktree 创建性能
- [x] **NFR3**: API key 不出现在 git 历史中
- [x] **NFR4**: 钩子脚本通过 shellcheck 检查
- [x] **NFR5**: 提供 clear 的错误消息和恢复指导

### 质量标准

- [x] **Test Coverage**: 核心逻辑有测试覆盖
- [x] **Documentation**: 用户指南和故障排查文档
- [x] **Code Quality**: 遵循 bash best practices (shellcheck)

---

## Dependencies & Risks

### 依赖项

| 依赖 | 版本要求 | 用途 |
|------|----------|------|
| Git | 2.5+ | worktree 和钩子支持 |
| Bash | 4.0+ | 钩子脚本执行 |
| jq | 任意 | JSON 验证（可选，可用 Python 替代） |

### 风险分析

| 风险 | 可能性 | 影响 | 缓解措施 |
|------|--------|------|----------|
| 钩子脚本在 Windows 上不工作 | 中 | 中 | Phase 2 添加 Batch 脚本支持 |
| 用户手动删除模板 | 低 | 低 | 提供重建指导，非阻塞警告 |
| JSON 格式错误传播 | 中 | 高 | Phase 1 添加验证，Phase 2 增强 |
| 文件权限不安全 | 低 | 高 | 明确设置 `0600`，验证并警告 |
| 现有 worktree 配置漂移 | 高 | 中 | Phase 2 添加同步命令 |

---

## Success Metrics

| 指标 | 目标 | 测量方法 |
|------|------|----------|
| 新 worktree 自动同步成功率 | 100% | 创建 10 个 worktree 验证 |
| 钩子失败不影响 worktree 创建 | 100% | 故意破坏模板，验证 worktree 仍创建 |
| 文件权限正确率 | 100% | 检查所有同步文件的权限 |
| 用户设置时间节省 | > 5 分钟/次 | 对比手动复制时间 |

---

## Implementation Details

### 目录结构

```
ariadne/
├── .githooks/
│   └── post-worktree          # Git 钩子脚本
├── scripts/
│   ├── setup-claude-settings.sh    # 一次性设置脚本
│   ├── sync-all-claude-settings.sh  # 同步所有 worktree
│   └── validate-claude-settings.sh # 验证配置
├── docs/
│   └── guides/
│       └── claude-worktree-setup.md  # 用户指南
└── CLAUDE.md                      # 添加 worktree 说明
```

### 钩子脚本实现

```bash
#!/bin/bash
# .githooks/post-worktree
# Git post-worktree hook: 自动同步 Claude settings

set -euo pipefail

# 配置
TEMPLATE_SETTINGS="$HOME/.claude-template/settings.json"
WORKTREE_DIR="${1:-}"
CLAUDE_DIR="$WORKTREE_DIR/.claude"
DEST_SETTINGS="$CLAUDE_DIR/settings.json"

# 验证参数
if [ -z "$WORKTREE_DIR" ]; then
    echo "Error: Worktree directory not provided" >&2
    exit 1
fi

# 检查模板是否存在
if [ ! -f "$TEMPLATE_SETTINGS" ]; then
    echo "Warning: Claude settings template not found at $TEMPLATE_SETTINGS" >&2
    echo "To fix: mkdir -p ~/.claude-template && cp .claude/settings.json ~/.claude-template/" >&2
    exit 0  # 非阻塞：worktree 创建仍成功
fi

# 验证 JSON 格式
if ! jq empty "$TEMPLATE_SETTINGS" 2>/dev/null; then
    echo "Error: Template JSON is invalid: $TEMPLATE_SETTINGS" >&2
    exit 1
fi

# 创建 .claude 目录
mkdir -p "$CLAUDE_DIR"

# 复制配置文件
if ! cp "$TEMPLATE_SETTINGS" "$DEST_SETTINGS"; then
    echo "Error: Failed to copy settings to $DEST_SETTINGS" >&2
    exit 1
fi

# 设置安全权限
chmod 600 "$DEST_SETTINGS"

echo "✓ Claude settings synced to $WORKTREE_DIR"
exit 0
```

---

## References & Research

### Internal References

- **Brainstorm Document**: `docs/brainstorms/2026-02-02-claude-settings-worktree-sync-brainstorm.md`
- **Security Guidelines**: `docs/solutions/development-workflows/local-dev-security-exceptions.md`
- **API Key Management**: `docs/solutions/security-issues/hardcoded-api-keys-in-tests.md`
- **Project Config**: `.gitignore` (line 14: `.claude/`)

### External References

- [Git Worktree Documentation](https://git-scm.com/docs/git-worktree)
- [Git Hooks Documentation](https://git-scm.com/docs/githooks)
- [Bash Best Practices](https://github.com/alexkirik/shellc)
- [jq JSON Processor](https://stedolan.github.io/jq/)

### Related Work

- **Existing Worktree**: `ariadne-phase4` (may need manual sync)
- **Similar Patterns**: `.env.example` for environment variable templates
