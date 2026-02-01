"""
Incremental Summarization Coordinator
=======================================

Coordinates incremental summary updates using parallel processing
and dependency tracking.
"""

import logging
import time
from dataclasses import dataclass, field
from typing import Any

from ariadne_core.models.types import SymbolData
from ariadne_core.storage.sqlite_store import SQLiteStore
from ariadne_llm import LLMClient

from .cost_tracker import LLMCostTracker
from .dependency_tracker import DependencyTracker
from .parallel_summarizer import ParallelSummarizer

logger = logging.getLogger(__name__)


@dataclass
class IncrementalResult:
    """Result of incremental summary regeneration.

    Attributes:
        regenerated_count: Number of summaries regenerated
        skipped_cached: Number of summaries skipped (cached and not stale)
        duration_seconds: Time taken for the operation
        cost_report: LLM cost report string
        stats: Detailed statistics
    """

    regenerated_count: int
    skipped_cached: int = 0
    duration_seconds: float = 0.0
    cost_report: str = ""
    stats: dict[str, Any] = field(default_factory=dict)


class IncrementalSummarizerCoordinator:
    """Coordinator for incremental summary updates.

    Orchestrates:
    1. Dependency analysis to find affected symbols
    2. Parallel summary generation
    3. Batch database updates
    4. Cost tracking and reporting
    """

    def __init__(
        self,
        llm_client: LLMClient,
        store: SQLiteStore,
        max_workers: int = 10,
    ) -> None:
        """Initialize coordinator.

        Args:
            llm_client: LLM client for generating summaries
            store: SQLiteStore for database access
            max_workers: Maximum concurrent workers
        """
        self.llm_client = llm_client
        self.store = store
        self.parallel = ParallelSummarizer(llm_client, max_workers=max_workers)
        self.tracker = DependencyTracker(store)
        self.cost_tracker = LLMCostTracker()

    def regenerate_incremental(
        self,
        changed_symbols: list[str] | list[SymbolData],
        symbol_source_map: dict[str, str] | None = None,
        show_progress: bool = True,
    ) -> IncrementalResult:
        """Regenerate summaries for changed symbols and their dependents.

        Args:
            changed_symbols: List of changed symbol FQNs or SymbolData objects
            symbol_source_map: Optional map from FQN to source code
            show_progress: Whether to show progress bar

        Returns:
            IncrementalResult with statistics and timing
        """
        start_time = time.time()

        # Normalize input to FQN list
        if changed_symbols and isinstance(changed_symbols[0], SymbolData):
            changed_fqns = [s.fqn for s in changed_symbols]  # type: ignore
        else:
            changed_fqns = changed_symbols  # type: ignore

        # 1. Get affected symbols
        affected = self.tracker.get_affected_symbols(changed_fqns)
        logger.info(
            f"Incremental update: {affected.total} symbols to regenerate "
            f"({len(changed_fqns)} changed + {len(affected.dependents)} dependents)"
        )

        # 2. Load symbol data for affected symbols
        symbols_data: list[tuple[SymbolData, str]] = []

        for fqn in affected.total_set:
            symbol_dict = self.store.get_symbol(fqn)
            if not symbol_dict:
                logger.warning(f"Symbol not found in store: {fqn}")
                continue

            # Get source code
            source_code = ""
            if symbol_source_map and fqn in symbol_source_map:
                source_code = symbol_source_map[fqn]
            elif symbol_dict.get("file_path"):
                # Could read from file, but for now skip
                logger.debug(f"No source code provided for {fqn}")
                continue

            if not source_code:
                continue

            # Convert to SymbolData
            from ariadne_core.models.types import SymbolKind

            kind_str = symbol_dict.get("kind", "")
            try:
                kind = SymbolKind(kind_str)
            except ValueError:
                logger.warning(f"Unknown symbol kind: {kind_str}")
                continue

            symbol = SymbolData(
                fqn=symbol_dict["fqn"],
                kind=kind,
                name=symbol_dict["name"],
                file_path=symbol_dict.get("file_path"),
                line_number=symbol_dict.get("line_number"),
                signature=symbol_dict.get("signature"),
                parent_fqn=symbol_dict.get("parent_fqn"),
                modifiers=symbol_dict.get("modifiers") or [],
                annotations=symbol_dict.get("annotations") or [],
            )

            symbols_data.append((symbol, source_code))

        # 3. Filter out cached non-stale summaries
        if not symbols_data:
            return IncrementalResult(
                regenerated_count=0,
                duration_seconds=time.time() - start_time,
                cost_report=self.cost_tracker.get_report(),
            )

        # Check for existing non-stale summaries
        filtered_symbols: list[tuple[SymbolData, str]] = []
        skipped_count = 0

        for symbol, source_code in symbols_data:
            existing = self.store.get_summary(symbol.fqn)
            if existing and not existing.get("is_stale"):
                # Skip if we have a fresh cached summary
                skipped_count += 1
                continue
            filtered_symbols.append((symbol, source_code))

        # 4. Parallel summarization
        summaries = self.parallel.summarize_symbols_batch(
            filtered_symbols, show_progress=show_progress
        )

        # 5. Batch update database
        for fqn, summary_text in summaries.items():
            from ariadne_core.models.types import SummaryData, SummaryLevel

            # Determine level
            symbol = next((s for s, _ in filtered_symbols if s.fqn == fqn), None)
            if symbol:
                if symbol.kind.name == "METHOD":
                    level = SummaryLevel.METHOD
                elif symbol.kind.name in ("CLASS", "INTERFACE"):
                    level = SummaryLevel.CLASS
                else:
                    level = SummaryLevel.METHOD

                summary = SummaryData(
                    target_fqn=fqn,
                    level=level,
                    summary=summary_text,
                    is_stale=False,  # Fresh summary
                )
                self.store.create_summary(summary)

        duration = time.time() - start_time

        return IncrementalResult(
            regenerated_count=len(summaries),
            skipped_cached=skipped_count,
            duration_seconds=duration,
            cost_report=self.cost_tracker.get_report(),
            stats={
                "changed": len(changed_fqns),
                "dependents": len(affected.dependents),
                "total_affected": affected.total,
                "success": self.parallel.stats["success"],
                "failed": self.parallel.stats["failed"],
            },
        )

    def close(self) -> None:
        """Clean up resources."""
        self.llm_client.close()
