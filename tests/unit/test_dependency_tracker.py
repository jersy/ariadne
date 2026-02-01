"""Tests for DependencyTracker."""

import sqlite3
import tempfile
from pathlib import Path

import pytest

from ariadne_analyzer.l1_business.dependency_tracker import (
    AffectedSymbols,
    DependencyTracker,
)
from ariadne_core.models.types import EdgeData, RelationKind, SymbolData, SymbolKind
from ariadne_core.storage.sqlite_store import SQLiteStore
from ariadne_core.storage.schema import ALL_SCHEMAS


@pytest.fixture
def temp_db():
    """Create a temporary database for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        store = SQLiteStore(str(db_path), init=True)
        yield store
        store.close()


@pytest.fixture
def populated_store(temp_db):
    """Create a store with test data."""
    # Create test symbols
    symbols = [
        SymbolData(
            fqn="com.example.ClassA",
            kind=SymbolKind.CLASS,
            name="ClassA",
            parent_fqn=None,
        ),
        SymbolData(
            fqn="com.example.ClassA.methodA()",
            kind=SymbolKind.METHOD,
            name="methodA",
            signature="public void methodA()",
            parent_fqn="com.example.ClassA",
        ),
        SymbolData(
            fqn="com.example.ClassA.methodB()",
            kind=SymbolKind.METHOD,
            name="methodB",
            signature="public void methodB()",
            parent_fqn="com.example.ClassA",
        ),
        SymbolData(
            fqn="com.example.ClassB",
            kind=SymbolKind.CLASS,
            name="ClassB",
            parent_fqn=None,
        ),
        SymbolData(
            fqn="com.example.ClassB.callMethodA()",
            kind=SymbolKind.METHOD,
            name="callMethodA",
            signature="public void callMethodA()",
            parent_fqn="com.example.ClassB",
        ),
        SymbolData(
            fqn="com.example.ClassC",
            kind=SymbolKind.CLASS,
            name="ClassC",
            parent_fqn=None,
        ),
        SymbolData(
            fqn="com.example.ClassC.callMethodB()",
            kind=SymbolKind.METHOD,
            name="callMethodB",
            signature="public void callMethodB()",
            parent_fqn="com.example.ClassC",
        ),
    ]

    temp_db.insert_symbols(symbols)

    # Create test edges (CALLS relationships)
    edges = [
        # ClassB.callMethodA() calls ClassA.methodA()
        EdgeData(
            from_fqn="com.example.ClassB.callMethodA()",
            to_fqn="com.example.ClassA.methodA()",
            relation=RelationKind.CALLS,
        ),
        # ClassC.callMethodB() calls ClassA.methodB()
        EdgeData(
            from_fqn="com.example.ClassC.callMethodB()",
            to_fqn="com.example.ClassA.methodB()",
            relation=RelationKind.CALLS,
        ),
    ]

    temp_db.insert_edges(edges)

    return temp_db


class TestDependencyTracker:
    """Test suite for DependencyTracker."""

    def test_get_affected_symbols_basic(self, populated_store):
        """Test basic affected symbol detection."""
        tracker = DependencyTracker(populated_store)

        # Change ClassA.methodA()
        changed = ["com.example.ClassA.methodA()"]
        affected = tracker.get_affected_symbols(changed)

        # Should include changed symbol, its caller, and parent class
        assert "com.example.ClassA.methodA()" in affected.changed
        assert "com.example.ClassB.callMethodA()" in affected.dependents
        # Parent class is also included as a dependent
        assert "com.example.ClassA" in affected.total_set
        assert affected.total == 3  # changed + caller + parent

    def test_get_affected_symbols_parent(self, populated_store):
        """Test that parent symbols are included as affected."""
        tracker = DependencyTracker(populated_store)

        # Change a method
        changed = ["com.example.ClassA.methodA()"]
        affected = tracker.get_affected_symbols(changed)

        # Parent class should be in affected
        assert "com.example.ClassA" in affected.total_set

    def test_get_affected_symbols_multiple_changes(self, populated_store):
        """Test affected symbols for multiple changes."""
        tracker = DependencyTracker(populated_store)

        # Change both methods in ClassA
        changed = [
            "com.example.ClassA.methodA()",
            "com.example.ClassA.methodB()",
        ]
        affected = tracker.get_affected_symbols(changed)

        # Should include both changed methods and their callers
        assert "com.example.ClassA.methodA()" in affected.changed
        assert "com.example.ClassA.methodB()" in affected.changed
        assert "com.example.ClassB.callMethodA()" in affected.dependents
        assert "com.example.ClassC.callMethodB()" in affected.dependents

    def test_get_affected_symbols_no_dependencies(self, populated_store):
        """Test when there are no dependencies."""
        tracker = DependencyTracker(populated_store)

        # Change a symbol with no dependencies
        changed = ["com.example.ClassB"]
        affected = tracker.get_affected_symbols(changed)

        assert affected.changed == [changed[0]]
        assert len(affected.dependents) == 0

    def test_get_callers(self, populated_store):
        """Test getting callers of a symbol."""
        tracker = DependencyTracker(populated_store)

        callers = tracker.get_callers("com.example.ClassA.methodA()")

        assert len(callers) == 1
        assert callers[0]["fqn"] == "com.example.ClassB.callMethodA()"

    def test_get_callees(self, populated_store):
        """Test getting callees of a symbol."""
        tracker = DependencyTracker(populated_store)

        callees = tracker.get_callees("com.example.ClassB.callMethodA()")

        assert len(callees) == 1
        assert callees[0]["fqn"] == "com.example.ClassA.methodA()"

    def test_get_parent_symbol(self, populated_store):
        """Test getting parent symbol."""
        tracker = DependencyTracker(populated_store)

        parent = tracker.get_parent_symbol("com.example.ClassA.methodA()")

        assert parent is not None
        assert parent["fqn"] == "com.example.ClassA"

    def test_get_parent_symbol_no_parent(self, populated_store):
        """Test getting parent when none exists."""
        tracker = DependencyTracker(populated_store)

        parent = tracker.get_parent_symbol("com.example.ClassA")

        assert parent is None

    def test_get_children_symbols(self, populated_store):
        """Test getting children symbols."""
        tracker = DependencyTracker(populated_store)

        children = tracker.get_children_symbols("com.example.ClassA")

        assert len(children) == 2
        fqns = {c["fqn"] for c in children}
        assert "com.example.ClassA.methodA()" in fqns
        assert "com.example.ClassA.methodB()" in fqns


class TestAffectedSymbols:
    """Test AffectedSymbols dataclass."""

    def test_affected_symbols_computation(self):
        """Test that total and total_set are computed correctly."""
        affected = AffectedSymbols(
            changed=["symbol1", "symbol2"],
            dependents=["symbol3", "symbol4"],
        )

        assert affected.total == 4
        assert affected.total_set == {"symbol1", "symbol2", "symbol3", "symbol4"}

    def test_affected_symbols_empty_dependents(self):
        """Test with no dependents."""
        affected = AffectedSymbols(changed=["symbol1"])

        assert affected.total == 1
        assert affected.total_set == {"symbol1"}

    def test_affected_symbols_overlap(self):
        """Test when changed and dependents overlap."""
        # This shouldn't happen in practice but test the logic
        affected = AffectedSymbols(
            changed=["symbol1", "symbol2"],
            dependents=["symbol2", "symbol3"],  # symbol2 is in both
        )

        assert affected.total == 3
        assert affected.total_set == {"symbol1", "symbol2", "symbol3"}
