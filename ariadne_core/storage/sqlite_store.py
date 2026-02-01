"""SQLite storage for Ariadne knowledge graph."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

from ariadne_core.models.types import EdgeData, SymbolData
from ariadne_core.storage.schema import ALL_SCHEMAS


class SQLiteStore:
    """SQLite-based storage for the code knowledge graph.

    Handles symbol indexing, edge storage, and graph queries.
    """

    def __init__(self, db_path: str = "ariadne.db", init: bool = False):
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA foreign_keys=ON")

        if init:
            self._rebuild_schema()
        else:
            self._ensure_schema()

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
        """Insert or replace symbols. Returns count inserted."""
        if not symbols:
            return 0
        cursor = self.conn.cursor()
        rows = [s.to_row() for s in symbols]
        cursor.executemany(
            """INSERT OR REPLACE INTO symbols
               (fqn, kind, name, file_path, line_number, modifiers, signature, parent_fqn, annotations)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
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

    def close(self) -> None:
        """Close the database connection."""
        self.conn.close()

    def __enter__(self) -> SQLiteStore:
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()
