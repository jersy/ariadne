---
status: completed
priority: p3
issue_id: "022"
tags:
  - code-review
  - documentation
  - developer-experience
dependencies: []
---

# Missing README.md Documentation

## Problem Statement

The project **lacks a main README.md** file. Only `CLAUDE.md` exists, which is project-specific instructions for Claude Code. Developers need comprehensive documentation for onboarding, setup, and architecture overview.

**Current State:**
```
ariadne/
├── CLAUDE.md          ✅ (exists - Claude-specific)
├── README.md          ❌ (MISSING)
├── docs/
│   ├── plans/         ✅ (exists)
│   ├── reviews/       ✅ (exists)
│   └── solutions/     ✅ (exists)
```

**What's Missing:**
- Quick start guide
- Installation instructions
- Architecture overview
- Usage examples
- Development workflow
- Contributing guidelines

## Why It Matters

1. **Developer Onboarding**: New contributors have no starting point
2. **Project Discovery**: README is the first thing people see
3. **Setup Friction**: No clear installation steps
4. **Adoption Barrier**: Hard to evaluate without README

## Findings

### From Code Quality Review:

> **Severity:** MEDIUM
>
> The project lacks a main README.md. Only CLAUDE.md exists. Developers need setup instructions, quick start, and architecture overview.

### From Implementation Review:

> **Observation:** Plan document should reference a README that doesn't exist.

### Affected Files:

| File | Status | Should Contain |
|------|--------|----------------|
| `README.md` | ❌ Missing | Project overview, quick start |
| `CONTRIBUTING.md` | ❌ Missing | Dev workflow, PR guidelines |
| `ARCHITECTURE.md` | ❌ Missing | System design, decisions |
| `CHANGELOG.md` | ❌ Missing | Version history |

## Proposed Solutions

### Solution 1: Create Comprehensive README.md (Recommended)

**Approach:** Create a standard README with all essential sections.

**Pros:**
- Industry standard practice
- GitHub renders README automatically
- Covers all essential information

**Cons:**
- Maintenance overhead
- Need to keep in sync with code

**Effort:** Medium
**Risk:** Low

**README Structure:**
```markdown
# Ariadne: Code Knowledge Graph for Architect Agents

## Overview

Ariadne is a multi-dimensional code knowledge graph system that provides intelligent foundation for "architect agents". It automatically extracts semantic information, structural relationships, and implicit rules from Java/Spring codebases.

**Core Features:**
- 🧠 **L1 Business Layer**: Natural language summaries, domain glossary
- 🏗️ **L2 Architecture Layer**: Call chains, dependencies, anti-patterns
- 🔍 **L3 Implementation Layer**: Symbol indexing, impact analysis

## Quick Start

### Installation

\`\`\`bash
# Clone repository
git clone https://github.com/your-org/ariadne.git
cd ariadne

# Install with uv (recommended)
uv pip install -e .

# Or with pip
pip install -e .
\`\`\`

### Configuration

\`\`\`bash
# Copy environment template
cp .env.example .env

# Edit with your settings
# ARIADNE_DEEPSEEK_API_KEY=your_key_here
\`\`\`

### Usage

\`\`\`bash
# Start API server
ariadne serve --port 8080

# Index a Java project
ariadne extract --project /path/to/java/project

# Search code
ariadne search "用户登录验证"
\`\`\`

## Documentation

- [Architecture](docs/ARCHITECTURE.md)
- [API Reference](docs/API.md)
- [Development Guide](docs/DEVELOPMENT.md)
- [Contributing](CONTRIBUTING.md)

## License

MIT
```

### Solution 2: Split Documentation Files

**Approach:** Create separate focused documentation files.

**Pros:**
- More organized for large projects
- Easier to maintain
- Can link between docs

**Cons:**
- More files to maintain
- README still needed as entry point

**Effort:** Medium
**Risk:** Low

**File Structure:**
```
ariadne/
├── README.md              # Overview + quick start
├── ARCHITECTURE.md        # System design
├── DEVELOPMENT.md         # Developer guide
├── CONTRIBUTING.md        # Contribution guidelines
├── CHANGELOG.md           # Version history
└── docs/
    ├── api/               # API documentation
    ├── guides/            # User guides
    └── solutions/         # (existing)
```

### Solution 3: Generate README from Template

**Approach:** Use a tool to generate README from code/docstrings.

**Pros:**
- Automated, stays in sync
- Less manual maintenance

**Cons:**
- May lack personalization
- Tool dependency

**Effort:** Low (initial setup)
**Risk:** Medium (tool limitations)

## Recommended Action

**Use Solution 1 (Comprehensive README.md)**

