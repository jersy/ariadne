"""
Ariadne Vector Store
====================

ChromaDB-based vector storage for semantic search.

Provides:
- Summary storage and search
- Glossary storage and search
- Constraint storage and search
"""

import logging
from pathlib import Path
from typing import Any

import chromadb
from chromadb.config import Settings

logger = logging.getLogger(__name__)

# Collection names
COLLECTION_SUMMARIES = "ariadne_summaries"
COLLECTION_GLOSSARY = "ariadne_glossary"
COLLECTION_CONSTRAINTS = "ariadne_constraints"


class ChromaVectorStore:
    """ChromaDB-based vector store for semantic search.

    Supports multiple collections for different data types:
    - summaries: Business summaries
    - glossary: Domain vocabulary
    - constraints: Business constraints
    """

    def __init__(self, persist_directory: str | Path) -> None:
        """Initialize vector store with persistent storage.

        Args:
            persist_directory: Directory to persist ChromaDB data
        """
        self.persist_directory = Path(persist_directory)
        self.persist_directory.mkdir(parents=True, exist_ok=True)

        # Initialize ChromaDB client with persistence
        self.client = chromadb.PersistentClient(
            path=str(self.persist_directory),
            settings=Settings(anonymized_telemetry=False),
        )

        # Get or create collections
        self.summaries_collection = self.client.get_or_create_collection(
            name=COLLECTION_SUMMARIES,
            metadata={"description": "Business summaries for code symbols"},
        )
        self.glossary_collection = self.client.get_or_create_collection(
            name=COLLECTION_GLOSSARY,
            metadata={"description": "Domain vocabulary mapping"},
        )
        self.constraints_collection = self.client.get_or_create_collection(
            name=COLLECTION_CONSTRAINTS,
            metadata={"description": "Business constraints and rules"},
        )

        logger.info(
            f"Initialized ChromaDB vector store at {self.persist_directory}"
        )

    # ============ Summary Operations ============

    def add_summary(
        self,
        summary_id: str,
        text: str,
        embedding: list[float] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Add a summary to the vector store.

        Args:
            summary_id: Unique identifier for the summary
            text: Summary text to embed
            embedding: Pre-computed embedding (optional, will compute if None)
            metadata: Optional metadata (fqn, level, kind, etc.)
        """
        if embedding is None:
            # Add without embedding - ChromaDB will use default embedder
            # For production, you should pass pre-computed embeddings
            logger.warning("No embedding provided, using default embedder")
            self.summaries_collection.add(
                ids=[summary_id],
                documents=[text],
                metadatas=[metadata] if metadata else None,
            )
        else:
            self.summaries_collection.add(
                ids=[summary_id],
                embeddings=[embedding],
                documents=[text],
                metadatas=[metadata] if metadata else None,
            )

    def search_summaries(
        self,
        query_embedding: list[float],
        n_results: int = 10,
        filters: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Search summaries by vector similarity.

        Args:
            query_embedding: Query vector
            n_results: Number of results to return
            filters: Optional metadata filters (e.g., {"level": "class"})

        Returns:
            Dict with ids, distances, metadatas, documents
        """
        results = self.summaries_collection.query(
            query_embeddings=[query_embedding],
            n_results=n_results,
            where=filters,
        )
        return results

    def get_summary(self, summary_id: str) -> dict[str, Any] | None:
        """Get a summary by ID.

        Args:
            summary_id: Summary identifier

        Returns:
            Summary data or None if not found
        """
        results = self.summaries_collection.get(ids=[summary_id])
        if results and results["ids"]:
            return {
                "id": results["ids"][0],
                "document": results["documents"][0] if results["documents"] else None,
                "metadata": results["metadatas"][0] if results["metadatas"] else None,
            }
        return None

    def delete_summaries(self, ids: list[str]) -> None:
        """Delete summaries by IDs.

        Args:
            ids: List of summary IDs to delete
        """
        self.summaries_collection.delete(ids=ids)

    def update_summary(
        self,
        summary_id: str,
        text: str | None = None,
        embedding: list[float] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Update an existing summary.

        Args:
            summary_id: Summary identifier
            text: New text (optional)
            embedding: New embedding (optional)
            metadata: New metadata (optional)
        """
        update_kwargs: dict[str, Any] = {"ids": [summary_id]}

        if text is not None:
            update_kwargs["documents"] = [text]
        if embedding is not None:
            update_kwargs["embeddings"] = [embedding]
        if metadata is not None:
            update_kwargs["metadatas"] = [metadata]

        self.summaries_collection.update(**update_kwargs)

    # ============ Glossary Operations ============

    def add_glossary_term(
        self,
        term_id: str,
        text: str,
        embedding: list[float] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Add a glossary term to the vector store.

        Args:
            term_id: Unique identifier for the term
            text: Term description (business meaning + synonyms)
            embedding: Pre-computed embedding (optional)
            metadata: Optional metadata (code_term, source_fqn, etc.)
        """
        update_kwargs: dict[str, Any] = {
            "ids": [term_id],
            "documents": [text],
        }

        if embedding is not None:
            update_kwargs["embeddings"] = [embedding]
        if metadata is not None:
            update_kwargs["metadatas"] = [metadata]

        self.glossary_collection.add(**update_kwargs)

    def search_glossary(
        self,
        query_embedding: list[float],
        n_results: int = 10,
        filters: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Search glossary by vector similarity.

        Args:
            query_embedding: Query vector
            n_results: Number of results to return
            filters: Optional metadata filters

        Returns:
            Dict with search results
        """
        return self.glossary_collection.query(
            query_embeddings=[query_embedding],
            n_results=n_results,
            where=filters,
        )

    def delete_glossary_terms(self, ids: list[str]) -> None:
        """Delete glossary terms by IDs.

        Args:
            ids: List of term IDs to delete
        """
        self.glossary_collection.delete(ids=ids)

    # ============ Constraint Operations ============

    def add_constraint(
        self,
        constraint_id: str,
        text: str,
        embedding: list[float] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Add a constraint to the vector store.

        Args:
            constraint_id: Unique identifier for the constraint
            text: Constraint description
            embedding: Pre-computed embedding (optional)
            metadata: Optional metadata (type, source_fqn, severity)
        """
        update_kwargs: dict[str, Any] = {
            "ids": [constraint_id],
            "documents": [text],
        }

        if embedding is not None:
            update_kwargs["embeddings"] = [embedding]
        if metadata is not None:
            update_kwargs["metadatas"] = [metadata]

        self.constraints_collection.add(**update_kwargs)

    def search_constraints(
        self,
        query_embedding: list[float],
        n_results: int = 10,
        filters: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Search constraints by vector similarity.

        Args:
            query_embedding: Query vector
            n_results: Number of results to return
            filters: Optional metadata filters

        Returns:
            Dict with search results
        """
        return self.constraints_collection.query(
            query_embeddings=[query_embedding],
            n_results=n_results,
            where=filters,
        )

    def delete_constraints(self, ids: list[str]) -> None:
        """Delete constraints by IDs.

        Args:
            ids: List of constraint IDs to delete
        """
        self.constraints_collection.delete(ids=ids)

    # ============ Utility Methods ============

    def clear_all(self) -> None:
        """Clear all collections (use with caution)."""
        self.client.delete_collection(COLLECTION_SUMMARIES)
        self.client.delete_collection(COLLECTION_GLOSSARY)
        self.client.delete_collection(COLLECTION_CONSTRAINTS)

        # Recreate collections
        self.summaries_collection = self.client.create_collection(
            name=COLLECTION_SUMMARIES,
        )
        self.glossary_collection = self.client.create_collection(
            name=COLLECTION_GLOSSARY,
        )
        self.constraints_collection = self.client.create_collection(
            name=COLLECTION_CONSTRAINTS,
        )

        logger.warning("Cleared all vector store collections")

    def get_stats(self) -> dict[str, int]:
        """Get statistics about the vector store.

        Returns:
            Dict with counts for each collection
        """
        return {
            "summaries": self.summaries_collection.count(),
            "glossary": self.glossary_collection.count(),
            "constraints": self.constraints_collection.count(),
        }
