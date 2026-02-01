"""Graph query endpoint for call graph traversal."""

import logging
import os
import time
from typing import Any, Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ariadne_api.schemas.graph import GraphQueryRequest, GraphResponse, GraphNode, GraphEdge, GraphMetadata
from ariadne_core.storage.sqlite_store import SQLiteStore

router = APIRouter()
logger = logging.getLogger(__name__)


def get_store() -> SQLiteStore:
    """Dependency to get SQLite store."""
    db_path = os.environ.get("ARIADNE_DB_PATH", "ariadne.db")
    if not os.path.exists(db_path):
        raise HTTPException(status_code=503, detail="Database not available")
    return SQLiteStore(db_path)


@router.post("/knowledge/graph/query", response_model=GraphResponse, tags=["graph"])
async def query_graph(request: GraphQueryRequest) -> GraphResponse:
    """Query the call graph with bidirectional traversal.

    Supports:
    - Forward traversal (calls made by a symbol)
    - Reverse traversal (callers of a symbol)
    - Bidirectional traversal (both directions)
    - Multiple relation types (calls, inherits, implements)
    """
    store = get_store()
    start_time = time.time()

    # Validate starting symbol exists
    start_symbol = store.get_symbol(request.start)
    if not start_symbol:
        raise HTTPException(status_code=404, detail=f"Symbol not found: {request.start}")

    nodes: dict[str, GraphNode] = {}
    edges: list[GraphEdge] = []

    # Traverse based on direction
    if request.direction in ("outgoing", "both"):
        outgoing_nodes, outgoing_edges = _traverse_outgoing(
            store, request.start, request.relation, request.depth, request.filters
        )
        nodes.update(outgoing_nodes)
        edges.extend(outgoing_edges)

    if request.direction in ("incoming", "both"):
        incoming_nodes, incoming_edges = _traverse_incoming(
            store, request.start, request.relation, request.depth, request.filters
        )
        nodes.update(incoming_nodes)
        edges.extend(incoming_edges)

    # Add start node if not already present
    if request.start not in nodes:
        nodes[request.start] = _create_node(start_symbol)

    # Apply max_results limit
    node_list = list(nodes.values())
    truncated = len(node_list) > request.max_results
    if truncated:
        node_list = node_list[: request.max_results]

    query_time_ms = int((time.time() - start_time) * 1000)

    return GraphResponse(
        nodes=node_list,
        edges=edges,
        metadata=GraphMetadata(
            max_depth=request.depth,
            total_nodes=len(nodes),
            total_edges=len(edges),
            truncated=truncated,
            query_time_ms=query_time_ms,
        ),
    )


def _traverse_outgoing(
    store: SQLiteStore,
    start_fqn: str,
    relation: str,
    max_depth: int,
    filters: dict[str, Any],
) -> tuple[dict[str, GraphNode], list[GraphEdge]]:
    """Traverse graph in outgoing direction (calls made by start_fqn)."""
    cursor = store.conn.cursor()

    # Get forward call chain using recursive CTE
    if relation == "calls":
        cursor.execute(
            """
            WITH RECURSIVE call_chain(depth, from_fqn, to_fqn, relation) AS (
                SELECT 0, from_fqn, to_fqn, relation
                FROM edges
                WHERE from_fqn = ? AND relation = 'calls'

                UNION ALL

                SELECT cc.depth + 1, e.from_fqn, e.to_fqn, e.relation
                FROM edges e
                JOIN call_chain cc ON e.from_fqn = cc.to_fqn
                WHERE cc.depth < ? AND e.relation = 'calls'
            )
            SELECT DISTINCT * FROM call_chain ORDER BY depth
            """,
            (start_fqn, max_depth),
        )
    else:
        # Other relation types
        cursor.execute(
            """
            WITH RECURSIVE chain(depth, from_fqn, to_fqn, relation) AS (
                SELECT 0, from_fqn, to_fqn, relation
                FROM edges
                WHERE from_fqn = ? AND relation = ?

                UNION ALL

                SELECT c.depth + 1, e.from_fqn, e.to_fqn, e.relation
                FROM edges e
                JOIN chain c ON e.from_fqn = c.to_fqn
                WHERE c.depth < ? AND e.relation = ?
            )
            SELECT DISTINCT * FROM chain ORDER BY depth
            """,
            (start_fqn, relation, max_depth, relation),
        )

    nodes: dict[str, GraphNode] = {}
    edges: list[GraphEdge] = []

    for row in cursor.fetchall():
        edge_data = dict(row)

        # Add nodes if not already present
        for fqn in [edge_data["from_fqn"], edge_data["to_fqn"]]:
            if fqn not in nodes:
                symbol = store.get_symbol(fqn)
                if symbol:
                    nodes[fqn] = _create_node(symbol)

        # Add edge
        edges.append(
            GraphEdge(
                from_fqn=edge_data["from_fqn"],
                to_fqn=edge_data["to_fqn"],
                relation=edge_data["relation"],
            )
        )

    return nodes, edges