Create a professional README that serves as the project's landing page, with links to additional documentation.

## Technical Details

### README Sections Required:

1. **Project Overview** (2-3 sentences)
2. **Features** (bullet points, 3-5 items)
3. **Quick Start** (installation + basic usage)
4. **Documentation Links** (architecture, API, development)
5. **Requirements** (Python version, Java for ASM service)
6. **Configuration** (environment variables)
7. **Examples** (2-3 usage examples)
8. **Troubleshooting** (common issues)
9. **License** (MIT or other)
10. **Acknowledgments** (references to CallGraph, ai-memory-system)

### Additional Documentation Files:

**ARCHITECTURE.md**:
```markdown
# Ariadne Architecture

## Three-Layer Knowledge Architecture

### L1: Business & Domain Layer
- Natural language summaries (LLM-generated)
- Domain glossary (Code Term → Business Meaning)
- Business constraints extraction

### L2: Architecture & Design Layer
- Call chain tracing
- External dependency topology
- Anti-pattern detection

### L3: Implementation Layer
- Symbol indexing (ASM bytecode analysis)
- Relationship graph (SQLite)
- Test mapping

## Technology Stack

| Component | Technology | Version |
|-----------|-----------|---------|
| Language | Python | 3.12+ |
| HTTP API | FastAPI | latest |
| Storage | SQLite | 3.x |
| Vector Store | ChromaDB | 0.5+ |
| Code Analysis | ASM | Java bytecode |
```

**DEVELOPMENT.md**:
```markdown
# Ariadne Development Guide

## Setup Development Environment

\`\`\`bash
# Install dev dependencies
uv pip install -e ".[dev]"

# Run tests
pytest

# Run with coverage
pytest --cov=ariadne

# Format code
ruff format .
ruff check .

# Type check
mypy ariadne_core/
\`\`\`

## Project Structure

\`\`\`
ariadne/
├── ariadne_core/          # Core extraction and storage
├── ariadne_analyzer/      # Analysis layers (L1/L2/L3)
├── ariadne_api/           # FastAPI service
├── ariadne_llm/           # LLM client
└── tests/                 # Test suite
\`\`\`

## Running Tests

\`\`\`bash
# Unit tests
pytest tests/unit/

# Integration tests
pytest tests/integration/

# API tests
pytest tests/api/
\`\`\`

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Run tests
5. Submit a pull request
```

### Files to Create:

1. **`README.md`** - Main project documentation
2. **`ARCHITECTURE.md`** - System architecture details
3. **`DEVELOPMENT.md`** - Developer guide
4. **`CONTRIBUTING.md`** - Contribution guidelines
5. **`CHANGELOG.md`** - Version history (start empty)

### Related Plan Updates:

The plan document should reference these new files in the "Documentation" section:

```markdown
## Documentation

### User Documentation
- README.md - Project overview and quick start
- docs/API.md - API reference (auto-generated)

### Developer Documentation
- ARCHITECTURE.md - System architecture
- DEVELOPMENT.md - Development guide
- CONTRIBUTING.md - Contribution guidelines
- CLAUDE.md - Claude-specific instructions
```

## Acceptance Criteria

- [x] README.md created with all required sections
- [ ] Quick start instructions tested by new developer
- [x] ARCHITECTURE.md with diagrams
- [x] DEVELOPMENT.md with setup steps
- [x] CONTRIBUTING.md with PR guidelines
- [x] CHANGELOG.md created (v0.1.0 entry)
- [ ] Badges added to README (build status, coverage, license)
- [x] Screenshots/examples of CLI usage (in README)
- [x] Links to documentation verified
- [ ] README renders correctly on GitHub

## Work Log

| Date | Action | Result |
|------|--------|--------|
| 2026-02-02 | Plan review completed | Missing README identified |
| 2026-02-02 | Created README.md | Project overview, features, quick start |
| 2026-02-02 | Created ARCHITECTURE.md | Three-layer architecture, tech stack |
| 2026-02-02 | Created DEVELOPMENT.md | Setup, testing, code style |
| 2026-02-02 | Created CONTRIBUTING.md | Workflow, PR guidelines |
| 2026-02-02 | Created CHANGELOG.md | Version history |
| | | |

## Resources

- **Affected Files**:
  - `README.md` (NEW)
  - `ARCHITECTURE.md` (NEW)
  - `DEVELOPMENT.md` (NEW)
  - `CONTRIBUTING.md` (NEW)
  - `CHANGELOG.md` (NEW)
- **Related Issues**:
  - Code Quality Review: Documentation gaps
- **References**:
  - Effective README: https://www.makeareadme.com/
  - Open Source Guide: https://opensource.guide/
