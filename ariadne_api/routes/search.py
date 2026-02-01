"""Search endpoint for semantic + keyword search."""

import logging
import os
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import ValidationError

from ariadne_api.schemas.search import SearchRequest, SearchResponse, SearchResultItem, SymbolRef, EntryPointRef
from ariadne_core.storage.sqlite_store import SQLiteStore
from ariadne_core.storage.vector_store import ChromaVectorStore

router = APIRouter()
logger = logging.getLogger(__name__)


def get_store() -> SQLiteStore:
    """Dependency to get SQLite store."""
    db_path = os.environ.get("ARIADNE_DB_PATH", "ariadne.db")
    if not os.path.exists(db_path):
        raise HTTPException(status_code=503, detail="Database not available")
    return SQLiteStore(db_path)


def get_vector_store() -> ChromaVectorStore | None:
    """Dependency to get vector store (returns None if unavailable)."""
    try:
        vector_path = os.environ.get("ARIADNE_VECTOR_PATH", "ariadne_vectors")
        return ChromaVectorStore(vector_path)
    except Exception as e:
        logger.warning(f"Vector store unavailable: {e}")
        return None


@router.get("/knowledge/search", response_model=SearchResponse, tags=["search"])
async def search_knowledge(
    query: str = Query(..., description="Search query", min_length=1),
    num_results: int = Query(10, ge=1, le=100),
    level: list[str] = Query(["method", "class", "package"]),
    entry_type: list[str] | None = Query(None),
    sort_by: str = Query("relevance"),
) -> SearchResponse:
    """Search the code knowledge graph using semantic + keyword search.

    Combines vector-based semantic search with SQL keyword search for comprehensive results.
    Falls back to keyword-only search if vector DB is unavailable.
    """
    store = get_store()
    vector_store = get_vector_store()

    results: list[SearchResultItem] = []
    warning: str | None = None

    # Try semantic search first
    if vector_store is not None:
        try:
            from ariadne_llm import create_embedder, LLMConfig, LLMProvider

            # Get embedder configuration
            provider = LLMProvider.OPENAI
            api_key = os.environ.get("ARIADNE_OPENAI_API_KEY")
            base_url = os.environ.get("ARIADNE_OPENAI_BASE_URL")
            embedding_model = os.environ.get("ARIADNE_OPENAI_EMBEDDING_MODEL", "text-embedding-3-small")

            if api_key:
                config = LLMConfig(
                    provider=provider,
                    api_key=api_key,
                    base_url=base_url,
                    embedding_model=embedding_model,
                )

                with create_embedder(config) as embedder:
                    # Generate embedding for query
                    query_embedding = embedder.embed_text(query)

                    # Search in vector store
                    search_result = vector_store.search_summaries(
                        query_embedding,
                        n_results=num_results,
                    )

                    # Process vector search results
                    if search_result.get("ids") and search_result["ids"][0]:
                        for i, fqn in enumerate(search_result["ids"][0]):
                            summary = search_result["documents"][0][i]
                            distance = search_result["distances"][0][i]
                            score = 1 - distance

                            # Get symbol details from store
                            symbol = store.get_symbol(fqn)
                            if symbol:
                                # Get entry points
                                entry_points = _get_entry_points_for_symbol(store, fqn)

                                results.append(
                                    SearchResultItem(
                                        fqn=fqn,
                                        kind=symbol["kind"],
                                        summary=summary,
                                        score=score,
                                        symbols=SymbolRef(
                                            fqn=symbol["fqn"],
                                            kind=symbol["kind"],
                                            name=symbol["name"],
                                            file_path=symbol.get("file_path"),
                                            line_number=symbol.get("line_number"),
                                            signature=symbol.get("signature"),
                                        ),
                                        entry_points=entry_points,
                                    )
                                )

        except Exception as e:
            logger.warning(f"Semantic search failed: {e}")
            warning = "Semantic search unavailable, using keyword search"
            results = []

    # If no results from semantic search, do keyword search
    if not results:
        results = _keyword_search(store, query, num_results, level)

    return SearchResponse(
        total=len(results),
        results=results,
        warning=warning,
    )


def _keyword_search(
    store: SQLiteStore,
    query: str,
    num_results: int,
    level: list[str],
) -> list[SearchResultItem]:
    """Fallback keyword search using SQL LIKE."""
    cursor = store.conn.cursor()
    query_pattern = f"%{query}%"

    # Search in symbols
    cursor.execute(
        """
        SELECT fqn, kind, name, file_path, line_number, signature
        FROM symbols
        WHERE name LIKE ? OR fqn LIKE ?
        LIMIT ?
        """,
        (query_pattern, query_pattern, num_results * 2),
    )

    results: list[SearchResultItem] = []
    for row in cursor.fetchall():
        symbol = dict(row)

        # Get summary if available
        summary_data = store.get_summary(symbol["fqn"])
        summary = summary_data["summary"] if summary_data else f"{symbol['kind']}: {symbol['name']}"

        # Get entry points
        entry_points = _get_entry_points_for_symbol(store, symbol["fqn"])

        results.append(
            SearchResultItem(
                fqn=symbol["fqn"],
                kind=symbol["kind"],
                summary=summary,
                score=0.5,  # Default score for keyword results
                symbols=SymbolRef(
                    fqn=symbol["fqn"],
                    kind=symbol["kind"],
                    name=symbol["name"],
                    file_path=symbol.get("file_path"),
                    line_number=symbol.get("line_number"),
                    signature=symbol.get("signature"),
                ),
                entry_points=entry_points,
            )
        )

    return results[:num_results]


def _get_entry_points_for_symbol(store: SQLiteStore, fqn: str) -> list[EntryPointRef]:
    """Get entry points for a symbol."""
    cursor = store.conn.cursor()

    # Direct entry point
    cursor.execute(
        "SELECT * FROM entry_points WHERE symbol_fqn = ?",
        (fqn,),
    )
    entry_points = []
    for row in cursor.fetchall():
        ep = dict(row)
        entry_points.append(
            EntryPointRef(
                fqn=ep["symbol_fqn"],
                entry_type=ep["entry_type"],
                http_method=ep.get("http_method"),
                http_path=ep.get("http_path"),
                cron_expression=ep.get("cron_expression"),
                mq_queue=ep.get("mq_queue"),
            )
        )

    return entry_points
