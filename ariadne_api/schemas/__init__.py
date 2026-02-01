"""API schemas for Ariadne."""

from ariadne_api.schemas.common import (
    ErrorResponse,
    HealthResponse,
    PaginatedResponse,
    SuccessResponse,
)
from ariadne_api.schemas.constraints import (
    AntiPatternViolation,
    CheckRequest,
    CheckResult,
    CodeChange,
    ConstraintEntry,
    ConstraintsResponse,
)
from ariadne_api.schemas.glossary import (
    GlossarySearchResponse,
    GlossaryTerm,
    GlossaryTermList,
)
from ariadne_api.schemas.graph import (
    GraphEdge,
    GraphMetadata,
    GraphNode,
    GraphQueryRequest,
    GraphResponse,
)
from ariadne_api.schemas.impact import (
    AffectedCaller,
    AffectedEntryPoint,
    ImpactResponse,
    MissingCoverage,
    RelatedTest,
)
from ariadne_api.schemas.jobs import JobResponse, RebuildRequest, RebuildResponse
from ariadne_api.schemas.search import (
    EntryPointRef,
    SearchRequest,
    SearchResponse,
    SearchResultItem,
    SymbolRef,
)
from ariadne_api.schemas.symbol import SymbolDetail

__all__ = [
    "ErrorResponse",
    "HealthResponse",
    "PaginatedResponse",
    "SuccessResponse",
    "AntiPatternViolation",
    "CheckRequest",
    "CheckResult",
    "CodeChange",
    "ConstraintEntry",
    "ConstraintsResponse",
    "GlossarySearchResponse",
    "GlossaryTerm",
    "GlossaryTermList",
    "GraphEdge",
    "GraphMetadata",
    "GraphNode",
    "GraphQueryRequest",
    "GraphResponse",
    "AffectedCaller",
    "AffectedEntryPoint",
    "ImpactResponse",
    "MissingCoverage",
    "RelatedTest",
    "JobResponse",
    "RebuildRequest",
    "RebuildResponse",
    "EntryPointRef",
    "SearchRequest",
    "SearchResponse",
    "SearchResultItem",
    "SymbolRef",
    "SymbolDetail",
]
