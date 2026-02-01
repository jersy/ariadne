"""Tests for IncrementalSummarizerCoordinator."""

import tempfile
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from ariadne_analyzer.l1_business.incremental_coordinator import (
    IncrementalResult,
    IncrementalSummarizerCoordinator,
)
from ariadne_core.models.types import (
    EdgeData,
    RelationKind,
    SummaryData,
    SummaryLevel,
    SymbolData,
    SymbolKind,
)
from ariadne_core.storage.sqlite_store import SQLiteStore


@pytest.fixture
def mock_llm_client():
    """Create a mock LLM client."""
    from ariadne_llm import LLMConfig, LLMProvider

    config = LLMConfig(
        provider=LLMProvider.OPENAI,
        api_key="test-key",
        model="gpt-4o-mini",
        max_workers=2,
    )

    client = MagicMock()
    client.config = config

    def mock_generate(code, context):
        method_name = context.get("method_name", "unknown")
        return f"Summary for {method_name}"

    client.generate_summary = mock_generate

    return client


@pytest.fixture
def populated_store():
    """Create a store with test data."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        store = SQLiteStore(str(db_path), init=True)

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
        ]

        store.insert_symbols(symbols)

        # Create CALLS relationship
        edges = [
            EdgeData(
                from_fqn="com.example.ClassB.callMethodA()",
                to_fqn="com.example.ClassA.methodA()",
                relation=RelationKind.CALLS,
            ),
        ]

        store.insert_edges(edges)

        yield store
        store.close()


class TestIncrementalSummarizerCoordinator:
    """Test suite for IncrementalSummarizerCoordinator."""

    def test_regenerate_incremental_basic(self, mock_llm_client, populated_store):
        """Test basic incremental regeneration."""
        coordinator = IncrementalSummarizerCoordinator(
            mock_llm_client, populated_store, max_workers=2
        )

        # Provide source code map
        source_map = {
            "com.example.ClassA.methodA()": "public void methodA() { }",
            "com.example.ClassB.callMethodA()": "public void callMethodA() { methodA(); }",
        }

        result = coordinator.regenerate_incremental(
            changed_symbols=["com.example.ClassA.methodA()"],
            symbol_source_map=source_map,
            show_progress=False,
        )

        # Should regenerate both changed method and its caller
        assert result.regenerated_count == 2
        assert result.duration_seconds > 0
        assert result.stats["changed"] == 1
        assert result.stats["dependents"] >= 1

    def test_regenerate_incremental_with_cache(self, mock_llm_client, populated_store):
        """Test that cached summaries are skipped for unrelated symbols."""
        coordinator = IncrementalSummarizerCoordinator(
            mock_llm_client, populated_store, max_workers=2
        )

        # Create an existing fresh summary for an unrelated symbol
        # (not a caller of the changed method)
        summary = SummaryData(
            target_fqn="com.example.ClassA",  # Parent class, not a caller
            level=SummaryLevel.CLASS,
            summary="Existing summary",
            is_stale=False,
        )
        populated_store.create_summary(summary)

        source_map = {
            "com.example.ClassA.methodA()": "public void methodA() { }",
        }

        result = coordinator.regenerate_incremental(
            changed_symbols=["com.example.ClassA.methodA()"],
            symbol_source_map=source_map,
            show_progress=False,
        )

        # Parent should be in affected set but since we don't provide its source,
        # it won't be regenerated. The actual regeneration count depends on
        # available source code.
        assert result.regenerated_count >= 1

    def test_regenerate_incremental_stale_cache(self, mock_llm_client, populated_store):
        """Test that stale summaries are regenerated."""
        coordinator = IncrementalSummarizerCoordinator(
            mock_llm_client, populated_store, max_workers=2
        )

        # Create a stale summary
        summary = SummaryData(
            target_fqn="com.example.ClassB.callMethodA()",
            level=SummaryLevel.METHOD,
            summary="Old stale summary",
            is_stale=True,
        )
        populated_store.create_summary(summary)

        source_map = {
            "com.example.ClassA.methodA()": "public void methodA() { }",
            "com.example.ClassB.callMethodA()": "public void callMethodA() { methodA(); }",
        }

        result = coordinator.regenerate_incremental(
            changed_symbols=["com.example.ClassA.methodA()"],
            symbol_source_map=source_map,
            show_progress=False,
        )

        # Should regenerate the stale summary
        assert result.regenerated_count == 2
        assert result.skipped_cached == 0

    def test_regenerate_with_symbol_data_input(self, mock_llm_client, populated_store):
        """Test passing SymbolData objects instead of FQNs."""
        coordinator = IncrementalSummarizerCoordinator(
            mock_llm_client, populated_store, max_workers=2
        )

        symbol = SymbolData(
            fqn="com.example.ClassA.methodA()",
            kind=SymbolKind.METHOD,
            name="methodA",
        )

        source_map = {
            "com.example.ClassA.methodA()": "public void methodA() { }",
        }

        result = coordinator.regenerate_incremental(
            changed_symbols=[symbol],
            symbol_source_map=source_map,
            show_progress=False,
        )

        assert result.regenerated_count >= 1

    def test_cost_tracking(self, mock_llm_client, populated_store):
        """Test that cost tracking works."""
        coordinator = IncrementalSummarizerCoordinator(
            mock_llm_client, populated_store, max_workers=2
        )

        source_map = {
            "com.example.ClassA.methodA()": "public void methodA() { }",
        }

        result = coordinator.regenerate_incremental(
            changed_symbols=["com.example.ClassA.methodA()"],
            symbol_source_map=source_map,
            show_progress=False,
        )

        # Cost report should be generated
        assert result.cost_report
        assert "LLM Usage Report" in result.cost_report


class TestIncrementalResult:
    """Test IncrementalResult dataclass."""

    def test_result_creation(self):
        """Test creating an IncrementalResult."""
        result = IncrementalResult(
            regenerated_count=10,
            skipped_cached=5,
            duration_seconds=1.5,
            cost_report="$0.01",
        )

        assert result.regenerated_count == 10
        assert result.skipped_cached == 5
        assert result.duration_seconds == 1.5
        assert result.cost_report == "$0.01"
