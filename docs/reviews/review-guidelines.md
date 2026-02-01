# Code Review Guidelines

This document contains guidelines for conducting code reviews in the Ariadne project.

## Pre-Review Checklist

Before starting a code review, reviewers should:

1. **Understand Project Context**
   - This is a local development tool, not a production SaaS
   - Single-user (developer) environment
   - No external network exposure

## Review Categories

### Security
- SQL injection vulnerabilities
- Path traversal
- Command injection
- Input validation
- Secret management (API keys in code)

### Performance

- N+1 query patterns
- Memory leaks
- Thread safety issues
- Blocking I/O in async contexts
- Unbounded operations

### Code Quality

- Code duplication
- Over-engineering (YAGNI violations)
- Naming conventions
- Documentation
- Test coverage

### Architecture

- SOLID principles
- Design patterns
- Component boundaries
- Extensibility
- Maintainability

## Issue Severity

### CRITICAL
- SQL injection
- Command injection
- Data loss bugs

### HIGH
- N+1 queries
- Thread safety issues
- Memory leaks
- Blocking I/O in async

### MEDIUM
- Code duplication
- Over-engineering
- Missing tests

### LOW
- Style inconsistencies
- Missing documentation
- Minor optimizations

## Local Development Only

The following are ACCEPTABLE for local development and should NOT be flagged:

| Issue | Status | Notes |
|-------|--------|-------|
| CORS: `*` with credentials | ✅ OK | Local only, no external exposure |
| No authentication | ✅ OK | Single developer environment |
| X-Forwarded-For trust | ✅ OK | No reverse proxy locally |

---

**Version**: 1.0
**Last Updated**: 2026-02-01
