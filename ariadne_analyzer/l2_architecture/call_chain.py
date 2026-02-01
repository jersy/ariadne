"""Call chain tracer for tracking request flows."""

from __future__ import annotations

import json
from typing import Any

from ariadne_core.models.types import CallChainResult
from ariadne_core.storage.sqlite_store import SQLiteStore


class CallChainTracer:
    """从入口点追踪完整调用链。"""

    def __init__(self, store: SQLiteStore):
        self.store = store

    def trace_from_entry(
        self,
        entry_pattern: str,
        max_depth: int = 10,
    ) -> CallChainResult:
        """追踪入口点的完整调用链。

        Args:
            entry_pattern: 入口模式，支持:
                - HTTP 模式: "POST /api/orders"
                - FQN 模式: "com.example.OrderController.create"
            max_depth: 最大追踪深度

        Returns:
            CallChainResult 包含调用链和外部依赖
        """
        # 1. 解析入口模式
        entry = self._resolve_entry(entry_pattern)
        if not entry:
            raise ValueError(f"Entry not found: {entry_pattern}")

        # 2. 获取调用链
        start_fqn = entry.get("symbol_fqn") or entry.get("fqn")
        chain = self.store.get_call_chain(start_fqn, max_depth)

        # 3. 标注层级
        annotated = self._annotate_layers(chain)

        # 4. 提取外部依赖
        deps = self._extract_dependencies(chain)

        return CallChainResult(
            entry=entry,
            chain=annotated,
            external_deps=deps,
            depth=max(c["depth"] for c in chain) if chain else 0,
        )

    def trace_from_fqn(
        self,
        fqn: str,
        max_depth: int = 10,
    ) -> CallChainResult:
        """从 FQN 直接追踪调用链（不需要入口点表）。

        Args:
            fqn: 符号的完全限定名
            max_depth: 最大追踪深度

        Returns:
            CallChainResult
        """
        symbol = self.store.get_symbol(fqn)
        if not symbol:
            raise ValueError(f"Symbol not found: {fqn}")

        chain = self.store.get_call_chain(fqn, max_depth)
        annotated = self._annotate_layers(chain)
        deps = self._extract_dependencies(chain)

        return CallChainResult(
            entry={"fqn": fqn, "symbol": symbol},
            chain=annotated,
            external_deps=deps,
            depth=max(c["depth"] for c in chain) if chain else 0,
        )

    def _resolve_entry(self, pattern: str) -> dict[str, Any] | None:
        """解析入口模式。"""
        # HTTP 模式: "GET /api/users" 或 "POST /api/orders"
        http_methods = ("GET ", "POST ", "PUT ", "DELETE ", "PATCH ", "HEAD ", "OPTIONS ")
        if pattern.startswith(http_methods):
            parts = pattern.split(" ", 1)
            if len(parts) == 2:
                method, path = parts
                entries = self.store.get_entry_points("http_api")
                for e in entries:
                    if e.get("http_method") == method and e.get("http_path") == path:
                        return e
                # 尝试路径前缀匹配
                for e in entries:
                    if e.get("http_method") == method and path.startswith(
                        e.get("http_path", "").rstrip("/")
                    ):
                        return e
            return None

        # FQN 模式: 直接查找符号
        symbol = self.store.get_symbol(pattern)
        if symbol:
            return {"fqn": pattern, "symbol": symbol}

        # 尝试在入口点表中查找
        all_entries = self.store.get_entry_points()
        for e in all_entries:
            if e.get("symbol_fqn") == pattern:
                return e

        return None

    def _annotate_layers(self, chain: list[dict]) -> list[dict]:
        """为调用链标注层级（Controller/Service/Repository）。"""
        for item in chain:
            to_fqn = item.get("to_fqn", "")
            layer = self._detect_layer(to_fqn)
            item["layer"] = layer
        return chain

    def _detect_layer(self, fqn: str) -> str:
        """检测符号所属的架构层级。"""
        symbol = self.store.get_symbol(fqn)
        if not symbol:
            # 尝试从 FQN 推断 - 检查完整的 FQN 而不只是最后一部分
            if "Controller" in fqn:
                return "controller"
            elif "Service" in fqn:
                return "service"
            elif "Mapper" in fqn or "Dao" in fqn or "Repository" in fqn:
                return "repository"
            return "unknown"

        # 从注解推断
        annotations_str = symbol.get("annotations", "")
        try:
            annotations = json.loads(annotations_str) if annotations_str else []
        except json.JSONDecodeError:
            annotations = []

        if any("RestController" in a or "Controller" in a for a in annotations):
            return "controller"
        elif any("Service" in a for a in annotations):
            return "service"
        elif any("Repository" in a or "Mapper" in a for a in annotations):
            return "repository"

        # 从符号名称推断
        name = symbol.get("name", "")
        if "Controller" in name:
            return "controller"
        elif "Service" in name and "Impl" not in name:
            return "service"
        elif "ServiceImpl" in name:
            return "service"
        elif "Mapper" in name or "Dao" in name or "Repository" in name:
            return "repository"

        # 从 FQN 推断（包括方法所在的类名）
        if "Controller" in fqn:
            return "controller"
        elif "Service" in fqn:
            return "service"
        elif "Mapper" in fqn or "Dao" in fqn or "Repository" in fqn:
            return "repository"

        return "unknown"

    def _extract_dependencies(self, chain: list[dict]) -> list[dict]:
        """从调用链中提取外部依赖。"""
        deps: list[dict] = []
        seen_targets: set[str] = set()

        # 收集调用链中所有方法的 FQN
        method_fqns: set[str] = set()
        for item in chain:
            method_fqns.add(item.get("from_fqn", ""))
            method_fqns.add(item.get("to_fqn", ""))

        # 查询这些方法的外部依赖
        for fqn in method_fqns:
            if not fqn:
                continue
            ext_deps = self.store.get_external_dependencies(caller_fqn=fqn)
            for dep in ext_deps:
                target = dep.get("target", "")
                if target not in seen_targets:
                    seen_targets.add(target)
                    deps.append(dep)

        return deps
