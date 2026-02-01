"""
Parallel LLM Summarizer
========================

High-performance parallel summarizer using ThreadPoolExecutor.
Processes multiple symbols concurrently with progress tracking and error isolation.
"""

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock
from typing import Any

from ariadne_core.models.types import SymbolData
from ariadne_llm import LLMClient

logger = logging.getLogger(__name__)


class ParallelSummarizer:
    """Parallel summarizer using ThreadPoolExecutor for concurrent LLM calls.

    Features:
    - Concurrent processing with configurable worker count
    - Progress bar with tqdm
    - Error isolation (single failure doesn't block others)
    - Fallback summaries for failed items
    """

    def __init__(self, llm_client: LLMClient, max_workers: int = 10) -> None:
        """Initialize parallel summarizer.

        Args:
            llm_client: LLM client for generating summaries
            max_workers: Maximum concurrent workers (defaults to 10)
        """
        self.llm_client = llm_client
        self.max_workers = max_workers
        self.stats: dict[str, int] = {
            "total": 0,
            "success": 0,
            "failed": 0,
            "skipped": 0,
        }
        self._stats_lock = Lock()

    def summarize_symbols_batch(
        self,
        symbols: list[tuple[SymbolData, str]],
        show_progress: bool = True,
    ) -> dict[str, str]:
        """Summarize multiple symbols in parallel.

        Args:
            symbols: List of (symbol_data, source_code) tuples
            show_progress: Whether to show progress bar

        Returns:
            Dict mapping FQN to generated summary
        """
        if not symbols:
            return {}

        self.stats["total"] = len(symbols)
        results: dict[str, str] = {}

        # Prepare items with context
        items = []
        for symbol, source_code in symbols:
            class_name = symbol.parent_fqn or ""
            context = {
                "class_name": class_name,
                "method_name": symbol.name,
                "signature": symbol.signature or "",
                "modifiers": symbol.modifiers or [],
                "annotations": symbol.annotations or [],
            }
            items.append((symbol.fqn, source_code, context))

        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # Submit all tasks
            futures = {
                executor.submit(self._summarize_single, fqn, code, ctx): (fqn, code, ctx)
                for fqn, code, ctx in items
            }

            # Collect results with optional progress bar
            if show_progress:
                try:
                    from tqdm import tqdm

                    with tqdm(total=len(items), desc="Summarizing") as pbar:
                        for future in as_completed(futures):
                            fqn, _, _ = futures[future]
                            try:
                                summary = future.result(timeout=self.llm_client.config.request_timeout)
                                results[fqn] = summary
                            except Exception as e:
                                logger.error(f"Failed to summarize {fqn}: {e}")
                                # Generate fallback summary
                                fallback = self._fallback_summary(fqn, futures[future][2])
                                results[fqn] = fallback
                                self._increment_failed()
                            finally:
                                pbar.update(1)
                except ImportError:
                    # tqdm not available, fall back to simple loop
                    show_progress = False

            if not show_progress:
                for future in as_completed(futures):
                    fqn, _, context = futures[future]
                    try:
                        summary = future.result(timeout=self.llm_client.config.request_timeout)
                        results[fqn] = summary
                    except Exception as e:
                        logger.error(f"Failed to summarize {fqn}: {e}")
                        fallback = self._fallback_summary(fqn, context)
                        results[fqn] = fallback
                        self._increment_failed()

        # Calculate success count (safe to do outside the thread pool)
        with self._stats_lock:
            self.stats["success"] = self.stats["total"] - self.stats["failed"]
        logger.info(
            f"Summarization complete: {self.stats['success']} succeeded, "
            f"{self.stats['failed']} failed"
        )

        return results

    def _increment_failed(self) -> None:
        """Thread-safe increment of failed counter."""
        with self._stats_lock:
            self.stats["failed"] += 1

    def _set_success_count(self, count: int) -> None:
        """Thread-safe set of success counter."""
        with self._stats_lock:
            self.stats["success"] = count

    def _summarize_single(self, fqn: str, source_code: str, context: dict[str, Any]) -> str:
        """Summarize a single symbol (runs in worker thread).

        Args:
            fqn: Fully qualified name of the symbol
            source_code: Source code to summarize
            context: Context dict (class_name, method_name, signature, etc.)

        Returns:
            Generated summary text
        """
        return self.llm_client.generate_summary(source_code, context)

    def _fallback_summary(self, fqn: str, context: dict[str, Any]) -> str:
        """Generate fallback summary based on signature.

        Args:
            fqn: Fully qualified name of the symbol
            context: Context dict

        Returns:
            Fallback summary text
        """
        # Extract method/class name from FQN
        name = fqn.split(".")[-1]

        # Check if it's likely a getter/setter
        signature = context.get("signature", "")
        if name.startswith("get") or name.startswith("is") or "return" in signature.lower():
            return "N/A (getter/accessor)"
        if name.startswith("set"):
            return "N/A (setter/mutator)"

        # Generate generic fallback
        modifiers = context.get("modifiers", [])
        if "static" in modifiers:
            return f"Static method: {name}"

        return f"Method: {name}"

    def get_stats(self) -> dict[str, int]:
        """Get statistics from last batch operation.

        Returns:
            Dict with total, success, failed, skipped counts
        """
        with self._stats_lock:
            return self.stats.copy()

    def reset_stats(self) -> None:
        """Reset statistics counters."""
        self.stats = {"total": 0, "success": 0, "failed": 0, "skipped": 0}
