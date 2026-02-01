# Ariadne Architecture

## Three-Layer Knowledge Architecture

Ariadne organizes code knowledge into three distinct layers, each serving different analysis needs:

### L1: Business & Domain Layer

**Purpose**: Bridge technical code with business meaning

- **Natural Language Summaries**: LLM-generated descriptions of what code does
- **Domain Glossary**: Code Term → Business Meaning mappings (e.g., "Sku" → "Stock Keeping Unit")
- **Business Constraints**: Extracted rules and invariants from code

**Components**:
- `ariadne_analyzer/l1_business/summarizer.py` - Summary generation
- `ariadne_analyzer/l1_business/glossary.py` - Domain vocabulary extraction
- `ariadne_analyzer/l1_business/constraints.py` - Business rule extraction

### L2: Architecture & Design Layer

**Purpose**: Understand system structure and design relationships

- **Call Chain Tracing**: Follow execution paths across methods
- **External Dependency Topology**: Database, Redis, MQ, RPC dependencies
- **Anti-Pattern Detection**: Identify architectural violations

**Components**:
- `ariadne_analyzer/l2_architecture/call_chain.py` - Call graph analysis
- `ariadne_analyzer/l2_architecture/dependency_tracker.py` - Dependency mapping
- `ariadne_analyzer/l2_architecture/anti_patterns.py` - Violation detection

### L3: Implementation Layer

**Purpose**: Low-level code facts and relationships

- **Symbol Indexing**: ASM bytecode analysis for classes, methods, fields
- **Relationship Graph**: SQLite-based edge storage (calls, inherits, uses)
- **Test Mapping**: Link production code to test code

**Components**:
- `ariadne_core/extractors/asm/` - Bytecode analysis
- `ariadne_core/storage/sqlite_store.py` - Graph storage
- `ariadne_analyzer/l3_implementation/test_mapper.py` - Test linking

## Technology Stack

| Component | Technology | Version |
|-----------|-----------|---------|
| Language | Python | 3.12+ |
| HTTP API | FastAPI | latest |
| Storage | SQLite | 3.x |
| Vector Store | ChromaDB | 0.5+ |
| Code Analysis | ASM | Java bytecode |
| LLM | OpenAI/DeepSeek/Ollama | - |

## Data Flow

```
Java Source Code
       ↓
   ASM Bytecode Analysis
       ↓
   Symbol Extraction (L3)
       ↓
   ┌─────────┬─────────┬─────────┐
   ↓         ↓         ↓         ↓
L3 Store  L2 Analysis  L1 LLM Summaries
   ↓         ↓         ↓
   └─────────┴─────────┴────→ API Layer
```

## Storage Schema

**SQLite Tables**:
- `symbols` - Code symbols (classes, methods, fields)
- `edges` - Relationships (calls, inherits, uses)
- `summaries` - L1 business summaries
- `glossary` - Domain vocabulary
- `constraints` - Business rules
- `entry_points` - HTTP APIs, scheduled tasks
- `anti_patterns` - Violations detected

**ChromaDB Collections**:
- `summaries` - Vector embeddings for summaries
- `glossary` - Vector embeddings for glossary terms

## API Endpoints

- `GET /health` - Health check
- `POST /api/v1/search` - Semantic code search
- `POST /api/v1/graph/query` - Graph traversal
- `GET /api/v1/symbol/{fqn}` - Symbol details
- `POST /api/v1/impact` - Impact analysis
- `GET /api/v1/knowledge/glossary` - Domain glossary
- `POST /api/v1/check` - Anti-pattern detection
- `POST /api/v1/rebuild` - Rebuild knowledge graph
