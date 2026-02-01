"""Core data types for Ariadne knowledge graph."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class SymbolKind(str, Enum):
    CLASS = "class"
    INTERFACE = "interface"
    METHOD = "method"
    FIELD = "field"


class RelationKind(str, Enum):
    CALLS = "calls"
    INHERITS = "inherits"
    IMPLEMENTS = "implements"
    INSTANTIATES = "instantiates"
    INJECTS = "injects"
    MEMBER_OF = "member_of"


@dataclass
class SymbolData:
    """A symbol (class, interface, method, field) in the knowledge graph."""

    fqn: str
    kind: SymbolKind
    name: str
    file_path: Optional[str] = None
    line_number: Optional[int] = None
    modifiers: list[str] = field(default_factory=list)
    signature: Optional[str] = None
    parent_fqn: Optional[str] = None
    annotations: list[str] = field(default_factory=list)

    def to_row(self) -> tuple:
        """Convert to SQLite row tuple."""
        return (
            self.fqn,
            self.kind.value,
            self.name,
            self.file_path,
            self.line_number,
            json.dumps(self.modifiers) if self.modifiers else None,
            self.signature,
            self.parent_fqn,
            json.dumps(self.annotations) if self.annotations else None,
        )


@dataclass
class EdgeData:
    """A relationship edge between two symbols."""

    from_fqn: str
    to_fqn: str
    relation: RelationKind
    metadata: Optional[dict] = None

    def to_row(self) -> tuple:
        """Convert to SQLite row tuple."""
        return (
            self.from_fqn,
            self.to_fqn,
            self.relation.value,
            json.dumps(self.metadata) if self.metadata else None,
        )


@dataclass
class ExtractionResult:
    """Result of extracting a Java project."""

    success: bool
    symbols: list[SymbolData] = field(default_factory=list)
    edges: list[EdgeData] = field(default_factory=list)
    stats: dict = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)
