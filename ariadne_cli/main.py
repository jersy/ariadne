"""Ariadne CLI - Code Knowledge Graph for Architect Agents."""

import argparse
import logging
import os
import sys
from pathlib import Path

logger = logging.getLogger(__name__)


def validate_project_path(file_path: str, project_root: Path) -> Path | None:
    """Validate that file_path is within project_root.

    Prevents path traversal attacks by ensuring resolved paths are contained
    within the project directory.

    Args:
        file_path: The file path to validate (from database)
        project_root: The root directory of the project

    Returns:
        Resolved Path if valid, None otherwise
    """
    if not file_path:
        return None

    try:
        resolved_path = Path(file_path).resolve()
        resolved_path.relative_to(project_root)
        # Path is within project root
        if not resolved_path.exists():
            logger.warning(f"Path does not exist: {file_path}")
            return None
        return resolved_path
    except ValueError:
        # Path is outside project root
        logger.warning(f"Path outside project root: {file_path}")
        return None


def main() -> int:
    """Main entry point for Ariadne CLI."""
    parser = argparse.ArgumentParser(
        prog="ariadne",
        description="Multi-layer code knowledge graph for architect agents",
    )
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Extract command
    extract_parser = subparsers.add_parser("extract", help="Extract symbols from Java project")
    extract_parser.add_argument(
        "--project",
        "-p",
        required=True,
        help="Path to Java project directory",
    )
    extract_parser.add_argument(
        "--output",
        "-o",
        default="ariadne.db",
        help="Output database file (default: ariadne.db)",
    )

    # Entries command (L2)
    entries_parser = subparsers.add_parser("entries", help="List entry points (HTTP APIs, scheduled tasks)")
    entries_parser.add_argument(
        "--db",
        default="ariadne.db",
        help="Database file (default: ariadne.db)",
    )
    entries_parser.add_argument(
        "--type",
        "-t",
        choices=["http_api", "scheduled", "mq_consumer"],
        help="Filter by entry type",
    )

    # Deps command (L2)
    deps_parser = subparsers.add_parser("deps", help="List external dependencies")
    deps_parser.add_argument(
        "--db",
        default="ariadne.db",
        help="Database file (default: ariadne.db)",
    )
    deps_parser.add_argument(
        "--caller",
        help="Filter by caller FQN pattern",
    )
    deps_parser.add_argument(
        "--type",
        "-t",
        choices=["redis", "mysql", "mq", "http", "rpc"],
        help="Filter by dependency type",
    )

    # Trace command (L2)
    trace_parser = subparsers.add_parser("trace", help="Trace call chain from entry point")
    trace_parser.add_argument(
        "entry",
        help="Entry point pattern (e.g., 'POST /api/orders' or method FQN)",
    )
    trace_parser.add_argument(
        "--db",
        default="ariadne.db",
        help="Database file (default: ariadne.db)",
    )
    trace_parser.add_argument(
        "--depth",
        type=int,
        default=10,
        help="Maximum trace depth (default: 10)",
    )

    # Check command (L2)
    check_parser = subparsers.add_parser("check", help="Check for anti-patterns")
    check_parser.add_argument(
        "--db",
        default="ariadne.db",
        help="Database file (default: ariadne.db)",
    )
    check_parser.add_argument(
        "--rule",
        help="Run specific rule only",
    )

    # Serve command (placeholder for Phase 4)
    serve_parser = subparsers.add_parser("serve", help="Start HTTP API server")
    serve_parser.add_argument(
        "--port",
        type=int,
        default=8080,
        help="Server port (default: 8080)",
    )

    # ========================
    # L1: Business Layer Commands
    # ========================

    # Summarize command (L1)
    summarize_parser = subparsers.add_parser("summarize", help="Generate LLM summaries for code")
    summarize_parser.add_argument(
        "--project",
        "-p",
        required=True,
        help="Path to Java project directory",
    )
    summarize_parser.add_argument(
        "--db",
        default="ariadne.db",
        help="Database file (default: ariadne.db)",
    )
    summarize_parser.add_argument(
        "--level",
        "-l",
        choices=["method", "class", "package", "module"],
        help="Summary level to generate",
    )
    summarize_parser.add_argument(
        "--incremental",
        action="store_true",
        help="Only summarize changed symbols",
    )

    # Summary command (L1)
    summary_parser = subparsers.add_parser("summary", help="Get summary for a symbol")
    summary_parser.add_argument(
        "--fqn",
        required=True,
        help="Fully qualified name of the symbol",
    )
    summary_parser.add_argument(
        "--db",
        default="ariadne.db",
        help="Database file (default: ariadne.db)",
    )

    # Search command (L1)
    search_parser = subparsers.add_parser("search", help="Semantic search using natural language")
    search_parser.add_argument(
        "query",
        help="Search query (natural language)",
    )
    search_parser.add_argument(
        "--db",
        default="ariadne.db",
        help="Database file (default: ariadne.db)",
    )
    search_parser.add_argument(
        "--limit",
        "-n",
        type=int,
        default=10,
        help="Number of results (default: 10)",
    )
    search_parser.add_argument(
        "--level",
        choices=["method", "class", "package", "module"],
        help="Filter by summary level",
    )

    # Glossary command (L1)
    glossary_parser = subparsers.add_parser("glossary", help="Build domain glossary")
    glossary_parser.add_argument(
        "--project",
        "-p",
        required=True,
        help="Path to Java project directory",
    )
    glossary_parser.add_argument(
        "--db",
        default="ariadne.db",
        help="Database file (default: ariadne.db)",
    )
    glossary_parser.add_argument(
        "--rebuild",
        action="store_true",
        help="Rebuild entire glossary",
    )

    # Term-search command (L1)
    term_search_parser = subparsers.add_parser("term-search", help="Search domain glossary")
    term_search_parser.add_argument(
        "term",
        help="Search term",
    )
    term_search_parser.add_argument(
        "--db",
        default="ariadne.db",
        help="Database file (default: ariadne.db)",
    )

    # Constraints command (L1)
    constraints_parser = subparsers.add_parser("constraints", help="Extract business constraints")
    constraints_parser.add_argument(
        "--project",
        "-p",
        required=True,
        help="Path to Java project directory",
    )
    constraints_parser.add_argument(
        "--db",
        default="ariadne.db",
        help="Database file (default: ariadne.db)",
    )
    constraints_parser.add_argument(
        "--rebuild",
        action="store_true",
        help="Rebuild all constraints",
    )

    # Constraint-search command (L1)
    constraint_search_parser = subparsers.add_parser("constraint-search", help="Search business constraints")
    constraint_search_parser.add_argument(
        "keyword",
        help="Search keyword",
    )
    constraint_search_parser.add_argument(
        "--db",
        default="ariadne.db",
        help="Database file (default: ariadne.db)",
    )

    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        return 0

    if args.command == "extract":
        from ariadne_core.extractors.asm.extractor import extract_project

        extract_project(args.project, args.output)
        return 0

    if args.command == "entries":
        return _cmd_entries(args)

    if args.command == "deps":
        return _cmd_deps(args)

    if args.command == "trace":
        return _cmd_trace(args)

    if args.command == "check":
        return _cmd_check(args)

    if args.command == "serve":
        from ariadne_api.app import run_server
        print(f"Starting Ariadne API server on port {args.port}")
        run_server(host="0.0.0.0", port=args.port)
        return 0

    # ========================
    # L1: Business Layer Commands
    # ========================

    if args.command == "summarize":
        return _cmd_summarize(args)

    if args.command == "summary":
        return _cmd_summary(args)

    if args.command == "search":
        return _cmd_search(args)

    if args.command == "glossary":
        return _cmd_glossary(args)

    if args.command == "term-search":
        return _cmd_term_search(args)

    if args.command == "constraints":
        return _cmd_constraints(args)

    if args.command == "constraint-search":
        return _cmd_constraint_search(args)

    return 0


