#!/bin/bash
# worktree-add.sh - Wrapper script for git worktree add with Claude settings sync
#
# This wrapper creates a new worktree and automatically syncs Claude settings.
# Use this instead of 'git worktree add' to ensure settings are copied.
#
# Usage:
#   ./scripts/worktree-add.sh <path> -b <branch>
#   ./scripts/worktree-add.sh ../feature-x -b feature/x

set -euo pipefail

# 颜色输出
GREEN='\033[0;32m'
NC='\033[0m'

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# 帮助信息
if [ "${1:-}" = "-h" ] || [ "${1:-}" = "--help" ]; then
    echo "Usage: $0 <path> -b <branch> [git worktree options...]"
    echo ""
    echo "Wrapper for 'git worktree add' that syncs Claude settings."
    echo ""
    echo "Arguments passed directly to git worktree add after syncing settings."
    exit 0
fi

# 检查模板是否存在
TEMPLATE_SETTINGS="$HOME/.claude-template/settings.json"
if [ ! -f "$TEMPLATE_SETTINGS" ]; then
    echo "Error: Template not found at $TEMPLATE_SETTINGS"
    echo "Run setup script first: ./scripts/setup-claude-settings.sh"
    exit 1
fi

# 创建 worktree
echo "Creating worktree..."
git worktree add "$@"

# 获取 worktree 路径（Git worktree add 的第一个参数通常是路径）
WORKTREE_PATH=""
while [ $# -gt 0 ]; do
    case "$1" in
        -b)
            shift 2
            ;;
        *)
            if [[ -z "$WORKTREE_PATH" && ! "$1" =~ ^- ]]; then
                WORKTREE_PATH="$1"
            fi
            shift
            ;;
    esac
done

# 解析相对路径
if [[ "$WORKTREE_PATH" =~ ^\.\. ]]; then
    # 相对路径，转换为绝对路径
    WORKTREE_PATH="$(cd "$WORKTREE_PATH" && pwd)"
elif [[ ! "$WORKTREE_PATH" =~ ^/ ]]; then
    # 相对当前目录
    WORKTREE_PATH="$(pwd)/$WORKTREE_PATH"
fi

# 同步 settings
if [ -n "$WORKTREE_PATH" ] && [ -d "$WORKTREE_PATH" ]; then
    CLAUDE_DIR="$WORKTREE_PATH/.claude"
    DEST_SETTINGS="$CLAUDE_DIR/settings.json"

    echo -e "${GREEN}✓${NC} Syncing Claude settings to $WORKTREE_PATH"

    mkdir -p "$CLAUDE_DIR"
    cp "$TEMPLATE_SETTINGS" "$DEST_SETTINGS"
    chmod 600 "$DEST_SETTINGS"

    echo -e "${GREEN}✓${NC} Settings copied successfully"
else
    echo "Warning: Could not determine worktree path, skipping settings sync"
fi

echo -e "${GREEN}✓${NC} Worktree ready!"
