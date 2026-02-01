# Claude Worktree 设置指南

本指南说明如何设置和使用 Claude Code settings 的 Git worktree 自动同步功能。

## 概述

当使用 Git worktree 进行并行开发时，`.claude/settings.json` 不会自动复制到新 worktree。这个功能通过 Git `post-worktree` 钩子自动同步配置，确保每个 worktree 都能获得正确的 LLM API 配置。

**架构：**
```
~/.claude-template/settings.json    # 安全位置：用户目录模板
              ↓ (post-worktree 钩子自动复制)
/path/to/new-worktree/.claude/settings.json
```

## 快速开始

### 1. 一次性设置

```bash
# 在项目根目录运行
./scripts/setup-claude-settings.sh
```

设置脚本会：
- ✅ 创建 `~/.claude-template/` 目录
- ✅ 复制当前 `.claude/settings.json` 到模板
- ✅ 设置模板权限为 `0600`（安全）
- ✅ 创建 `.githooks/post-worktree` 钩子
- ✅ 配置 Git 使用项目钩子

### 2. 创建新 Worktree

```bash
# 新建 worktree 会自动获得配置
git worktree add ../feature-x -b feature/x

# 输出: ✓ Claude settings synced to ../feature-x
```

### 3. 验证配置

```bash
# 检查新 worktree 的配置
cat ../feature-x/.claude/settings.json

# 验证文件权限（应该是 600）
stat -f %Lp ../feature-x/.claude/settings.json
# macOS: 100600
# Linux:  600
```

## 工作原理

### Git Hook 执行流程

```
1. 用户运行: git worktree add ../feature-x -b feature/x
2. Git 创建 worktree 目录
3. Git 执行 .githooks/post-worktree 钩子
4. 钩子从 ~/.claude-template/settings.json 复制配置
5. 配置写入到 ../feature-x/.claude/settings.json
6. 设置权限为 0600
7. 输出成功消息
```

### 非阻塞设计

钩子设计为**非阻塞**，即使同步失败，worktree 仍会成功创建：

| 场景 | 行为 | 结果 |
|------|------|------|
| 模板不存在 | 记录警告，退出码 0 | Worktree 创建成功，无配置 |
| JSON 无效 | 记录错误，退出码 1 | Worktree 创建成功，配置无效 |
| 复制失败 | 记录错误，退出码 1 | Worktree 创建成功，无配置 |

## 故障排查

### 问题 1: 新 Worktree 没有 Settings.json

**症状：**
```bash
git worktree add ../test -b test
# 没有输出 "✓ Claude settings synced"
ls ../test/.claude/
# 文件不存在或为空
```

**原因：** 模板文件不存在

**解决方案：**
```bash
# 1. 检查模板是否存在
ls ~/.claude-template/settings.json

# 2. 如果不存在，重新运行设置脚本
./scripts/setup-claude-settings.sh

# 3. 验证模板已创建
test -f ~/.claude-template/settings.json && echo "Template exists"
```

---

### 问题 2: JSON 验证失败

**症状：**
```bash
git worktree add ../test -b test
# Error: Template JSON is invalid: ~/.claude-template/settings.json
```

**原因：** 模板文件 JSON 格式错误

**解决方案：**
```bash
# 1. 验证 JSON 格式
jq empty ~/.claude-template/settings.json

# 2. 查看错误详情
jq . ~/.claude-template/settings.json

# 3. 从当前配置重建模板
cp .claude/settings.json ~/.claude-template/settings.json

# 4. 验证重建成功
jq empty ~/.claude-template/settings.json
```

---

### 问题 3: 钩子未执行

**症状：**
```bash
git worktree add ../test -b test
# 没有任何钩子输出
ls ../test/.claude/settings.json
# 文件不存在
```

**原因：** Git 未配置使用项目钩子

**解决方案：**
```bash
# 1. 检查 Git 钩子配置
git config core.hooksPath
# 应该返回: .githooks

# 2. 如果返回空，重新配置
git config core.hooksPath .githooks

# 3. 验证钩子文件存在且可执行
test -x .githooks/post-worktree && echo "Hook is executable"
```

---

### 问题 4: 文件权限不正确

**症状：**
```bash
stat -f %Lp ../test/.claude/settings.json
# 返回: 644 (世界可读)
```

**原因：** 钩子未正确设置权限，或 umask 配置覆盖

**解决方案：**
```bash
# 1. 手动修复权限
chmod 600 ~/.claude-template/settings.json

# 2. 检查当前 umask
umask
# 推荐值: 0077 (新文件权限 644) 或 0077 (新文件权限 600)

# 3. 同步到所有 worktree
find .. -name ".claude" -type d -exec chmod 600 {}/settings.json \;
```

---

### 问题 5: 现有 Worktree 配置过时

**症状：** 修改了模板配置，但现有 worktree 仍使用旧配置

**原因：** 钩子只在新建 worktree 时执行，不更新现有 worktree