def _traverse_incoming(
    store: SQLiteStore,
    start_fqn: str,
    relation: str,
    max_depth: int,
    filters: dict[str, Any],
) -> tuple[dict[str, GraphNode], list[GraphEdge]]:
    """Traverse graph in incoming direction (callers of start_fqn)."""
    cursor = store.conn.cursor()

    # Get reverse callers using recursive CTE
    if relation == "calls":
        cursor.execute(
            """
            WITH RECURSIVE callers(depth, from_fqn, to_fqn, relation) AS (
                SELECT 0, from_fqn, to_fqn, relation
                FROM edges
                WHERE to_fqn = ? AND relation = 'calls'

                UNION ALL

                SELECT c.depth + 1, e.from_fqn, e.to_fqn, e.relation
                FROM edges e
                JOIN callers c ON e.to_fqn = c.from_fqn
                WHERE c.depth < ? AND e.relation = 'calls'
            )
            SELECT DISTINCT * FROM callers ORDER BY depth
            """,
            (start_fqn, max_depth),
        )
    else:
        cursor.execute(
            """
            WITH RECURSIVE callers(depth, from_fqn, to_fqn, relation) AS (
                SELECT 0, from_fqn, to_fqn, relation
                FROM edges
                WHERE to_fqn = ? AND relation = ?

                UNION ALL

                SELECT c.depth + 1, e.from_fqn, e.to_fqn, e.relation
                FROM edges e
                JOIN callers c ON e.to_fqn = c.from_fqn
                WHERE c.depth < ? AND e.relation = ?
            )
            SELECT DISTINCT * FROM callers ORDER BY depth
            """,
            (start_fqn, relation, max_depth, relation),
        )

    nodes: dict[str, GraphNode] = {}
    edges: list[GraphEdge] = []

    for row in cursor.fetchall():
        edge_data = dict(row)

        # Add nodes if not already present
        for fqn in [edge_data["from_fqn"], edge_data["to_fqn"]]:
            if fqn not in nodes:
                symbol = store.get_symbol(fqn)
                if symbol:
                    nodes[fqn] = _create_node(symbol)

        # Add edge
        edges.append(
            GraphEdge(
                from_fqn=edge_data["from_fqn"],
                to_fqn=edge_data["to_fqn"],
                relation=edge_data["relation"],
            )
        )

    return nodes, edges


def _create_node(symbol: dict[str, Any]) -> GraphNode:
    """Create a GraphNode from a symbol dict."""
    # Determine layer from annotations
    layer = None
    annotations = symbol.get("annotations")
    if annotations is None:
        annotations = []
    elif isinstance(annotations, str):
        annotations = [annotations]

    if "Controller" in annotations or "RestController" in annotations:
        layer = "controller"
    elif "Service" in annotations:
        layer = "service"
    elif "Repository" in annotations:
        layer = "repository"

    return GraphNode(
        fqn=symbol["fqn"],
        kind=symbol["kind"],
        name=symbol["name"],
        layer=layer,
        file_path=symbol.get("file_path"),
        line_number=symbol.get("line_number"),
        metadata={
            "modifiers": symbol.get("modifiers", []),
            "signature": symbol.get("signature"),
        },
    )