def _cmd_entries(args: argparse.Namespace) -> int:
    """List entry points."""
    from ariadne_core.storage.sqlite_store import SQLiteStore

    store = SQLiteStore(args.db)
    try:
        entries = store.get_entry_points(entry_type=args.type)

        if not entries:
            print("No entry points found.")
            return 0

        # Group by type
        by_type: dict[str, list[dict]] = {}
        for e in entries:
            t = e["entry_type"]
            if t not in by_type:
                by_type[t] = []
            by_type[t].append(e)

        for entry_type, items in by_type.items():
            print(f"\n[{entry_type.upper()}] ({len(items)} entries)")
            print("-" * 60)
            for item in items:
                if entry_type == "http_api":
                    method = item.get("http_method", "GET")
                    path = item.get("http_path", "/")
                    print(f"  {method:6} {path}")
                    print(f"         -> {item['symbol_fqn']}")
                elif entry_type == "scheduled":
                    cron = item.get("cron_expression") or "(no cron)"
                    print(f"  {cron}")
                    print(f"         -> {item['symbol_fqn']}")
                elif entry_type == "mq_consumer":
                    queue = item.get("mq_queue") or "(unknown queue)"
                    print(f"  {queue}")
                    print(f"         -> {item['symbol_fqn']}")

        print(f"\nTotal: {len(entries)} entry points")
        return 0
    finally:
        store.close()


