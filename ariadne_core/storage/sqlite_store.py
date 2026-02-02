"""SQLite storage for Ariadne knowledge graph."""

from __future__ import annotations

import logging
import os
import re
import sqlite3
from pathlib import Path
from threading import local
from typing import Any

logger = logging.getLogger(__name__)

from ariadne_core.models.types import (
    AntiPatternData,
    ConstraintEntry,
    EdgeData,
    EntryPointData,
    ExternalDependencyData,
    GlossaryEntry,
    SummaryData,
    SymbolData,
)
from ariadne_core.storage.schema import ALL_SCHEMAS


class SQLiteStore:
    """SQLite-based storage for the code knowledge graph.

    Handles symbol indexing, edge storage, and graph queries.
    """

    # Pre-compiled regex patterns (class constants for performance)
    _TEST_METHOD_PATTERN = re.compile(
        r'@Test\s+(?:public\s+)?(?:static\s+)?(?:\w+\s+)+(\w+)\s*\('
    )
    _TEST_METHOD_NAME_PATTERN = re.compile(
        r'(?:public|protected|private)?\s+(?:static\s+)?(?:\w+\s+)+test(\w+)\s*\(',
        re.MULTILINE
    )

    def __init__(self, db_path: str = "ariadne.db", init: bool = False):
        self.db_path = db_path
        self._local = local()

        if init:
            self._rebuild_schema()
        else:
            self._ensure_schema()

    @property
    def conn(self):
        """Get thread-local SQLite connection.

        Creates a new connection for each thread on first access.
        Connections are reused within the same thread.
        """
        if not hasattr(self._local, 'conn'):
            self._local.conn = sqlite3.connect(
                self.db_path,
                check_same_thread=False  # Allow access from any thread
            )
            self._local.conn.row_factory = sqlite3.Row
            self._local.conn.execute("PRAGMA journal_mode=WAL")
            self._local.conn.execute("PRAGMA foreign_keys=ON")
            self._local.conn.execute("PRAGMA busy_timeout=30000")  # 30s timeout
        return self._local.conn

    def _rebuild_schema(self) -> None:
        """Drop and recreate all tables."""
        cursor = self.conn.cursor()
        # Drop existing tables
        for table in [
            "constraints", "glossary", "summaries",
            "anti_patterns", "external_dependencies", "entry_points",
            "edges", "symbols", "index_metadata",
        ]:
            cursor.execute(f"DROP TABLE IF EXISTS {table}")
        self.conn.commit()
        self._ensure_schema()

    def _ensure_schema(self) -> None:
        """Create tables if they don't exist."""
        cursor = self.conn.cursor()
        for schema_sql in ALL_SCHEMAS.values():
            cursor.executescript(schema_sql)
        self.conn.commit()

    # ========================
    # Symbol CRUD
    # ========================

    def insert_symbols(self, symbols: list[SymbolData]) -> int:
        """Insert or update symbols. Returns count inserted."""
        if not symbols:
            return 0
        cursor = self.conn.cursor()
        rows = [s.to_row() for s in symbols]
        cursor.executemany(
            """INSERT INTO symbols
               (fqn, kind, name, file_path, line_number, modifiers, signature, parent_fqn, annotations)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(fqn) DO UPDATE SET
               kind = excluded.kind,
               name = excluded.name,
               file_path = excluded.file_path,
               line_number = excluded.line_number,
               modifiers = excluded.modifiers,
               signature = excluded.signature,
               parent_fqn = excluded.parent_fqn,
               annotations = excluded.annotations,
               updated_at = CURRENT_TIMESTAMP""",
            rows,
        )
        self.conn.commit()
        return len(rows)

    def get_symbol(self, fqn: str) -> dict[str, Any] | None:
        """Get a symbol by FQN."""
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM symbols WHERE fqn = ?", (fqn,))
        row = cursor.fetchone()
        return dict(row) if row else None

    def get_symbols_by_kind(self, kind: str) -> list[dict[str, Any]]:
        """Get all symbols of a given kind."""
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM symbols WHERE kind = ?", (kind,))
        return [dict(row) for row in cursor.fetchall()]

    def get_symbols_by_parent(self, parent_fqn: str) -> list[dict[str, Any]]:
        """Get all symbols with a given parent FQN."""
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM symbols WHERE parent_fqn = ?", (parent_fqn,))
        return [dict(row) for row in cursor.fetchall()]

    def get_symbol_count(self) -> int:
        """Get total symbol count."""
        cursor = self.conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM symbols")
        return cursor.fetchone()[0]

    def search_symbols(self, name_pattern: str, kind: str | None = None) -> list[dict[str, Any]]:
        """Search symbols by name pattern (LIKE query)."""
        cursor = self.conn.cursor()
        if kind:
            cursor.execute(
                "SELECT * FROM symbols WHERE name LIKE ? AND kind = ? LIMIT 100",
                (f"%{name_pattern}%", kind),
            )
        else:
            cursor.execute(
                "SELECT * FROM symbols WHERE name LIKE ? LIMIT 100",
                (f"%{name_pattern}%",),
            )
        return [dict(row) for row in cursor.fetchall()]

    # ========================
    # Edge CRUD
    # ========================

    def insert_edges(self, edges: list[EdgeData]) -> int:
        """Insert edges. Returns count inserted."""
        if not edges:
            return 0
        cursor = self.conn.cursor()
        rows = [e.to_row() for e in edges]
        cursor.executemany(
            "INSERT INTO edges (from_fqn, to_fqn, relation, metadata) VALUES (?, ?, ?, ?)",
            rows,
        )
        self.conn.commit()
        return len(rows)

    def get_edges_from(self, fqn: str, relation: str | None = None) -> list[dict[str, Any]]:
        """Get outgoing edges from a symbol."""
        cursor = self.conn.cursor()
        if relation:
            cursor.execute(
                "SELECT * FROM edges WHERE from_fqn = ? AND relation = ?",
                (fqn, relation),
            )
        else:
            cursor.execute("SELECT * FROM edges WHERE from_fqn = ?", (fqn,))
        return [dict(row) for row in cursor.fetchall()]

    def get_edges_to(self, fqn: str, relation: str | None = None) -> list[dict[str, Any]]:
        """Get incoming edges to a symbol."""
        cursor = self.conn.cursor()
        if relation:
            cursor.execute(
                "SELECT * FROM edges WHERE to_fqn = ? AND relation = ?",
                (fqn, relation),
            )
        else:
            cursor.execute("SELECT * FROM edges WHERE to_fqn = ?", (fqn,))
        return [dict(row) for row in cursor.fetchall()]

    def get_edge_count(self) -> int:
        """Get total edge count."""
        cursor = self.conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM edges")
        return cursor.fetchone()[0]

    def get_related_symbols(
        self,
        fqn: str,
        relation: str | None = None,
        direction: str = "both",
    ) -> list[dict[str, Any]]:
        """Get related symbols by edge relation.

        Args:
            fqn: The symbol FQN to find relations for
            relation: Optional edge relation filter (e.g., 'calls', 'inherits')
            direction: Direction of relations ('incoming', 'outgoing', or 'both')

        Returns:
            List of related symbol dicts

        Raises:
            ValueError: If direction is not one of 'incoming', 'outgoing', 'both'
        """
        if direction not in ("incoming", "outgoing", "both"):
            raise ValueError(f"Invalid direction: {direction}")

        cursor = self.conn.cursor()
        results = []

        if direction in ("outgoing", "both"):
            # Get symbols this FQN points to
            if relation:
                cursor.execute(
                    "SELECT s.* FROM symbols s "
                    "JOIN edges e ON s.fqn = e.to_fqn "
                    "WHERE e.from_fqn = ? AND e.relation = ?",
                    (fqn, relation),
                )
            else:
                cursor.execute(
                    "SELECT s.* FROM symbols s "
                    "JOIN edges e ON s.fqn = e.to_fqn "
                    "WHERE e.from_fqn = ?",
                    (fqn,),
                )
            results.extend([dict(row) for row in cursor.fetchall()])

        if direction in ("incoming", "both"):
            # Get symbols that point to this FQN
            if relation:
                cursor.execute(
                    "SELECT s.* FROM symbols s "
                    "JOIN edges e ON s.fqn = e.from_fqn "
                    "WHERE e.to_fqn = ? AND e.relation = ?",
                    (fqn, relation),
                )
            else:
                cursor.execute(
                    "SELECT s.* FROM symbols s "
                    "JOIN edges e ON s.fqn = e.from_fqn "
                    "WHERE e.to_fqn = ?",
                    (fqn,),
                )
            results.extend([dict(row) for row in cursor.fetchall()])

        return results

    # ========================
    # Graph traversal
    # ========================

    def get_call_chain(self, start_fqn: str, max_depth: int = 10) -> list[dict[str, Any]]:
        """Traverse call chain from start_fqn using recursive CTE.

        Returns list of (depth, from_fqn, to_fqn, relation) rows.
        """
        cursor = self.conn.cursor()
        cursor.execute(
            """
            WITH RECURSIVE call_chain(depth, from_fqn, to_fqn, relation) AS (
                SELECT 0, from_fqn, to_fqn, relation
                FROM edges
                WHERE from_fqn = ? AND relation = 'calls'

                UNION ALL

                SELECT cc.depth + 1, e.from_fqn, e.to_fqn, e.relation
                FROM edges e
                JOIN call_chain cc ON e.from_fqn = cc.to_fqn
                WHERE cc.depth < ? AND e.relation = 'calls'
            )
            SELECT DISTINCT * FROM call_chain ORDER BY depth
            """,
            (start_fqn, max_depth),
        )
        return [dict(row) for row in cursor.fetchall()]

    def get_reverse_callers(self, target_fqn: str, max_depth: int = 10) -> list[dict[str, Any]]:
        """Find all callers of target_fqn (reverse traversal)."""
        cursor = self.conn.cursor()
        cursor.execute(
            """
            WITH RECURSIVE callers(depth, from_fqn, to_fqn, relation) AS (
                SELECT 0, from_fqn, to_fqn, relation
                FROM edges
                WHERE to_fqn = ? AND relation = 'calls'

                UNION ALL

                SELECT c.depth + 1, e.from_fqn, e.to_fqn, e.relation
                FROM edges e
                JOIN callers c ON e.to_fqn = c.from_fqn
                WHERE c.depth < ? AND e.relation = 'calls'
            )
            SELECT DISTINCT * FROM callers ORDER BY depth
            """,
            (target_fqn, max_depth),
        )
        return [dict(row) for row in cursor.fetchall()]

    # ========================
    # Metadata
    # ========================

    def get_metadata(self, key: str) -> str | None:
        """Get metadata value by key."""
        cursor = self.conn.cursor()
        cursor.execute("SELECT value FROM index_metadata WHERE key = ?", (key,))
        row = cursor.fetchone()
        return row[0] if row else None

    def set_metadata(self, key: str, value: str) -> None:
        """Set metadata key-value pair."""
        cursor = self.conn.cursor()
        cursor.execute(
            "INSERT OR REPLACE INTO index_metadata (key, value) VALUES (?, ?)",
            (key, value),
        )
        self.conn.commit()

    # ========================
    # Cleanup
    # ========================

    def clean_all(self) -> dict[str, int]:
        """Delete all data from all tables. Returns counts."""
        cursor = self.conn.cursor()
        counts = {}
        for table in ["edges", "symbols", "index_metadata"]:
            cursor.execute(f"SELECT COUNT(*) FROM {table}")
            counts[table] = cursor.fetchone()[0]
            cursor.execute(f"DELETE FROM {table}")
        self.conn.commit()
        return counts

    def clean_by_file(self, file_path: str) -> int:
        """Delete symbols and edges for a given file path. Returns symbols deleted."""
        cursor = self.conn.cursor()
        # Get FQNs for the file
        cursor.execute("SELECT fqn FROM symbols WHERE file_path = ?", (file_path,))
        fqns = [row[0] for row in cursor.fetchall()]
        if not fqns:
            return 0
        placeholders = ",".join("?" * len(fqns))
        cursor.execute(
            f"DELETE FROM edges WHERE from_fqn IN ({placeholders}) OR to_fqn IN ({placeholders})",
            fqns + fqns,
        )
        cursor.execute(f"DELETE FROM symbols WHERE fqn IN ({placeholders})", fqns)
        self.conn.commit()
        return len(fqns)

    # ========================
    # L2: Entry Points
    # ========================

    def insert_entry_points(self, entries: list[EntryPointData]) -> int:
        """Insert or update entry points. Returns count inserted."""
        if not entries:
            return 0
        cursor = self.conn.cursor()
        cursor.executemany(
            """INSERT INTO entry_points
               (symbol_fqn, entry_type, http_method, http_path, cron_expression, mq_queue)
               VALUES (?, ?, ?, ?, ?, ?)
               ON CONFLICT(symbol_fqn) DO UPDATE SET
               entry_type = excluded.entry_type,
               http_method = excluded.http_method,
               http_path = excluded.http_path,
               cron_expression = excluded.cron_expression,
               mq_queue = excluded.mq_queue""",
            [e.to_row() for e in entries],
        )
        self.conn.commit()
        return len(entries)

    def get_entry_points(self, entry_type: str | None = None) -> list[dict[str, Any]]:
        """Get entry points, optionally filtered by type."""
        cursor = self.conn.cursor()
        if entry_type:
            cursor.execute("SELECT * FROM entry_points WHERE entry_type = ?", (entry_type,))
        else:
            cursor.execute("SELECT * FROM entry_points")
        return [dict(row) for row in cursor.fetchall()]

    def get_entry_point_count(self) -> int:
        """Get total entry point count."""
        cursor = self.conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM entry_points")
        return cursor.fetchone()[0]

    # ========================
    # L2: External Dependencies
    # ========================

    def insert_external_dependencies(self, deps: list[ExternalDependencyData]) -> int:
        """Insert external dependencies. Returns count inserted."""
        if not deps:
            return 0
        cursor = self.conn.cursor()
        cursor.executemany(
            """INSERT INTO external_dependencies
               (caller_fqn, dependency_type, target, strength)
               VALUES (?, ?, ?, ?)""",
            [d.to_row() for d in deps],
        )
        self.conn.commit()
        return len(deps)

    def get_external_dependencies(
        self,
        caller_fqn: str | None = None,
        dependency_type: str | None = None,
    ) -> list[dict[str, Any]]:
        """Get external dependencies with optional filters."""
        cursor = self.conn.cursor()
        if caller_fqn and dependency_type:
            cursor.execute(
                "SELECT * FROM external_dependencies WHERE caller_fqn = ? AND dependency_type = ?",
                (caller_fqn, dependency_type),
            )
        elif caller_fqn:
            cursor.execute(
                "SELECT * FROM external_dependencies WHERE caller_fqn = ?",
                (caller_fqn,),
            )
        elif dependency_type:
            cursor.execute(
                "SELECT * FROM external_dependencies WHERE dependency_type = ?",
                (dependency_type,),
            )
        else:
            cursor.execute("SELECT * FROM external_dependencies")
        return [dict(row) for row in cursor.fetchall()]

    def get_external_dependency_count(self) -> int:
        """Get total external dependency count."""
        cursor = self.conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM external_dependencies")
        return cursor.fetchone()[0]

    # ========================
    # L2: Anti-Patterns
    # ========================

    def insert_anti_patterns(self, patterns: list[AntiPatternData]) -> int:
        """Insert anti-pattern detection results. Returns count inserted."""
        if not patterns:
            return 0
        cursor = self.conn.cursor()
        cursor.executemany(
            """INSERT INTO anti_patterns
               (rule_id, from_fqn, to_fqn, severity, message)
               VALUES (?, ?, ?, ?, ?)""",
            [p.to_row() for p in patterns],
        )
        self.conn.commit()
        return len(patterns)

    def get_anti_patterns(
        self,
        rule_id: str | None = None,
        severity: str | None = None,
    ) -> list[dict[str, Any]]:
        """Get anti-patterns with optional filters."""
        cursor = self.conn.cursor()
        if rule_id and severity:
            cursor.execute(
                "SELECT * FROM anti_patterns WHERE rule_id = ? AND severity = ?",
                (rule_id, severity),
            )
        elif rule_id:
            cursor.execute("SELECT * FROM anti_patterns WHERE rule_id = ?", (rule_id,))
        elif severity:
            cursor.execute("SELECT * FROM anti_patterns WHERE severity = ?", (severity,))
        else:
            cursor.execute("SELECT * FROM anti_patterns")
        return [dict(row) for row in cursor.fetchall()]

    def clear_anti_patterns(self) -> int:
        """Clear all anti-patterns. Returns count deleted."""
        cursor = self.conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM anti_patterns")
        count = cursor.fetchone()[0]
        cursor.execute("DELETE FROM anti_patterns")
        self.conn.commit()
        return count

    def close(self) -> None:
        """Close the database connection."""
        self.conn.close()

    def __enter__(self) -> SQLiteStore:
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()

    # ========================
    # L1: Summaries
    # ========================

    def create_summary(self, summary: SummaryData) -> None:
        """Create a new summary record.

        Args:
            summary: SummaryData to create
        """
        cursor = self.conn.cursor()
        cursor.execute(
            """INSERT INTO summaries (target_fqn, level, summary, vector_id, is_stale, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(target_fqn) DO UPDATE SET
               summary = excluded.summary,
               vector_id = excluded.vector_id,
               is_stale = excluded.is_stale,
               updated_at = excluded.updated_at""",
            summary.to_row(),
        )
        self.conn.commit()

    def get_summary(self, target_fqn: str, level: str | None = None) -> dict[str, Any] | None:
        """Get a summary by target FQN and optional level.

        Args:
            target_fqn: Target symbol FQN
            level: Optional summary level filter

        Returns:
            Summary dict or None if not found
        """
        cursor = self.conn.cursor()
        if level:
            cursor.execute(
                "SELECT * FROM summaries WHERE target_fqn = ? AND level = ?",
                (target_fqn, level),
            )
        else:
            cursor.execute("SELECT * FROM summaries WHERE target_fqn = ?", (target_fqn,))
        row = cursor.fetchone()
        return dict(row) if row else None

    def mark_summary_stale(self, target_fqn: str) -> None:
        """Mark a summary as stale (needs regeneration).

        Args:
            target_fqn: Target symbol FQN to mark stale
        """
        cursor = self.conn.cursor()
        cursor.execute(
            "UPDATE summaries SET is_stale = 1 WHERE target_fqn = ?",
            (target_fqn,),
        )
        self.conn.commit()

    def mark_summaries_stale(self, target_fqns: list[str]) -> int:
        """Mark multiple summaries as stale in batch.

        Uses a single UPDATE with IN clause for efficiency and correctness.

        Args:
            target_fqns: List of target symbol FQNs to mark stale

        Returns:
            Number of summaries marked stale
        """
        if not target_fqns:
            return 0

        cursor = self.conn.cursor()
        placeholders = ",".join("?" * len(target_fqns))
        cursor.execute(
            f"UPDATE summaries SET is_stale = 1, updated_at = CURRENT_TIMESTAMP "
            f"WHERE target_fqn IN ({placeholders})",
            target_fqns,
        )
        self.conn.commit()
        return cursor.rowcount

    def get_stale_summaries(self, limit: int = 1000) -> list[dict[str, Any]]:
        """Get summaries marked as stale.

        Args:
            limit: Maximum number of summaries to return

        Returns:
            List of stale summary dicts
        """
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT * FROM summaries WHERE is_stale = 1 LIMIT ?",
            (limit,),
        )
        return [dict(row) for row in cursor.fetchall()]

    def update_summary_vector_id(self, target_fqn: str, vector_id: str) -> None:
        """Update the vector ID for a summary.

        Args:
            target_fqn: Target symbol FQN
            vector_id: Vector store ID
        """
        cursor = self.conn.cursor()
        cursor.execute(
            "UPDATE summaries SET vector_id = ?, is_stale = 0 WHERE target_fqn = ?",
            (vector_id, target_fqn),
        )
        self.conn.commit()

    def get_summaries_by_level(self, level: str) -> list[dict[str, Any]]:
        """Get all summaries of a given level.

        Args:
            level: Summary level (method, class, package, module)

        Returns:
            List of summary dicts
        """
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM summaries WHERE level = ?", (level,))
        return [dict(row) for row in cursor.fetchall()]

    def get_summary_count(self) -> int:
        """Get total summary count."""
        cursor = self.conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM summaries")
        return cursor.fetchone()[0]

    # ========================
    # L1: Glossary
    # ========================

    def create_glossary_entry(self, entry: GlossaryEntry) -> None:
        """Create a new glossary entry.

        Args:
            entry: GlossaryEntry to create
        """
        cursor = self.conn.cursor()
        cursor.execute(
            """INSERT INTO glossary (code_term, business_meaning, synonyms, source_fqn, vector_id, created_at)
               VALUES (?, ?, ?, ?, ?, ?)
               ON CONFLICT(code_term) DO UPDATE SET
               business_meaning = excluded.business_meaning,
               synonyms = excluded.synonyms,
               source_fqn = excluded.source_fqn,
               vector_id = excluded.vector_id""",
            entry.to_row(),
        )
        self.conn.commit()

    def get_glossary_entry(self, code_term: str) -> dict[str, Any] | None:
        """Get a glossary entry by code term.

        Args:
            code_term: Code term to look up

        Returns:
            Glossary entry dict or None if not found
        """
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM glossary WHERE code_term = ?", (code_term,))
        row = cursor.fetchone()
        return dict(row) if row else None

    def search_glossary_terms(self, pattern: str) -> list[dict[str, Any]]:
        """Search glossary terms by pattern.

        Args:
            pattern: Search pattern for code_term or business_meaning

        Returns:
            List of matching glossary entries
        """
        cursor = self.conn.cursor()
        cursor.execute(
            """SELECT * FROM glossary
               WHERE code_term LIKE ? OR business_meaning LIKE ?
               LIMIT 100""",
            (f"%{pattern}%", f"%{pattern}%"),
        )
        return [dict(row) for row in cursor.fetchall()]

    def get_glossary_by_source(self, source_fqn: str) -> list[dict[str, Any]]:
        """Get all glossary entries from a source FQN.

        Args:
            source_fqn: Source symbol FQN

        Returns:
            List of glossary entries
        """
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM glossary WHERE source_fqn = ?", (source_fqn,))
        return [dict(row) for row in cursor.fetchall()]

    def update_glossary_vector_id(self, code_term: str, vector_id: str) -> None:
        """Update the vector ID for a glossary entry.

        Args:
            code_term: Code term
            vector_id: Vector store ID
        """
        cursor = self.conn.cursor()
        cursor.execute(
            "UPDATE glossary SET vector_id = ? WHERE code_term = ?",
            (vector_id, code_term),
        )
        self.conn.commit()

    def get_glossary_count(self) -> int:
        """Get total glossary entry count."""
        cursor = self.conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM glossary")
        return cursor.fetchone()[0]

    # ========================
    # L1: Constraints
    # ========================

    def create_constraint(self, constraint: ConstraintEntry) -> None:
        """Create a new constraint entry.

        Args:
            constraint: ConstraintEntry to create
        """
        cursor = self.conn.cursor()
        cursor.execute(
            """INSERT INTO constraints (name, description, source_fqn, source_line, constraint_type, vector_id, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(name) DO UPDATE SET
               description = excluded.description,
               source_fqn = excluded.source_fqn,
               source_line = excluded.source_line,
               constraint_type = excluded.constraint_type,
               vector_id = excluded.vector_id""",
            constraint.to_row(),
        )
        self.conn.commit()

    def get_constraint(self, name: str) -> dict[str, Any] | None:
        """Get a constraint by name.

        Args:
            name: Constraint name

        Returns:
            Constraint dict or None if not found
        """
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM constraints WHERE name = ?", (name,))
        row = cursor.fetchone()
        return dict(row) if row else None

    def get_constraints_by_source(self, source_fqn: str) -> list[dict[str, Any]]:
        """Get all constraints from a source FQN.

        Args:
            source_fqn: Source symbol FQN

        Returns:
            List of constraint dicts
        """
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM constraints WHERE source_fqn = ?", (source_fqn,))
        return [dict(row) for row in cursor.fetchall()]

    def get_constraints_by_type(self, constraint_type: str) -> list[dict[str, Any]]:
        """Get all constraints of a given type.

        Args:
            constraint_type: Constraint type (validation, business_rule, invariant)

        Returns:
            List of constraint dicts
        """
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM constraints WHERE constraint_type = ?", (constraint_type,))
        return [dict(row) for row in cursor.fetchall()]

    def search_constraints(self, pattern: str) -> list[dict[str, Any]]:
        """Search constraints by pattern in name or description.

        Args:
            pattern: Search pattern

        Returns:
            List of matching constraint dicts
        """
        cursor = self.conn.cursor()
        cursor.execute(
            """SELECT * FROM constraints
               WHERE name LIKE ? OR description LIKE ?
               LIMIT 100""",
            (f"%{pattern}%", f"%{pattern}%"),
        )
        return [dict(row) for row in cursor.fetchall()]

    def update_constraint_vector_id(self, name: str, vector_id: str) -> None:
        """Update the vector ID for a constraint.

        Args:
            name: Constraint name
            vector_id: Vector store ID
        """
        cursor = self.conn.cursor()
        cursor.execute(
            "UPDATE constraints SET vector_id = ? WHERE name = ?",
            (vector_id, name),
        )
        self.conn.commit()

    def get_constraint_count(self) -> int:
        """Get total constraint count."""
        cursor = self.conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM constraints")
        return cursor.fetchone()[0]

    # ========================
    # Atomic Vector Operations
    # ========================

    def create_summary_with_vector(
        self,
        summary: SummaryData,
        embedding: list[float] | None = None,
        vector_store: ChromaVectorStore | None = None,
    ) -> str | None:
        """Create summary with optional vector storage in single transaction.

        This ensures data consistency between SQLite and ChromaDB by:
        1. Creating SQLite record first
        2. Adding to ChromaDB only after SQLite succeeds
        3. Updating SQLite with vector_id only after ChromaDB succeeds

        Args:
            summary: SummaryData to create
            embedding: Optional embedding vector for semantic search
            vector_store: Optional ChromaVectorStore instance

        Returns:
            Vector ID if embedding was provided and stored, None otherwise

        Raises:
            Exception: If SQLite or ChromaDB operation fails
        """
        cursor = self.conn.cursor()

        try:
            with self.conn:
                # 1. Insert SQLite record without vector_id
                cursor.execute(
                    """INSERT INTO summaries (target_fqn, level, summary, is_stale, created_at, updated_at)
                       VALUES (?, ?, ?, ?, ?, ?)
                       RETURNING id
                    """,
                    (summary.target_fqn, summary.level.value, summary.summary, False, "datetime('now')", "datetime('now')"),
                )
                summary_id = cursor.fetchone()[0]

                vector_id = None

                # 2. Add to ChromaDB if embedding provided
                # This must succeed or entire transaction rolls back
                if embedding is not None and vector_store is not None:
                    vector_store.add_summary(
                        summary_id=str(summary_id),
                        text=summary.summary,
                        embedding=embedding,
                        metadata={"fqn": summary.target_fqn, "level": summary.level.value},
                    )
                    # 3. Update vector_id only after ChromaDB success
                    cursor.execute(
                        "UPDATE summaries SET vector_id = ? WHERE id = ?",
                        (str(summary_id), summary_id),
                    )
                    vector_id = str(summary_id)

                return vector_id

        except Exception as e:
            logger.error(f"Failed to create summary with vector: {e}")
            # If ChromaDB failed, the entire transaction (including SQLite insert) is rolled back
            raise

    def delete_summary_cascade(
        self,
        target_fqn: str,
        vector_store: ChromaVectorStore | None = None,
    ) -> bool:
        """Delete summary from both SQLite and ChromaDB atomically.

        Args:
            target_fqn: Target symbol FQN
            vector_store: Optional ChromaVectorStore instance

        Returns:
            True if deleted, False if not found
        """
        cursor = self.conn.cursor()

        try:
            with self.conn:
                # 1. Get vector_id from SQLite
                cursor.execute("SELECT vector_id FROM summaries WHERE target_fqn = ?", (target_fqn,))
                row = cursor.fetchone()
                if not row:
                    return False

                vector_id = row[0]

                # 2. Delete from ChromaDB before SQLite (best effort)
                if vector_id and vector_store is not None:
                    try:
                        vector_store.delete_summaries([vector_id])
                    except Exception as e:
                        logger.warning(f"Failed to delete from ChromaDB (continuing): {e}")

                # 3. Delete from SQLite
                cursor.execute("DELETE FROM summaries WHERE target_fqn = ?", (target_fqn,))
                return True

        except Exception as e:
            logger.error(f"Failed to delete summary: {e}")
            raise

    def mark_summaries_stale_by_file(self, file_path: str) -> int:
        """Mark summaries as stale when source file changes.

        Also marks parent-level summaries (class/package) as stale.

        Args:
            file_path: Path to the modified source file

        Returns:
            Number of summaries marked stale
        """
        cursor = self.conn.cursor()
        try:
            with self.conn:
                # Mark method-level summaries stale
                cursor.execute(
                    """UPDATE summaries SET is_stale = 1, updated_at = datetime('now')
                       WHERE target_fqn IN (
                           SELECT fqn FROM symbols WHERE file_path = ?
                       )""",
                    (file_path,),
                )
                method_count = cursor.rowcount

                # Mark parent summaries stale as well
                cursor.execute(
                    """UPDATE summaries SET is_stale = 1, updated_at = datetime('now')
                       WHERE target_fqn IN (
                           SELECT DISTINCT s.parent_fqn FROM symbols s
                           WHERE s.file_path = ?
                           AND s.parent_fqn IS NOT NULL
                       )""",
                    (file_path,),
                )

                return method_count + cursor.rowcount

        except Exception as e:
            logger.error(f"Failed to mark summaries stale: {e}")
            raise

    # ========================
    # Test Mapping and Coverage
    # ========================

    def get_test_mapping(self, fqn: str) -> dict[str, Any]:
        """Get test file mappings for a source symbol.

        Uses Maven Surefire test naming conventions to find test files:
        - Test*.java (e.g., TestUserService.java)
        - *Test.java (e.g., UserServiceTest.java) - RECOMMENDED
        - *Tests.java (e.g., UserServiceTests.java)
        - *IT.java (e.g., UserServiceIT.java - integration tests)

        Args:
            fqn: Source symbol FQN

        Returns:
            Dictionary with source_fqn, source_file, and test_mappings list
        """
        # Get source symbol
        symbol = self.get_symbol(fqn)
        if not symbol or not symbol.get("file_path"):
            return {
                "source_fqn": fqn,
                "source_file": None,
                "test_mappings": [],
            }

        source_file = symbol["file_path"]
        source_path = Path(source_file)

        # Generate test file paths based on naming conventions
        test_mappings = []
        test_paths = self._generate_test_paths(source_path)

        for test_path_str in test_paths:
            test_path = Path(test_path_str)
            test_exists = test_path.exists()

            # Extract test methods if test file exists
            test_methods = []
            if test_exists:
                test_methods = self._extract_test_methods(test_path)

            # Get test file name as pattern
            test_file_name = test_path.name

            test_mappings.append({
                "test_file": str(test_path),
                "test_exists": test_exists,
                "test_pattern": test_file_name,
                "test_methods": test_methods,
            })

        return {
            "source_fqn": fqn,
            "source_file": source_file,
            "test_mappings": test_mappings,
        }

    def _generate_test_paths(self, source_path: Path) -> list[str]:
        """Generate possible test file paths from source path.

        Based on Maven Surefire conventions:
        - src/main/java/.../Foo.java -> src/test/java/.../FooTest.java
        - src/main/java/.../Foo.java -> src/test/java/.../FooTests.java
        - src/main/java/.../Foo.java -> src/test/java/.../FooIT.java
        """
        path_str = str(source_path)

        # Replace main/java with test/java
        if "/main/java/" in path_str:
            test_base = path_str.replace("/main/java/", "/test/java/")
        elif "\\main\\java\\" in path_str:
            test_base = path_str.replace("\\main\\java\\", "\\test\\java\\")
        else:
            # No standard Maven/Gradle structure
            return []

        # Remove .java extension
        if test_base.endswith(".java"):
            test_base = test_base[:-5]

        # Generate test file names based on conventions
        test_paths = []
        base_class_name = Path(test_base).stem

        for suffix in ["Test", "Tests", "IT"]:
            test_dir = Path(test_base).parent
            test_path = test_dir / f"{base_class_name}{suffix}.java"
            test_paths.append(str(test_path))

        return test_paths

    def _extract_test_methods(self, test_file: Path) -> list[str]:
        """Extract test method names from a test file.

        Looks for methods annotated with @Test or starting with "test".

        Args:
            test_file: Path to the test file

        Returns:
            List of test method names
        """
        try:
            content = test_file.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            return []

        test_methods = []
        # Use cached class regex patterns (P2 #034 fix)
        for match in self._TEST_METHOD_PATTERN.finditer(content):
            test_methods.append(match.group(1))

        # Also match methods starting with "test" (without @Test)
        for match in self._TEST_METHOD_NAME_PATTERN.finditer(content):
            method_name = "test" + match.group(1)
            if method_name not in test_methods:
                test_methods.append(method_name)

        return test_methods

    def analyze_coverage(self, fqn: str) -> dict[str, Any]:
        """Analyze test coverage for a target symbol.

        Uses the edges table to find all callers and determines which
        callers have test coverage.

        Args:
            fqn: Target symbol FQN

        Returns:
            Dictionary with statistics, callers list, and warnings
        """
        cursor = self.conn.cursor()

        # Get all callers (incoming edges) - single query
        cursor.execute(
            """SELECT DISTINCT e.from_fqn, s.kind, s.name, s.file_path
               FROM edges e
               JOIN symbols s ON e.from_fqn = s.fqn
               WHERE e.to_fqn = ?""",
            (fqn,)
        )
        callers = [dict(row) for row in cursor.fetchall()]

        total_callers = len(callers)
        tested_callers = 0
        caller_info_list = []
        warnings = []

        for caller in callers:
            caller_fqn = caller["from_fqn"]
            caller_file = caller.get("file_path", "")
            caller_name = caller.get("name", caller_fqn)

            # Determine if caller is a test file (uses file_path from query)
            is_test_file = self._is_test_file(caller_file)

            # P2 #033 fix: Simplified coverage check - caller is covered if it's a test file
            # No need for additional get_test_mapping() call in the loop
            is_covered = is_test_file

            if is_test_file:
                tested_callers += 1
            else:
                # Generate warning for uncovered non-test caller
                # P2 #039 fix: Use English instead of Chinese
                warnings.append({
                    "type": "untested_caller",
                    "severity": "medium",
                    "message": f"{caller_name} calls {fqn} but has no test coverage",
                    "caller_fqn": caller_fqn,
                })

            caller_info_list.append({
                "caller_fqn": caller_fqn,
                "caller_kind": caller.get("kind"),
                "caller_name": caller_name,
                "caller_file": caller_file,
                "is_test_file": is_test_file,
                "is_covered": is_covered,
            })

        # Calculate coverage percentage
        coverage_percentage = 0.0
        if total_callers > 0:
            coverage_percentage = (tested_callers / total_callers) * 100.0

        return {
            "target_fqn": fqn,
            "statistics": {
                "total_callers": total_callers,
                "tested_callers": tested_callers,
                "coverage_percentage": round(coverage_percentage, 2),
            },
            "callers": caller_info_list,
            "warnings": warnings,
        }

    def _is_test_file(self, file_path: str) -> bool:
        """Determine if a file is a test file based on path patterns.

        Checks for:
        - Path contains /test/ or \\test\\
        - Filename matches test patterns (Test*.java, *Test.java, *Tests.java, *IT.java)

        Args:
            file_path: File path to check

        Returns:
            True if the file appears to be a test file
        """
        if not file_path:
            return False

        path_lower = file_path.lower()

        # Check if path contains test directory
        if "/test/" in path_lower or "\\test\\" in path_lower:
            return True

        # Check filename patterns
        filename = Path(file_path).name
        if (
            filename.startswith("Test") or
            filename.endswith("Test.java") or
            filename.endswith("Tests.java") or
            filename.endswith("IT.java")
        ):
            return True

        return False
