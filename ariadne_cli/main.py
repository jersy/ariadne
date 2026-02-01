"""Ariadne CLI - Code Knowledge Graph for Architect Agents."""

import argparse
import sys


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
        print(f"Server would start on port {args.port} (not implemented yet)")
        return 0

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


if __name__ == "__main__":
    sys.exit(main())
