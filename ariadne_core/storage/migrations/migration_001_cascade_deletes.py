"""Migration 001: Add ON DELETE CASCADE and cleanup triggers.

This migration ensures data integrity by:
1. Adding cascade delete triggers for edges table
2. Ensuring foreign keys have ON DELETE CASCADE
3. Cleaning up orphaned records

IMPORTANT: This migration will DELETE orphaned records. Run with dry_run=True
first to preview what will be deleted. Deleted records are backed up to
_deleted_orphans_backup_001 table for potential recovery.

Related issue: 018-pending-p1-cascade-delete-orphaned-edges.md
"""

import json
import logging
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)

# Migration metadata
version = "001"
name = "cascade_deletes"
description = "Add ON DELETE CASCADE triggers and cleanup orphaned records"


def upgrade(conn: Any, dry_run: bool = False) -> dict[str, int]:
    """Apply migration to add cascade delete behavior.

    IMPORTANT: Run with dry_run=True first to preview what will be deleted.
    Deleted records are backed up to _deleted_orphans_backup_001 table.

    Args:
        conn: SQLite connection object
        dry_run: If True, only report what would be deleted without deleting

    Returns:
        Dictionary with counts of orphaned records found/deleted
    """
    cursor = conn.cursor()

    logger.info(
        f"Running migration {version} with dry_run={dry_run}",
        extra={"migration": version, "dry_run": dry_run}
    )

    # Enable foreign keys
    cursor.execute("PRAGMA foreign_keys = ON")

    # 1. Add cascade delete triggers for edges table (safe, no data loss)
    _create_edges_triggers(cursor)

    # 2. Clean up orphaned records (with dry-run support)
    orphaned_counts = _cleanup_orphaned_records(cursor, dry_run=dry_run)

    # 3. Ensure foreign keys have CASCADE for L2/L1 tables
    _ensure_cascade_constraints(cursor)

    # Only commit if not in dry-run mode
    if not dry_run:
        conn.commit()
    else:
        conn.rollback()  # Explicit rollback to make intent clear

    # Log results
    if orphaned_counts:
        total_orphans = sum(orphaned_counts.values())
        if dry_run:
            logger.info(
                f"[DRY-RUN] Migration {version}: would delete {total_orphans} orphaned records",
                extra={
                    "migration": version,
                    "dry_run": True,
                    "would_delete": total_orphans,
                    "orphaned_counts": orphaned_counts,
                }
            )
        else:
            logger.info(
                f"Migration {version} completed: deleted {total_orphans} orphaned records",
                extra={
                    "migration": version,
                    "deleted": total_orphans,
                    "orphaned_counts": orphaned_counts,
                }
            )
    else:
        logger.info(
            f"Migration {version} completed: no orphaned records found",
            extra={"migration": version}
        )

    return orphaned_counts


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


