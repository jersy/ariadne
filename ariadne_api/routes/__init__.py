"""API routes for Ariadne."""

# Import all route modules
from ariadne_api.routes import (
    check,
    constraints,
    graph,
    health,
    impact,
    jobs,
    rebuild,
    search,
    symbol,
)  # noqa: F401

__all__ = ["check", "constraints", "graph", "health", "impact", "jobs", "rebuild", "search", "symbol"]
