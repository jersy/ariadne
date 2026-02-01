"""Migration 001: Add ON DELETE CASCADE and cleanup triggers.

This migration ensures data integrity by:
1. Adding cascade delete triggers for edges table
2. Ensuring foreign keys have ON DELETE CASCADE
3. Cleaning up orphaned records

Related issue: 018-pending-p1-cascade-delete-orphaned-edges.md
"""

import logging
from typing import Any

logger = logging.getLogger(__name__)

# Migration metadata
version = "001"
name = "cascade_deletes"
description = "Add ON DELETE CASCADE triggers and cleanup orphaned records"


def upgrade(conn: Any) -> None:
    """Apply migration to add cascade delete behavior.

    Args:
        conn: SQLite connection object
    """
    cursor = conn.cursor()

    # Enable foreign keys
    cursor.execute("PRAGMA foreign_keys = ON")

    # 1. Add cascade delete triggers for edges table
    _create_edges_triggers(cursor)

    # 2. Clean up orphaned records
    orphaned_counts = _cleanup_orphaned_records(cursor)

    # 3. Ensure foreign keys have CASCADE for L2/L1 tables
    _ensure_cascade_constraints(cursor)

    conn.commit()

    # Log results
    if orphaned_counts:
        total_orphans = sum(orphaned_counts.values())
        logger.info(
            f"Migration {version} completed: cleaned up {total_orphans} orphaned records",
            extra={
                "migration": version,
                "orphaned_counts": orphaned_counts,
            }
        )
    else:
        logger.info(
            f"Migration {version} completed: no orphaned records found",
            extra={"migration": version}
        )


def _create_edges_triggers(cursor: Any) -> None:
    """Create cascade delete triggers for edges table.

    The edges table uses TEXT references (not FK constraints) because
    edges can reference symbols outside the indexed codebase. We use
    triggers instead to clean up edges when symbols are deleted.
    """
    # Delete outgoing edges when a symbol is deleted
    cursor.execute("""
        CREATE TRIGGER IF NOT EXISTS edges_delete_outgoing_on_symbol_delete
        AFTER DELETE ON symbols
        FOR EACH ROW
        WHEN EXISTS (SELECT 1 FROM edges WHERE from_fqn = OLD.fqn)
        BEGIN
            DELETE FROM edges WHERE from_fqn = OLD.fqn;
        END;
    """)

    # Delete incoming edges when a symbol is deleted
    cursor.execute("""
        CREATE TRIGGER IF NOT EXISTS edges_delete_incoming_on_symbol_delete
        AFTER DELETE ON symbols
        FOR EACH ROW
        WHEN EXISTS (SELECT 1 FROM edges WHERE to_fqn = OLD.fqn)
        BEGIN
            DELETE FROM edges WHERE to_fqn = OLD.fqn;
        END;
    """)


