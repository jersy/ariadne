"""Base class for anti-pattern detection rules."""

from __future__ import annotations

from abc import ABC, abstractmethod

from ariadne_core.models.types import AntiPatternData
from ariadne_core.storage.sqlite_store import SQLiteStore


class AntiPatternRule(ABC):
    """反模式检测规则的基类。"""

    @property
    @abstractmethod
    def rule_id(self) -> str:
        """规则 ID。"""
        pass

    @property
    @abstractmethod
    def severity(self) -> str:
        """严重性: error, warning, info。"""
        pass

    @property
    @abstractmethod
    def description(self) -> str:
        """规则描述。"""
        pass

    @abstractmethod
    def detect(self, store: SQLiteStore) -> list[AntiPatternData]:
        """执行检测并返回发现的反模式。"""
        pass
