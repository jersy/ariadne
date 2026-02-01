"""
Hierarchical LLM Summarizer for Code
=====================================

Implements bottom-up hierarchical summarization:
Method → Class → Package → Module
"""

import logging
from typing import Any

from ariadne_core.models.types import SummaryData, SummaryLevel, SymbolData, SymbolKind
from ariadne_core.storage.sqlite_store import SQLiteStore
from ariadne_llm import LLMClient, LLMConfig
from ariadne_llm.config import LLMProvider

from .dependency_tracker import DependencyTracker
from .parallel_summarizer import ParallelSummarizer
from .prompts import (
    format_class_prompt,
    format_method_prompt,
    format_module_prompt,
    format_package_prompt,
)

logger = logging.getLogger(__name__)


class HierarchicalSummarizer:
    """Hierarchical LLM-based code summarizer.

    Implements bottom-up summarization strategy:
    1. Method level: Summarize individual methods
    2. Class level: Aggregate method summaries into class summary
    3. Package level: Aggregate class summaries into package summary
    4. Module level: Aggregate package summaries into module summary
    """

    def __init__(self, config: LLMConfig | None = None) -> None:
        """Initialize summarizer with LLM client.

        Args:
            config: Optional LLMConfig (uses env if not provided)
        """
        if config is None:
            config = LLMConfig.from_env()

        self.llm_client = LLMClient(config)
        self.config = config

    def __enter__(self) -> "HierarchicalSummarizer":
        """Context manager entry."""
        return self

    def __exit__(self, *args: Any) -> None:
        """Context manager exit - ensures cleanup."""
        self.close()

    def summarize_method(
        self,
        method: SymbolData,
        source_code: str,
        class_context: dict[str, Any] | None = None,
    ) -> str:
        """Generate summary for a single method.

        Args:
            method: Method symbol data
            source_code: Method source code
            class_context: Optional class context (class_name, class_type, annotations)

        Returns:
            Generated summary text
        """
        context = {
            "class_name": class_context.get("class_name", "") if class_context else "",
            "method_name": method.name,
            "signature": method.signature or "",
            "modifiers": method.modifiers or [],
            "annotations": method.annotations or [],
        }

        prompt = format_method_prompt(
            class_name=context["class_name"],
            method_name=context["method_name"],
            signature=context["signature"],
            modifiers=context["modifiers"],
            annotations=context["annotations"],
            source_code=source_code,
        )

        summary = self.llm_client.generate_summary(source_code, context)
        return summary

    def summarize_class(
        self,
        class_data: SymbolData,
        method_summaries: list[tuple[str, str]],
        class_type: str = "class",
    ) -> str:
        """Generate summary for a class from its method summaries.

        Args:
            class_data: Class symbol data
            method_summaries: List of (method_name, summary) tuples
            class_type: Type of class (class, interface, enum, etc.)

        Returns:
            Generated class summary
        """
        # Filter out N/A summaries
        valid_summaries = [s for _, s in method_summaries if s and s != "N/A"]

        if not valid_summaries:
            # No valid summaries, return generic description
            return f"{class_data.name} ({class_type})"

        prompt = format_class_prompt(
            class_name=class_data.name,
            class_type=class_type,
            annotations=class_data.annotations or [],
            method_summaries=valid_summaries,
        )

        try:
            summary = self.llm_client._call_llm(prompt)
            return summary.strip()
        except Exception as e:
            logger.error(f"Failed to summarize class {class_data.name}: {e}")
            return f"{class_data.name} ({class_type})"

    def summarize_package(
        self,
        package_name: str,
        class_summaries: list[tuple[str, str]],
    ) -> str:
        """Generate summary for a package from its class summaries.

        Args:
            package_name: Package name (e.g., com.example.service)
            class_summaries: List of (class_name, summary) tuples

        Returns:
            Generated package summary
        """
        valid_summaries = [s for _, s in class_summaries if s and s != "N/A"]

        if not valid_summaries:
            return f"{package_name} package"

        prompt = format_package_prompt(
            package_name=package_name,
            class_summaries=valid_summaries,
        )

        try:
            summary = self.llm_client._call_llm(prompt)
            return summary.strip()
        except Exception as e:
            logger.error(f"Failed to summarize package {package_name}: {e}")
            return f"{package_name} package"

    def summarize_module(
        self,
        module_name: str,
        package_summaries: list[tuple[str, str]],
    ) -> str:
        """Generate summary for a module from its package summaries.

        Args:
            module_name: Module name (e.g., com.example)
            package_summaries: List of (package_name, summary) tuples

        Returns:
            Generated module summary
        """
        valid_summaries = [s for _, s in package_summaries if s and s != "N/A"]

        if not valid_summaries:
            return f"{module_name} module"

        prompt = format_module_prompt(
            module_name=module_name,
            package_summaries=valid_summaries,
        )

        try:
            summary = self.llm_client._call_llm(prompt)
            return summary.strip()
        except Exception as e:
            logger.error(f"Failed to summarize module {module_name}: {e}")
            return f"{module_name} module"

    def generate_incremental_summaries(
        self,
        changed_symbols: list[SymbolData],
        symbol_source_map: dict[str, str],
        store: SQLiteStore | None = None,
    ) -> list[SummaryData]:
        """Generate summaries for changed symbols incrementally.

        .. deprecated::
            Use IncrementalSummarizerCoordinator instead for new code.
            This method is kept for backward compatibility but provides
            less sophisticated incremental update capabilities.

        Args:
            changed_symbols: List of symbols that have changed
            symbol_source_map: Map from FQN to source code
            store: Optional SQLiteStore for dependency tracking

        Returns:
            List of generated summaries
        """
        summaries: list[SummaryData] = []

        # Use dependency tracking if store is provided
        if store:
            tracker = DependencyTracker(store)
            changed_fqns = [s.fqn for s in changed_symbols]
            affected = tracker.get_affected_symbols(changed_fqns)

            # Get all affected symbols
            affected_symbols = []
            for fqn in affected.total_set:
                symbol = store.get_symbol(fqn)
                if symbol:
                    from ariadne_core.models.types import SymbolKind

                    kind_str = symbol.get("kind", "")
                    try:
                        kind = SymbolKind(kind_str)
                    except ValueError:
                        continue

                    symbol_data = SymbolData(
                        fqn=symbol["fqn"],
                        kind=kind,
                        name=symbol["name"],
                        file_path=symbol.get("file_path"),
                        line_number=symbol.get("line_number"),
                        signature=symbol.get("signature"),
                        parent_fqn=symbol.get("parent_fqn"),
                        modifiers=symbol.get("modifiers") or [],
                        annotations=symbol.get("annotations") or [],
                    )
                    affected_symbols.append(symbol_data)

            logger.info(
                f"Incremental update: {len(changed_symbols)} changed -> "
                f"{len(affected_symbols)} total affected"
            )

            # Use parallel summarizer for affected symbols
            parallel = ParallelSummarizer(self.llm_client, max_workers=self.config.max_workers)

            items = []
            for symbol in affected_symbols:
                source_code = symbol_source_map.get(symbol.fqn, "")
                if not source_code:
                    continue
                items.append((symbol, source_code))

            if items:
                summary_results = parallel.summarize_symbols_batch(items, show_progress=True)

                for fqn, summary_text in summary_results.items():
                    # Determine summary level
                    symbol = next((s for s in affected_symbols if s.fqn == fqn), None)
                    if not symbol:
                        continue

                    if symbol.kind == SymbolKind.METHOD:
                        level = SummaryLevel.METHOD
                    elif symbol.kind in (SymbolKind.CLASS, SymbolKind.INTERFACE):
                        level = SummaryLevel.CLASS
                    else:
                        level = SummaryLevel.METHOD

                    summaries.append(
                        SummaryData(
                            target_fqn=fqn,
                            level=level,
                            summary=summary_text,
                        )
                    )

        else:
            # Original behavior without dependency tracking
            # Group symbols by type
            methods = [s for s in changed_symbols if s.kind == SymbolKind.METHOD]
            classes = [
                s
                for s in changed_symbols
                if s.kind in (SymbolKind.CLASS, SymbolKind.INTERFACE)
            ]

            # Generate method summaries
            for method in methods:
                source_code = symbol_source_map.get(method.fqn, "")
                if not source_code:
                    continue

                class_name = method.parent_fqn or ""
                summary_text = self.summarize_method(
                    method, source_code, {"class_name": class_name}
                )

                summaries.append(
                    SummaryData(
                        target_fqn=method.fqn,
                        level=SummaryLevel.METHOD,
                        summary=summary_text,
                    )
                )

            # Generate class summaries (aggregating method summaries)
            for cls in classes:
                # Get method summaries for this class
                class_methods = [
                    s for s in summaries if s.target_fqn.startswith(cls.fqn)
                ]
                method_summaries = [(s.target_fqn, s.summary) for s in class_methods]

                if not method_summaries:
                    continue

                summary_text = self.summarize_class(cls, method_summaries)

                summaries.append(
                    SummaryData(
                        target_fqn=cls.fqn,
                        level=SummaryLevel.CLASS,
                        summary=summary_text,
                    )
                )

        return summaries

    def batch_summarize_methods(
        self,
        methods: list[tuple[SymbolData, str]],
        concurrent_limit: int = 5,
    ) -> list[tuple[str, str]]:
        """Batch summarize multiple methods concurrently.

        Args:
            methods: List of (method_data, source_code) tuples
            concurrent_limit: Maximum concurrent LLM calls

        Returns:
            List of (fqn, summary) tuples
        """
        items = []
        for method, source_code in methods:
            class_name = method.parent_fqn or ""
            context = {
                "class_name": class_name,
                "method_name": method.name,
                "signature": method.signature or "",
                "modifiers": method.modifiers or [],
                "annotations": method.annotations or [],
            }
            items.append({"code": source_code, "context": context})

        summaries = self.llm_client.batch_generate_summaries(items, concurrent_limit)

        return [(method.fqn, summary) for (method, _), summary in zip(methods, summaries)]

    def close(self) -> None:
        """Close the LLM client."""
        self.llm_client.close()