def _cmd_deps(args: argparse.Namespace) -> int:
    """List external dependencies."""
    from ariadne_core.storage.sqlite_store import SQLiteStore

    store = SQLiteStore(args.db)
    try:
        deps = store.get_external_dependencies(
            caller_fqn=args.caller,
            dependency_type=args.type,
        )

        if not deps:
            print("No external dependencies found.")
            return 0

        # Group by type
        by_type: dict[str, list[dict]] = {}
        for d in deps:
            t = d["dependency_type"]
            if t not in by_type:
                by_type[t] = []
            by_type[t].append(d)

        for dep_type, items in by_type.items():
            print(f"\n[{dep_type.upper()}] ({len(items)} calls)")
            print("-" * 60)
            for item in items:
                strength = item.get("strength", "strong")
                print(f"  {item['caller_fqn']}")
                print(f"    -> {item['target']} ({strength})")

        print(f"\nTotal: {len(deps)} external dependencies")
        return 0
    finally:
        store.close()


def _cmd_trace(args: argparse.Namespace) -> int:
    """Trace call chain from entry point."""
    from ariadne_analyzer.l2_architecture.call_chain import CallChainTracer
    from ariadne_core.storage.sqlite_store import SQLiteStore

    store = SQLiteStore(args.db)
    try:
        tracer = CallChainTracer(store)

        try:
            result = tracer.trace_from_entry(args.entry, max_depth=args.depth)
        except ValueError as e:
            print(f"Error: {e}")
            return 1

        print(f"Entry: {result.entry_fqn}")
        print(f"Depth: {result.max_depth}")
        print("\nCall Chain:")

        for item in result.chain:
            indent = "  " * item["depth"]
            layer_str = f" [{item['layer']}]" if item.get("layer") else ""
            print(f"{indent}-> {item['to_fqn']}{layer_str}")

        if result.external_deps:
            print("\nExternal Dependencies:")
            for dep in result.external_deps:
                print(f"  - {dep['dependency_type']}: {dep['target']}")

        return 0
    finally:
        store.close()


