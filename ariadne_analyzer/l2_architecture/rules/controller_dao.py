"""Controller-DAO anti-pattern rule."""

from __future__ import annotations

import json

from ariadne_core.models.types import AntiPatternData, Severity
from ariadne_core.storage.sqlite_store import SQLiteStore

from ariadne_analyzer.l2_architecture.rules.base import AntiPatternRule


class ControllerDaoRule(AntiPatternRule):
    """检测 Controller 直接调用 DAO/Mapper 的反模式。

    Controller 层应该通过 Service 层访问数据层，
    直接调用 DAO/Mapper 会导致业务逻辑分散、难以维护。
    """

    @property
    def rule_id(self) -> str:
        return "controller-dao"

    @property
    def severity(self) -> Severity:
        return Severity.ERROR

    @property
    def description(self) -> str:
        return "Controller 不应直接调用 DAO/Mapper，请通过 Service 层中转"

    def detect(self, store: SQLiteStore) -> list[AntiPatternData]:
        """检测 Controller 直接调用 DAO 的情况。"""
        results: list[AntiPatternData] = []

        # 获取所有类
        all_classes = store.get_symbols_by_kind("class")

        # 筛选 Controller 类
        controllers = []
        for cls in all_classes:
            if self._is_controller(cls):
                controllers.append(cls)

        # 检查每个 Controller 的方法
        for controller in controllers:
            # 获取 Controller 中的方法
            methods = store.get_symbols_by_parent(controller["fqn"])

            for method in methods:
                if method["kind"] != "method":
                    continue

                # 获取方法的所有调用
                calls = store.get_edges_from(method["fqn"], "calls")

                for call in calls:
                    to_fqn = call.get("to_fqn", "")

                    # 检查是否调用了 DAO/Mapper
                    if self._is_dao_call(to_fqn, store):
                        results.append(
                            AntiPatternData(
                                rule_id=self.rule_id,
                                from_fqn=method["fqn"],
                                to_fqn=to_fqn,
                                severity=Severity.ERROR,
                                message=self.description,
                            )
                        )

        return results

    def _is_controller(self, symbol: dict) -> bool:
        """判断是否是 Controller 类。"""
        name = symbol.get("name", "")
        annotations_str = symbol.get("annotations", "")

        # 从注解判断
        try:
            annotations = json.loads(annotations_str) if annotations_str else []
        except json.JSONDecodeError:
            annotations = []

        for ann in annotations:
            if "RestController" in ann or "Controller" in ann:
                return True

        # 从名称判断
        return "Controller" in name

    def _is_dao_call(self, fqn: str, store: SQLiteStore) -> bool:
        """判断是否是 DAO/Mapper 调用。"""
        if not fqn:
            return False

        # 提取类名部分
        if "(" in fqn:
            fqn = fqn.split("(")[0]

        if "." not in fqn:
            return False

        # 获取方法所属的类
        class_fqn = fqn.rsplit(".", 1)[0]
        class_name = class_fqn.rsplit(".", 1)[-1] if "." in class_fqn else class_fqn

        # 从名称判断
        if any(
            pattern in class_name
            for pattern in ("Mapper", "Dao", "Repository")
        ):
            # 排除 Base 类
            if class_name.startswith("Base"):
                return False
            return True

        # 尝试查询符号
        class_symbol = store.get_symbol(class_fqn)
        if class_symbol:
            annotations_str = class_symbol.get("annotations", "")
            try:
                annotations = json.loads(annotations_str) if annotations_str else []
            except json.JSONDecodeError:
                annotations = []

            for ann in annotations:
                if "Repository" in ann or "Mapper" in ann:
                    return True

        return False
