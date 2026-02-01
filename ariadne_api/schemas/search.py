"""Schemas for search endpoint."""

from pydantic import BaseModel, Field

from ariadne_api.schemas.common import PaginatedResponse


class SearchRequest(BaseModel):
    """Request parameters for knowledge search."""

    query: str = Field(description="Search query string", min_length=1)
    num_results: int = Field(default=10, ge=1, le=100, description="Number of results to return")
    level: list[str] = Field(
        default=["method", "class", "package"],
        description="Filter by summary level (method, class, package)",
    )
    entry_type: list[str] | None = Field(
        default=None,
        description="Filter by entry type (http_api, scheduled, mq_consumer)",
    )
    sort_by: str = Field(
        default="relevance",
        description="Sort by: relevance, name, recent",
    )


class SymbolRef(BaseModel):
    """Reference to a symbol in search results."""

    fqn: str = Field(description="Fully qualified name")
    kind: str = Field(description="Symbol kind (method, class, interface, field)")
    name: str = Field(description="Symbol name")
    file_path: str | None = Field(default=None, description="Source file path")
    line_number: int | None = Field(default=None, description="Line number")
    signature: str | None = Field(default=None, description="Signature for methods")


class EntryPointRef(BaseModel):
    """Reference to an entry point in search results."""

    fqn: str = Field(description="Entry point FQN")
    entry_type: str = Field(description="Entry type (http_api, scheduled, mq_consumer)")
    http_method: str | None = Field(default=None, description="HTTP method for API endpoints")
    http_path: str | None = Field(default=None, description="HTTP path for API endpoints")
    cron_expression: str | None = Field(default=None, description="Cron expression for scheduled tasks")
    mq_queue: str | None = Field(default=None, description="MQ queue name")


class SearchResultItem(BaseModel):
    """Single search result."""

    fqn: str = Field(description="Symbol FQN")
    kind: str = Field(description="Symbol kind")
    summary: str = Field(description="Business summary of the symbol")
    score: float = Field(description="Relevance score (0-1)")
    symbols: SymbolRef | None = Field(default=None, description="Symbol details")
    entry_points: list[EntryPointRef] = Field(default_factory=list, description="Related entry points")
    constraints: list[str] = Field(default_factory=list, description="Related business constraints")


class SearchResponse(PaginatedResponse):
    """Response from knowledge search."""

    warning: str | None = Field(default=None, description="Warning message (e.g., degraded mode)")
    results: list[SearchResultItem] = Field(description="Search results")
