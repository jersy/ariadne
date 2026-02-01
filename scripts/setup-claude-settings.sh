#!/bin/bash
# setup-claude-settings.sh - 一次性设置脚本
#
# 此脚本设置 Claude Code settings 的自动同步功能
# 功能：
#   1. 创建 ~/.claude-template/ 目录
#   2. 复制当前 .claude/settings.json 到模板位置
#   3. 设置模板文件权限为 0600 (仅用户可读写)
#   4. 创建 .githooks/ 目录和 post-worktree 钩子
#   5. 配置 Git 使用项目钩子

set -euo pipefail

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 日志函数
log_info() {
    echo -e "${GREEN}✓${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}⚠${NC} $1" >&2
}

log_error() {
    echo -e "${RED}✗${NC} $1" >&2
}

# 获取脚本所在目录的绝对路径
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

echo "=== Claude Settings Worktree Auto-Sync Setup ==="
echo ""

# 1. 检查当前 settings.json 是否存在
CURRENT_SETTINGS="$PROJECT_ROOT/.claude/settings.json"
if [ ! -f "$CURRENT_SETTINGS" ]; then
    log_error "Settings file not found: $CURRENT_SETTINGS"
    echo "Please ensure .claude/settings.json exists in the project root."
    exit 1
fi

log_info "Found settings file: $CURRENT_SETTINGS"

# 2. 创建模板目录
TEMPLATE_DIR="$HOME/.claude-template"
TEMPLATE_SETTINGS="$TEMPLATE_DIR/settings.json"

if [ ! -d "$TEMPLATE_DIR" ]; then
    mkdir -p "$TEMPLATE_DIR"
    log_info "Created template directory: $TEMPLATE_DIR"
else
    log_info "Template directory already exists: $TEMPLATE_DIR"
fi

# 3. 复制当前配置到模板位置
if [ -f "$TEMPLATE_SETTINGS" ]; then
    log_warn "Template already exists at $TEMPLATE_SETTINGS"
    echo -n "  Overwrite? [y/N]: "
    read -r response
    if [[ "$response" =~ ^[Yy]$ ]]; then
        cp "$CURRENT_SETTINGS" "$TEMPLATE_SETTINGS"
        log_info "Updated template file"
    else
        log_warn "Keeping existing template, skipping copy"
    fi
else
    cp "$CURRENT_SETTINGS" "$TEMPLATE_SETTINGS"
    log_info "Copied settings to template: $TEMPLATE_SETTINGS"
fi

# 4. 设置模板文件权限为 0600
chmod 600 "$TEMPLATE_SETTINGS"
log_info "Set template permissions to 0600 (user read/write only)"

# 5. 验证 JSON 格式
if command -v jq >/dev/null 2>&1; then
    if jq empty "$TEMPLATE_SETTINGS" >/dev/null 2>&1; then
        log_info "Template JSON is valid"
    else
        log_error "Template JSON is invalid!"
        echo "Please check: $TEMPLATE_SETTINGS"
        exit 1
    fi
else
    log_warn "jq not found, skipping JSON validation"
    echo "  Install jq for JSON validation: brew install jq"
fi

# 6. 创建 .githooks 目录
GITHOOKS_DIR="$PROJECT_ROOT/.githooks"
if [ ! -d "$GITHOOKS_DIR" ]; then
    mkdir -p "$GITHOOKS_DIR"
    log_info "Created githooks directory: $GITHOOKS_DIR"
else
    log_info "Githooks directory already exists: $GITHOOKS_DIR"
fi

# 7. 创建 post-worktree 钩子
HOOK_FILE="$GITHOOKS_DIR/post-worktree"

cat > "$HOOK_FILE" << 'HOOK_EOF'
#!/bin/bash
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
if command -v jq >/dev/null 2>&1; then
    if ! jq empty "$TEMPLATE_SETTINGS" >/dev/null 2>&1; then
        echo "Error: Template JSON is invalid: $TEMPLATE_SETTINGS" >&2
        exit 1
    fi
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
HOOK_EOF

chmod +x "$HOOK_FILE"
log_info "Created post-worktree hook: $HOOK_FILE"

# 8. 配置 Git 使用项目钩子
if git config core.hooksPath ".githooks" 2>/dev/null; then
    log_info "Configured Git to use project hooks"
else
    log_warn "Failed to configure Git hooks (may already be configured)"
fi

# 9. 检测现有 worktree
echo ""
log_info "Checking for existing worktrees..."

if command -v git >/dev/null 2>&1; then
    WORKTREES=$(git worktree list 2>/dev/null | grep -v "bare" | wc -l | tr -d ' ' || echo "0")

    if [ "$WORKTREES" -gt 0 ]; then
        echo ""
        log_warn "Found $WORKTREES existing worktree(s)"
        echo ""
        echo "Existing worktrees will NOT be automatically synced."
        echo "To sync existing worktrees manually, run:"
        echo "  cp ~/.claude-template/settings.json <worktree-path>/.claude/"
        echo ""
        echo "Current worktrees:"
        git worktree list
    else
        log_info "No existing worktrees found"
    fi
fi

# 10. 完成
echo ""
echo "=== Setup Complete ==="
echo ""
echo "Template location: $TEMPLATE_SETTINGS"
echo "Hook location:   $HOOK_FILE"
echo ""
echo "Next steps:"
echo "  1. Test by creating a new worktree:"
echo "     git worktree add ../test-branch -b test"
echo ""
echo "  2. New worktrees will automatically receive Claude settings"
echo ""
echo "  3. To update template in the future:"
echo "     nano ~/.claude-template/settings.json"
echo ""
echo "  4. To sync existing worktrees manually:"
echo "     cp ~/.claude-template/settings.json <worktree>/.claude/"
