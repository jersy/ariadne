"""Unit tests for SQLiteStore."""

import tempfile
from pathlib import Path

import pytest

from ariadne_core.models.types import EdgeData, RelationKind, SymbolData, SymbolKind
from ariadne_core.storage.sqlite_store import SQLiteStore


@pytest.fixture
def store():
    """Create a temporary SQLite store for testing."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    store = SQLiteStore(db_path, init=True)
    yield store
    store.close()
    Path(db_path).unlink(missing_ok=True)


class TestSymbols:
    def test_insert_and_get_symbol(self, store: SQLiteStore):
        symbol = SymbolData(
            fqn="com.example.UserService",
            kind=SymbolKind.CLASS,
            name="UserService",
            file_path="/path/to/UserService.java",
            line_number=10,
            modifiers=["public"],
            annotations=["@Service"],
        )
        store.insert_symbols([symbol])

        result = store.get_symbol("com.example.UserService")
        assert result is not None
        assert result["fqn"] == "com.example.UserService"
        assert result["kind"] == "class"
        assert result["name"] == "UserService"
        assert result["line_number"] == 10

    def test_get_symbols_by_kind(self, store: SQLiteStore):
        symbols = [
            SymbolData(fqn="com.example.User", kind=SymbolKind.CLASS, name="User"),
            SymbolData(fqn="com.example.Order", kind=SymbolKind.CLASS, name="Order"),
            SymbolData(fqn="com.example.User.getName", kind=SymbolKind.METHOD, name="getName"),
        ]
        store.insert_symbols(symbols)

        classes = store.get_symbols_by_kind("class")
        assert len(classes) == 2

        methods = store.get_symbols_by_kind("method")
        assert len(methods) == 1

    def test_search_symbols(self, store: SQLiteStore):
        symbols = [
            SymbolData(fqn="com.example.UserService", kind=SymbolKind.CLASS, name="UserService"),
            SymbolData(fqn="com.example.UserRepository", kind=SymbolKind.CLASS, name="UserRepository"),
            SymbolData(fqn="com.example.OrderService", kind=SymbolKind.CLASS, name="OrderService"),
        ]
        store.insert_symbols(symbols)

        results = store.search_symbols("User")
        assert len(results) == 2

        results = store.search_symbols("Service", kind="class")
        assert len(results) == 2

    def test_get_symbol_count(self, store: SQLiteStore):
        symbols = [
            SymbolData(fqn="com.example.A", kind=SymbolKind.CLASS, name="A"),
            SymbolData(fqn="com.example.B", kind=SymbolKind.CLASS, name="B"),
        ]
        store.insert_symbols(symbols)

        assert store.get_symbol_count() == 2


class TestEdges:
    def test_insert_and_get_edges(self, store: SQLiteStore):
        # First insert symbols for foreign key constraint
        store.insert_symbols([
            SymbolData(fqn="com.example.A", kind=SymbolKind.CLASS, name="A"),
            SymbolData(fqn="com.example.B", kind=SymbolKind.CLASS, name="B"),
        ])
        edge = EdgeData(
            from_fqn="com.example.A",
            to_fqn="com.example.B",
            relation=RelationKind.CALLS,
            metadata={"line": 42},
        )
        store.insert_edges([edge])

        from_edges = store.get_edges_from("com.example.A")
        assert len(from_edges) == 1
        assert from_edges[0]["to_fqn"] == "com.example.B"

        to_edges = store.get_edges_to("com.example.B")
        assert len(to_edges) == 1
        assert to_edges[0]["from_fqn"] == "com.example.A"

    def test_get_edges_by_relation(self, store: SQLiteStore):
        # First insert symbols for foreign key constraint
        store.insert_symbols([
            SymbolData(fqn="A", kind=SymbolKind.CLASS, name="A"),
            SymbolData(fqn="B", kind=SymbolKind.CLASS, name="B"),
            SymbolData(fqn="C", kind=SymbolKind.CLASS, name="C"),
        ])
        edges = [
            EdgeData(from_fqn="A", to_fqn="B", relation=RelationKind.CALLS),
            EdgeData(from_fqn="A", to_fqn="C", relation=RelationKind.INHERITS),
        ]
        store.insert_edges(edges)

        call_edges = store.get_edges_from("A", relation="calls")
        assert len(call_edges) == 1
        assert call_edges[0]["to_fqn"] == "B"


class TestGraphTraversal:
    def test_call_chain(self, store: SQLiteStore):
        # First insert symbols for foreign key constraint
        store.insert_symbols([
            SymbolData(fqn="A", kind=SymbolKind.CLASS, name="A"),
            SymbolData(fqn="B", kind=SymbolKind.CLASS, name="B"),
            SymbolData(fqn="C", kind=SymbolKind.CLASS, name="C"),
            SymbolData(fqn="D", kind=SymbolKind.CLASS, name="D"),
        ])
        # Create a call chain: A -> B -> C -> D
        edges = [
            EdgeData(from_fqn="A", to_fqn="B", relation=RelationKind.CALLS),
            EdgeData(from_fqn="B", to_fqn="C", relation=RelationKind.CALLS),
            EdgeData(from_fqn="C", to_fqn="D", relation=RelationKind.CALLS),
        ]
        store.insert_edges(edges)

        chain = store.get_call_chain("A", max_depth=10)
        assert len(chain) == 3
        assert chain[0]["depth"] == 0
        assert chain[0]["to_fqn"] == "B"

    def test_reverse_callers(self, store: SQLiteStore):
        # First insert symbols for foreign key constraint
        store.insert_symbols([
            SymbolData(fqn="A", kind=SymbolKind.CLASS, name="A"),
            SymbolData(fqn="B", kind=SymbolKind.CLASS, name="B"),
            SymbolData(fqn="C", kind=SymbolKind.CLASS, name="C"),
        ])
        # A and B both call C
        edges = [
            EdgeData(from_fqn="A", to_fqn="C", relation=RelationKind.CALLS),
            EdgeData(from_fqn="B", to_fqn="C", relation=RelationKind.CALLS),
        ]
        store.insert_edges(edges)

        callers = store.get_reverse_callers("C")
        assert len(callers) == 2
        caller_fqns = {c["from_fqn"] for c in callers}
        assert caller_fqns == {"A", "B"}


class TestMetadata:
    def test_set_and_get_metadata(self, store: SQLiteStore):
        store.set_metadata("version", "1.0.0")
        assert store.get_metadata("version") == "1.0.0"

    def test_update_metadata(self, store: SQLiteStore):
        store.set_metadata("key", "value1")
        store.set_metadata("key", "value2")
        assert store.get_metadata("key") == "value2"


class TestCleanup:
    def test_clean_all(self, store: SQLiteStore):
        store.insert_symbols([
            SymbolData(fqn="A", kind=SymbolKind.CLASS, name="A"),
            SymbolData(fqn="B", kind=SymbolKind.CLASS, name="B"),
        ])
        store.insert_edges([
            EdgeData(from_fqn="A", to_fqn="B", relation=RelationKind.CALLS),
        ])

        counts = store.clean_all()
        assert counts["symbols"] == 2
        assert counts["edges"] == 1
        assert store.get_symbol_count() == 0

    def test_clean_by_file(self, store: SQLiteStore):
        store.insert_symbols([
            SymbolData(fqn="A", kind=SymbolKind.CLASS, name="A", file_path="/path/a.java"),
            SymbolData(fqn="B", kind=SymbolKind.CLASS, name="B", file_path="/path/b.java"),
        ])
        store.insert_edges([
            EdgeData(from_fqn="A", to_fqn="B", relation=RelationKind.CALLS),
        ])

        deleted = store.clean_by_file("/path/a.java")
        assert deleted == 1
        assert store.get_symbol("A") is None
        assert store.get_symbol("B") is not None


class TestBatchCreateSummaries:
    """Tests for batch_create_summaries() method (Phase 4.1)."""

    def test_batch_create_empty_list(self, store: SQLiteStore):
        """Test batch create with empty list returns 0."""
        from ariadne_core.models.types import SummaryData, SummaryLevel

        count = store.batch_create_summaries([])
        assert count == 0

    def test_batch_create_single_summary(self, store: SQLiteStore):
        """Test batch create with single summary."""
        from ariadne_core.models.types import SummaryData, SummaryLevel, SymbolKind

        # First create the symbol for foreign key constraint
        store.insert_symbols([
            SymbolData(
                fqn="com.example.ClassA",
                kind=SymbolKind.CLASS,
                name="ClassA",
            )
        ])

        summary = SummaryData(
            target_fqn="com.example.ClassA",
            level=SummaryLevel.CLASS,
            summary="Test summary",
            is_stale=False,
        )
        count = store.batch_create_summaries([summary])
        assert count == 1

        # Verify in database
        result = store.get_summary("com.example.ClassA")
        assert result is not None
        assert result["summary"] == "Test summary"
        assert result["is_stale"] == 0

    def test_batch_create_multiple_summaries(self, store: SQLiteStore):
        """Test batch create with multiple summaries."""
        from ariadne_core.models.types import SummaryData, SummaryLevel, SymbolKind

        # Create symbols for foreign key constraint
        symbols = [
            SymbolData(fqn=f"com.example.Class{i}", kind=SymbolKind.CLASS, name=f"Class{i}")
            for i in range(10)
        ]
        store.insert_symbols(symbols)

        summaries = [
            SummaryData(
                target_fqn=f"com.example.Class{i}",
                level=SummaryLevel.CLASS,
                summary=f"Summary {i}",
                is_stale=False,
            )
            for i in range(10)
        ]

        count = store.batch_create_summaries(summaries)
        assert count == 10

        # Verify all in database
        for i in range(10):
            fqn = f"com.example.Class{i}"
            result = store.get_summary(fqn)
            assert result is not None
            assert result["summary"] == f"Summary {i}"

    def test_batch_upsert_replaces_existing(self, store: SQLiteStore):
        """Test batch upsert replaces existing summaries."""
        from ariadne_core.models.types import SummaryData, SummaryLevel, SymbolKind

        # Create the symbol
        store.insert_symbols([
            SymbolData(fqn="com.example.ClassA", kind=SymbolKind.CLASS, name="ClassA")
        ])

        # Create initial summary
        summary1 = SummaryData(
            target_fqn="com.example.ClassA",
            level=SummaryLevel.CLASS,
            summary="Original summary",
            is_stale=True,
        )
        store.create_summary(summary1)

        # Batch create updated version
        summary2 = SummaryData(
            target_fqn="com.example.ClassA",
            level=SummaryLevel.CLASS,
            summary="Updated summary",
            is_stale=False,
        )
        count = store.batch_create_summaries([summary2])
        assert count == 1

        # Verify updated
        result = store.get_summary("com.example.ClassA")
        assert result["summary"] == "Updated summary"
        assert result["is_stale"] == 0

    def test_batch_create_mixed_levels(self, store: SQLiteStore):
        """Test batch create with different summary levels."""
        from ariadne_core.models.types import SummaryData, SummaryLevel, SymbolKind

        # Create symbols for foreign key constraint
        store.insert_symbols([
            SymbolData(fqn="com.example.MyClass", kind=SymbolKind.CLASS, name="MyClass"),
            SymbolData(fqn="com.example.myMethod", kind=SymbolKind.METHOD, name="myMethod"),
        ])

        summaries = [
            SummaryData(
                target_fqn="com.example.MyClass",
                level=SummaryLevel.CLASS,
                summary="Class summary",
                is_stale=False,
            ),
            SummaryData(
                target_fqn="com.example.myMethod",
                level=SummaryLevel.METHOD,
                summary="Method summary",
                is_stale=False,
            ),
        ]

        count = store.batch_create_summaries(summaries)
        assert count == 2

        # Verify correct levels
        class_result = store.get_summary("com.example.MyClass")
        method_result = store.get_summary("com.example.myMethod")
        assert class_result["level"] == "class"
        assert method_result["level"] == "method"
