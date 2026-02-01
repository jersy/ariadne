"""Tests for ParallelSummarizer."""

import time
from unittest.mock import MagicMock, patch

import pytest

from ariadne_analyzer.l1_business.parallel_summarizer import ParallelSummarizer
from ariadne_core.models.types import SymbolData, SymbolKind
from ariadne_llm import LLMConfig, LLMProvider


@pytest.fixture
def mock_llm_client():
    """Create a mock LLM client."""
    config = LLMConfig(
        provider=LLMProvider.OPENAI,
        api_key="test-key",
        model="gpt-4o-mini",
        max_workers=2,
        request_timeout=30.0,
    )

    client = MagicMock()
    client.config = config

    # Mock generate_summary to return predictable results
    def mock_generate(code, context):
        # Simulate LLM API latency
        time.sleep(0.01)
        method_name = context.get("method_name", "unknown")
        return f"Summary for {method_name}"

    client.generate_summary = mock_generate

    return client


@pytest.fixture
def sample_symbols():
    """Create sample symbols for testing."""
    symbols = []
    for i in range(10):
        symbol = SymbolData(
            fqn=f"com.example.TestClass.method{i}()",
            kind=SymbolKind.METHOD,
            name=f"method{i}",
            signature=f"public void method{i}()",
            parent_fqn="com.example.TestClass",
            modifiers=["public"],
        )
        source_code = f"public void method{i}() {{ return {i}; }}"
        symbols.append((symbol, source_code))
    return symbols


