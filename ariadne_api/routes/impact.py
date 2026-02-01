"""Impact analysis endpoint."""

import logging
from fastapi import APIRouter, HTTPException, Query

from ariadne_analyzer.l3_implementation.impact_analyzer import ImpactAnalyzer
from ariadne_api.dependencies import get_store
from ariadne_api.schemas.impact import (
    AffectedCaller,
    AffectedEntryPoint,
    ImpactResponse,
    MissingCoverage,
    RelatedTest,
)

router = APIRouter()
logger = logging.getLogger(__name__)


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
    with get_store() as store:
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

        # Filter by risk threshold if specified
        risk_levels = {"low": 0, "medium": 1, "high": 2, "critical": 3}
        threshold_value = risk_levels.get(risk_threshold.lower(), 0)
        result_risk_value = risk_levels.get(result.risk_level.lower(), 0)

        if result_risk_value < threshold_value:
            # Return empty response if below threshold
            return ImpactResponse(
                target={
                    "fqn": target,
                    "kind": target_symbol.get("kind"),
                    "name": target_symbol.get("name"),
                },
                affected_callers=[],
                affected_entry_points=[],
                related_tests=[],
                missing_test_coverage=[],
                risk_level="low",
                confidence=result.confidence,
            )

        # Convert domain models to response models
        affected_callers = [
            AffectedCaller(
                fqn=c["from_fqn"],
                kind=c.get("from_kind"),
                name=c.get("from_name"),
                layer=c.get("layer"),
                depth=c.get("depth"),
            )
            for c in result.affected_callers
        ]

        affected_entry_points = [
            AffectedEntryPoint(
                fqn=ep["fqn"],
                entry_type=ep["entry_type"],
                http_method=ep.get("http_method"),
                http_path=ep.get("http_path"),
            )
            for ep in result.affected_entry_points
        ]

        related_tests = [
            RelatedTest(
                test_file=t.get("test_file"),
                covers=t.get("covers", []),
            )
            for t in result.related_tests
        ]

        missing_coverage = [
            MissingCoverage(
                fqn=m["fqn"],
                kind=m.get("kind"),
                name=m.get("name"),
                layer=m.get("layer"),
                depth=m.get("depth", 0),
            )
            for m in result.missing_test_coverage
        ]

        return ImpactResponse(
            target={
                "fqn": target,
                "kind": target_symbol.get("kind"),
                "name": target_symbol.get("name"),
            },
            affected_callers=affected_callers,
            affected_entry_points=affected_entry_points,
            related_tests=related_tests,
            missing_test_coverage=missing_coverage,
            risk_level=result.risk_level,
            confidence=result.confidence,
        )
