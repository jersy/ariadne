# Ariadne: Code Knowledge Graph for Architect Agents

Ariadne is a multi-dimensional code knowledge graph system that provides intelligent foundation for "architect agents". It automatically extracts semantic information, structural relationships, and implicit rules from Java/Spring codebases.

## Overview

Ariadne analyzes Java bytecode to build a three-layer knowledge graph:

- 🧠 **L1 Business Layer**: Natural language summaries, domain glossary, business constraints
- 🏗️ **L2 Architecture Layer**: Call chains, dependency topology, anti-pattern detection
- 🔍 **L3 Implementation Layer**: Symbol indexing, impact analysis, test mapping

## Features

- **Symbol Extraction**: ASM-based bytecode analysis for Java projects
- **Semantic Search**: Vector embedding search with ChromaDB
- **Impact Analysis**: Trace call chains to predict change impact
- **Business Glossary**: LLM-generated domain vocabulary (Code Term → Business Meaning)
- **Anti-Pattern Detection**: Identify architectural violations and code smells
- **HTTP API**: RESTful API for all capabilities (FastAPI)

## Quick Start

### Installation

```bash
# Clone repository
git clone https://github.com/your-org/ariadne.git
cd ariadne

# Install with uv (recommended)
uv pip install -e .

# Or with pip
pip install -e .
```

### Configuration

```bash
# Set environment variables for LLM access
export ARIADNE_DEEPSEEK_API_KEY=your_key_here
# or
export ARIADNE_OPENAI_API_KEY=your_key_here
```

### Usage

```bash
# Start API server
ariadne serve --port 8080

# Index a Java project
ariadne extract --project /path/to/java/project

# Search code by business meaning
ariadne search "用户登录验证"

# View entry points (HTTP APIs, scheduled tasks)
ariadne entries

# Analyze impact of changes
ariadne impact com.example.UserService

# Check for anti-patterns
ariadne check
```

## Documentation

- [Architecture](ARCHITECTURE.md) - Three-layer knowledge architecture
- [Development Guide](DEVELOPMENT.md) - Setup and contribution workflow
- [Contributing](CONTRIBUTING.md) - PR guidelines and code review
- [API Documentation](docs/) - Detailed API reference

## Requirements

- **Python**: 3.12+
- **Java**: 8+ (for ASM bytecode service)
- **Dependencies**: See `pyproject.toml`

## Project Structure

```
ariadne/
├── ariadne_core/          # Core extraction and storage
├── ariadne_analyzer/      # Analysis layers (L1/L2/L3)
├── ariadne_api/           # FastAPI HTTP service
├── ariadne_llm/           # LLM client (OpenAI/DeepSeek/Ollama)
├── ariadne_cli/           # Command-line interface
└── tests/                 # Test suite
```

## License

MIT

## Acknowledgments

Inspired by and built upon:
- [CallGraph](https://github.com/gousiosg/java-callgraph) - Java call graph analysis
- [ai-memory-system](https://github.com/fum2024/ai-memory-system) - AI memory architecture
