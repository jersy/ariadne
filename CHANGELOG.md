# Changelog

All notable changes to Ariadne will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- HTTP API layer with FastAPI for all capabilities
- Glossary API endpoints for domain vocabulary access
- Prompt injection protection in LLM client
- Agent-native API completeness

### Changed
- Strengthened system prompts with security rules
- Improved rate limiting and middleware
- Enhanced error handling and logging

### Fixed
- N+1 query pattern in impact analyzer
- Thread safety issues in incremental coordinator
- Dual-write consistency between SQLite and ChromaDB
- Cascade delete orphaned edges

## [0.4.0] - 2026-02-02

### Added
- L1 Business Layer with natural language summaries
- Domain glossary extraction
- HTTP API endpoints (search, graph, impact, constraints, glossary)
- Rate limiting middleware
- Request tracing middleware

### Changed
- Improved LLM client with retry logic
- Enhanced batch processing capabilities

## [0.3.0] - 2026-02-01

### Added
- Three-layer knowledge architecture
- Vector embedding search with ChromaDB
- Impact analysis for change prediction
- Anti-pattern detection

## [0.2.0] - 2026-01-31

### Added
- ASM-based bytecode extraction
- Symbol indexing
- Call graph analysis
- Test mapping

## [0.1.0] - 2026-01-30

### Added
- Initial project structure
- Basic symbol extraction
- SQLite storage
