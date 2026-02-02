#!/bin/bash
# Setup script to enable compound workflow in your own codebase
# Usage: ./setup-compound-for-your-repo.sh /path/to/your/repo

set -e

TARGET_REPO=$1

if [ -z "$TARGET_REPO" ]; then
  echo "Usage: $0 /path/to/your/repo"
  exit 1
fi

if [ ! -d "$TARGET_REPO" ]; then
  echo "Error: Directory $TARGET_REPO does not exist"
  exit 1
fi

echo "Setting up compound workflow in $TARGET_REPO..."

# Create directory structure
echo "Creating docs/solutions/ directories..."
mkdir -p "$TARGET_REPO/docs/solutions"/{build-errors,test-failures,runtime-errors,performance-issues,database-issues,security-issues,ui-bugs,integration-issues,logic-errors,developer-experience,workflow-issue,best-practice,documentation-gap}

# Copy schema.yaml (you'll need to customize this for your project)
echo "Copying schema.yaml..."
cp plugins/compound-engineering/skills/compound-docs/schema.yaml "$TARGET_REPO/docs/solutions/"

# Copy template
echo "Copying resolution template..."
mkdir -p "$TARGET_REPO/docs/solutions/assets"
cp plugins/compound-engineering/skills/compound-docs/assets/resolution-template.md "$TARGET_REPO/docs/solutions/assets/"

# Copy references
echo "Copying references..."
mkdir -p "$TARGET_REPO/docs/solutions/references"
cp plugins/compound-engineering/skills/compound-docs/references/yaml-schema.md "$TARGET_REPO/docs/solutions/references/"

# Create a README
cat > "$TARGET_REPO/docs/solutions/README.md" << 'EOF'
# Solutions Documentation

This directory contains documented solutions to problems encountered during development.

## Using the Compound Workflow

When you solve a non-trivial problem:

1. **Auto-trigger**: Just say "that worked" or "it's fixed" in your Claude Code session
2. **Manual trigger**: Run `/workflows:compound` command

The workflow will:
- Extract problem context from conversation
- Generate categorized documentation with YAML frontmatter
- Create searchable knowledge base for future reference

## Directory Structure

- `build-errors/` - Compilation, bundling, build failures
- `test-failures/` - Test issues and failures
- `runtime-errors/` - Exceptions during execution
- `performance-issues/` - N+1 queries, slow performance
- `database-issues/` - Migrations, schema problems
- `security-issues/` - Auth, authorization, vulnerabilities
- `ui-bugs/` - Frontend, UI/UX issues
- `integration-issues/` - External API, service integration
- `logic-errors/` - Business logic bugs
- `developer-experience/` - DX improvements, tooling
- `workflow-issue/` - Process improvements
- `best-practice/` - Patterns to follow
- `documentation-gap/` - Missing documentation

## Customization

Edit `schema.yaml` to customize:
- Available problem types
- Component categories
- Root cause classifications
- Your project-specific needs

## Philosophy

**Each documented solution compounds your knowledge.**

- First time: Research (30 min)
- Document it: 5 min
- Next time: Quick lookup (2 min)

Knowledge compounds. 🚀
EOF

echo ""
echo "✓ Setup complete!"
echo ""
echo "Next steps:"
echo "1. Customize docs/solutions/schema.yaml for your project"
echo "2. Update the 'component' enum with your actual modules"
echo "3. Start using: claude /workflows:compound"
echo ""
echo "When you solve a problem, just say 'that worked!' and the workflow will document it."
