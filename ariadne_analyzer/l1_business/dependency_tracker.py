"""
Dependency Tracker for Incremental Summarization
===================================================

Tracks 1-hop dependencies to determine which symbols need re-summarization
when a change occurs.
"""

import logging
from dataclasses import dataclass, field
from typing import Any

from ariadne_core.storage.sqlite_store import SQLiteStore

logger = logging.getLogger(__name__)


@dataclass
class AffectedSymbols:
    """Result of dependency analysis for changed symbols.

    Attributes:
        changed: List of changed symbol FQNs
        dependents: List of dependent symbol FQNs (1-hop)
        total: Total number of affected symbols
        total_set: Set of all affected FQNs for easy lookup
    """

    changed: list[str]
    dependents: list[str] = field(default_factory=list)
    total: int = 0
    total_set: set[str] = field(default_factory=set)

    def __post_init__(self) -> None:
        """Compute total and total_set from changed and dependents."""
        self.total_set = set(self.changed) | set(self.dependents)
        self.total = len(self.total_set)


class DependencyTracker:
    """1-hop dependency tracker for incremental summarization.

    Identifies which symbols need re-summarization when a change occurs:
    - Direct callers (CALLS relationship)
    - Containing parent classes/packages (CONTAINS/MEMBER_OF relationship)
    """

    def __init__(self, store: SQLiteStore) -> None:
        """Initialize dependency tracker.

        Args:
            store: SQLiteStore instance for database access
        """
        self.store = store

    def get_affected_symbols(self, changed_fqns: list[str]) -> AffectedSymbols:
        """Get all symbols affected by the given changes.

        Args:
            changed_fqns: List of changed symbol FQNs

        Returns:
            AffectedSymbols containing changed and dependent symbols
        """
        affected = set(changed_fqns)
        dependents: set[str] = set()

        for fqn in changed_fqns:
            # 1. Get direct callers (incoming CALLS edges)
            callers = self.store.get_related_symbols(
                fqn, relation="calls", direction="incoming"
            )
            dependents.update(c["fqn"] for c in callers)

            # 2. Get containing parent (via parent_fqn or MEMBER_OF)
            symbol = self.store.get_symbol(fqn)
            if symbol and symbol.get("parent_fqn"):
                parent_fqn = symbol["parent_fqn"]
                affected.add(parent_fqn)
                dependents.add(parent_fqn)

            # 3. Mark the changed symbol's summary as stale
            self.store.mark_summary_stale(fqn)

        # Also mark all dependent summaries as stale
        if dependents:
            self.store.mark_summaries_stale(list(dependents))

        logger.info(
            f"Dependency analysis: {len(changed_fqns)} changed -> "
            f"{len(dependents)} dependents affected"
        )

        return AffectedSymbols(
            changed=changed_fqns,
            dependents=list(dependents),
        )

    def get_callers(self, fqn: str, max_depth: int = 1) -> list[dict[str, Any]]:
        """Get symbols that call the given symbol.

        Args:
            fqn: Target symbol FQN
            max_depth: Maximum depth to traverse (1 for direct callers only)

        Returns:
            List of caller symbol dicts
        """
        if max_depth != 1:
            # For now, only support 1-hop
            logger.warning("max_depth > 1 not yet supported, using 1-hop")

        return self.store.get_related_symbols(
            fqn, relation="calls", direction="incoming"
        )

    def get_callees(self, fqn: str, max_depth: int = 1) -> list[dict[str, Any]]:
        """Get symbols called by the given symbol.

        Args:
            fqn: Source symbol FQN
            max_depth: Maximum depth to traverse (1 for direct callees only)

        Returns:
            List of callee symbol dicts
        """
        if max_depth != 1:
            logger.warning("max_depth > 1 not yet supported, using 1-hop")

        return self.store.get_related_symbols(
            fqn, relation="calls", direction="outgoing"
        )

    def get_parent_symbol(self, fqn: str) -> dict[str, Any] | None:
        """Get the parent symbol containing the given symbol.

        Args:
            fqn: Child symbol FQN

        Returns:
            Parent symbol dict or None if no parent
        """
        symbol = self.store.get_symbol(fqn)
        if not symbol:
            return None

        parent_fqn = symbol.get("parent_fqn")
        if not parent_fqn:
            return None

        return self.store.get_symbol(parent_fqn)

    def get_children_symbols(self, parent_fqn: str) -> list[dict[str, Any]]:
        """Get all child symbols contained in the given parent.

        Args:
            parent_fqn: Parent symbol FQN

        Returns:
            List of child symbol dicts
        """
        return self.store.get_symbols_by_parent(parent_fqn)
