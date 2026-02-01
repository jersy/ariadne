"""Search endpoint for semantic + keyword search."""

import asyncio
import logging
import os
from collections import defaultdict
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import ValidationError

from ariadne_api.dependencies import get_store
from ariadne_api.schemas.search import SearchRequest, SearchResponse, SearchResultItem, SymbolRef, EntryPointRef
from ariadne_core.storage.vector_store import ChromaVectorStore

router = APIRouter()
logger = logging.getLogger(__name__)


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
    with get_store() as store:
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
                        # Generate embedding for query (run in thread pool to avoid blocking event loop)
                        query_embedding = await asyncio.to_thread(embedder.embed_text, query)

                        # Search in vector store
                        search_result = vector_store.search_summaries(
                            query_embedding,
                            n_results=num_results,
                        )

                        # Process vector search results
                        if search_result.get("ids") and search_result["ids"][0]:
                            result_fqns = search_result["ids"][0]

                            # Batch fetch all symbols and entry points (fixes N+1 query)
                            symbols_map = _batch_get_symbols(store, result_fqns)
                            entry_points_map = _batch_get_entry_points(store, result_fqns)

                            for i, fqn in enumerate(result_fqns):
                                summary = search_result["documents"][0][i]
                                distance = search_result["distances"][0][i]
                                score = 1 - distance

                                # Get symbol details from batch-fetched map
                                symbol = symbols_map.get(fqn)
                                if symbol:
                                    # Get entry points from batch-fetched map
                                    entry_points = entry_points_map.get(fqn, [])

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
    store,
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

    symbols = [dict(row) for row in cursor.fetchall()]

    if not symbols:
        return []

    # Collect FQNs for batch queries
    symbol_fqns = [s["fqn"] for s in symbols]

    # Batch fetch summaries and entry points (fixes N+1 query)
    summaries_map = _batch_get_summaries(store, symbol_fqns)
    entry_points_map = _batch_get_entry_points(store, symbol_fqns)

    results: list[SearchResultItem] = []
    for symbol in symbols:
        fqn = symbol["fqn"]

        # Get summary from batch-fetched map
        summary_data = summaries_map.get(fqn)
        summary = summary_data["summary"] if summary_data else f"{symbol['kind']}: {symbol['name']}"

        # Get entry points from batch-fetched map
        entry_points = entry_points_map.get(fqn, [])

        results.append(
            SearchResultItem(
                fqn=fqn,
                kind=symbol["kind"],
                summary=summary,
                score=0.5,  # Default score for keyword results
                symbols=SymbolRef(
                    fqn=fqn,
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


def _get_entry_points_for_symbol(store, fqn: str) -> list[EntryPointRef]:
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


def _batch_get_symbols(store, fqns: list[str]) -> dict[str, dict[str, Any]]:
    """Batch fetch symbols by FQN.

    Returns a dictionary mapping FQN to symbol data.
    """
    if not fqns:
        return {}

    placeholders = ",".join("?" * len(fqns))
    cursor = store.conn.cursor()

    cursor.execute(
        f"SELECT * FROM symbols WHERE fqn IN ({placeholders})",
        fqns,
    )

    return {row["fqn"]: dict(row) for row in cursor.fetchall()}


def _batch_get_entry_points(store, fqns: list[str]) -> dict[str, list[EntryPointRef]]:
    """Batch fetch entry points for multiple symbols.

    Returns a dictionary mapping FQN to list of entry points.
    """
    if not fqns:
        return {}

    placeholders = ",".join("?" * len(fqns))
    cursor = store.conn.cursor()

    cursor.execute(
        f"SELECT * FROM entry_points WHERE symbol_fqn IN ({placeholders})",
        fqns,
    )

    result: dict[str, list[EntryPointRef]] = defaultdict(list)
    for row in cursor.fetchall():
        ep = dict(row)
        result[ep["symbol_fqn"]].append(
            EntryPointRef(
                fqn=ep["symbol_fqn"],
                entry_type=ep["entry_type"],
                http_method=ep.get("http_method"),
                http_path=ep.get("http_path"),
                cron_expression=ep.get("cron_expression"),
                mq_queue=ep.get("mq_queue"),
            )
        )

    return result


def _batch_get_summaries(store, fqns: list[str]) -> dict[str, dict[str, Any]]:
    """Batch fetch summaries for multiple symbols.

    Returns a dictionary mapping FQN to summary data.
    """
    if not fqns:
        return {}

    placeholders = ",".join("?" * len(fqns))
    cursor = store.conn.cursor()

    cursor.execute(
        f"SELECT * FROM summaries WHERE target_fqn IN ({placeholders})",
        fqns,
    )

    return {row["target_fqn"]: dict(row) for row in cursor.fetchall()}
