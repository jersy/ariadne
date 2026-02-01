"""Unit tests for ariadne_core.storage.vector_store module."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from ariadne_core.storage.vector_store import (
    COLLECTION_CONSTRAINTS,
    COLLECTION_GLOSSARY,
    COLLECTION_SUMMARIES,
    ChromaVectorStore,
)


@pytest.fixture
def temp_vector_store(tmp_path):
    """Create a temporary vector store for testing."""
    store = ChromaVectorStore(tmp_path / "vectors")
    yield store
    # Cleanup is handled by tmp_path fixture


class TestChromaVectorStore:
    """Tests for ChromaVectorStore."""

    def test_initialization(self, tmp_path):
        """Test vector store initialization creates collections."""
        store = ChromaVectorStore(tmp_path / "vectors")

        # Check that collections were created
        assert store.summaries_collection is not None
        assert store.glossary_collection is not None
        assert store.constraints_collection is not None

    def test_get_stats(self, temp_vector_store):
        """Test getting store statistics."""
        stats = temp_vector_store.get_stats()

        assert "summaries" in stats
        assert "glossary" in stats
        assert "constraints" in stats
        assert stats["summaries"] == 0
        assert stats["glossary"] == 0
        assert stats["constraints"] == 0

    def test_add_and_get_summary(self, temp_vector_store):
        """Test adding and retrieving a summary."""
        temp_vector_store.add_summary(
            summary_id="test_1",
            text="用户登录验证",
            metadata={"fqn": "com.example.AuthService", "level": "class"},
        )

        result = temp_vector_store.get_summary("test_1")

        assert result is not None
        assert result["id"] == "test_1"
        assert result["document"] == "用户登录验证"
        assert result["metadata"]["fqn"] == "com.example.AuthService"

    def test_delete_summary(self, temp_vector_store):
        """Test deleting a summary."""
        temp_vector_store.add_summary(
            summary_id="test_1",
            text="Test summary",
        )

        # Verify it was added
        assert temp_vector_store.get_summary("test_1") is not None

        # Delete it
        temp_vector_store.delete_summaries(["test_1"])

        # Verify it's gone
        assert temp_vector_store.get_summary("test_1") is None

    def test_update_summary(self, temp_vector_store):
        """Test updating a summary."""
        temp_vector_store.add_summary(
            summary_id="test_1",
            text="Original text",
            metadata={"version": 1},
        )

        temp_vector_store.update_summary(
            summary_id="test_1",
            text="Updated text",
            metadata={"version": 2},
        )

        result = temp_vector_store.get_summary("test_1")

        assert result["document"] == "Updated text"
        assert result["metadata"]["version"] == 2

    def test_search_summaries(self, temp_vector_store):
        """Test searching summaries."""
        import numpy as np

        # Add test summaries
        temp_vector_store.add_summary(
            summary_id="test_1",
            text="用户登录验证",
            embedding=np.random.rand(1536).tolist(),
            metadata={"level": "class"},
        )
        temp_vector_store.add_summary(
            summary_id="test_2",
            text="订单处理服务",
            embedding=np.random.rand(1536).tolist(),
            metadata={"level": "class"},
        )

        # Search with a query vector
        query_vector = np.random.rand(1536).tolist()
        results = temp_vector_store.search_summaries(query_vector, n_results=2)

        assert results["ids"] is not None
        # ChromaDB returns results as a nested list, check we got some results
        assert len(results["ids"]) > 0
        # All results should have 2 items (n_results=2)
        assert len(results["ids"][0]) <= 2

    def test_search_with_filters(self, temp_vector_store):
        """Test searching summaries with metadata filters."""
        import numpy as np

        # Add test summaries with different levels
        temp_vector_store.add_summary(
            summary_id="method_1",
            text="方法摘要",
            embedding=np.random.rand(1536).tolist(),
            metadata={"level": "method"},
        )
        temp_vector_store.add_summary(
            summary_id="class_1",
            text="类摘要",
            embedding=np.random.rand(1536).tolist(),
            metadata={"level": "class"},
        )

        # Search with level filter
        query_vector = np.random.rand(1536).tolist()
        results = temp_vector_store.search_summaries(
            query_vector, n_results=10, filters={"level": "method"}
        )

        # Should only return method-level results
        for level in results["metadatas"][0]:
            assert level["level"] == "method"

    def test_add_glossary_term(self, temp_vector_store):
        """Test adding a glossary term."""
        temp_vector_store.add_glossary_term(
            term_id="term_1",
            text="SKU - 商品库存单位，唯一标识一个可售卖的商品规格",
            metadata={"code_term": "SKU", "source_fqn": "com.example.Sku"},
        )

        stats = temp_vector_store.get_stats()
        assert stats["glossary"] == 1

    def test_add_constraint(self, temp_vector_store):
        """Test adding a constraint."""
        temp_vector_store.add_constraint(
            constraint_id="constraint_1",
            text="库存数量不可为负",
            metadata={"type": "business_rule", "source_fqn": "com.example.InventoryService"},
        )

        stats = temp_vector_store.get_stats()
        assert stats["constraints"] == 1

    def test_clear_all(self, temp_vector_store):
        """Test clearing all collections."""
        # Add some data
        temp_vector_store.add_summary(summary_id="test_1", text="Test")
        temp_vector_store.add_glossary_term(term_id="term_1", text="Test")

        # Clear all
        temp_vector_store.clear_all()

        # Verify everything is cleared
        stats = temp_vector_store.get_stats()
        assert stats["summaries"] == 0
        assert stats["glossary"] == 0
        assert stats["constraints"] == 0


class TestVectorStoreIntegration:
    """Integration tests for vector store with SQLite."""

    def test_vector_and_sqlite_integration(self, tmp_path):
        """Test that vector store integrates with SQLite store."""
        from ariadne_core.storage.sqlite_store import SQLiteStore
        from ariadne_core.models.types import SummaryData, SummaryLevel

        db_path = tmp_path / "test.db"
        vector_path = tmp_path / "vectors"

        # Create stores
        sqlite_store = SQLiteStore(str(db_path), init=True)
        vector_store = ChromaVectorStore(vector_path)

        try:
            # Create a summary
            summary = SummaryData(
                target_fqn="com.example.TestClass",
                level=SummaryLevel.CLASS,
                summary="测试类摘要",
            )

            # Store in SQLite
            sqlite_store.create_summary(summary)

            # Store in vector store
            vector_store.add_summary(
                summary_id="test_1",
                text="测试类摘要",
                metadata={"fqn": "com.example.TestClass", "level": "class"},
            )

            # Verify SQLite has the summary
            retrieved = sqlite_store.get_summary("com.example.TestClass")
            assert retrieved is not None
            assert retrieved["summary"] == "测试类摘要"

            # Verify vector store has the summary
            vector_result = vector_store.get_summary("test_1")
            assert vector_result is not None

        finally:
            sqlite_store.close()
