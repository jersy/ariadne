"""Shadow rebuild with atomic swap for safe database rebuilds.

This module implements a shadow rebuild strategy that:
1. Builds a new index in a separate database file
2. Verifies the new index integrity
3. Atomically swaps the databases
4. Preserves the old database as backup

This ensures zero data loss even if the rebuild process crashes.

Related issue: 017-pending-p1-rebuild-operation-data-loss-risk.md
"""

from __future__ import annotations

import logging
import os
import sqlite3
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any

from ariadne_core.models.types import ExtractionResult
from ariadne_core.storage.sqlite_store import SQLiteStore

logger = logging.getLogger(__name__)


class RebuildFailedError(Exception):
    """Raised when rebuild fails after starting."""

    pass


class IntegrityError(Exception):
    """Raised when index verification fails."""

    pass


class RebuildStats:
    """Statistics for rebuild operations."""

    def __init__(
        self,
        symbols_count: int = 0,
        edges_count: int = 0,
        entries_count: int = 0,
        deps_count: int = 0,
        duration: float = 0.0,
    ):
        self.symbols_count = symbols_count
        self.edges_count = edges_count
        self.entries_count = entries_count
        self.deps_count = deps_count
        self.duration = duration


class ShadowRebuilder:
    """Shadow rebuild with atomic swap for safe database rebuilds.

    The rebuild process:
    1. Creates a new database file
    2. Builds the index in the new file
    3. Verifies the new index integrity
    4. Atomically swaps the database files
    5. Keeps the old database as backup

    If the process fails at any point, the original database remains intact.
    """

    def __init__(
        self,
        db_path: str = "ariadne.db",
        project_root: str = ".",
        service_url: str = "http://localhost:8766",
    ):
        """Initialize the shadow rebuilder.

        Args:
            db_path: Path to the current database file
            project_root: Root directory of the project to index
            service_url: URL of the ASM analysis service
        """
        self.db_path = db_path
        self.project_root = project_root
        self.service_url = service_url

    def rebuild_full(self) -> dict[str, Any]:
        """Perform a full rebuild with shadow database and atomic swap.

        Returns:
            Dictionary with rebuild statistics

        Raises:
            RebuildFailedError: If rebuild fails after starting
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_suffix = f"_backup_{timestamp}"
        new_db_path = f"ariadne_new_{timestamp}.db"

        logger.info(
            f"Starting shadow rebuild",
            extra={
                "event": "shadow_rebuild_start",
                "timestamp": timestamp,
                "new_db": new_db_path,
            }
        )

        try:
            # Step 1: Build new index in separate file
            logger.info(f"Building new index at {new_db_path}")
            stats = self._build_new_index(new_db_path)

            # Step 2: Verify integrity of new index
            logger.info("Verifying new index integrity")
            if not self._verify_new_index(new_db_path):
                raise IntegrityError("Built index failed verification")

            # Step 3: Atomic swap
            logger.info("Performing atomic database swap")
            self._atomic_swap_databases(
                current=self.db_path,
                new=new_db_path,
                backup_suffix=backup_suffix,
            )

            # Step 4: Schedule cleanup of old backup
            self._schedule_backup_cleanup(self.db_path + backup_suffix)

            logger.info(
                f"Shadow rebuild completed successfully",
                extra={
                    "event": "shadow_rebuild_complete",
                    "backup": self.db_path + backup_suffix,
                    "symbols": stats.symbols_count,
                    "edges": stats.edges_count,
                    "duration": stats.duration,
                }
            )

            return {
                "status": "success",
                "symbols_indexed": stats.symbols_count,
                "edges_created": stats.edges_count,
                "entries_detected": stats.entries_count,
                "deps_analyzed": stats.deps_count,
                "duration_seconds": stats.duration,
                "backup_path": self.db_path + backup_suffix,
            }

        except Exception as e:
            # Rollback: Clean up failed rebuild
            logger.error(
                f"Rebuild failed, keeping current database: {e}",
                extra={
                    "event": "shadow_rebuild_failed",
                    "error": str(e),
                }
            )

            # Delete incomplete new database
            if os.path.exists(new_db_path):
                try:
                    os.remove(new_db_path)
                    logger.info(f"Removed incomplete new database: {new_db_path}")
                except OSError as cleanup_error:
                    logger.warning(f"Failed to remove {new_db_path}: {cleanup_error}")

            raise RebuildFailedError(f"Rebuild failed: {e}") from e

    def _build_new_index(self, new_db_path: str) -> RebuildStats:
        """Build the index in a new database file.

        Args:
            new_db_path: Path for the new database file

        Returns:
            RebuildStats with extraction statistics
        """
        import time

        start_time = time.time()

        # Import Extractor here to avoid circular dependency
        from ariadne_core.extractors.asm.extractor import Extractor

        # Create new store with fresh schema
        new_store = SQLiteStore(new_db_path, init=True)

        # Create extractor with the new store
        extractor = Extractor(
            db_path=new_db_path,
            service_url=self.service_url,
            init=False,
        )
        extractor.store = new_store

        # Run extraction
        result: ExtractionResult = extractor.extract_project(self.project_root)

        duration = time.time() - start_time

        if not result.success:
            raise RebuildFailedError(f"Extraction failed: {result.errors}")

        stats = RebuildStats(
            symbols_count=result.stats.get("total_symbols", 0),
            edges_count=result.stats.get("total_edges", 0),
            entries_count=result.stats.get("total_entries", 0),
            deps_count=result.stats.get("total_deps", 0),
            duration=duration,
        )

        new_store.close()
        return stats

    def _verify_new_index(self, new_db_path: str) -> bool:
        """Verify the new index meets integrity criteria.

        Args:
            new_db_path: Path to the new database file

        Returns:
            True if verification passes

        Raises:
            IntegrityError: If verification fails
        """
        conn = sqlite3.connect(new_db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        try:
            # Check 1: Minimum symbol count
            cursor.execute("SELECT COUNT(*) FROM symbols")
            symbol_count = cursor.fetchone()[0]

            if symbol_count == 0:
                raise IntegrityError("No symbols indexed - database is empty")

            logger.info(f"Verification: {symbol_count} symbols indexed")

            # Check 2: No orphaned edges
            cursor.execute("""
                SELECT COUNT(*) FROM edges e
                LEFT JOIN symbols s ON e.from_fqn = s.fqn
                WHERE s.fqn IS NULL
            """)
            orphaned_from = cursor.fetchone()[0]

            cursor.execute("""
                SELECT COUNT(*) FROM edges e
                LEFT JOIN symbols s ON e.to_fqn = s.fqn
                WHERE s.fqn IS NULL
            """)
            orphaned_to = cursor.fetchone()[0]

            total_orphaned = orphaned_from + orphaned_to
            if total_orphaned > 0:
                raise IntegrityError(f"{total_orphaned} orphaned edges detected")

            logger.info("Verification: No orphaned edges found")

            # Check 3: Foreign key integrity
            cursor.execute("PRAGMA foreign_key_check")
            fk_violations = cursor.fetchall()

            if fk_violations:
                raise IntegrityError(f"Foreign key violations: {len(fk_violations)}")

            logger.info("Verification: Foreign key integrity OK")

            # Check 4: Database integrity
            cursor.execute("PRAGMA integrity_check")
            integrity_result = cursor.fetchone()[0]

            if integrity_result != "ok":
                raise IntegrityError(f"Database integrity check failed: {integrity_result}")

            logger.info("Verification: Database integrity OK")

            return True

        finally:
            conn.close()

    def _atomic_swap_databases(
        self, current: str, new: str, backup_suffix: str
    ) -> None:
        """Atomically swap database files using three-way swap.

        This implementation ensures there is never a window where no valid database
        exists by using a temporary intermediate file and os.replace() which is
        atomic on both POSIX and Windows.

        Process:
        1. Rename new -> temp (atomic)
        2. Rename current -> backup (atomic)
        3. Rename temp -> current (atomic)
        4. Verify current exists

        At any point, at least one valid database exists.

        Args:
            current: Path to current database file
            new: Path to new database file
            backup_suffix: Suffix to append to current when backing up

        Raises:
            IOError: If swap fails and rollback is needed
        """
        backup_path = current + backup_suffix
        temp_path = current + ".tmp_swap"
        current_exists = os.path.exists(current)

        # Clean up any leftover temp file from previous failed swap
        if os.path.exists(temp_path):
            logger.info(f"Cleaning up leftover temp file: {temp_path}")
            try:
                os.remove(temp_path)
            except OSError as e:
                logger.warning(f"Failed to remove temp file: {e}")

        try:
            # Step 1: Move new database to temp location (atomic with os.replace)
            logger.info(f"Moving new database to temp: {new} -> {temp_path}")
            os.replace(new, temp_path)

            # Step 2: Move current database to backup location (atomic)
            if current_exists:
                logger.info(f"Backing up current database: {current} -> {backup_path}")
                os.replace(current, backup_path)

            # Step 3: Move temp database to current location (atomic)
            logger.info(f"Moving temp database to current: {temp_path} -> {current}")
            os.replace(temp_path, current)

            # Verify: A valid database must exist at current path
            if not os.path.exists(current):
                # This should never happen with os.replace, but handle it
                raise IOError(f"Swap verification failed: no database at {current}")

            logger.info(
                "Atomic swap completed successfully",
                extra={
                    "event": "swap_complete",
                    "current": current,
                    "backup": backup_path,
                }
            )

        except Exception as e:
            # Attempt recovery from whichever valid database exists
            logger.error(f"Atomic swap failed, attempting recovery: {e}")

            # Recovery priority: temp > backup > new
            recovered = False

            if os.path.exists(temp_path):
                logger.info("Recovering from temp database")
                try:
                    if os.path.exists(current):
                        os.remove(current)
                    os.replace(temp_path, current)
                    recovered = True
                except OSError as recovery_error:
                    logger.error(f"Failed to recover from temp: {recovery_error}")

            elif os.path.exists(backup_path):
                logger.info("Recovering from backup database")
                try:
                    if os.path.exists(current):
                        os.remove(current)
                    os.replace(backup_path, current)
                    recovered = True
                except OSError as recovery_error:
                    logger.error(f"Failed to recover from backup: {recovery_error}")

            elif os.path.exists(new):
                logger.info("Recovering from new database")
                try:
                    if os.path.exists(current):
                        os.remove(current)
                    os.replace(new, current)
                    recovered = True
                except OSError as recovery_error:
                    logger.error(f"Failed to recover from new: {recovery_error}")

            if not recovered or not os.path.exists(current):
                raise IOError(
                    f"Catastrophic swap failure: no valid database found. "
                    f"Manual recovery required. Paths checked: current={current}, "
                    f"temp={temp_path}, backup={backup_path}, new={new}"
                ) from e

            logger.info("Recovery completed successfully")

    def _check_and_recover_swap_incomplete(self, current: str, backup_suffix: str) -> bool:
        """Check if previous swap was incomplete and recover automatically.

        This should be called on SQLiteStore initialization to ensure the database
        is in a valid state after a potential crash during swap.

        Args:
            current: Path to current database file
            backup_suffix: Suffix used for backup files

        Returns:
            True if recovery was performed, False otherwise
        """
        backup_path = current + backup_suffix
        temp_path = current + ".tmp_swap"

        # Check for incomplete swap indicators
        current_exists = os.path.exists(current)
        backup_exists = os.path.exists(backup_path)
        temp_exists = os.path.exists(temp_path)

        # Case 1: current doesn't exist but backup does (main recovery scenario)
        if not current_exists and backup_exists:
            logger.warning(
                f"Detected incomplete swap: current missing, backup exists. Recovering.",
                extra={"event": "swap_recovery", "backup": backup_path}
            )
            try:
                os.replace(backup_path, current)
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
                os.replace(temp_path, current)
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

    def _schedule_backup_cleanup(self, backup_path: str) -> None:
        """Schedule cleanup of old backup database.

        In production, this would use a background task or cron job.
        For now, we just log a reminder.

        Args:
            backup_path: Path to the backup database file
        """
        logger.info(
            f"Backup database preserved at {backup_path}",
            extra={
                "event": "backup_preserved",
                "backup_path": backup_path,
                "note": "Implement background cleanup for old backups",
            }
        )

        # TODO: Implement background cleanup
        # Options:
        # 1. Use a background thread to delete after N days
        # 2. Use a cron job to clean up backups older than N days
        # 3. Add API endpoint to manually clean up old backups


def cleanup_old_backups(
    db_path: str = "ariadne.db",
    keep_count: int = 3,
) -> list[str]:
    """Clean up old backup databases, keeping only the most recent ones.

    Args:
        db_path: Path to the current database file
        keep_count: Number of recent backups to keep

    Returns:
        List of backup files that were removed
    """
    db_dir = Path(db_path).parent
    db_name = Path(db_path).name

    # Find all backup files
    backup_files = []
    for file_path in db_dir.glob(f"{db_name}_backup_*"):
        if file_path.is_file():
            backup_files.append(file_path)

    # Sort by modification time (newest first)
    backup_files.sort(key=lambda p: p.stat().st_mtime, reverse=True)

    # Keep only the most recent ones
    to_remove = backup_files[keep_count:]
    removed = []

    for file_path in to_remove:
        try:
            file_path.unlink()
            removed.append(str(file_path))
            logger.info(f"Removed old backup: {file_path}")
        except OSError as e:
            logger.warning(f"Failed to remove backup {file_path}: {e}")

    return removed
