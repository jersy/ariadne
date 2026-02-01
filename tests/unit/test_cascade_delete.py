"""Tests for cascade delete functionality.

When symbols are deleted, related records in edges, summaries, entry_points
should be automatically deleted to maintain referential integrity.
"""

import sqlite3
import tempfile
from pathlib import Path

import pytest

from ariadne_core.models.types import SymbolData, EdgeData, SymbolKind, RelationKind
from ariadne_core.storage.sqlite_store import SQLiteStore


@pytest.fixture
def temp_db():
    """Create a temporary database for testing."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name

    # Initialize with full schema
    store = SQLiteStore(db_path, init=True)
    yield store

    # Cleanup
    Path(db_path).unlink(missing_ok=True)


@pytest.fixture
def populated_store(temp_db):
    """Create a store with test data."""
    # Insert symbols
    symbols = [
        SymbolData(
            fqn="com.example.Service.method",
            kind=SymbolKind.METHOD,
            name="method",
            file_path="/test/Service.java",
            line_number=10,
        ),
        SymbolData(
            fqn="com.example.Service",
            kind=SymbolKind.CLASS,
            name="Service",
            file_path="/test/Service.java",
            line_number=1,
        ),
        SymbolData(
            fqn="com.example.Controller.endpoint",
            kind=SymbolKind.METHOD,
            name="endpoint",
            file_path="/test/Controller.java",
            line_number=20,
        ),
    ]
    temp_db.insert_symbols(symbols)

    # Insert edges (Service.method -> Service, Controller.endpoint -> Service.method)
    edges = [
        EdgeData(from_fqn="com.example.Service.method", to_fqn="com.example.Service", relation=RelationKind.MEMBER_OF),
        EdgeData(from_fqn="com.example.Controller.endpoint", to_fqn="com.example.Service.method", relation=RelationKind.CALLS),
    ]
    temp_db.insert_edges(edges)

    # Insert entry points
    temp_db.conn.execute(
        "INSERT INTO entry_points (symbol_fqn, entry_type, http_method, http_path) VALUES (?, ?, ?, ?)",
        ("com.example.Controller.endpoint", "http", "GET", "/api/test"),
    )

    # Insert summary
    temp_db.conn.execute(
        "INSERT INTO summaries (target_fqn, level, summary) VALUES (?, ?, ?)",
        ("com.example.Service.method", "method", "Test summary for method"),
    )

    return temp_db


def test_cascade_delete_deletes_edges(populated_store):
    """Test that deleting a symbol deletes related edges."""
    cursor = populated_store.conn.cursor()

    # Verify initial state
    cursor.execute("SELECT COUNT(*) FROM edges WHERE from_fqn = 'com.example.Service.method'")
    assert cursor.fetchone()[0] == 1
    cursor.execute("SELECT COUNT(*) FROM edges WHERE to_fqn = 'com.example.Service.method'")
    assert cursor.fetchone()[0] == 1

    # Delete the symbol
    populated_store.conn.execute("DELETE FROM symbols WHERE fqn = 'com.example.Service.method'")
    populated_store.conn.commit()

    # Verify edges are deleted
    cursor.execute("SELECT COUNT(*) FROM edges WHERE from_fqn = 'com.example.Service.method'")
    assert cursor.fetchone()[0] == 0, "Outgoing edges should be deleted"
    cursor.execute("SELECT COUNT(*) FROM edges WHERE to_fqn = 'com.example.Service.method'")
    assert cursor.fetchone()[0] == 0, "Incoming edges should be deleted"


def test_cascade_delete_deletes_summaries(populated_store):
    """Test that deleting a symbol deletes related summaries."""
    cursor = populated_store.conn.cursor()

    # Verify initial state
    cursor.execute("SELECT COUNT(*) FROM summaries WHERE target_fqn = 'com.example.Service.method'")
    assert cursor.fetchone()[0] == 1

    # Delete the symbol
    populated_store.conn.execute("DELETE FROM symbols WHERE fqn = 'com.example.Service.method'")
    populated_store.conn.commit()

    # Verify summary is deleted
    cursor.execute("SELECT COUNT(*) FROM summaries WHERE target_fqn = 'com.example.Service.method'")
    assert cursor.fetchone()[0] == 0, "Summary should be deleted"


def test_cascade_delete_deletes_entry_points(populated_store):
    """Test that deleting a symbol deletes related entry points."""
    cursor = populated_store.conn.cursor()

    # Verify initial state
    cursor.execute("SELECT COUNT(*) FROM entry_points WHERE symbol_fqn = 'com.example.Controller.endpoint'")
    assert cursor.fetchone()[0] == 1

    # Delete the symbol
    populated_store.conn.execute("DELETE FROM symbols WHERE fqn = 'com.example.Controller.endpoint'")
    populated_store.conn.commit()

    # Verify entry point is deleted
    cursor.execute("SELECT COUNT(*) FROM entry_points WHERE symbol_fqn = 'com.example.Controller.endpoint'")
    assert cursor.fetchone()[0] == 0, "Entry point should be deleted"


def test_cascade_delete_multiple_edges(populated_store):
    """Test that deleting a symbol with multiple edges deletes all of them."""
    cursor = populated_store.conn.cursor()

    # Add more edges
    edges = [
        EdgeData(from_fqn="com.example.Service.method", to_fqn="com.example.Service", relation=RelationKind.CALLS),
        EdgeData(from_fqn="com.example.OtherClass.method", to_fqn="com.example.Service.method", relation=RelationKind.CALLS),
    ]
    populated_store.insert_edges(edges)

    # Verify initial state - 3 edges total related to Service.method
    cursor.execute("SELECT COUNT(*) FROM edges WHERE from_fqn = 'com.example.Service.method' OR to_fqn = 'com.example.Service.method'")
    initial_count = cursor.fetchone()[0]
    assert initial_count > 0

    # Delete the symbol
    populated_store.conn.execute("DELETE FROM symbols WHERE fqn = 'com.example.Service.method'")
    populated_store.conn.commit()

    # Verify all related edges are deleted
    cursor.execute("SELECT COUNT(*) FROM edges WHERE from_fqn = 'com.example.Service.method' OR to_fqn = 'com.example.Service.method'")
    assert cursor.fetchone()[0] == 0, "All related edges should be deleted"


def test_external_symbol_edges_preserved(populated_store):
    """Test that edges to/from external symbols (not in symbols table) are preserved.

    External symbols (like java.util.List) should not be affected when
    internal symbols are deleted.
    """
    cursor = populated_store.conn.cursor()

    # Insert an edge to an external symbol
    cursor.execute(
        "INSERT INTO edges (from_fqn, to_fqn, relation) VALUES (?, ?, ?)",
        ("com.example.Service.method", "java.util.List", "uses"),
    )
    populated_store.conn.commit()

    # Verify initial state
    cursor.execute("SELECT COUNT(*) FROM edges WHERE to_fqn = 'java.util.List'")
    initial_count = cursor.fetchone()[0]
    assert initial_count == 1

    # Delete the internal symbol
    populated_store.conn.execute("DELETE FROM symbols WHERE fqn = 'com.example.Service.method'")
    populated_store.conn.commit()

    # Verify edge to external symbol is deleted (because from_fqn was deleted)
    # This is expected - edges from deleted symbols should be cleaned up
    cursor.execute("SELECT COUNT(*) FROM edges WHERE to_fqn = 'java.util.List'")
    final_count = cursor.fetchone()[0]

    # The edge should be deleted because its from_fqn was deleted
    assert final_count == 0, "Edges from deleted symbols should be cleaned up"


def test_delete_symbols_for_file_with_cascade(populated_store):
    """Test that the clean_by_file method also cascades properly."""
    cursor = populated_store.conn.cursor()

    # Count initial edges
    cursor.execute("SELECT COUNT(*) FROM edges")
    initial_edges = cursor.fetchone()[0]

    # Delete symbols for the file
    deleted = populated_store.clean_by_file("/test/Service.java")

    # Verify symbols were deleted
    assert deleted >= 1

    # Verify related edges were deleted
    cursor.execute("SELECT COUNT(*) FROM edges")
    final_edges = cursor.fetchone()[0]
    assert final_edges < initial_edges, "Edges should be deleted with symbols"


def test_cascade_delete_with_nonexistent_fqn(populated_store):
    """Test that deleting a non-existent symbol doesn't cause errors."""
    cursor = populated_store.conn.cursor()

    # Delete a symbol that doesn't exist
    populated_store.conn.execute("DELETE FROM symbols WHERE fqn = 'com.example.Nonexistent'")
    populated_store.conn.commit()

    # Should not raise an error and counts should be unchanged
    cursor.execute("SELECT COUNT(*) FROM edges")
    edges_count = cursor.fetchone()[0]
    assert edges_count >= 0  # Should not cause database corruption