**解决方案：**
```bash
# 方案 A: 手动同步单个 worktree
cp ~/.claude-template/settings.json ../existing-worktree/.claude/

# 方案 B: 同步所有 worktree
git worktree list | awk '{print $1}' | while read path; do
    if [ -f "$path/.claude/settings.json" ]; then
        cp ~/.claude-template/settings.json "$path/.claude/settings.json"
        echo "Synced: $path"
    fi
done

# 方案 C: 使用同步脚本（未来实现）
./scripts/sync-all-claude-settings.sh
```

---

## 平台兼容性

### macOS

✅ **完全支持**

```bash
# 验证系统
uname -s
# 输出: Darwin

# 验证 Bash
bash --version
# 要求: 4.0+

# 验证 Git
git --version
# 要求: 2.5+
```

### Linux

✅ **完全支持**

```bash
# 验证系统
uname -s
# 输出: Linux

# 验证 Bash
bash --version
# 要求: 4.0+

# 验证 Git
git --version
# 要求: 2.5+
```

### Windows (Git Bash)

✅ **支持**

```bash
# Git Bash 提供 Unix-like 环境
# 路径格式: /c/Users/...

# 验证
echo $HOME
# 输出: /c/Users/YourUsername
```

**注意事项：**
- 模板路径 `$HOME/.claude-template/` 在 Git Bash 中工作正常
- 文件权限 `chmod 600` 在 Git Bash 中有效
- Windows 原生 Git 不支持 Bash 钩子（需要 Batch 脚本）

### Windows (WSL)

✅ **支持**

```bash
# WSL 提供完整的 Linux 环境
# 路径格式: /mnt/c/Users/...

# 验证
uname -s
# 输出: Linux
```

**注意事项：**
- 模板路径 `$HOME/.claude-template/` 指向 WSL home 目录
- Windows 文件系统通过 `/mnt/c/...` 访问
- 如果 Git 在 Windows 上运行但代码在 WSL 中，需要额外配置

---

## 安全最佳实践

### 1. 文件权限

所有 settings.json 文件应设置为 `0600`（仅用户可读写）：

```bash
# 检查模板权限
stat -f %Lp ~/.claude-template/settings.json
# macOS: 应该是 100600
# Linux:  应该是 600

# 修复权限
chmod 600 ~/.claude-template/settings.json
```

### 2. Git 排除

确认 `.gitignore` 包含 `.claude/`：

```bash
# 验证
grep ".claude/" .gitignore

# 如果没有，添加
echo ".claude/" >> .gitignore
```

### 3. API Key 管理

- ✅ **DO**: 存储在用户目录 `~/`（不在仓库中）
- ✅ **DO**: 设置文件权限为 `0600`
- ✅ **DO**: 使用 `~/.claude-template/` 作为单一真实来源
- ❌ **DON'T**: 提交 settings.json 到仓库
- ❌ **DON'T**: 在日志、调试输出中打印 API key
- ❌ **DON'T**: 在多用户系统上使用默认权限

---

## 常见使用场景

### 场景 1: 首次设置

```bash
# 1. 克隆项目后，进入目录
cd ariadne

# 2. 运行设置脚本
./scripts/setup-claude-settings.sh

# 3. 验证设置
test -f ~/.claude-template/settings.json && echo "Setup complete"
```

### 场景 2: 更新 API 配置

```bash
# 1. 编辑模板
nano ~/.claude-template/settings.json

# 2. 验证 JSON 格式
jq empty ~/.claude-template/settings.json

# 3. 新 worktree 会自动使用新配置
git worktree add ../new-feature -b feature/new
```

### 场景 3: 同步现有 Worktree

```bash
# 1. 列出所有 worktree
git worktree list

# 2. 手动同步（一次性）
for path in $(git worktree list | awk '{print $1}'); do
    cp ~/.claude-template/settings.json "$path/.claude/settings.json"
    echo "Synced: $path"
done

# 3. 验证
grep -r "ANTHROPIC_AUTH_TOKEN" ../*/.claude/settings.json
```

### 场景 4: 重建模板

```bash
# 1. 从当前配置重建
cp .claude/settings.json ~/.claude-template/settings.json

# 2. 设置权限
chmod 600 ~/.claude-template/settings.json

# 3. 验证
jq empty ~/.claude-template/settings.json && echo "Template is valid"
```

---

## 高级用法

### 自定义模板位置

如果需要使用不同的模板位置，可以修改钩子脚本：

```bash
# 编辑钩子
nano .githooks/post-worktree

# 修改模板路径
TEMPLATE_SETTINGS="$HOME/custom/location/settings.json"
```

### 项目特定配置

如果某些项目需要不同的配置：

```bash
# 在项目根目录创建项目特定配置
cp ~/.claude-template/settings.json .claude/settings.json

# 根据项目修改
nano .claude/settings.json

# 该项目的 worktree 会使用项目配置
# （因为钩子会覆盖模板）
```

---

## 相关文档

- **实现计划**: `docs/plans/2026-02-02-feat-claude-settings-worktree-auto-sync-plan.md`
- **设计讨论**: `docs/brainstorms/2026-02-02-claude-settings-worktree-sync-brainstorm.md`
- **Git Worktree**: https://git-scm.com/docs/git-worktree
- **Git Hooks**: https://git-scm.com/docs/githooks