def _cleanup_orphaned_records(cursor: Any, dry_run: bool = False) -> dict[str, int]:
    """Clean up orphaned records across all tables.

    IMPORTANT: This will DELETE data. Run with dry_run=True first to preview.

    Args:
        cursor: SQLite cursor
        dry_run: If True, only report what would be deleted without deleting

    Returns:
        Dictionary with table names and orphaned counts
    """
    orphaned_counts = {}
    backup_table = "_deleted_orphans_backup_001"

    # Create backup table if not exists (only when not in dry-run mode)
    if not dry_run:
        cursor.execute(f"""
            CREATE TABLE IF NOT EXISTS {backup_table} (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                table_name TEXT NOT NULL,
                record_id TEXT NOT NULL,
                record_data JSON,
                deleted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        logger.info(f"Created backup table: {backup_table}")

    # Helper function to backup and delete orphaned records
    def _backup_and_delete_orphans(
        table_name: str,
        id_column: str,
        where_clause: str,
        count_query: str,
        data_query: str,
    ) -> int:
        """Backup and delete orphaned records for a table.

        Args:
            table_name: Name of the table
            id_column: Primary key column name
            where_clause: WHERE clause to find orphans
            count_query: Query to count orphans
            data_query: Query to select orphan data for backup

        Returns:
            Number of orphans deleted (or would be deleted in dry-run)
        """
        # Count orphans
        cursor.execute(count_query)
        orphan_count = cursor.fetchone()[0]

        if orphan_count == 0:
            return 0

        if dry_run:
            logger.info(f"[DRY-RUN] Would delete {orphan_count} orphaned records from {table_name}")
            return orphan_count

        # Backup the records
        cursor.execute(f"""
            INSERT INTO {backup_table} (table_name, record_id, record_data, deleted_at)
            SELECT '{table_name}',
                   {id_column},
                   json_object(
                       'data', json({data_query})
                   ),
                   datetime('now')
            FROM ({data_query}) AS orphan_data
        """)

        # Delete the records
        cursor.execute(f"DELETE FROM {table_name} WHERE {where_clause}")
        deleted_count = cursor.rowcount

        logger.info(f"Deleted {deleted_count} orphaned records from {table_name}, backed up to {backup_table}")
        return deleted_count

    # Check and clean orphaned edges (from side)
    orphaned_counts["edges_from"] = _backup_and_delete_orphans(
        table_name="edges",
        id_column="'from_fqn' || ':' || 'to_fqn' || ':' || relation",
        where_clause="from_fqn NOT IN (SELECT fqn FROM symbols)",
        count_query="""
            SELECT COUNT(*) FROM edges e
            LEFT JOIN symbols s ON e.from_fqn = s.fqn
            WHERE s.fqn IS NULL
        """,
        data_query="""
            SELECT from_fqn, to_fqn, relation, id
            FROM edges e
            LEFT JOIN symbols s ON e.from_fqn = s.fqn
            WHERE s.fqn IS NULL
        """,
    )

    # Check and clean orphaned edges (to side)
    orphaned_counts["edges_to"] = _backup_and_delete_orphans(
        table_name="edges",
        id_column="'from_fqn' || ':' || 'to_fqn' || ':' || relation",
        where_clause="to_fqn NOT IN (SELECT fqn FROM symbols)",
        count_query="""
            SELECT COUNT(*) FROM edges e
            LEFT JOIN symbols s ON e.to_fqn = s.fqn
            WHERE s.fqn IS NULL
        """,
        data_query="""
            SELECT from_fqn, to_fqn, relation, id
            FROM edges e
            LEFT JOIN symbols s ON e.to_fqn = s.fqn
            WHERE s.fqn IS NULL
        """,
    )

    # Check and clean orphaned entry_points (if table exists)
    if _table_exists(cursor, "entry_points"):
        orphaned_counts["entry_points"] = _backup_and_delete_orphans(
            table_name="entry_points",
            id_column="symbol_fqn",
            where_clause="symbol_fqn NOT IN (SELECT fqn FROM symbols)",
            count_query="""
                SELECT COUNT(*) FROM entry_points ep
                LEFT JOIN symbols s ON ep.symbol_fqn = s.fqn
                WHERE s.fqn IS NULL
            """,
            data_query="""
                SELECT symbol_fqn, entry_type, id
                FROM entry_points ep
                LEFT JOIN symbols s ON ep.symbol_fqn = s.fqn
                WHERE s.fqn IS NULL
            """,
        )

    # Check and clean orphaned external_dependencies (if table exists)
    if _table_exists(cursor, "external_dependencies"):
        orphaned_counts["external_dependencies"] = _backup_and_delete_orphans(
            table_name="external_dependencies",
            id_column="caller_fqn || ':' || target_fqn || ':' || dependency_type",
            where_clause="caller_fqn NOT IN (SELECT fqn FROM symbols)",
            count_query="""
                SELECT COUNT(*) FROM external_dependencies ed
                LEFT JOIN symbols s ON ed.caller_fqn = s.fqn
                WHERE s.fqn IS NULL
            """,
            data_query="""
                SELECT caller_fqn, target_fqn, dependency_type, id
                FROM external_dependencies ed
                LEFT JOIN symbols s ON ed.caller_fqn = s.fqn
                WHERE s.fqn IS NULL
            """,
        )

    # Check and clean orphaned summaries (if table exists)
    if _table_exists(cursor, "summaries"):
        orphaned_counts["summaries"] = _backup_and_delete_orphans(
            table_name="summaries",
            id_column="target_fqn",
            where_clause="target_fqn NOT IN (SELECT fqn FROM symbols)",
            count_query="""
                SELECT COUNT(*) FROM summaries sum
                LEFT JOIN symbols s ON sum.target_fqn = s.fqn
                WHERE s.fqn IS NULL
            """,
            data_query="""
                SELECT target_fqn, summary, vector_id, id
                FROM summaries sum
                LEFT JOIN symbols s ON sum.target_fqn = s.fqn
                WHERE s.fqn IS NULL
            """,
        )

    # Check and clean orphaned glossary (if table exists)
    if _table_exists(cursor, "glossary"):
        orphaned_counts["glossary"] = _backup_and_delete_orphans(
            table_name="glossary",
            id_column="code_term",
            where_clause="source_fqn IS NOT NULL AND source_fqn NOT IN (SELECT fqn FROM symbols)",
            count_query="""
                SELECT COUNT(*) FROM glossary g
                LEFT JOIN symbols s ON g.source_fqn = s.fqn
                WHERE g.source_fqn IS NOT NULL AND s.fqn IS NULL
            """,
            data_query="""
                SELECT code_term, business_meaning, synonyms, source_fqn, id
                FROM glossary g
                LEFT JOIN symbols s ON g.source_fqn = s.fqn
                WHERE g.source_fqn IS NOT NULL AND s.fqn IS NULL
            """,
        )

    # Check and clean orphaned constraints (if table exists)
    if _table_exists(cursor, "constraints"):
        orphaned_counts["constraints"] = _backup_and_delete_orphans(
            table_name="constraints",
            id_column="source_fqn || ':' || constraint_type",
            where_clause="source_fqn IS NOT NULL AND source_fqn NOT IN (SELECT fqn FROM symbols)",
            count_query="""
                SELECT COUNT(*) FROM constraints c
                LEFT JOIN symbols s ON c.source_fqn = s.fqn
                WHERE c.source_fqn IS NOT NULL AND s.fqn IS NULL
            """,
            data_query="""
                SELECT source_fqn, constraint_type, expression, id
                FROM constraints c
                LEFT JOIN symbols s ON c.source_fqn = s.fqn
                WHERE c.source_fqn IS NOT NULL AND s.fqn IS NULL
            """,
        )

    # Check and clean orphaned anti_patterns (if table exists)
    if _table_exists(cursor, "anti_patterns"):
        orphaned_counts["anti_patterns"] = _backup_and_delete_orphans(
            table_name="anti_patterns",
            id_column="from_fqn || ':' || pattern_name",
            where_clause="from_fqn NOT IN (SELECT fqn FROM symbols)",
            count_query="""
                SELECT COUNT(*) FROM anti_patterns ap
                LEFT JOIN symbols s ON ap.from_fqn = s.fqn
                WHERE s.fqn IS NULL
            """,
            data_query="""
                SELECT from_fqn, pattern_name, severity, id
                FROM anti_patterns ap
                LEFT JOIN symbols s ON ap.from_fqn = s.fqn
                WHERE s.fqn IS NULL
            """,
        )

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