def _cleanup_orphaned_records(cursor: Any) -> dict[str, int]:
    """Clean up orphaned records across all tables.

    Returns:
        Dictionary with table names and orphaned counts
    """
    orphaned_counts = {}

    # Check and clean orphaned edges (from side)
    cursor.execute("""
        SELECT COUNT(*) FROM edges e
        LEFT JOIN symbols s ON e.from_fqn = s.fqn
        WHERE s.fqn IS NULL
    """)
    orphaned_edge_from = cursor.fetchone()[0]
    if orphaned_edge_from > 0:
        cursor.execute("""
            DELETE FROM edges WHERE from_fqn NOT IN (SELECT fqn FROM symbols)
        """)
        orphaned_counts["edges_from"] = orphaned_edge_from

    # Check and clean orphaned edges (to side)
    cursor.execute("""
        SELECT COUNT(*) FROM edges e
        LEFT JOIN symbols s ON e.to_fqn = s.fqn
        WHERE s.fqn IS NULL
    """)
    orphaned_edge_to = cursor.fetchone()[0]
    if orphaned_edge_to > 0:
        cursor.execute("""
            DELETE FROM edges WHERE to_fqn NOT IN (SELECT fqn FROM symbols)
        """)
        orphaned_counts["edges_to"] = orphaned_edge_to

    # Check and clean orphaned entry_points (if table exists)
    if _table_exists(cursor, "entry_points"):
        cursor.execute("""
            SELECT COUNT(*) FROM entry_points ep
            LEFT JOIN symbols s ON ep.symbol_fqn = s.fqn
            WHERE s.fqn IS NULL
        """)
        orphaned = cursor.fetchone()[0]
        if orphaned > 0:
            cursor.execute("""
                DELETE FROM entry_points
                WHERE symbol_fqn NOT IN (SELECT fqn FROM symbols)
            """)
            orphaned_counts["entry_points"] = orphaned

    # Check and clean orphaned external_dependencies (if table exists)
    if _table_exists(cursor, "external_dependencies"):
        cursor.execute("""
            SELECT COUNT(*) FROM external_dependencies ed
            LEFT JOIN symbols s ON ed.caller_fqn = s.fqn
            WHERE s.fqn IS NULL
        """)
        orphaned = cursor.fetchone()[0]
        if orphaned > 0:
            cursor.execute("""
                DELETE FROM external_dependencies
                WHERE caller_fqn NOT IN (SELECT fqn FROM symbols)
            """)
            orphaned_counts["external_dependencies"] = orphaned

    # Check and clean orphaned summaries (if table exists)
    if _table_exists(cursor, "summaries"):
        cursor.execute("""
            SELECT COUNT(*) FROM summaries sum
            LEFT JOIN symbols s ON sum.target_fqn = s.fqn
            WHERE s.fqn IS NULL
        """)
        orphaned = cursor.fetchone()[0]
        if orphaned > 0:
            cursor.execute("""
                DELETE FROM summaries
                WHERE target_fqn NOT IN (SELECT fqn FROM symbols)
            """)
            orphaned_counts["summaries"] = orphaned

    # Check and clean orphaned glossary (if table exists)
    if _table_exists(cursor, "glossary"):
        cursor.execute("""
            SELECT COUNT(*) FROM glossary g
            LEFT JOIN symbols s ON g.source_fqn = s.fqn
            WHERE g.source_fqn IS NOT NULL AND s.fqn IS NULL
        """)
        orphaned = cursor.fetchone()[0]
        if orphaned > 0:
            cursor.execute("""
                DELETE FROM glossary
                WHERE source_fqn IS NOT NULL
                AND source_fqn NOT IN (SELECT fqn FROM symbols)
            """)
            orphaned_counts["glossary"] = orphaned

    # Check and clean orphaned constraints (if table exists)
    if _table_exists(cursor, "constraints"):
        cursor.execute("""
            SELECT COUNT(*) FROM constraints c
            LEFT JOIN symbols s ON c.source_fqn = s.fqn
            WHERE c.source_fqn IS NOT NULL AND s.fqn IS NULL
        """)
        orphaned = cursor.fetchone()[0]
        if orphaned > 0:
            cursor.execute("""
                DELETE FROM constraints
                WHERE source_fqn IS NOT NULL
                AND source_fqn NOT IN (SELECT fqn FROM symbols)
            """)
            orphaned_counts["constraints"] = orphaned

    # Check and clean orphaned anti_patterns (if table exists)
    if _table_exists(cursor, "anti_patterns"):
        cursor.execute("""
            SELECT COUNT(*) FROM anti_patterns ap
            LEFT JOIN symbols s ON ap.from_fqn = s.fqn
            WHERE s.fqn IS NULL
        """)
        orphaned = cursor.fetchone()[0]
        if orphaned > 0:
            cursor.execute("""
                DELETE FROM anti_patterns
                WHERE from_fqn NOT IN (SELECT fqn FROM symbols)
            """)
            orphaned_counts["anti_patterns"] = orphaned

    return orphaned_counts


