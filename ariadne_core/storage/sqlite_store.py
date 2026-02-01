"""SQLite storage for Ariadne knowledge graph."""

from __future__ import annotations

import json
import logging
import os
import sqlite3
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
from ariadne_core.storage import migrations  # type: ignore


class SQLiteStore:
    """SQLite-based storage for the code knowledge graph.

    Handles symbol indexing, edge storage, and graph queries.
    """

    def __init__(self, db_path: str = "ariadne.db", init: bool = False):
        self.db_path = db_path
        self._local = local()

        if init:
            self._rebuild_schema()
        else:
            self._ensure_schema()

        # Check and recover from incomplete swap (if crashed during rebuild)
        self._check_and_recover_swap_incomplete()

    def _check_and_recover_swap_incomplete(self) -> bool:
        """Check if previous shadow rebuild swap was incomplete and recover.

        This should be called on initialization to ensure the database is in a
        valid state after a potential crash during shadow rebuild.

        Returns:
            True if recovery was performed, False otherwise
        """
        backup_suffix = "_backup"
        backup_path = self.db_path + backup_suffix
        temp_path = self.db_path + ".tmp_swap"

        # Check for incomplete swap indicators
        current_exists = os.path.exists(self.db_path)
        backup_exists = os.path.exists(backup_path)
        temp_exists = os.path.exists(temp_path)

        # Case 1: current doesn't exist but backup does (main recovery scenario)
        if not current_exists and backup_exists:
            logger.warning(
                f"Detected incomplete swap: current missing, backup exists. Recovering.",
                extra={"event": "swap_recovery", "backup": backup_path}
            )
            try:
                os.replace(backup_path, self.db_path)
                logger.info("Recovery from backup completed")
                return True
            except OSError as e:
                logger.error(f"Failed to recover from backup: {e}")
                return False

        # Case 2: temp exists but current doesn't (race window scenario)
        if not current_exists and temp_exists:
            logger.warning(
                f"Detected incomplete swap: current missing, temp exists. Recovering.",
                extra={"event": "swap_recovery", "temp": temp_path}
            )
            try:
                os.replace(temp_path, self.db_path)
                logger.info("Recovery from temp completed")
                return True
            except OSError as e:
                logger.error(f"Failed to recover from temp: {e}")
                return False

        # Case 3: temp still exists (previous swap failed, need cleanup)
        if temp_exists:
            logger.info(f"Cleaning up leftover temp file from previous swap: {temp_path}")
            try:
                os.remove(temp_path)
            except OSError as e:
                logger.warning(f"Failed to remove temp file: {e}")

        return False

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
        """Create tables if they don't exist and run migrations."""
        cursor = self.conn.cursor()
        for schema_sql in ALL_SCHEMAS.values():
            cursor.executescript(schema_sql)
        self.conn.commit()

        # Run pending migrations
        self._run_migrations()

    def _run_migrations(self) -> None:
        """Run pending database migrations."""
        self._run_migrations_impl(dry_run=False)

    def preview_migrations(self) -> dict[str, Any]:
        """Preview pending migrations without applying them.

        Returns:
            Dictionary with migration results for each pending migration
        """
        return self._run_migrations_impl(dry_run=True)

    def _run_migrations_impl(self, dry_run: bool = False) -> dict[str, Any]:
        """Run or preview pending database migrations.

        Args:
            dry_run: If True, only report what would happen without applying changes

        Returns:
            Dictionary with results from each migration (only when dry_run=True)
        """
        # Get applied migrations
        cursor = self.conn.cursor()

        # Create migrations table if it doesn't exist
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS _migrations (
                version TEXT PRIMARY KEY,
                applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Get applied migrations
        cursor.execute("SELECT version FROM _migrations ORDER BY version")
        applied = {row[0] for row in cursor.fetchall()}

        results = {}

        # Run pending migrations
        for migration in migrations.ALL_MIGRATIONS:
            if migration["version"] not in applied:
                logger.info(
                    f"{'[DRY-RUN] ' if dry_run else ''}Running migration {migration['version']}: {migration['name']}",
                    extra={
                        "event": "migration_start",
                        "version": migration["version"],
                        "migration_name": migration["name"],
                        "dry_run": dry_run,
                    }
                )
                try:
                    # Call upgrade with dry_run parameter
                    migration_result = migration["upgrade"](self.conn, dry_run=dry_run)

                    # Record migration (only if not dry_run)
                    if not dry_run:
                        cursor.execute(
                            "INSERT INTO _migrations (version) VALUES (?)",
                            (migration["version"],)
                        )
                        self.conn.commit()
                        logger.info(
                            f"Migration {migration['version']} completed",
                            extra={
                                "event": "migration_complete",
                                "version": migration["version"],
                            }
                        )
                    else:
                        # In dry-run mode, return the results
                        results[migration["version"]] = migration_result

                except Exception as e:
                    if not dry_run:
                        self.conn.rollback()
                        logger.error(
                            f"Migration {migration['version']} failed: {e}",
                            extra={
                                "event": "migration_failed",
                                "version": migration["version"],
                                "error": str(e),
                            }
                        )
                        raise
                    else:
                        # In dry-run mode, just record the error and continue
                        results[migration["version"]] = {
                            "error": str(e),
                            "status": "failed"
                        }
                        logger.warning(
                            f"[DRY-RUN] Migration {migration['version']} would fail: {e}",
                            extra={
                                "event": "migration_dry_run_failed",
                                "version": migration["version"],
                                "error": str(e),
                            }
                        )

        return results

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

    def batch_update_summaries(
        self, summaries: dict[str, str], level: str | None = None
    ) -> int:
        """Batch update multiple summaries in a single transaction.

        Args:
            summaries: Dict mapping target_fqn to summary text
            level: Optional summary level (defaults to 'method')

        Returns:
            Number of summaries updated
        """
        if not summaries:
            return 0

        cursor = self.conn.cursor()
        level_value = level or "method"

        try:
            with self.conn:
                # Use executemany for batch update within transaction
                rows = [
                    (summary_text, False, fqn)
                    for fqn, summary_text in summaries.items()
                ]
                cursor.executemany(
                    """UPDATE summaries
                       SET summary = ?, is_stale = ?, updated_at = CURRENT_TIMESTAMP
                       WHERE target_fqn = ?""",
                    rows,
                )
                return cursor.rowcount
        except Exception:
            # Rowcount may not be available with executemany in all SQLite versions
            # Return the count of items processed
            return len(summaries)

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
        """Create summary with optional vector storage using two-phase commit.

        Implements proper two-phase commit for dual-write consistency:
        1. Write to ChromaDB FIRST (outside SQLite transaction)
        2. Then write to SQLite in a transaction
        3. If SQLite fails, rollback ChromaDB
        4. Track pending operations for recovery

        This ensures that if ChromaDB write succeeds but SQLite fails, we can
        clean up the orphaned vector. If SQLite succeeds but ChromaDB fails, the
        SQLite transaction is rolled back.

        Args:
            summary: SummaryData to create
            embedding: Optional embedding vector for semantic search
            vector_store: Optional ChromaVectorStore instance

        Returns:
            Vector ID if embedding was provided and stored, None otherwise

        Raises:
            Exception: If SQLite operation fails (ChromaDB is cleaned up)
        """
        cursor = self.conn.cursor()
        vector_id = None

        # Phase 1: Write to ChromaDB first (outside transaction)
        if embedding is not None and vector_store is not None:
            try:
                # Generate a unique vector_id
                import uuid
                vector_id = str(uuid.uuid4())

                # Add to ChromaDB BEFORE SQLite transaction
                vector_store.add_summary(
                    summary_id=vector_id,
                    text=summary.summary,
                    embedding=embedding,
                    metadata={"fqn": summary.target_fqn, "level": summary.level.value},
                )
                logger.debug(
                    f"ChromaDB write succeeded for {summary.target_fqn}",
                    extra={"event": "chroma_write_success", "vector_id": vector_id}
                )
            except Exception as e:
                logger.error(
                    f"ChromaDB write failed for {summary.target_fqn}: {e}",
                    extra={"event": "chroma_write_failed", "fqn": summary.target_fqn}
                )
                # ChromaDB failed - we haven't written to SQLite yet, so safe to continue
                # without vector_id
                vector_id = None

        # Phase 2: Write to SQLite (with rollback if needed)
        try:
            with self.conn:
                # Insert SQLite record with vector_id
                cursor.execute(
                    """INSERT INTO summaries (target_fqn, level, summary, vector_id, is_stale, created_at, updated_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?)
                       RETURNING id
                    """,
                    (summary.target_fqn, summary.level.value, summary.summary, vector_id, False, "datetime('now')", "datetime('now')"),
                )
                summary_id = cursor.fetchone()[0]

                # Track sync state
                if vector_id:
                    cursor.execute(
                        """INSERT INTO vector_sync_state (vector_id, sqlite_table, sqlite_record_id, record_fqn, sync_status, last_synced_at)
                           VALUES (?, 'summaries', ?, ?, 'synced', datetime('now'))
                        """,
                        (vector_id, summary_id, summary.target_fqn),
                    )

                return vector_id

        except Exception as e:
            # SQLite write failed - need to rollback ChromaDB
            logger.error(
                f"SQLite write failed for {summary.target_fqn}, rolling back ChromaDB: {e}",
                extra={"event": "sqlite_write_failed", "fqn": summary.target_fqn}
            )

            # Rollback ChromaDB write
            if vector_id and vector_store is not None:
                try:
                    vector_store.delete_summaries([vector_id])
                    logger.info(
                        f"Rolled back ChromaDB vector {vector_id}",
                        extra={"event": "chroma_rollback", "vector_id": vector_id}
                    )
                except Exception as rollback_error:
                    logger.critical(
                        f"Failed to rollback ChromaDB vector {vector_id}: {rollback_error}",
                        extra={"event": "chroma_rollback_failed", "vector_id": vector_id}
                    )
                    # Track orphaned vector in SEPARATE transaction (outside rollback context)
                    self._track_orphaned_vector_separate_txn(vector_id, summary.target_fqn, rollback_error, e)

            raise

    def delete_summary_cascade(
        self,
        target_fqn: str,
        vector_store: ChromaVectorStore | None = None,
    ) -> bool:
        """Delete summary from both SQLite and ChromaDB using two-phase commit.

        Uses two-phase commit:
        1. Get vector_id from SQLite
        2. Delete from ChromaDB FIRST
        3. Then delete from SQLite
        4. If SQLite fails, ChromaDB deletion is already done (desired state)

        Args:
            target_fqn: Target symbol FQN
            vector_store: Optional ChromaVectorStore instance

        Returns:
            True if deleted, False if not found
        """
        cursor = self.conn.cursor()

        # Phase 1: Get vector_id from SQLite (no transaction yet)
        cursor.execute("SELECT id, vector_id FROM summaries WHERE target_fqn = ?", (target_fqn,))
        row = cursor.fetchone()
        if not row:
            return False

        summary_id, vector_id = row[0], row[1]

        # Phase 2: Delete from ChromaDB FIRST (outside transaction)
        if vector_id and vector_store is not None:
            try:
                vector_store.delete_summaries([vector_id])
                logger.debug(
                    f"Deleted vector {vector_id} from ChromaDB",
                    extra={"event": "chroma_delete_success", "vector_id": vector_id}
                )
            except Exception as e:
                logger.warning(
                    f"Failed to delete from ChromaDB (continuing with SQLite delete): {e}",
                    extra={"event": "chroma_delete_failed", "vector_id": vector_id}
                )
                # Track for cleanup
                try:
                    cursor.execute(
                        """INSERT INTO pending_vectors (temp_id, operation_type, sqlite_table, payload, vector_id, error_message)
                           VALUES (?, 'delete', 'summaries', ?, ?, ?)
                        """,
                        (vector_id, json.dumps({"fqn": target_fqn}), vector_id, str(e)),
                    )
                    self.conn.commit()
                except Exception:
                    pass

        # Phase 3: Delete from SQLite (transaction for atomicity)
        try:
            with self.conn:
                # Clean up sync state
                if vector_id:
                    cursor.execute("DELETE FROM vector_sync_state WHERE vector_id = ?", (vector_id,))

                # Delete summary
                cursor.execute("DELETE FROM summaries WHERE target_fqn = ?", (target_fqn,))
                return True

        except Exception as e:
            logger.error(f"Failed to delete summary from SQLite: {e}")
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
    # Vector Sync Recovery
    # ========================

    def detect_orphaned_records(self) -> dict[str, int]:
        """Detect orphaned records for cross-store synchronization.

        Returns:
            Dictionary with counts of orphaned records by type
        """
        cursor = self.conn.cursor()
        orphans = {}

        # Summaries with vector_id but no matching sync state
        cursor.execute("""
            SELECT COUNT(*) FROM summaries s
            LEFT JOIN vector_sync_state v ON s.vector_id = v.vector_id
            WHERE s.vector_id IS NOT NULL AND v.vector_id IS NULL
        """)
        orphans["summaries_without_sync_state"] = cursor.fetchone()[0]

        # Sync state records without matching summary
        cursor.execute("""
            SELECT COUNT(*) FROM vector_sync_state v
            LEFT JOIN summaries s ON v.sqlite_record_id = s.id AND v.sqlite_table = 'summaries'
            WHERE v.sqlite_table = 'summaries' AND s.id IS NULL
        """)
        orphans["sync_state_without_summary"] = cursor.fetchone()[0]

        # Pending operations older than 1 hour
        cursor.execute("""
            SELECT COUNT(*) FROM pending_vectors
            WHERE created_at < datetime('now', '-1 hour')
        """)
        orphans["stale_pending_operations"] = cursor.fetchone()[0]

        # Summaries marked for sync but still pending
        cursor.execute("""
            SELECT COUNT(*) FROM vector_sync_state
            WHERE sync_status = 'pending'
            AND created_at < datetime('now', '-10 minutes')
        """)
        orphans["stalled_sync_operations"] = cursor.fetchone()[0]

        return orphans

    def recover_orphaned_vectors(
        self,
        vector_store: ChromaVectorStore | None = None,
    ) -> dict[str, int]:
        """Recover orphaned vectors from failed sync operations.

        This cleans up:
        1. Vectors in ChromaDB that don't have corresponding SQLite records
        2. Pending operations that can be retried or cleaned up

        Args:
            vector_store: Optional ChromaVectorStore for cleanup

        Returns:
            Dictionary with recovery statistics
        """
        cursor = self.conn.cursor()
        stats = {
            "vectors_deleted": 0,
            "pending_cleaned": 0,
            "sync_state_cleaned": 0,
            "errors": 0,
        }

        try:
            # Clean up sync state records without matching summary
            cursor.execute("""
                SELECT v.vector_id, v.sqlite_record_id
                FROM vector_sync_state v
                LEFT JOIN summaries s ON v.sqlite_record_id = s.id AND v.sqlite_table = 'summaries'
                WHERE v.sqlite_table = 'summaries' AND s.id IS NULL
            """)
            orphaned_sync = cursor.fetchall()

            for vector_id, sqlite_id in orphaned_sync:
                try:
                    # Delete from ChromaDB if available
                    if vector_id and vector_store is not None:
                        vector_store.delete_summaries([vector_id])
                        stats["vectors_deleted"] += 1

                    # Delete sync state record
                    cursor.execute("DELETE FROM vector_sync_state WHERE vector_id = ?", (vector_id,))
                    stats["sync_state_cleaned"] += 1

                except Exception as e:
                    logger.error(f"Failed to clean up orphaned sync state {vector_id}: {e}")
                    stats["errors"] += 1

            # Clean up stale pending operations
            cursor.execute("""
                SELECT id, temp_id, operation_type, vector_id
                FROM pending_vectors
                WHERE created_at < datetime('now', '-1 hour')
            """)
            stale_pending = cursor.fetchall()

            for pending_id, temp_id, op_type, vector_id in stale_pending:
                try:
                    # For pending deletes, clean up ChromaDB
                    if op_type == 'delete' and vector_id and vector_store is not None:
                        vector_store.delete_summaries([vector_id])
                        stats["vectors_deleted"] += 1

                    # Delete pending record
                    cursor.execute("DELETE FROM pending_vectors WHERE id = ?", (pending_id,))
                    stats["pending_cleaned"] += 1

                except Exception as e:
                    logger.error(f"Failed to clean up pending operation {pending_id}: {e}")
                    stats["errors"] += 1

            self.conn.commit()

            logger.info(
                f"Vector sync recovery completed",
                extra={
                    "event": "vector_sync_recovery",
                    "stats": stats,
                }
            )

        except Exception as e:
            self.conn.rollback()
            logger.error(f"Vector sync recovery failed: {e}")
            raise

        return stats

    def _track_orphaned_vector_separate_txn(
        self,
        vector_id: str,
        target_fqn: str,
        rollback_error: Exception,
        original_error: Exception,
    ) -> None:
        """Track an orphaned vector in a separate transaction (outside rollback context).

        This is called when the two-phase commit fails and we need to track
        an orphaned ChromaDB vector for later cleanup. Using a separate
        database connection ensures the tracking survives the main transaction rollback.

        Args:
            vector_id: The vector_id that was written to ChromaDB
            target_fqn: The target symbol FQN
            rollback_error: The error from ChromaDB rollback attempt
            original_error: The original SQLite write error
        """
        import sqlite3
        from datetime import datetime

        try:
            # Create a new database connection (outside the rolled-back transaction)
            tracking_conn = sqlite3.connect(self.db_path, timeout=30.0)
            try:
                tracking_conn.execute("BEGIN IMMEDIATE")

                # Insert tracking record with detailed error information
                tracking_conn.execute(
                    """INSERT INTO pending_vectors (temp_id, operation_type, sqlite_table, payload, vector_id, error_message, created_at)
                       VALUES (?, 'delete', 'summaries', ?, ?, ?)
                    """,
                    (
                        vector_id,
                        json.dumps({
                            "fqn": target_fqn,
                            "original_error": str(original_error),
                            "rollback_error": str(rollback_error),
                            "tracking_time": datetime.utcnow().isoformat(),
                        }),
                        vector_id,
                        f"Orphan after rollback: {rollback_error}",
                    ),
                )
                tracking_conn.commit()

                logger.info(
                    f"Tracked orphaned vector {vector_id} for later cleanup",
                    extra={"event": "orphan_tracked", "vector_id": vector_id, "target_fqn": target_fqn}
                )

            finally:
                tracking_conn.close()

        except Exception as tracking_error:
            # This is critical - if we can't track, we need to log at CRITICAL level
            logger.critical(
                f"CRITICAL: Failed to track orphaned vector {vector_id}. "
                f"Manual cleanup required. Original error: {original_error}, "
                f"Rollback error: {rollback_error}, Tracking error: {tracking_error}",
                extra={
                    "event": "orphan_tracking_failed",
                    "vector_id": vector_id,
                    "target_fqn": target_fqn,
                }
            )

    def get_pending_sync_operations(self) -> list[dict[str, Any]]:
        """Get pending sync operations that may need recovery.

        Returns:
            List of pending sync operations
        """
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT id, temp_id, operation_type, sqlite_table, payload, vector_id,
                   error_message, retry_count, created_at
            FROM pending_vectors
            WHERE retry_count < 3
            ORDER BY created_at DESC
            LIMIT 100
        """)
        return [dict(row) for row in cursor.fetchall()]

    # ========================
    # Glossary Methods
    # ========================

    def get_glossary_terms(
        self,
        prefix: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        """Get glossary terms with optional prefix filtering.

        Args:
            prefix: Optional filter by code_term prefix (e.g., "Order")
            limit: Maximum results to return (1-1000)
            offset: Pagination offset

        Returns:
            List of glossary term dictionaries
        """
        limit = max(1, min(limit, 1000))
        cursor = self.conn.cursor()

        query = "SELECT * FROM glossary"
        params = []

        if prefix:
            query += " WHERE code_term LIKE ?"
            params.append(f"{prefix}%")

        query += " ORDER BY code_term LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        cursor.execute(query, params)
        return [dict(row) for row in cursor.fetchall()]

    def get_glossary_term(self, code_term: str) -> dict[str, Any] | None:
        """Get a specific glossary term by code_term.

        Args:
            code_term: The exact code term to look up

        Returns:
            Glossary term dictionary or None if not found
        """
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT * FROM glossary WHERE code_term = ?",
            (code_term,)
        )
        row = cursor.fetchone()
        return dict(row) if row else None

    def get_glossary_term_count(self) -> int:
        """Get the total count of glossary terms.

        Returns:
            Total number of glossary terms
        """
        cursor = self.conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM glossary")
        return cursor.fetchone()[0]
