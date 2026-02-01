"""Database schema definitions for Ariadne knowledge graph."""

# Phase 1 (L3): Core symbol and edge tables
SCHEMA_L3 = """
-- Symbol nodes
CREATE TABLE IF NOT EXISTS symbols (
    id INTEGER PRIMARY KEY,
    fqn TEXT NOT NULL UNIQUE,
    kind TEXT NOT NULL,
    name TEXT NOT NULL,
    file_path TEXT,
    line_number INTEGER,
    modifiers TEXT,
    signature TEXT,
    parent_fqn TEXT,
    annotations TEXT,
    file_hash TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_symbols_fqn ON symbols(fqn);
CREATE INDEX IF NOT EXISTS idx_symbols_kind ON symbols(kind);
CREATE INDEX IF NOT EXISTS idx_symbols_file ON symbols(file_path);
CREATE INDEX IF NOT EXISTS idx_symbols_parent ON symbols(parent_fqn);

-- Relationship edges
CREATE TABLE IF NOT EXISTS edges (
    id INTEGER PRIMARY KEY,
    from_fqn TEXT NOT NULL,
    to_fqn TEXT NOT NULL,
    relation TEXT NOT NULL,
    metadata TEXT,
    FOREIGN KEY (from_fqn) REFERENCES symbols(fqn),
    FOREIGN KEY (to_fqn) REFERENCES symbols(fqn)
);

CREATE INDEX IF NOT EXISTS idx_edges_from ON edges(from_fqn);
CREATE INDEX IF NOT EXISTS idx_edges_to ON edges(to_fqn);
CREATE INDEX IF NOT EXISTS idx_edges_relation ON edges(relation);

-- Index metadata (for tracking indexed state)
CREATE TABLE IF NOT EXISTS index_metadata (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""

# Phase 2 (L2): Architecture layer tables
SCHEMA_L2 = """
-- Entry points (HTTP API, scheduled, MQ consumers)
CREATE TABLE IF NOT EXISTS entry_points (
    id INTEGER PRIMARY KEY,
    symbol_fqn TEXT NOT NULL,
    entry_type TEXT NOT NULL,
    http_method TEXT,
    http_path TEXT,
    cron_expression TEXT,
    mq_queue TEXT,
    FOREIGN KEY (symbol_fqn) REFERENCES symbols(fqn)
);

-- External dependencies (Redis, MySQL, MQ, RPC)
CREATE TABLE IF NOT EXISTS external_dependencies (
    id INTEGER PRIMARY KEY,
    caller_fqn TEXT NOT NULL,
    dependency_type TEXT NOT NULL,
    target TEXT,
    strength TEXT DEFAULT 'strong',
    FOREIGN KEY (caller_fqn) REFERENCES symbols(fqn)
);

-- Anti-pattern detection results
CREATE TABLE IF NOT EXISTS anti_patterns (
    id INTEGER PRIMARY KEY,
    rule_id TEXT NOT NULL,
    from_fqn TEXT NOT NULL,
    to_fqn TEXT,
    severity TEXT NOT NULL,
    message TEXT NOT NULL,
    detected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""

# Phase 3 (L1): Business layer tables
SCHEMA_L1 = """
-- Business summaries (text in SQLite, vectors in ChromaDB)
CREATE TABLE IF NOT EXISTS summaries (
    id INTEGER PRIMARY KEY,
    target_fqn TEXT NOT NULL,
    level TEXT NOT NULL,
    summary TEXT NOT NULL,
    vector_id TEXT,
    is_stale BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Domain glossary
CREATE TABLE IF NOT EXISTS glossary (
    id INTEGER PRIMARY KEY,
    code_term TEXT NOT NULL,
    business_meaning TEXT NOT NULL,
    synonyms TEXT,
    source_fqn TEXT,
    vector_id TEXT
);

-- Business constraints
CREATE TABLE IF NOT EXISTS constraints (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT NOT NULL,
    source_fqn TEXT,
    source_line INTEGER,
    constraint_type TEXT,
    vector_id TEXT
);
"""

ALL_SCHEMAS = {
    "l3": SCHEMA_L3,
    "l2": SCHEMA_L2,
    "l1": SCHEMA_L1,
}
