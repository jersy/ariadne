"""Schemas for impact analysis endpoint."""

from pydantic import BaseModel, Field

from ariadne_api.schemas.common import PaginatedResponse


class ImpactRequest(BaseModel):
    """Request parameters for impact analysis."""

    target: str = Field(description="Symbol FQN to analyze")
    depth: int = Field(default=5, ge=1, le=20, description="Reverse traversal depth")
    include_tests: bool = Field(default=True, description="Include test mapping")
    include_transitive: bool = Field(default=False, description="Include N-order dependencies")
    risk_threshold: str = Field(default="low", description="Filter by risk level (low, medium, high, critical)")


class AffectedCaller(BaseModel):
    """A caller that would be affected by the change."""

    fqn: str = Field(description="Caller FQN")
    kind: str = Field(description="Symbol kind")
    name: str = Field(description="Symbol name")
    layer: str = Field(description="Architectural layer")
    depth: int = Field(description="Distance from target")


class AffectedEntryPoint(BaseModel):
    """An entry point that would be affected by the change."""

    fqn: str = Field(description="Entry point FQN")
    entry_type: str = Field(description="Entry type (http_api, scheduled, mq_consumer)")
    http_method: str | None = Field(default=None, description="HTTP method")
    http_path: str | None = Field(default=None, description="HTTP path")
    cron_expression: str | None = Field(default=None, description="Cron expression")
    mq_queue: str | None = Field(default=None, description="MQ queue")


class RelatedTest(BaseModel):
    """A test file related to affected symbols."""

    path: str = Field(description="Test file path")
    covers: list[str] = Field(description="Symbols covered by this test")
    additional_tests: list[str] = Field(default_factory=list, description="Additional test files")


class MissingCoverage(BaseModel):
    """Affected symbol without test coverage."""

    fqn: str = Field(description="Symbol FQN")
    kind: str = Field(description="Symbol kind")
    name: str = Field(description="Symbol name")
    layer: str = Field(description="Architectural layer")
    depth: int = Field(description="Distance from target")


class ImpactResponse(BaseModel):
    """Response from impact analysis."""

    target: dict = Field(description="Target symbol information")
    affected_callers: list[AffectedCaller] = Field(description="Affected callers")
    affected_entry_points: list[AffectedEntryPoint] = Field(description="Affected entry points")
    related_tests: list[RelatedTest] = Field(description="Related test files")
    missing_test_coverage: list[MissingCoverage] = Field(description="Missing test coverage")
    risk_level: str = Field(description="Overall risk level (LOW, MEDIUM, HIGH, CRITICAL)")
    confidence: float = Field(description="Confidence score (0-1)")
