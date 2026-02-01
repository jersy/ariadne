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

-- Relationship edges (no FK constraint - edges can reference external symbols)
CREATE TABLE IF NOT EXISTS edges (
    id INTEGER PRIMARY KEY,
    from_fqn TEXT NOT NULL,
    to_fqn TEXT NOT NULL,
    relation TEXT NOT NULL,
    metadata TEXT
);

CREATE INDEX IF NOT EXISTS idx_edges_from ON edges(from_fqn);
CREATE INDEX IF NOT EXISTS idx_edges_to ON edges(to_fqn);
CREATE INDEX IF NOT EXISTS idx_edges_relation ON edges(relation);
-- 复合索引：用于 get_call_chain 和 get_reverse_callers 查询优化
CREATE INDEX IF NOT EXISTS idx_edges_from_relation ON edges(from_fqn, relation);
CREATE INDEX IF NOT EXISTS idx_edges_to_relation ON edges(to_fqn, relation);

-- Cascade delete triggers for edges table
-- Delete outgoing edges when a symbol is deleted
CREATE TRIGGER IF NOT EXISTS edges_delete_outgoing_on_symbol_delete
    AFTER DELETE ON symbols
    FOR EACH ROW
    WHEN EXISTS (SELECT 1 FROM edges WHERE from_fqn = OLD.fqn)
BEGIN
    DELETE FROM edges WHERE from_fqn = OLD.fqn;
END;

-- Delete incoming edges when a symbol is deleted
CREATE TRIGGER IF NOT EXISTS edges_delete_incoming_on_symbol_delete
    AFTER DELETE ON symbols
    FOR EACH ROW
    WHEN EXISTS (SELECT 1 FROM edges WHERE to_fqn = OLD.fqn)
BEGIN
    DELETE FROM edges WHERE to_fqn = OLD.fqn;
END;

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
    FOREIGN KEY (symbol_fqn) REFERENCES symbols(fqn) ON DELETE CASCADE
);

-- External dependencies (Redis, MySQL, MQ, RPC)
CREATE TABLE IF NOT EXISTS external_dependencies (
    id INTEGER PRIMARY KEY,
    caller_fqn TEXT NOT NULL,
    dependency_type TEXT NOT NULL,
    target TEXT,
    strength TEXT DEFAULT 'strong',
    FOREIGN KEY (caller_fqn) REFERENCES symbols(fqn) ON DELETE CASCADE
);

-- Anti-pattern detection results
CREATE TABLE IF NOT EXISTS anti_patterns (
    id INTEGER PRIMARY KEY,
    rule_id TEXT NOT NULL,
    from_fqn TEXT NOT NULL,
    to_fqn TEXT,
    severity TEXT NOT NULL CHECK(severity IN ('error', 'warning', 'info')),
    message TEXT NOT NULL,
    detected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (from_fqn) REFERENCES symbols(fqn) ON DELETE CASCADE,
    FOREIGN KEY (to_fqn) REFERENCES symbols(fqn) ON DELETE SET NULL
);
"""

# Phase 3 (L1): Business layer tables
SCHEMA_L1 = """
-- Business summaries (text in SQLite, vectors in ChromaDB)
CREATE TABLE IF NOT EXISTS summaries (
    id INTEGER PRIMARY KEY,
    target_fqn TEXT NOT NULL UNIQUE,
    level TEXT NOT NULL CHECK(level IN ('method', 'class', 'package', 'module')),
    summary TEXT NOT NULL,
    vector_id TEXT,
    is_stale BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (target_fqn) REFERENCES symbols(fqn) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_summaries_target_fqn ON summaries(target_fqn);
CREATE INDEX IF NOT EXISTS idx_summaries_level ON summaries(level);
CREATE INDEX IF NOT EXISTS idx_summaries_stale ON summaries(is_stale);
CREATE INDEX IF NOT EXISTS idx_summaries_target_stale ON summaries(target_fqn, is_stale);
CREATE INDEX IF NOT EXISTS idx_summaries_vector_id ON summaries(vector_id);

-- Domain glossary
CREATE TABLE IF NOT EXISTS glossary (
    id INTEGER PRIMARY KEY,
    code_term TEXT NOT NULL UNIQUE,
    business_meaning TEXT NOT NULL,
    synonyms TEXT,
    source_fqn TEXT,
    vector_id TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (source_fqn) REFERENCES symbols(fqn) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_glossary_code_term ON glossary(code_term);
CREATE INDEX IF NOT EXISTS idx_glossary_source_fqn ON glossary(source_fqn);
CREATE INDEX IF NOT EXISTS idx_glossary_vector_id ON glossary(vector_id);

-- Business constraints
CREATE TABLE IF NOT EXISTS constraints (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    description TEXT NOT NULL,
    source_fqn TEXT,
    source_line INTEGER,
    constraint_type TEXT,
    vector_id TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (source_fqn) REFERENCES symbols(fqn) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_constraints_name ON constraints(name);
CREATE INDEX IF NOT EXISTS idx_constraints_source_fqn ON constraints(source_fqn);
CREATE INDEX IF NOT EXISTS idx_constraints_type ON constraints(constraint_type);
CREATE INDEX IF NOT EXISTS idx_constraints_vector_id ON constraints(vector_id);
"""

# Phase 4 (API): Job queue for async rebuild operations
SCHEMA_JOBS = """
-- Rebuild jobs for async processing
CREATE TABLE IF NOT EXISTS impact_jobs (
    id INTEGER PRIMARY KEY,
    job_id TEXT NOT NULL UNIQUE,
    mode TEXT NOT NULL CHECK(mode IN ('full', 'incremental')),
    status TEXT NOT NULL CHECK(status IN ('pending', 'running', 'complete', 'failed')),
    progress INTEGER DEFAULT 0,
    total_files INTEGER DEFAULT 0,
    processed_files INTEGER DEFAULT 0,
    target_paths TEXT,
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    error_message TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_impact_jobs_job_id ON impact_jobs(job_id);
CREATE INDEX IF NOT EXISTS idx_impact_jobs_status ON impact_jobs(status);
CREATE INDEX IF NOT EXISTS idx_impact_jobs_created ON impact_jobs(created_at);

-- Job metadata for queue management
CREATE TABLE IF NOT EXISTS job_metadata (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""

ALL_SCHEMAS = {
    "l3": SCHEMA_L3,
    "l2": SCHEMA_L2,
    "l1": SCHEMA_L1,
    "jobs": SCHEMA_JOBS,
}
