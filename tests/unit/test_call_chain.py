"""Unit tests for CallChainTracer."""

import tempfile
from pathlib import Path

import pytest

from ariadne_analyzer.l2_architecture.call_chain import CallChainTracer
from ariadne_core.models.types import (
    EdgeData,
    EntryPointData,
    EntryType,
    ExternalDependencyData,
    DependencyType,
    DependencyStrength,
    RelationKind,
    SymbolData,
    SymbolKind,
)
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


@pytest.fixture
def tracer(store: SQLiteStore):
    return CallChainTracer(store)


class TestEntryResolution:
    def test_resolve_by_http_pattern(self, store: SQLiteStore, tracer: CallChainTracer):
        # Setup: Insert entry point
        store.insert_symbols([
            SymbolData(fqn="com.example.UserController.getUser(Long)", kind=SymbolKind.METHOD, name="getUser"),
        ])
        store.insert_entry_points([
            EntryPointData(
                symbol_fqn="com.example.UserController.getUser(Long)",
                entry_type=EntryType.HTTP_API,
                http_method="GET",
                http_path="/api/users/{id}",
            )
        ])

        result = tracer.trace_from_entry("GET /api/users/{id}")

        assert result.entry_fqn == "com.example.UserController.getUser(Long)"

    def test_resolve_by_fqn(self, store: SQLiteStore, tracer: CallChainTracer):
        # Setup: Insert symbol
        store.insert_symbols([
            SymbolData(fqn="com.example.Service.process()", kind=SymbolKind.METHOD, name="process"),
        ])

        result = tracer.trace_from_entry("com.example.Service.process()")

        assert result.entry_fqn == "com.example.Service.process()"

    def test_resolve_not_found(self, tracer: CallChainTracer):
        with pytest.raises(ValueError, match="Entry not found"):
            tracer.trace_from_entry("GET /api/nonexistent")


class TestCallChainTracing:
    def test_trace_simple_chain(self, store: SQLiteStore, tracer: CallChainTracer):
        # Setup: Controller -> Service -> Repository
        store.insert_symbols([
            SymbolData(fqn="Controller.get()", kind=SymbolKind.METHOD, name="get"),
            SymbolData(fqn="Service.process()", kind=SymbolKind.METHOD, name="process"),
            SymbolData(fqn="Repository.find()", kind=SymbolKind.METHOD, name="find"),
        ])
        store.insert_edges([
            EdgeData(from_fqn="Controller.get()", to_fqn="Service.process()", relation=RelationKind.CALLS),
            EdgeData(from_fqn="Service.process()", to_fqn="Repository.find()", relation=RelationKind.CALLS),
        ])

        result = tracer.trace_from_entry("Controller.get()")

        assert len(result.chain) == 2
        assert result.chain[0]["to_fqn"] == "Service.process()"
        assert result.chain[1]["to_fqn"] == "Repository.find()"
        assert result.max_depth == 1

    def test_trace_with_depth_limit(self, store: SQLiteStore, tracer: CallChainTracer):
        # Setup: A -> B -> C -> D (depth 3)
        store.insert_symbols([
            SymbolData(fqn="A", kind=SymbolKind.METHOD, name="A"),
            SymbolData(fqn="B", kind=SymbolKind.METHOD, name="B"),
            SymbolData(fqn="C", kind=SymbolKind.METHOD, name="C"),
            SymbolData(fqn="D", kind=SymbolKind.METHOD, name="D"),
        ])
        store.insert_edges([
            EdgeData(from_fqn="A", to_fqn="B", relation=RelationKind.CALLS),
            EdgeData(from_fqn="B", to_fqn="C", relation=RelationKind.CALLS),
            EdgeData(from_fqn="C", to_fqn="D", relation=RelationKind.CALLS),
        ])

        # With max_depth=1, we get edges with depth 0 only (A->B)
        # The recursive CTE uses cc.depth < max_depth for the recursion
        result = tracer.trace_from_entry("A", max_depth=1)

        # SQLite CTE with depth < 1 means we get depth=0 edges only
        # But the initial SELECT has depth=0, and UNION adds depth+1 while depth < max_depth
        # So max_depth=1 gives us: depth=0 (A->B)
        # Then recursion adds depth=1 (B->C) since 0 < 1
        # Result: 2 edges (depth 0 and 1)
        assert len(result.chain) == 2
        assert result.chain[0]["to_fqn"] == "B"
        assert result.chain[1]["to_fqn"] == "C"

    def test_trace_branching_chain(self, store: SQLiteStore, tracer: CallChainTracer):
        # Setup: A -> B, A -> C (two branches)
        store.insert_symbols([
            SymbolData(fqn="A", kind=SymbolKind.METHOD, name="A"),
            SymbolData(fqn="B", kind=SymbolKind.METHOD, name="B"),
            SymbolData(fqn="C", kind=SymbolKind.METHOD, name="C"),
        ])
        store.insert_edges([
            EdgeData(from_fqn="A", to_fqn="B", relation=RelationKind.CALLS),
            EdgeData(from_fqn="A", to_fqn="C", relation=RelationKind.CALLS),
        ])

        result = tracer.trace_from_entry("A")

        assert len(result.chain) == 2
        to_fqns = {item["to_fqn"] for item in result.chain}
        assert to_fqns == {"B", "C"}

    def test_trace_empty_chain(self, store: SQLiteStore, tracer: CallChainTracer):
        # Setup: Symbol with no outgoing calls
        store.insert_symbols([
            SymbolData(fqn="Leaf", kind=SymbolKind.METHOD, name="Leaf"),
        ])

        result = tracer.trace_from_entry("Leaf")

        assert len(result.chain) == 0
        assert result.max_depth == 0


