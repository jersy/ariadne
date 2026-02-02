# Ariadne Development Guide

## Setup Development Environment

```bash
# Install development dependencies
uv pip install -e ".[dev]"

# Run tests
pytest

# Run with coverage
pytest --cov=ariadne_core --cov=ariadne_analyzer --cov=ariadne_api

# Format code
ruff format .

# Lint code
ruff check .

# Type check
mypy ariadne_core/
```

## Project Structure

```
ariadne/
├── ariadne_core/          # Core extraction and storage
│   ├── extractors/        # ASM bytecode analysis
│   ├── storage/           # SQLite + ChromaDB
│   └── models/            # Data models
├── ariadne_analyzer/      # Analysis layers
│   ├── l1_business/       # L1: Business layer
│   ├── l2_architecture/   # L2: Architecture layer
│   └── l3_implementation/ # L3: Implementation layer
├── ariadne_api/           # FastAPI service
│   ├── routes/            # API endpoints
│   ├── schemas/           # Pydantic models
│   └── middleware/        # Middleware (rate limit, tracing)
├── ariadne_llm/           # LLM client
│   ├── client.py          # OpenAI-compatible client
│   ├── embedder.py        # Vector embeddings
│   └── config.py          # Configuration
├── ariadne_cli/           # Command-line interface
└── tests/                 # Test suite
    ├── unit/              # Unit tests
    ├── integration/       # Integration tests
    └── api/               # API tests
```

## Running Tests

```bash
# All tests
pytest

# Unit tests only
pytest tests/unit/

# Integration tests only
pytest tests/integration/

# API tests only
pytest tests/api/

# Specific test file
pytest tests/unit/test_llm_client.py

# With verbose output
pytest -v

# Stop on first failure
pytest -x
```

## Code Style

- **Formatter**: Ruff (compatible with Black)
- **Linter**: Ruff (compatible with Flake8, isort, etc.)
- **Type Checker**: mypy
- **Docstring Style**: Google style

## Commit Conventions

Follow [Conventional Commits](https://www.conventionalcommits.org/):

- `feat:` New feature
- `fix:` Bug fix
- `docs:` Documentation changes
- `refactor:` Code refactoring
- `test:` Test additions/changes
- `chore:` Build/tooling changes

## Development Workflow

1. Create a feature branch from `main`
2. Make changes with commit messages following conventions
3. Run tests and ensure they pass
4. Run linting and fix any issues
5. Submit a pull request

## Debugging

```bash
# Run with verbose logging
ARIADNE_LOG_LEVEL=DEBUG ariadne extract --project /path/to/project

# Run API server with auto-reload
ARIADNE_RELOAD=true ariadne serve --port 8080

# Check database contents
sqlite3 ariadne.db "SELECT * FROM symbols LIMIT 10"
```

## Performance Profiling

```bash
# Profile symbol extraction
python -m cProfile -o profile.stats ariadne extract --project /path/to/project
python -m pstats profile.stats
```
