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

    if args.command == "serve":
        print(f"Server would start on port {args.port} (not implemented yet)")
        return 0

    return 0


if __name__ == "__main__":
    sys.exit(main())
