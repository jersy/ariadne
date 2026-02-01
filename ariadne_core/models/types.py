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


# ========================
# L2 Architecture Layer Types
# ========================


class EntryType(str, Enum):
    """入口点类型。"""

    HTTP_API = "http_api"
    SCHEDULED = "scheduled"
    MQ_CONSUMER = "mq_consumer"


class DependencyType(str, Enum):
    """外部依赖类型。"""

    REDIS = "redis"
    MYSQL = "mysql"
    MQ = "mq"
    HTTP = "http"
    RPC = "rpc"


class DependencyStrength(str, Enum):
    """依赖强度。"""

    STRONG = "strong"
    WEAK = "weak"


class Severity(str, Enum):
    """反模式严重性。"""

    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


@dataclass
class EntryPointData:
    """入口点（HTTP API、定时任务、消息消费者）。"""

    symbol_fqn: str
    entry_type: EntryType
    http_method: Optional[str] = None
    http_path: Optional[str] = None
    cron_expression: Optional[str] = None
    mq_queue: Optional[str] = None

    def to_row(self) -> tuple:
        """Convert to SQLite row tuple."""
        return (
            self.symbol_fqn,
            self.entry_type.value,
            self.http_method,
            self.http_path,
            self.cron_expression,
            self.mq_queue,
        )


@dataclass
class ExternalDependencyData:
    """外部依赖调用（Redis/MySQL/MQ 等）。"""

    caller_fqn: str
    dependency_type: DependencyType
    target: str
    strength: DependencyStrength = DependencyStrength.STRONG

    def to_row(self) -> tuple:
        """Convert to SQLite row tuple."""
        return (
            self.caller_fqn,
            self.dependency_type.value,
            self.target,
            self.strength.value,
        )


@dataclass
class AntiPatternData:
    """反模式检测结果。"""

    rule_id: str
    from_fqn: str
    severity: Severity
    message: str
    to_fqn: Optional[str] = None

    def to_row(self) -> tuple:
        """Convert to SQLite row tuple."""
        return (
            self.rule_id,
            self.from_fqn,
            self.to_fqn,
            self.severity.value,
            self.message,
        )


@dataclass
class CallChainResult:
    """调用链追踪结果。"""

    entry: dict
    chain: list[dict]
    external_deps: list[dict]
    depth: int

    @property
    def entry_fqn(self) -> str:
        """获取入口点的 FQN。"""
        return self.entry.get("symbol_fqn") or self.entry.get("fqn", "")

    @property
    def max_depth(self) -> int:
        """最大深度的别名。"""
        return self.depth
