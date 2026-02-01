"""Anti-pattern rules package."""

from ariadne_analyzer.l2_architecture.rules.base import AntiPatternRule
from ariadne_analyzer.l2_architecture.rules.controller_dao import ControllerDaoRule

__all__ = ["AntiPatternRule", "ControllerDaoRule"]
