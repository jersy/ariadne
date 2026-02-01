"""Schemas for constraints and check endpoints."""

from pydantic import BaseModel, Field


class ConstraintEntry(BaseModel):
    """A business constraint entry."""

    name: str = Field(description="Constraint name")
    description: str = Field(description="Constraint description")
    source_fqn: str | None = Field(default=None, description="Source symbol FQN")
    source_line: int | None = Field(default=None, description="Source line number")
    constraint_type: str | None = Field(default=None, description="Constraint type")


class AntiPatternViolation(BaseModel):
    """An anti-pattern violation."""

    rule_id: str = Field(description="Rule identifier")
    from_fqn: str = Field(description="Source symbol FQN")
    to_fqn: str | None = Field(default=None, description="Target symbol FQN")
    severity: str = Field(description="Severity level (error, warning, info)")
    message: str = Field(description="Violation message")
    detected_at: str = Field(description="Detection timestamp")


class CodeChange(BaseModel):
    """A code change for live checking."""

    file: str = Field(description="File path")
    diff: str | None = Field(default=None, description="Git diff")
    added_symbols: list[str] = Field(default_factory=list, description="Added symbol FQNs")
    removed_symbols: list[str] = Field(default_factory=list, description="Removed symbol FQNs")


class CheckRequest(BaseModel):
    """Request for live code check."""

    changes: list[CodeChange] = Field(description="Code changes to check")


class CheckResult(BaseModel):
    """Result of code check."""

    violations: list[AntiPatternViolation] = Field(description="Detected violations")
    warnings: list[AntiPatternViolation] = Field(description="Warnings")
    suggestions: list[str] = Field(default_factory=list, description="Suggestions for fixes")


class ConstraintsResponse(BaseModel):
    """Response from constraints endpoint."""

    constraints: list[ConstraintEntry] = Field(description="Business constraints")
    anti_patterns: list[AntiPatternViolation] = Field(description="Detected anti-patterns")
