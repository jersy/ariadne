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
        stats: Detailed statistics including performance metrics
    """

    regenerated_count: int
    skipped_cached: int = 0
    duration_seconds: float = 0.0
    cost_report: str = ""
    stats: dict[str, Any] = field(default_factory=dict)

    # Performance metrics
    dependency_analysis_time: float = 0.0
    symbol_load_time: float = 0.0
    summarization_time: float = 0.0
    database_update_time: float = 0.0
    throughput_per_second: float = 0.0


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

        logger.info(
            f"Starting incremental update",
            extra={
                "event": "incremental_update_start",
                "changed_count": len(changed_fqns),
                "max_workers": self.parallel.max_workers,
            }
        )

        # 1. Get affected symbols
        dep_start = time.time()
        affected = self.tracker.get_affected_symbols(changed_fqns)
        dep_time = time.time() - dep_start

        logger.info(
            f"Incremental update: {affected.total} symbols to regenerate "
            f"({len(changed_fqns)} changed + {len(affected.dependents)} dependents)",
            extra={
                "event": "dependency_analysis_complete",
                "total_affected": affected.total,
                "changed": len(changed_fqns),
                "dependents": len(affected.dependents),
                "dependency_analysis_time": f"{dep_time:.2f}s",
            }
        )

        # 2. Load symbol data for affected symbols
        symbols_data: list[tuple[SymbolData, str]] = []

        # Batch fetch: Get all symbols in one query
        if not affected.total_set:
            duration = time.time() - start_time
            logger.info(
                f"No symbols to process",
                extra={
                    "event": "incremental_update_complete",
                    "duration": f"{duration:.2f}s",
                    "regenerated": 0,
                }
            )
            return IncrementalResult(
                regenerated_count=0,
                duration_seconds=duration,
                cost_report=self.cost_tracker.get_report(),
                stats={
                    "changed": len(changed_fqns),
                    "dependents": len(affected.dependents),
                    "total_affected": 0,
                },
            )

        load_start = time.time()
        placeholders = ",".join("?" * len(affected.total_set))
        cursor = self.store.conn.cursor()
        symbol_dicts = cursor.execute(
            f"SELECT * FROM symbols WHERE fqn IN ({placeholders})",
            list(affected.total_set)
        ).fetchall()

        for symbol_dict in [dict(row) for row in symbol_dicts]:
            fqn = symbol_dict["fqn"]

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

        load_time = time.time() - load_start

        # 3. Filter out cached non-stale summaries
        if not symbols_data:
            duration = time.time() - start_time
            logger.info(
                f"No valid symbols with source code",
                extra={
                    "event": "incremental_update_complete",
                    "duration": f"{duration:.2f}s",
                    "regenerated": 0,
                }
            )
            return IncrementalResult(
                regenerated_count=0,
                duration_seconds=duration,
                cost_report=self.cost_tracker.get_report(),
            )

        # Check for existing non-stale summaries - batch fetch
        filtered_symbols: list[tuple[SymbolData, str]] = []
        skipped_count = 0

        if symbols_data:
            fqns = [s.fqn for s, _ in symbols_data]
            placeholders = ",".join("?" * len(fqns))
            summaries = cursor.execute(
                f"SELECT target_fqn, is_stale FROM summaries WHERE target_fqn IN ({placeholders})",
                fqns
            ).fetchall()
            fresh_summaries = {row[0]: row[1] for row in summaries if not row[1]}

            for symbol, source_code in symbols_data:
                if symbol.fqn in fresh_summaries:
                    # Skip if we have a fresh cached summary
                    skipped_count += 1
                    continue
                filtered_symbols.append((symbol, source_code))

        logger.info(
            f"Filtered {len(filtered_symbols)} symbols to process, "
            f"{skipped_count} cached",
            extra={
                "event": "cache_filter_complete",
                "to_process": len(filtered_symbols),
                "cached": skipped_count,
            }
        )

        # 4. Parallel summarization
        sum_start = time.time()
        summaries = self.parallel.summarize_symbols_batch(
            filtered_symbols, show_progress=show_progress
        )
        sum_time = time.time() - sum_start

        logger.info(
            f"Generated {len(summaries)} summaries in {sum_time:.2f}s",
            extra={
                "event": "summarization_complete",
                "generated": len(summaries),
                "summarization_time": f"{sum_time:.2f}s",
                "throughput": f"{len(summaries) / sum_time:.1f} summaries/sec",
            }
        )

        # 5. Batch update database
        db_start = time.time()

        # Batch fetch all existing summaries to avoid N+1 queries
        if summaries:
            placeholders = ",".join("?" * len(summaries))
            with self.store.conn.cursor() as cursor:
                existing_summaries = cursor.execute(
                    f"SELECT target_fqn, is_stale FROM summaries WHERE target_fqn IN ({placeholders})",
                    list(summaries.keys())
                ).fetchall()
                # Build lookup dict: FQN -> is_stale
                fresh_summaries = {row[0]: row[1] for row in existing_summaries if not row[1]}
        else:
            fresh_summaries = {}

        for fqn, summary_text in summaries.items():
            from ariadne_core.models.types import SummaryData, SummaryLevel

            # Check if already fresh (O(1) lookup instead of DB query)
            if fqn in fresh_summaries:
                logger.info(f"Skipping {fqn} - no longer stale (concurrent update)")
                continue

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

        db_time = time.time() - db_start

        duration = time.time() - start_time
        throughput = len(summaries) / duration if duration > 0 else 0

        logger.info(
            f"Incremental update complete: {len(summaries)} regenerated, "
            f"{skipped_count} cached, {duration:.2f}s total",
            extra={
                "event": "incremental_update_complete",
                "regenerated": len(summaries),
                "cached": skipped_count,
                "duration": f"{duration:.2f}s",
                "throughput": f"{throughput:.1f} summaries/sec",
                "dependency_time": f"{dep_time:.2f}s",
                "load_time": f"{load_time:.2f}s",
                "summarization_time": f"{sum_time:.2f}s",
                "db_time": f"{db_time:.2f}s",
            }
        )

        # Get thread-safe snapshot of parallel stats
        parallel_stats = self.parallel.get_stats()

        return IncrementalResult(
            regenerated_count=len(summaries),
            skipped_cached=skipped_count,
            duration_seconds=duration,
            cost_report=self.cost_tracker.get_report(),
            stats={
                "changed": len(changed_fqns),
                "dependents": len(affected.dependents),
                "total_affected": affected.total,
                "success": parallel_stats["success"],
                "failed": parallel_stats["failed"],
            },
            dependency_analysis_time=dep_time,
            symbol_load_time=load_time,
            summarization_time=sum_time,
            database_update_time=db_time,
            throughput_per_second=throughput,
        )

    def close(self) -> None:
        """Clean up resources."""
        self.llm_client.close()