def _ensure_cascade_constraints(cursor: Any) -> None:
    """Ensure foreign keys have ON DELETE CASCADE.

    Note: SQLite doesn't support ALTER CONSTRAINT directly. Tables created
    after this schema will have CASCADE automatically. This function
    handles tables that might have been created before CASCADE was added.

    For existing databases with data, we use triggers to simulate CASCADE.
    """
    # For tables that don't support ALTER CONSTRAINT, we use triggers
    # These will be idempotent due to IF NOT EXISTS

    # entry_points cascade trigger (if table exists and no CASCADE)
    if _table_exists(cursor, "entry_points"):
        if not _has_cascade_constraint(cursor, "entry_points", "symbol_fqn"):
            cursor.execute("""
                CREATE TRIGGER IF NOT EXISTS entry_points_cascade_delete
                AFTER DELETE ON symbols
                FOR EACH ROW
                WHEN EXISTS (SELECT 1 FROM entry_points WHERE symbol_fqn = OLD.fqn)
                BEGIN
                    DELETE FROM entry_points WHERE symbol_fqn = OLD.fqn;
                END;
            """)

    # external_dependencies cascade trigger
    if _table_exists(cursor, "external_dependencies"):
        if not _has_cascade_constraint(cursor, "external_dependencies", "caller_fqn"):
            cursor.execute("""
                CREATE TRIGGER IF NOT EXISTS external_dependencies_cascade_delete
                AFTER DELETE ON symbols
                FOR EACH ROW
                WHEN EXISTS (SELECT 1 FROM external_dependencies WHERE caller_fqn = OLD.fqn)
                BEGIN
                    DELETE FROM external_dependencies WHERE caller_fqn = OLD.fqn;
                END;
            """)

    # summaries cascade trigger
    if _table_exists(cursor, "summaries"):
        if not _has_cascade_constraint(cursor, "summaries", "target_fqn"):
            cursor.execute("""
                CREATE TRIGGER IF NOT EXISTS summaries_cascade_delete
                AFTER DELETE ON symbols
                FOR EACH ROW
                WHEN EXISTS (SELECT 1 FROM summaries WHERE target_fqn = OLD.fqn)
                BEGIN
                    DELETE FROM summaries WHERE target_fqn = OLD.fqn;
                END;
            """)

    # anti_patterns cascade trigger (from_fqn)
    if _table_exists(cursor, "anti_patterns"):
        if not _has_cascade_constraint(cursor, "anti_patterns", "from_fqn"):
            cursor.execute("""
                CREATE TRIGGER IF NOT EXISTS anti_patterns_cascade_delete
                AFTER DELETE ON symbols
                FOR EACH ROW
                WHEN EXISTS (SELECT 1 FROM anti_patterns WHERE from_fqn = OLD.fqn)
                BEGIN
                    DELETE FROM anti_patterns WHERE from_fqn = OLD.fqn;
                END;
            """)


def _table_exists(cursor: Any, table_name: str) -> bool:
    """Check if a table exists in the database."""
    cursor.execute("""
        SELECT name FROM sqlite_master
        WHERE type='table' AND name=?
    """, (table_name,))
    return cursor.fetchone() is not None


def _has_cascade_constraint(cursor: Any, table_name: str, fk_column: str) -> bool:
    """Check if a foreign key constraint has ON DELETE CASCADE.

    This is a simplified check - in production we'd parse the SQL schema.
    For now, we assume triggers are needed if we can't verify CASCADE.
    """
    # Get the CREATE TABLE statement
    cursor.execute("""
        SELECT sql FROM sqlite_master
        WHERE type='table' AND name=?
    """, (table_name,))
    result = cursor.fetchone()
    if not result or not result[0]:
        return False

    create_sql = result[0].upper()
    # Check if CASCADE is mentioned for this foreign key
    # This is a simple heuristic - in production we'd parse the SQL properly
    return "ON DELETE CASCADE" in create_sql


# Export migration metadata
migration_001_cascade_deletes = {
    "version": version,
    "name": name,
    "description": description,
    "upgrade": upgrade,
}
