"""Schemas for symbol detail endpoint."""

from pydantic import BaseModel, Field


class SymbolDetail(BaseModel):
    """Detailed information about a symbol."""

    fqn: str = Field(description="Fully qualified name")
    kind: str = Field(description="Symbol kind (method, class, interface, field)")
    name: str = Field(description="Symbol name")
    file_path: str | None = Field(default=None, description="Source file path")
    line_number: int | None = Field(default=None, description="Line number")
    modifiers: list[str] = Field(default_factory=list, description="Access modifiers (public, private, etc.)")
    signature: str | None = Field(default=None, description="Method signature")
    parent_fqn: str | None = Field(default=None, description="Parent class FQN")
    annotations: list[str] = Field(default_factory=list, description="Java annotations")
    summary: str | None = Field(default=None, description="Business summary (if available)")
    entry_point: dict[str, str | None] | None = Field(default=None, description="Entry point details (if applicable)")
