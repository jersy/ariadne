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


# ========================
# Batch Operations Schemas (P2 #036)
# ========================

class BatchTestMappingRequest(BaseModel):
    """Request for batch test mapping."""

    fqns: list[str] = Field(description="List of source symbol FQNs to map", min_length=1, max_length=100)
    include_methods: bool = Field(default=True, description="Include test methods in response")


class BatchTestMappingSummary(BaseModel):
    """Summary statistics for batch test mapping."""

    total: int = Field(description="Total number of FQNs requested")
    found: int = Field(description="Number of symbols found in database")
    with_tests: int = Field(description="Number of symbols with existing test files")


class BatchTestMappingResponse(BaseModel):
    """Response from batch test mapping endpoint."""

    mappings: dict[str, TestMappingResponse] = Field(description="Test mappings by FQN")
    summary: BatchTestMappingSummary = Field(description="Summary statistics")


class BatchCoverageRequest(BaseModel):
    """Request for batch coverage analysis."""

    targets: list[str] = Field(description="List of target symbol FQNs to analyze", min_length=1, max_length=100)


class BatchCoverageSummary(BaseModel):
    """Summary statistics for batch coverage analysis."""

    total: int = Field(description="Total number of targets requested")
    average_coverage: float = Field(description="Average coverage percentage across all targets")
    total_warnings: int = Field(description="Total warnings across all targets")


class BatchCoverageResponse(BaseModel):
    """Response from batch coverage analysis endpoint."""

    coverage: dict[str, CoverageAnalysisResponse] = Field(description="Coverage analysis by target FQN")
    summary: BatchCoverageSummary = Field(description="Summary statistics")
