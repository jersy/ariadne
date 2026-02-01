"""Anti-pattern detector for architecture violations."""

from __future__ import annotations

from ariadne_core.models.types import AntiPatternData
from ariadne_core.storage.sqlite_store import SQLiteStore

from ariadne_analyzer.l2_architecture.rules.base import AntiPatternRule
from ariadne_analyzer.l2_architecture.rules.controller_dao import ControllerDaoRule


class AntiPatternDetector:
    """反模式检测器，运行所有注册的规则。"""

    def __init__(self, store: SQLiteStore):
        self.store = store
        self.rules: list[AntiPatternRule] = [
            ControllerDaoRule(),
            # 后续可添加更多规则:
            # CircularDepRule(),
            # ServiceControllerRule(),
            # NoTransactionRule(),
        ]

    def detect_all(self) -> list[AntiPatternData]:
        """运行所有规则并返回检测结果。"""
        results: list[AntiPatternData] = []
        for rule in self.rules:
            results.extend(rule.detect(self.store))
        return results

    def detect_by_rule(self, rule_id: str) -> list[AntiPatternData]:
        """运行指定规则。"""
        for rule in self.rules:
            if rule.rule_id == rule_id:
                return rule.detect(self.store)
        raise ValueError(f"Unknown rule: {rule_id}")

    def list_rules(self) -> list[dict]:
        """列出所有可用规则。"""
        return [
            {
                "rule_id": rule.rule_id,
                "severity": rule.severity,
                "description": rule.description,
            }
            for rule in self.rules
        ]