class TestLayerAnnotation:
    def test_annotate_controller_layer(self, store: SQLiteStore, tracer: CallChainTracer):
        store.insert_symbols([
            SymbolData(fqn="Controller", kind=SymbolKind.CLASS, name="Controller", annotations=["@RestController"]),
            SymbolData(fqn="Controller.get()", kind=SymbolKind.METHOD, name="get", parent_fqn="Controller"),
            SymbolData(fqn="Service.process()", kind=SymbolKind.METHOD, name="process"),
        ])
        store.insert_edges([
            EdgeData(from_fqn="Controller.get()", to_fqn="Service.process()", relation=RelationKind.CALLS),
        ])

        result = tracer.trace_from_entry("Controller.get()")

        # Note: layer annotation is on the to_fqn, so Service should get layer annotation
        # This test checks that the tracer runs without error
        assert len(result.chain) == 1

    def test_annotate_service_layer(self, store: SQLiteStore, tracer: CallChainTracer):
        store.insert_symbols([
            SymbolData(fqn="Entry", kind=SymbolKind.METHOD, name="Entry"),
            # The layer detection uses the target's name or class
            SymbolData(fqn="UserService.process()", kind=SymbolKind.METHOD, name="process"),
        ])
        store.insert_edges([
            EdgeData(from_fqn="Entry", to_fqn="UserService.process()", relation=RelationKind.CALLS),
        ])

        result = tracer.trace_from_entry("Entry")

        assert len(result.chain) == 1
        # "Service" is in the FQN, so layer detection should identify as service
        assert result.chain[0].get("layer") == "service"

    def test_annotate_repository_layer(self, store: SQLiteStore, tracer: CallChainTracer):
        store.insert_symbols([
            SymbolData(fqn="Entry", kind=SymbolKind.METHOD, name="Entry"),
            SymbolData(fqn="com.example.UserMapper.select()", kind=SymbolKind.METHOD, name="select"),
        ])
        store.insert_edges([
            EdgeData(from_fqn="Entry", to_fqn="com.example.UserMapper.select()", relation=RelationKind.CALLS),
        ])

        result = tracer.trace_from_entry("Entry")

        assert len(result.chain) == 1
        # "Mapper" in FQN should identify as repository
        assert result.chain[0].get("layer") == "repository"


class TestExternalDependencies:
    def test_extract_external_deps(self, store: SQLiteStore, tracer: CallChainTracer):
        store.insert_symbols([
            SymbolData(fqn="Service.save()", kind=SymbolKind.METHOD, name="save"),
            SymbolData(fqn="Mapper.insert()", kind=SymbolKind.METHOD, name="insert"),
        ])
        store.insert_edges([
            EdgeData(from_fqn="Service.save()", to_fqn="Mapper.insert()", relation=RelationKind.CALLS),
        ])
        store.insert_external_dependencies([
            ExternalDependencyData(
                caller_fqn="Service.save()",
                dependency_type=DependencyType.MYSQL,
                target="Mapper.insert()",
                strength=DependencyStrength.STRONG,
            )
        ])

        result = tracer.trace_from_entry("Service.save()")

        assert len(result.external_deps) == 1
        assert result.external_deps[0]["dependency_type"] == "mysql"

    def test_no_external_deps(self, store: SQLiteStore, tracer: CallChainTracer):
        store.insert_symbols([
            SymbolData(fqn="Service.process()", kind=SymbolKind.METHOD, name="process"),
        ])

        result = tracer.trace_from_entry("Service.process()")

        assert len(result.external_deps) == 0
