"""Test mapping and coverage analysis endpoints."""

import logging
from fastapi import APIRouter, HTTPException, Query

from ariadne_api.dependencies import get_store
from ariadne_api.schemas.tests import (
    CallerInfo,
    CoverageAnalysisResponse,
    CoverageStats,
    CoverageWarning,
    TestMappingEntry,
    TestMappingResponse,
)

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/knowledge/tests/{fqn:path}", response_model=TestMappingResponse, tags=["tests"])
async def get_test_mapping(fqn: str) -> TestMappingResponse:
    """Get test file mappings for a source symbol.

    Uses Maven Surefire test naming conventions to find test files:
    - Test*.java (e.g., TestUserService.java)
    - *Test.java (e.g., UserServiceTest.java) - RECOMMENDED
    - *Tests.java (e.g., UserServiceTests.java)
    - *IT.java (e.g., UserServiceIT.java - integration tests)

    Returns:
        TestMappingResponse with source FQN and test file mappings
    """
    with get_store() as store:
        # Verify symbol exists
        symbol = store.get_symbol(fqn)
        if not symbol:
            raise HTTPException(
                status_code=404,
                detail=f"Symbol not found: {fqn}",
            )

        # Get test mapping
        mapping = store.get_test_mapping(fqn)

        # Convert to response model
        test_mappings = [
            TestMappingEntry(
                test_file=tm["test_file"],
                test_exists=tm["test_exists"],
                test_pattern=tm.get("test_pattern", ""),
                test_methods=tm.get("test_methods", []),
            )
            for tm in mapping["test_mappings"]
        ]

        return TestMappingResponse(
            source_fqn=mapping["source_fqn"],
            source_file=mapping.get("source_file"),
            test_mappings=test_mappings,
        )


@router.get("/knowledge/coverage", response_model=CoverageAnalysisResponse, tags=["tests"])
async def get_coverage_analysis(
    target: str = Query(..., description="Target symbol FQN to analyze"),
) -> CoverageAnalysisResponse:
    """Analyze test coverage for a target symbol.

    Uses the edges table to find all callers and determines which
    callers have test coverage.

    Returns:
        CoverageAnalysisResponse with statistics and warnings
    """
    with get_store() as store:
        # Verify symbol exists
        symbol = store.get_symbol(target)
        if not symbol:
            raise HTTPException(
                status_code=404,
                detail=f"Symbol not found: {target}",
            )

        # Analyze coverage
        coverage = store.analyze_coverage(target)

        # Convert to response model
        stats = CoverageStats(**coverage["statistics"])

        callers = [
            CallerInfo(
                caller_fqn=c["caller_fqn"],
                caller_kind=c.get("caller_kind"),
                caller_name=c.get("caller_name"),
                caller_file=c["caller_file"],
                is_test_file=c["is_test_file"],
                is_covered=c["is_covered"],
            )
            for c in coverage["callers"]
        ]

        warnings = [
            CoverageWarning(
                type=w["type"],
                severity=w["severity"],
                message=w["message"],
                caller_fqn=w["caller_fqn"],
            )
            for w in coverage["warnings"]
        ]

        return CoverageAnalysisResponse(
            target_fqn=coverage["target_fqn"],
            statistics=stats,
            callers=callers,
            warnings=warnings,
        )
