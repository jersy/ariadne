"""Schemas for test mapping and coverage analysis endpoints."""

from pydantic import BaseModel, Field


class TestMappingEntry(BaseModel):
    """A single test file mapping entry."""

    test_file: str = Field(description="Path to the test file")
    test_exists: bool = Field(description="Whether the test file exists")
    test_pattern: str = Field(description="Test file naming pattern")
    test_methods: list[str] = Field(default_factory=list, description="Test method names found")


class TestMappingResponse(BaseModel):
    """Response from test mapping endpoint."""

    source_fqn: str = Field(description="Source symbol FQN")
    source_file: str | None = Field(description="Source file path", default=None)
    test_mappings: list[TestMappingEntry] = Field(description="List of test file mappings")


class CallerInfo(BaseModel):
    """Information about a caller symbol."""

    caller_fqn: str = Field(description="Caller FQN")
    caller_kind: str | None = Field(description="Caller symbol kind", default=None)
    caller_name: str | None = Field(description="Caller symbol name", default=None)
    caller_file: str = Field(description="Caller file path")
    is_test_file: bool = Field(description="Whether caller is a test file")
    is_covered: bool = Field(description="Whether caller has test coverage")


class CoverageStats(BaseModel):
    """Coverage statistics."""

    total_callers: int = Field(description="Total number of callers")
    tested_callers: int = Field(description="Number of callers with test coverage")
    coverage_percentage: float = Field(description="Coverage percentage (0-100)")


class CoverageWarning(BaseModel):
    """Warning about missing test coverage."""

    type: str = Field(description="Warning type (e.g., 'untested_caller')")
    severity: str = Field(description="Warning severity (low, medium, high)")
    message: str = Field(description="Warning message")
    caller_fqn: str = Field(description="Caller FQN that lacks coverage")


class CoverageAnalysisResponse(BaseModel):
    """Response from coverage analysis endpoint."""

    target_fqn: str = Field(description="Target symbol FQN")
    statistics: CoverageStats = Field(description="Coverage statistics")
    callers: list[CallerInfo] = Field(description="List of caller information")
    warnings: list[CoverageWarning] = Field(description="List of coverage warnings")
