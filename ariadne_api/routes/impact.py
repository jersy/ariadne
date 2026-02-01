"""Impact analysis endpoint."""

import logging
import os

from fastapi import APIRouter, HTTPException, Query

from ariadne_analyzer.l3_implementation.impact_analyzer import ImpactAnalyzer
from ariadne_api.schemas.impact import (
    AffectedCaller,
    AffectedEntryPoint,
    ImpactResponse,
    MissingCoverage,
    RelatedTest,
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


@router.get("/knowledge/impact", response_model=ImpactResponse, tags=["impact"])
async def analyze_impact(
    target: str = Query(..., description="Symbol FQN to analyze"),
    depth: int = Query(5, ge=1, le=20, description="Reverse traversal depth"),
    include_tests: bool = Query(True, description="Include test mapping"),
    include_transitive: bool = Query(False, description="Include N-order dependencies"),
    risk_threshold: str = Query("low", description="Filter by risk level"),
) -> ImpactResponse:
    """Analyze the impact of changing a specific symbol.

    Performs reverse call graph traversal to find:
    - All callers that would be affected
    - Entry points that would be impacted
    - Test files that cover affected code
    - Missing test coverage for affected paths

    Returns risk level based on caller count, entry point proximity,
    and test coverage.
    """
    store = get_store()
    analyzer = ImpactAnalyzer(store)

    # Get target symbol details
    target_symbol = store.get_symbol(target)
    if not target_symbol:
        raise HTTPException(
            status_code=404,
            detail=f"Symbol not found: {target}",
        )

    # Run impact analysis
    result = analyzer.analyze_impact(
        target_fqn=target,
        depth=depth,
        include_tests=include_tests,
        include_transitive=include_transitive,
    )

    # Convert to response format
    return ImpactResponse(
        target={
            "fqn": target_symbol["fqn"],
            "kind": target_symbol["kind"],
            "name": target_symbol["name"],
        },
        affected_callers=[
            AffectedCaller(
                fqn=c["from_fqn"],
                kind=c.get("from_kind", "unknown"),
                name=c.get("from_name", ""),
                layer=c.get("layer", "unknown"),
                depth=c["depth"],
            )
            for c in result.affected_callers
        ],
        affected_entry_points=[
            AffectedEntryPoint(
                fqn=ep["fqn"],
                entry_type=ep["entry_type"],
                http_method=ep.get("http_method"),
                http_path=ep.get("http_path"),
                cron_expression=ep.get("cron_expression"),
                mq_queue=ep.get("mq_queue"),
            )
            for ep in result.affected_entry_points
        ],
        related_tests=[
            RelatedTest(
                path=t["path"],
                covers=t.get("covers", []),
                additional_tests=t.get("additional_tests", []),
            )
            for t in result.related_tests
        ],
        missing_test_coverage=[
            MissingCoverage(
                fqn=m["fqn"],
                kind=m.get("kind", "unknown"),
                name=m.get("name", ""),
                layer=m.get("layer", "unknown"),
                depth=m["depth"],
            )
            for m in result.missing_test_coverage
        ],
        risk_level=result.risk_level,
        confidence=result.confidence,
    )