def _cmd_check(args: argparse.Namespace) -> int:
    """Check for anti-patterns."""
    from ariadne_analyzer.l2_architecture.anti_patterns import AntiPatternDetector
    from ariadne_core.storage.sqlite_store import SQLiteStore

    store = SQLiteStore(args.db)
    try:
        detector = AntiPatternDetector(store)

        if args.rule:
            patterns = detector.detect_by_rule(args.rule)
        else:
            patterns = detector.detect_all()

        if not patterns:
            print("No anti-patterns detected.")
            return 0

        errors = 0
        warnings = 0

        for p in patterns:
            severity = p.severity.value if hasattr(p.severity, "value") else str(p.severity)
            if severity == "error":
                errors += 1
                prefix = "[ERROR]"
            elif severity == "warning":
                warnings += 1
                prefix = "[WARN] "
            else:
                prefix = "[INFO] "

            print(f"{prefix} {p.rule_id}: {p.from_fqn} -> {p.to_fqn}")
            print(f"        {p.message}")

        print(f"\nFound {errors} error(s), {warnings} warning(s)")
        return 1 if errors > 0 else 0
    finally:
        store.close()


# ========================
# L1: Business Layer Commands
# ========================


def _cmd_summarize(args: argparse.Namespace) -> int:
    """Generate LLM summaries for code."""
    from ariadne_analyzer.l1_business import HierarchicalSummarizer
    from ariadne_core.models.types import SymbolKind, SummaryData, SummaryLevel
    from ariadne_core.storage.sqlite_store import SQLiteStore

    # Resolve project root for path validation
    project_root = Path(args.project).resolve()

    store = SQLiteStore(args.db)

    try:
        # Get symbols to summarize
        if args.incremental:
            # Only summarize stale symbols
            stale_summaries = store.get_stale_summaries()
            if not stale_summaries:
                print("No stale summaries to update.")
                return 0

            fqns = [s["target_fqn"] for s in stale_summaries]
            symbols = []
            for fqn in fqns:
                sym = store.get_symbol(fqn)
                if sym:
                    symbols.append(sym)
        else:
            # Summarize all methods
            symbols = store.get_symbols_by_kind("method")

        if not symbols:
            print("No symbols found to summarize.")
            return 0

        # Use context manager for automatic cleanup
        with HierarchicalSummarizer() as summarizer:
            print(f"Summarizing {len(symbols)} symbols...")

            count = 0
            for symbol in symbols:
                # Read source code with path validation
                file_path = symbol.get("file_path")
                validated_path = validate_project_path(file_path, project_root)

                if not validated_path:
                    continue

                with open(validated_path) as f:
                    source_code = f.read()

                # Generate summary
                summary_text = summarizer.summarize_method(
                    SymbolData(
                        fqn=symbol["fqn"],
                        kind=SymbolKind(symbol["kind"]),
                        name=symbol["name"],
                        signature=symbol.get("signature"),
                        modifiers=symbol.get("modifiers", []),
                        annotations=symbol.get("annotations", []),
                    ),
                    source_code,
                )

                # Store summary
                summary = SummaryData(
                    target_fqn=symbol["fqn"],
                    level=SummaryLevel.METHOD,
                    summary=summary_text,
                )

                store.create_summary(summary)
                count += 1

                if count % 10 == 0:
                    print(f"  Progress: {count}/{len(symbols)}")

            print(f"\nGenerated {count} summaries.")
            return 0
    except Exception as e:
        print(f"Error: {e}")
        import traceback

        traceback.print_exc()
        return 1


def _cmd_summary(args: argparse.Namespace) -> int:
    """Get summary for a symbol."""
    from ariadne_core.storage.sqlite_store import SQLiteStore

    store = SQLiteStore(args.db)
    try:
        summary = store.get_summary(args.fqn)

        if not summary:
            print(f"No summary found for {args.fqn}")
            return 1

        print(f"FQN: {summary['target_fqn']}")
        print(f"Level: {summary['level']}")
        print(f"Summary: {summary['summary']}")
        return 0
    finally:
        store.close()