class TestParallelSummarizer:
    """Test suite for ParallelSummarizer."""

    def test_summarize_symbols_batch_basic(self, mock_llm_client, sample_symbols):
        """Test basic batch summarization."""
        summarizer = ParallelSummarizer(mock_llm_client, max_workers=2)

        results = summarizer.summarize_symbols_batch(sample_symbols, show_progress=False)

        assert len(results) == 10
        # Check that all symbol FQNs are in results
        expected_fqns = [symbol.fqn for symbol, _ in sample_symbols]
        assert all(fqn in results for fqn in expected_fqns)
        assert all(summary.startswith("Summary for") for summary in results.values())

    def test_concurrent_processing(self, mock_llm_client):
        """Test that concurrent processing is faster than sequential."""
        # Create symbols with simulated delay
        symbols = []
        for i in range(5):
            symbol = SymbolData(
                fqn=f"com.example.TestClass.method{i}()",
                kind=SymbolKind.METHOD,
                name=f"method{i}",
                parent_fqn="com.example.TestClass",
            )
            source_code = f"public void method{i}() {{}}"
            symbols.append((symbol, source_code))

        # Add delay to LLM client
        original_generate = mock_llm_client.generate_summary

        def slow_generate(code, context):
            time.sleep(0.05)  # 50ms per call
            return original_generate(code, context)

        mock_llm_client.generate_summary = slow_generate

        summarizer = ParallelSummarizer(mock_llm_client, max_workers=5)

        start = time.time()
        results = summarizer.summarize_symbols_batch(symbols, show_progress=False)
        duration = time.time() - start

        assert len(results) == 5
        # With 5 workers and 50ms delay, should complete in ~100ms (not 250ms sequential)
        assert duration < 0.2, f"Concurrent processing took {duration:.2f}s (expected < 0.2s)"

    def test_error_isolation(self, mock_llm_client):
        """Test that single failures don't block other processing."""
        symbols = []

        # Add some normal symbols
        for i in range(3):
            symbol = SymbolData(
                fqn=f"com.example.TestClass.method{i}()",
                kind=SymbolKind.METHOD,
                name=f"method{i}",
            )
            symbols.append((symbol, f"public void method{i}() {{}}"))

        # Add a symbol that will cause an error
        error_symbol = SymbolData(
            fqn="com.example.TestClass.errorMethod()",
            kind=SymbolKind.METHOD,
            name="errorMethod",
        )
        symbols.append((error_symbol, "error code"))

        # Mock generate_summary to fail for specific symbols
        def selective_generate(code, context):
            if "errorMethod" in context.get("method_name", ""):
                raise Exception("Simulated error")
            return f"Summary for {context.get('method_name')}"

        mock_llm_client.generate_summary = selective_generate

        summarizer = ParallelSummarizer(mock_llm_client, max_workers=2)

        results = summarizer.summarize_symbols_batch(symbols, show_progress=False)

        # Should have all results (error items get fallback)
        assert len(results) == 4

        # Normal items should have summaries
        assert "Summary for method0" in results["com.example.TestClass.method0()"]
        assert "Summary for method1" in results["com.example.TestClass.method1()"]
        assert "Summary for method2" in results["com.example.TestClass.method2()"]

        # Error item should have fallback
        assert "Method: errorMethod" in results["com.example.TestClass.errorMethod()"]

        # Stats should reflect failures
        stats = summarizer.get_stats()
        assert stats["failed"] == 1
        assert stats["success"] == 3

    def test_fallback_summary_getter_setter(self, mock_llm_client):
        """Test fallback summary generation for getters/setters."""
        summarizer = ParallelSummarizer(mock_llm_client)

        # Test getter
        context_getter = {"signature": "public String getName()"}
        fallback = summarizer._fallback_summary("com.example.Test.getName()", context_getter)
        assert "N/A" in fallback and "getter" in fallback.lower()

        # Test setter
        context_setter = {"signature": "public void setName(String name)"}
        fallback = summarizer._fallback_summary("com.example.Test.setName()", context_setter)
        assert "N/A" in fallback and "setter" in fallback.lower()

        # Test regular method
        context_regular = {"signature": "public void process()"}
        fallback = summarizer._fallback_summary("com.example.Test.process()", context_regular)
        assert "Method: process" in fallback

    def test_stats_tracking(self, mock_llm_client, sample_symbols):
        """Test statistics tracking."""
        summarizer = ParallelSummarizer(mock_llm_client, max_workers=2)

        # First batch
        summarizer.summarize_symbols_batch(sample_symbols[:5], show_progress=False)
        stats = summarizer.get_stats()
        assert stats["total"] == 5
        assert stats["success"] == 5
        assert stats["failed"] == 0

        # Reset and second batch
        summarizer.reset_stats()
        summarizer.summarize_symbols_batch(sample_symbols[5:], show_progress=False)
        stats = summarizer.get_stats()
        assert stats["total"] == 5

    def test_empty_input(self, mock_llm_client):
        """Test handling of empty input."""
        summarizer = ParallelSummarizer(mock_llm_client)

        results = summarizer.summarize_symbols_batch([], show_progress=False)

        assert results == {}

    def test_max_workers_configuration(self, mock_llm_client):
        """Test that max_workers is properly configured."""
        summarizer = ParallelSummarizer(mock_llm_client, max_workers=15)

        assert summarizer.max_workers == 15

    def test_progress_bar_disabled(self, mock_llm_client, sample_symbols):
        """Test that progress bar can be disabled."""
        summarizer = ParallelSummarizer(mock_llm_client)

        # Should not raise even if tqdm is not available
        results = summarizer.summarize_symbols_batch(sample_symbols, show_progress=False)

        assert len(results) == 10


class TestParallelSummarizerIntegration:
    """Integration tests for ParallelSummarizer with real LLM client."""

    @pytest.mark.integration
    def test_with_real_llm_client(self):
        """Test with real LLM client (requires API key)."""
        import os

        # Skip if no API key available
        api_key = os.environ.get("ARIADNE_OPENAI_API_KEY")
        if not api_key:
            pytest.skip("ARIADNE_OPENAI_API_KEY not set")

        from ariadne_llm import LLMClient

        config = LLMConfig.from_env()
        client = LLMClient(config)

        # Create test symbols
        symbols = []
        for i in range(3):
            symbol = SymbolData(
                fqn=f"com.example.TestClass.method{i}()",
                kind=SymbolKind.METHOD,
                name=f"method{i}",
            )
            source_code = f"public void method{i}() {{ System.out.println({i}); }}"
            symbols.append((symbol, source_code))

        summarizer = ParallelSummarizer(client, max_workers=2)

        try:
            results = summarizer.summarize_symbols_batch(symbols, show_progress=False)

            assert len(results) == 3
            assert all(summary for summary in results.values() if summary != "N/A")
        finally:
            client.close()
