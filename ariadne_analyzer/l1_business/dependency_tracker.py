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

        Uses batch fetching to avoid N+1 query problems.

        Args:
            changed_fqns: List of changed symbol FQNs

        Returns:
            AffectedSymbols containing changed and dependent symbols
        """
        if not changed_fqns:
            return AffectedSymbols(changed=[])

        affected = set(changed_fqns)
        dependents: set[str] = set()

        # Batch fetch: Get all callers for changed symbols in 2 queries
        placeholders = ",".join("?" * len(changed_fqns))

        # Query 1: Batch fetch all incoming CALLS edges
        cursor = self.store.conn.cursor()
        callers = cursor.execute(
            f"""SELECT DISTINCT e.from_fqn FROM edges e
                WHERE e.to_fqn IN ({placeholders}) AND e.relation = 'calls'""",
            changed_fqns
        ).fetchall()
        dependents.update(c[0] for c in callers)

        # Query 2: Batch fetch all symbols and their parents
        symbols = cursor.execute(
            f"SELECT fqn, parent_fqn FROM symbols WHERE fqn IN ({placeholders})",
            changed_fqns
        ).fetchall()

        for _fqn, parent_fqn in symbols:
            if parent_fqn:
                affected.add(parent_fqn)
                dependents.add(parent_fqn)

        # ATOMIC: Mark all affected symbols (changed + dependents) as stale in one transaction
        all_to_mark = list(affected | dependents)
        if all_to_mark:
            self.store.mark_summaries_stale(all_to_mark)

        logger.info(
            f"Dependency analysis: {len(changed_fqns)} changed -> "
            f"{len(dependents)} dependents affected"
        )

        return AffectedSymbols(
            changed=changed_fqns,
            dependents=list(dependents),
        )

    def get_callers(self, fqn: str) -> list[dict[str, Any]]:
        """Get symbols that call the given symbol (1-hop only).

        Args:
            fqn: Target symbol FQN

        Returns:
            List of caller symbol dicts
        """
        return self.store.get_related_symbols(
            fqn, relation="calls", direction="incoming"
        )

    def get_callees(self, fqn: str) -> list[dict[str, Any]]:
        """Get symbols called by the given symbol (1-hop only).

        Args:
            fqn: Source symbol FQN

        Returns:
            List of callee symbol dicts
        """
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
