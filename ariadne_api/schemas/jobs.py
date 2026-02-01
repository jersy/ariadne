"""Schemas for job queue and rebuild endpoints."""

from pydantic import BaseModel, Field


class RebuildRequest(BaseModel):
    """Request to trigger a rebuild."""

    mode: str = Field(default="incremental", description="Rebuild mode: 'incremental' or 'full'")
    target_paths: list[str] | None = Field(default=None, description="Specific files/directories for incremental rebuild")
    run_async: bool = Field(default=True, description="Run in background (async) or wait for completion", alias="async")


class RebuildResponse(BaseModel):
    """Response from rebuild request."""

    job_id: str | None = Field(default=None, description="Job ID (for async rebuilds)")
    status: str = Field(description="Job status: 'pending', 'running', 'complete'")
    message: str = Field(description="Human-readable message")
    stats: dict[str, int | str] | None = Field(default=None, description="Rebuild statistics (for sync rebuilds)")


class JobResponse(BaseModel):
    """Response from job status query."""

    job_id: str = Field(description="Job ID")
    mode: str = Field(description="Rebuild mode")
    status: str = Field(description="Job status")
    progress: int = Field(description="Progress percentage (0-100)")
    total_files: int = Field(description="Total files to process")
    processed_files: int = Field(description="Number of files processed")
    target_paths: list[str] | None = Field(default=None, description="Target paths")
    started_at: str | None = Field(default=None, description="Start timestamp")
    completed_at: str | None = Field(default=None, description="Completion timestamp")
    error_message: str | None = Field(default=None, description="Error message (if failed)")
    created_at: str = Field(description="Creation timestamp")
