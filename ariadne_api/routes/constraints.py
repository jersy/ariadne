"""Constraints endpoint for business constraints and anti-patterns."""

import logging
from fastapi import APIRouter, HTTPException, Query

from ariadne_analyzer.l2_architecture.anti_patterns import AntiPatternDetector
from ariadne_api.dependencies import get_store
from ariadne_api.schemas.constraints import (
    AntiPatternViolation,
    ConstraintEntry,
    ConstraintsResponse,
)

router = APIRouter()
logger = logging.getLogger(__name__)

# Whitelist of allowed severity values to prevent injection
ALLOWED_SEVERITIES = {"error", "warning", "info", "critical"}


@router.get("/knowledge/constraints", response_model=ConstraintsResponse, tags=["constraints"])
async def get_constraints(
    context: str | None = Query(None, description="Filter by file path or FQN"),
    severity: str | None = Query(None, description="Filter by severity (error, warning, info, critical)"),
) -> ConstraintsResponse:
    """Get business constraints and detected anti-patterns.

    Returns cached constraints and anti-pattern violations. Optionally filter
    by context (file path or symbol FQN) or severity level.
    """
    # Validate severity against whitelist
    if severity and severity not in ALLOWED_SEVERITIES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid severity: {severity}. Must be one of: {', '.join(sorted(ALLOWED_SEVERITIES))}",
        )

    with get_store() as store:
        # Get constraints
        constraints = _get_constraints(store, context)

        # Get anti-patterns
        anti_patterns = _get_anti_patterns(store, context, severity)

        return ConstraintsResponse(
            constraints=constraints,
            anti_patterns=anti_patterns,
        )


def _get_constraints(
    store,
    context: str | None,
) -> list[ConstraintEntry]:
    """Get business constraints."""
    cursor = store.conn.cursor()

    if context:
        # Filter by context (source FQN or name prefix)
        cursor.execute(
            """
            SELECT * FROM constraints
            WHERE source_fqn LIKE ? OR name LIKE ?
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
    store,
    context: str | None,
    severity: str | None,
) -> list[AntiPatternViolation]:
    """Get detected anti-pattern violations.

    NOTE: SQL injection safety is ensured by:
    1. All column names are hardcoded strings (not from user input)
    2. User values are properly parameterized with ? placeholders
    3. Severity is validated against ALLOWED_SEVERITIES whitelist
    """
    cursor = store.conn.cursor()

    # Build WHERE clause using only hardcoded column names.
    # User input goes into params (parameterized), never into SQL structure.
    where_clauses = []
    params = []

    if context:
        where_clauses.append("from_fqn LIKE ?")
        params.append(f"{context}%")

    if severity:
        where_clauses.append("severity = ?")
        params.append(severity)

    # Safe to join: where_clauses contains only trusted, hardcoded strings
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