def _cmd_search(args: argparse.Namespace) -> int:
    """Semantic search using natural language."""
    from ariadne_llm import LLMConfig, create_embedder
    from ariadne_core.storage.sqlite_store import SQLiteStore
    from ariadne_core.storage.vector_store import ChromaVectorStore

    # Get vector DB path from env or default
    vector_path = os.environ.get("ARIADNE_VECTOR_DB_PATH", "~/.ariadne/vectors")
    vector_path = Path(vector_path).expanduser()

    store = SQLiteStore(args.db)
    try:
        # Initialize embedder
        config = LLMConfig.from_env()
        embedder = create_embedder(config)
        vector_store = ChromaVectorStore(vector_path)

        # Embed query
        query_embedding = embedder.embed_text(args.query)

        # Search summaries
        filters = {"level": args.level} if args.level else None
        results = vector_store.search_summaries(query_embedding, args.limit, filters)

        if not results or not results.get("ids"):
            print("No results found.")
            return 0

        # Display results
        ids = results["ids"][0]
        distances = results.get("distances", [[]])[0]
        metadatas = results.get("metadatas", [[]])[0]
        documents = results.get("documents", [[]])[0]

        print(f"Search results for '{args.query}':\n")

        for i, (sid, dist, doc, meta) in enumerate(
            zip(ids, distances, documents, metadatas), 1
        ):
            similarity = 1 - dist  # Convert distance to similarity
            print(f"{i}. [{meta.get('level', 'unknown')}] {sid}")
            print(f"   Summary: {doc}")
            print(f"   Similarity: {similarity:.2f}")
            print()

        return 0
    except Exception as e:
        print(f"Error: {e}")
        import traceback

        traceback.print_exc()
        return 1
    finally:
        store.close()


def _cmd_glossary(args: argparse.Namespace) -> int:
    """Build domain glossary."""
    print("Glossary extraction not yet implemented.")
    print("Use 'ariadne term-search' to search existing glossary.")
    return 0


def _cmd_term_search(args: argparse.Namespace) -> int:
    """Search domain glossary."""
    from ariadne_core.storage.sqlite_store import SQLiteStore

    store = SQLiteStore(args.db)
    try:
        entries = store.search_glossary_terms(args.term)

        if not entries:
            print(f"No glossary entries found for '{args.term}'")
            return 0

        print(f"Glossary entries for '{args.term}':\n")

        for entry in entries:
            print(f"Term: {entry['code_term']}")
            print(f"Meaning: {entry['business_meaning']}")
            if entry.get("synonyms"):
                synonyms = entry["synonyms"]
                if isinstance(synonyms, str):
                    import json

                    synonyms = json.loads(synonyms)
                print(f"Synonyms: {', '.join(synonyms)}")
            print(f"Source: {entry.get('source_fqn', 'unknown')}")
            print()

        return 0
    finally:
        store.close()


def _cmd_constraints(args: argparse.Namespace) -> int:
    """Extract business constraints."""
    print("Constraint extraction not yet implemented.")
    print("Use 'ariadne constraint-search' to search existing constraints.")
    return 0


def _cmd_constraint_search(args: argparse.Namespace) -> int:
    """Search business constraints."""
    from ariadne_core.storage.sqlite_store import SQLiteStore

    store = SQLiteStore(args.db)
    try:
        constraints = store.search_constraints(args.keyword)

        if not constraints:
            print(f"No constraints found for '{args.keyword}'")
            return 0

        print(f"Constraints matching '{args.keyword}':\n")

        for constraint in constraints:
            print(f"Name: {constraint['name']}")
            print(f"Type: {constraint['constraint_type']}")
            print(f"Description: {constraint['description']}")
            if constraint.get("source_fqn"):
                print(f"Source: {constraint['source_fqn']}")
            print()

        return 0
    finally:
        store.close()


if __name__ == "__main__":
    sys.exit(main())
