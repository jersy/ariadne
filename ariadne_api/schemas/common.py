"""Common Pydantic schemas for Ariadne API responses."""

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    """Health check response."""

    status: str = Field(description="Service status: 'healthy', 'degraded', or 'unhealthy'")
    services: dict[str, str] = Field(
        default_factory=dict,
        description="Status of individual services (database, vector_db, llm)",
    )


class ErrorResponse(BaseModel):
    """RFC 7807 Problem Details for error responses."""

    type: str = Field(default="about:blank", description="Error type URI")
    title: str = Field(description="Short error title")
    status: int = Field(description="HTTP status code")
    detail: str | None = Field(default=None, description="Detailed error message")
    instance: str | None = Field(default=None, description="Request identifier")


class PaginatedResponse(BaseModel):
    """Base class for paginated responses."""

    total: int = Field(description="Total number of results")
    offset: int = Field(default=0, description="Result offset")
    limit: int = Field(default=100, description="Results per page")


class SuccessResponse(BaseModel):
    """Generic success response."""

    message: str = Field(description="Success message")
    data: dict[str, object] | None = Field(default=None, description="Additional data")
