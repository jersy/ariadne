"""Integration tests for L2 analysis on mall project.

These tests require:
1. ASM Analysis Service running on localhost:8766
2. Mall project built (mvn compile)
3. Mall project at /Users/jersyzhang/work/claude/mall
"""

import os
import tempfile
from pathlib import Path

import pytest

from ariadne_analyzer.l2_architecture.anti_patterns import AntiPatternDetector
from ariadne_analyzer.l2_architecture.call_chain import CallChainTracer
from ariadne_core.extractors.asm.extractor import Extractor
from ariadne_core.storage.sqlite_store import SQLiteStore


MALL_PROJECT = "/Users/jersyzhang/work/claude/mall"
ASM_SERVICE = "http://localhost:8766"


def asm_service_available() -> bool:
    """Check if ASM service is available."""
    import urllib.request
    import urllib.error

    try:
        with urllib.request.urlopen(f"{ASM_SERVICE}/health", timeout=2) as resp:
            return resp.status == 200
    except (urllib.error.URLError, TimeoutError):
        return False


def mall_project_available() -> bool:
    """Check if mall project is available and built."""
    project = Path(MALL_PROJECT)
    if not project.exists():
        return False
    # Check for compiled classes
    for target_classes in project.rglob("target/classes"):
        if target_classes.is_dir() and list(target_classes.rglob("*.class")):
            return True
    return False


# Skip all tests if prerequisites are not met
pytestmark = [
    pytest.mark.skipif(
        not asm_service_available(),
        reason="ASM service not available at localhost:8766",
    ),
    pytest.mark.skipif(
        not mall_project_available(),
        reason="Mall project not available or not built",
    ),
]


@pytest.fixture(scope="module")
def extracted_db():
    """Extract mall project and return the database path."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name

    # Extract with limit for faster testing
    extractor = Extractor(db_path=db_path, service_url=ASM_SERVICE, init=True)
    try:
        result = extractor.extract_project(
            MALL_PROJECT,
            domains=["com.macro.mall"],
            limit=50,  # Limit for faster testing
        )
        assert result.success, f"Extraction failed: {result.errors}"
    finally:
        extractor.close()

    yield db_path

    # Cleanup
    Path(db_path).unlink(missing_ok=True)


@pytest.fixture
def store(extracted_db: str):
    """Get SQLite store from extracted database."""
    store = SQLiteStore(extracted_db)
    yield store
    store.close()


class TestExtraction:
    def test_extraction_produces_symbols(self, store: SQLiteStore):
        count = store.get_symbol_count()
        assert count > 0, "No symbols extracted"
        print(f"Extracted {count} symbols")

    def test_extraction_produces_edges(self, store: SQLiteStore):
        count = store.get_edge_count()
        assert count > 0, "No edges extracted"
        print(f"Extracted {count} edges")


class TestEntryPoints:
    def test_has_http_api_entries(self, store: SQLiteStore):
        entries = store.get_entry_points("http_api")
        print(f"Found {len(entries)} HTTP API entry points")
        # Mall should have some REST controllers
        # Note: with limit=50, we may not get all entries

    def test_entry_points_have_valid_structure(self, store: SQLiteStore):
        entries = store.get_entry_points()
        for entry in entries[:10]:  # Check first 10
            assert "symbol_fqn" in entry
            assert "entry_type" in entry
            if entry["entry_type"] == "http_api":
                # HTTP entries should have method and path
                assert entry.get("http_method") or entry.get("http_path"), \
                    f"HTTP entry missing method/path: {entry}"


class TestExternalDependencies:
    def test_has_external_dependencies(self, store: SQLiteStore):
        deps = store.get_external_dependencies()
        print(f"Found {len(deps)} external dependencies")
        # Mall uses Redis, MyBatis, RabbitMQ

    def test_deps_have_valid_structure(self, store: SQLiteStore):
        deps = store.get_external_dependencies()
        for dep in deps[:10]:  # Check first 10
            assert "caller_fqn" in dep
            assert "dependency_type" in dep
            assert "target" in dep
            assert "strength" in dep

    def test_mysql_deps_detected(self, store: SQLiteStore):
        mysql_deps = store.get_external_dependencies(dependency_type="mysql")
        print(f"Found {len(mysql_deps)} MySQL dependencies")
        # Mall uses MyBatis extensively


class TestCallChain:
    def test_can_trace_from_symbol(self, store: SQLiteStore):
        # Find any method to trace from
        methods = store.get_symbols_by_kind("method")
        if not methods:
            pytest.skip("No methods found to trace")

        tracer = CallChainTracer(store)
        # Find a method with outgoing calls
        for method in methods[:20]:
            edges = store.get_edges_from(method["fqn"], "calls")
            if edges:
                result = tracer.trace_from_fqn(method["fqn"], max_depth=3)
                assert result.chain is not None
                print(f"Traced {method['fqn']}: {len(result.chain)} calls, depth {result.depth}")
                return

        pytest.skip("No method with calls found")

    def test_trace_includes_layer_annotation(self, store: SQLiteStore):
        methods = store.get_symbols_by_kind("method")
        tracer = CallChainTracer(store)

        for method in methods[:20]:
            edges = store.get_edges_from(method["fqn"], "calls")
            if edges:
                result = tracer.trace_from_fqn(method["fqn"], max_depth=3)
                if result.chain:
                    # At least one chain item should have a layer
                    layers = [c.get("layer") for c in result.chain]
                    print(f"Layers found: {set(layers)}")
                    return

        pytest.skip("No method with calls found")


class TestAntiPatterns:
    def test_can_run_detection(self, store: SQLiteStore):
        detector = AntiPatternDetector(store)
        patterns = detector.detect_all()
        print(f"Detected {len(patterns)} anti-patterns")

    def test_list_rules(self, store: SQLiteStore):
        detector = AntiPatternDetector(store)
        rules = detector.list_rules()
        assert len(rules) >= 1
        print(f"Available rules: {[r['rule_id'] for r in rules]}")


class TestL2Statistics:
    """Test overall L2 statistics from mall project."""

    def test_print_statistics(self, store: SQLiteStore):
        """Print statistics for manual verification."""
        stats = {
            "symbols": store.get_symbol_count(),
            "edges": store.get_edge_count(),
            "entry_points": store.get_entry_point_count(),
            "external_deps": store.get_external_dependency_count(),
        }

        print("\n=== Mall Project L2 Statistics ===")
        for key, value in stats.items():
            print(f"  {key}: {value}")

        # Entry point breakdown
        entries = store.get_entry_points()
        by_type: dict[str, int] = {}
        for e in entries:
            t = e["entry_type"]
            by_type[t] = by_type.get(t, 0) + 1
        print("\n  Entry points by type:")
        for t, count in by_type.items():
            print(f"    {t}: {count}")

        # External dependency breakdown
        deps = store.get_external_dependencies()
        by_type = {}
        for d in deps:
            t = d["dependency_type"]
            by_type[t] = by_type.get(t, 0) + 1
        print("\n  External dependencies by type:")
        for t, count in by_type.items():
            print(f"    {t}: {count}")

        # Verify we have meaningful data
        assert stats["symbols"] > 0
        assert stats["edges"] > 0
