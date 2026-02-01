"""Constraints endpoint for business constraints and anti-patterns."""

import logging
import os

from fastapi import APIRouter, HTTPException, Query

from ariadne_analyzer.l2_architecture.anti_patterns import AntiPatternDetector
from ariadne_api.schemas.constraints import (
    AntiPatternViolation,
    ConstraintEntry,
    ConstraintsResponse,
)
from ariadne_core.storage.sqlite_store import SQLiteStore

router = APIRouter()
logger = logging.getLogger(__name__)


def get_store() -> SQLiteStore:
    """Dependency to get SQLite store."""
    db_path = os.environ.get("ARIADNE_DB_PATH", "ariadne.db")
    if not os.path.exists(db_path):
        raise HTTPException(status_code=503, detail="Database not available")
    return SQLiteStore(db_path)


@router.get("/knowledge/constraints", response_model=ConstraintsResponse, tags=["constraints"])
async def get_constraints(
    context: str | None = Query(None, description="Filter by file path or FQN"),
    severity: str | None = Query(None, description="Filter by severity (error, warning, info)"),
) -> ConstraintsResponse:
    """Get business constraints and detected anti-patterns.

    Returns cached constraints and anti-pattern violations. Optionally filter
    by context (file path or symbol FQN) or severity level.
    """
    store = get_store()

    # Get constraints
    constraints = _get_constraints(store, context)

    # Get anti-patterns
    anti_patterns = _get_anti_patterns(store, context, severity)

    return ConstraintsResponse(
        constraints=constraints,
        anti_patterns=anti_patterns,
    )


def _get_constraints(
    store: SQLiteStore,
    context: str | None,
) -> list[ConstraintEntry]:
    """Get business constraints."""
    cursor = store.conn.cursor()

    if context:
        # Filter by context (file path or FQN)
        cursor.execute(
            """
            SELECT * FROM constraints
            WHERE source_fqn LIKE ? OR file_path LIKE ?
            ORDER BY name
            """,
            (f"{context}%", f"{context}%"),
        )
    else:
        cursor.execute(
            """
            SELECT * FROM constraints
            ORDER BY name
            """
        )

    constraints = []
    for row in cursor.fetchall():
        c = dict(row)
        constraints.append(
            ConstraintEntry(
                name=c["name"],
                description=c["description"],
                source_fqn=c.get("source_fqn"),
                source_line=c.get("source_line"),
                constraint_type=c.get("constraint_type"),
            )
        )

    return constraints


def _get_anti_patterns(
    store: SQLiteStore,
    context: str | None,
    severity: str | None,
) -> list[AntiPatternViolation]:
    """Get detected anti-pattern violations."""
    cursor = store.conn.cursor()

    # Build query with filters
    where_clauses = []
    params = []

    if context:
        where_clauses.append("from_fqn LIKE ?")
        params.append(f"{context}%")

    if severity:
        where_clauses.append("severity = ?")
        params.append(severity)

    where_sql = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""

    cursor.execute(
        f"""
        SELECT * FROM anti_patterns
        {where_sql}
        ORDER BY severity DESC, detected_at DESC
        """,
        params,
    )

    violations = []
    for row in cursor.fetchall():
        v = dict(row)
        violations.append(
            AntiPatternViolation(
                rule_id=v["rule_id"],
                from_fqn=v["from_fqn"],
                to_fqn=v.get("to_fqn"),
                severity=v["severity"],
                message=v["message"],
                detected_at=v["detected_at"],
            )
        )

    return violations
