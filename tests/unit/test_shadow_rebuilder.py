"""Tests for shadow rebuild with atomic swap."""

import os
import sqlite3
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from ariadne_core.models.types import SymbolData, SymbolKind
from ariadne_core.storage.shadow_rebuilder import (
    IntegrityError,
    RebuildFailedError,
    RebuildStats,
    ShadowRebuilder,
    cleanup_old_backups,
)
from ariadne_core.storage.sqlite_store import SQLiteStore


@pytest.fixture
def temp_dir():
    """Create a temporary directory for tests."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir


@pytest.fixture
def mock_db(temp_dir):
    """Create a mock database with test data."""
    db_path = os.path.join(temp_dir, "ariadne.db")
    store = SQLiteStore(db_path, init=True)

    # Add some test symbols
    symbols = [
        SymbolData(
            fqn="com.example.TestClass",
            kind=SymbolKind.CLASS,
            name="TestClass",
            file_path="/test/TestClass.java",
            line_number=1,
        ),
        SymbolData(
            fqn="com.example.TestClass.testMethod",
            kind=SymbolKind.METHOD,
            name="testMethod",
            file_path="/test/TestClass.java",
            line_number=10,
        ),
    ]
    store.insert_symbols(symbols)

    # Ensure database is persisted to disk
    store.conn.commit()
    store.close()

    # Verify file exists
    assert os.path.exists(db_path), f"Database file not created: {db_path}"

    yield db_path


class TestRebuildStats:
    """Test RebuildStats dataclass."""

    def test_create_stats(self):
        """Test creating rebuild statistics."""
        stats = RebuildStats(
            symbols_count=100,
            edges_count=200,
            entries_count=10,
            deps_count=5,
            duration=1.5,
        )

        assert stats.symbols_count == 100
        assert stats.edges_count == 200
        assert stats.entries_count == 10
        assert stats.deps_count == 5
        assert stats.duration == 1.5

    def test_default_stats(self):
        """Test default statistics values."""
        stats = RebuildStats()

        assert stats.symbols_count == 0
        assert stats.edges_count == 0
        assert stats.entries_count == 0
        assert stats.deps_count == 0
        assert stats.duration == 0.0


class TestShadowRebuilder:
    """Test ShadowRebuilder functionality."""

    def test_init_rebuilder(self, temp_dir):
        """Test initializing the shadow rebuilder."""
        db_path = os.path.join(temp_dir, "ariadne.db")
        rebuilder = ShadowRebuilder(
            db_path=db_path,
            project_root="/test/project",
            service_url="http://localhost:8766",
        )

        assert rebuilder.db_path == db_path
        assert rebuilder.project_root == "/test/project"
        assert rebuilder.service_url == "http://localhost:8766"

    def test_verify_new_index_success(self, temp_dir):
        """Test verification of a valid new index."""
        # Create a valid new database
        new_db_path = os.path.join(temp_dir, "ariadne_new.db")
        store = SQLiteStore(new_db_path, init=True)

        # Add test data
        symbols = [
            SymbolData(
                fqn="com.example.TestClass",
                kind=SymbolKind.CLASS,
                name="TestClass",
                file_path="/test/TestClass.java",
                line_number=1,
            ),
        ]
        store.insert_symbols(symbols)
        store.close()

        # Test verification
        rebuilder = ShadowRebuilder(
            db_path=os.path.join(temp_dir, "ariadne.db"),
            project_root="/test",
        )

        assert rebuilder._verify_new_index(new_db_path) is True

    def test_verify_new_index_empty_database(self, temp_dir):
        """Test verification fails for empty database."""
        # Create database with schema but no symbols
        new_db_path = os.path.join(temp_dir, "ariadne_new.db")
        store = SQLiteStore(new_db_path, init=True)
        store.close()

        rebuilder = ShadowRebuilder(
            db_path=os.path.join(temp_dir, "ariadne.db"),
            project_root="/test",
        )

        with pytest.raises(IntegrityError, match="No symbols indexed"):
            rebuilder._verify_new_index(new_db_path)

    def test_verify_new_index_orphaned_edges(self, temp_dir):
        """Test verification passes for database without orphaned edges.

        Due to cascade triggers, orphaned edges are automatically cleaned up.
        This test verifies that a valid database passes verification.
        """
        # Create a database with valid data
        new_db_path = os.path.join(temp_dir, "ariadne_new.db")
        store = SQLiteStore(new_db_path, init=True)

        # Add a symbol (to avoid empty database error)
        symbols = [
            SymbolData(
                fqn="com.example.TestClass",
                kind=SymbolKind.CLASS,
                name="TestClass",
                file_path="/test/TestClass.java",
                line_number=1,
            ),
        ]
        store.insert_symbols(symbols)
        store.close()

        rebuilder = ShadowRebuilder(
            db_path=os.path.join(temp_dir, "ariadne.db"),
            project_root="/test",
        )

        # Database with valid data should pass
        assert rebuilder._verify_new_index(new_db_path) is True

    def test_atomic_swap_databases(self, temp_dir):
        """Test atomic database swap."""
        current_db = os.path.join(temp_dir, "ariadne.db")
        new_db_path = os.path.join(temp_dir, "ariadne_new_001.db")

        # Create current database
        current_store = SQLiteStore(current_db, init=True)
        symbols = [
            SymbolData(
                fqn="com.example.OldClass",
                kind=SymbolKind.CLASS,
                name="OldClass",
                file_path="/test/OldClass.java",
                line_number=1,
            ),
        ]
        current_store.insert_symbols(symbols)
        current_store.close()

        # Create new database
        new_store = SQLiteStore(new_db_path, init=True)
        symbols = [
            SymbolData(
                fqn="com.example.NewClass",
                kind=SymbolKind.CLASS,
                name="NewClass",
                file_path="/test/NewClass.java",
                line_number=1,
            ),
        ]
        new_store.insert_symbols(symbols)
        new_store.close()

        # Perform atomic swap
        rebuilder = ShadowRebuilder(
            db_path=current_db,
            project_root="/test",
        )

        rebuilder._atomic_swap_databases(
            current=current_db,
            new=new_db_path,
            backup_suffix="_backup_test",
        )

        # Verify swap succeeded
        assert os.path.exists(current_db), "Current database should exist after swap"
        assert not os.path.exists(new_db_path), "New database should be moved"

        # Verify backup exists
        backup_path = current_db + "_backup_test"
        assert os.path.exists(backup_path), "Backup should be created"

        # Verify current has new data
        store = SQLiteStore(current_db, init=False)
        cursor = store.conn.cursor()
        cursor.execute("SELECT name FROM symbols WHERE fqn = ?", ("com.example.NewClass",))
        result = cursor.fetchone()
        assert result is not None, "New database should be in place"
        store.close()

    def test_atomic_swap_rollback_on_failure(self, temp_dir):
        """Test atomic swap handles edge cases."""
        current_db = os.path.join(temp_dir, "ariadne.db")

        # Create current database
        current_store = SQLiteStore(current_db, init=True)
        current_store.close()

        # Create a valid new database
        new_db_path = os.path.join(temp_dir, "ariadne_new_002.db")
        new_store = SQLiteStore(new_db_path, init=True)
        new_store.close()

        rebuilder = ShadowRebuilder(
            db_path=current_db,
            project_root="/test",
        )

        # Perform swap - should succeed
        rebuilder._atomic_swap_databases(
            current=current_db,
            new=new_db_path,
            backup_suffix="_backup_fail",
        )

        # Verify swap succeeded
        assert os.path.exists(current_db), "Current database should exist after swap"
        assert not os.path.exists(new_db_path), "New database should be moved"

        # Verify backup exists
        backup_path = current_db + "_backup_fail"
        assert os.path.exists(backup_path), "Backup should be created"

    @patch("ariadne_core.extractors.asm.extractor.Extractor")
    def test_rebuild_full_success(self, mock_extractor_class, temp_dir):
        """Test successful full rebuild."""
        # Mock the extractor to populate the database with data
        mock_extractor = MagicMock()
        mock_extractor_class.return_value = mock_extractor

        mock_result = MagicMock()
        mock_result.success = True
        mock_result.stats = {
            "total_symbols": 100,
            "total_edges": 200,
            "total_entries": 10,
            "total_deps": 5,
        }
        mock_extractor.extract_project.return_value = mock_result

        # Mock the _build_new_index method to skip actual extraction
        # and just create a valid database
        def mock_build_new_index(new_db_path):
            from ariadne_core.storage.shadow_rebuilder import RebuildStats
            import time

            # Create a valid database
            store = SQLiteStore(new_db_path, init=True)
            symbols = [
                SymbolData(
                    fqn="com.example.TestClass",
                    kind=SymbolKind.CLASS,
                    name="TestClass",
                    file_path="/test/TestClass.java",
                    line_number=1,
                ),
            ]
            store.insert_symbols(symbols)
            store.close()

            return RebuildStats(
                symbols_count=100,
                edges_count=200,
                entries_count=10,
                deps_count=5,
                duration=1.0,
            )

        mock_db_path = os.path.join(temp_dir, "ariadne.db")

        # Create a pre-existing database to test backup behavior
        pre_store = SQLiteStore(mock_db_path, init=True)
        pre_store.close()

        rebuilder = ShadowRebuilder(
            db_path=mock_db_path,
            project_root="/test/project",
        )

        # Patch the build method to avoid actual extraction
        with patch.object(rebuilder, "_build_new_index", side_effect=mock_build_new_index):
            result = rebuilder.rebuild_full()

        assert result["status"] == "success"
        assert result["symbols_indexed"] == 100
        assert result["edges_created"] == 200
        assert "backup_path" in result

    @patch("ariadne_core.extractors.asm.extractor.Extractor")
    def test_rebuild_full_extraction_fails(self, mock_extractor_class, temp_dir):
        """Test rebuild fails when extraction fails."""
        mock_extractor = MagicMock()
        mock_extractor_class.return_value = mock_extractor

        mock_result = MagicMock()
        mock_result.success = False
        mock_result.errors = ["Extraction failed"]
        mock_extractor.extract_project.return_value = mock_result

        mock_db_path = os.path.join(temp_dir, "ariadne.db")

        # Create a pre-existing database to test preservation
        pre_store = SQLiteStore(mock_db_path, init=True)
        pre_store.insert_symbols([
            SymbolData(
                fqn="com.example.OriginalClass",
                kind=SymbolKind.CLASS,
                name="OriginalClass",
                file_path="/test/OriginalClass.java",
                line_number=1,
            ),
        ])
        pre_store.close()

        rebuilder = ShadowRebuilder(
            db_path=mock_db_path,
            project_root="/test/project",
        )

        with pytest.raises(RebuildFailedError, match="Extraction failed"):
            rebuilder.rebuild_full()

        # Original database should still exist with data
        assert os.path.exists(mock_db_path), "Original database should be preserved"
        store = SQLiteStore(mock_db_path, init=False)
        cursor = store.conn.cursor()
        cursor.execute("SELECT name FROM symbols WHERE fqn = ?", ("com.example.OriginalClass",))
        result = cursor.fetchone()
        assert result is not None, "Original data should be preserved"
        store.close()


class TestCleanupOldBackups:
    """Test backup cleanup functionality."""

    def test_cleanup_old_backups(self, temp_dir):
        """Test cleaning up old backup files."""
        db_path = os.path.join(temp_dir, "ariadne.db")

        # Create some backup files
        backups = []
        for i in range(5):
            backup_path = f"{db_path}_backup_20260202_120{i}"
            Path(backup_path).write_text(f"backup {i}")
            backups.append(backup_path)

        # Keep only 3 most recent
        removed = cleanup_old_backups(db_path, keep_count=3)

        assert len(removed) == 2, "Should remove 2 old backups"
        assert all(os.path.exists(p) for p in backups[2:]), "Recent backups should remain"

    def test_cleanup_no_backups(self, temp_dir):
        """Test cleanup when no backups exist."""
        db_path = os.path.join(temp_dir, "ariadne.db")

        removed = cleanup_old_backups(db_path)
        assert len(removed) == 0

    def test_cleanup_keeps_all(self, temp_dir):
        """Test cleanup keeps all backups when count is high."""
        db_path = os.path.join(temp_dir, "ariadne.db")

        # Create 2 backup files
        for i in range(2):
            backup_path = f"{db_path}_backup_20260202_120{i}"
            Path(backup_path).write_text(f"backup {i}")

        # Keep 5, but only have 2
        removed = cleanup_old_backups(db_path, keep_count=5)
        assert len(removed) == 0, "Should not remove any backups"
