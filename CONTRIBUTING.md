# Contributing to Ariadne

Thank you for your interest in contributing to Ariadne!

## Getting Started

1. Fork the repository
2. Clone your fork: `git clone https://github.com/YOUR_USERNAME/ariadne.git`
3. Install dependencies: `uv pip install -e ".[dev]"`
4. Create a feature branch: `git checkout -b feature/your-feature-name`

## Development Workflow

1. Make your changes
2. Write/update tests for your changes
3. Run tests: `pytest`
4. Format code: `ruff format .`
5. Lint code: `ruff check .`
6. Commit with conventional commit message
7. Push to your fork: `git push origin feature/your-feature-name`
8. Create a pull request

## Code Review Guidelines

### What We Look For

- **Correctness**: Does the code do what it's supposed to?
- **Clarity**: Is the code easy to understand?
- **Simplicity**: Is the solution as simple as possible?
- **Tests**: Are there tests for new functionality?
- **Documentation**: Are docs updated for API changes?

### Review Process

1. Automated checks (CI) must pass
2. At least one maintainer approval required
3. Address all review comments
4. Squash commits if needed before merge

## Coding Standards

### Python

- Type hints required for all public functions
- Docstrings using Google style
- Maximum line length: 100 characters
- Use `ruff` for formatting and linting

### Tests

- Write tests for all new functionality
- Test edge cases and error conditions
- Use descriptive test names
- Mock external dependencies (LLM API, file system)

## Pull Request Checklist

- [ ] Tests pass locally
- [ ] Code formatted with `ruff format .`
- [ ] Code passes `ruff check .`
- [ ] Documentation updated
- [ ] Commit messages follow conventions
- [ ] PR description summarizes changes

## Reporting Issues

When reporting bugs, please include:

- Python version
- Operating system
- Steps to reproduce
- Expected vs actual behavior
- Error messages or stack traces

## Feature Requests

For feature requests:

- Describe the problem you're trying to solve
- Explain why this feature would help
- Suggest a possible implementation (optional)
- Consider if this aligns with project goals

## License

By contributing, you agree that your contributions will be licensed under the MIT License.
