"""Schemas for graph query endpoint."""

from pydantic import BaseModel, Field
from typing import Any, Literal

from ariadne_api.schemas.common import PaginatedResponse


class GraphQueryRequest(BaseModel):
    """Request for graph traversal query."""

    start: str = Field(description="Starting symbol FQN")
    relation: str = Field(
        default="calls",
        description="Relation type: calls, inherits, implements",
    )
    direction: Literal["outgoing", "incoming", "both"] = Field(
        default="outgoing",
        description="Traversal direction",
    )
    depth: int = Field(default=3, ge=1, le=20, description="Maximum traversal depth")
    filters: dict[str, Any] = Field(
        default_factory=dict,
        description="Filter criteria (kind, layer, etc.)",
    )
    max_results: int = Field(default=1000, ge=1, le=5000, description="Maximum number of nodes")


class GraphNode(BaseModel):
    """A node in the graph."""

    fqn: str = Field(description="Fully qualified name")
    kind: str = Field(description="Symbol kind (method, class, interface, field)")
    name: str = Field(description="Symbol name")
    layer: str | None = Field(default=None, description="Architectural layer (controller, service, repository)")
    file_path: str | None = Field(default=None, description="Source file path")
    line_number: int | None = Field(default=None, description="Line number")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Additional metadata")


class GraphEdge(BaseModel):
    """An edge in the graph."""

    from_fqn: str = Field(description="Source symbol FQN")
    to_fqn: str = Field(description="Target symbol FQN")
    relation: str = Field(description="Relation type (calls, inherits, implements)")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Additional edge metadata")


class GraphMetadata(BaseModel):
    """Metadata about graph query results."""

    max_depth: int = Field(description="Maximum depth reached")
    total_nodes: int = Field(description="Total number of nodes")
    total_edges: int = Field(description="Total number of edges")
    truncated: bool = Field(default=False, description="Whether results were truncated")
    query_time_ms: int | None = Field(default=None, description="Query execution time in milliseconds")


class GraphResponse(BaseModel):
    """Response from graph query."""

    nodes: list[GraphNode] = Field(description="Graph nodes")
    edges: list[GraphEdge] = Field(description="Graph edges")
    metadata: GraphMetadata = Field(description="Query metadata")
