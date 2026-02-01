"""Check endpoint for live code analysis."""

import logging
from fastapi import APIRouter

from ariadne_api.dependencies import get_store
from ariadne_api.schemas.constraints import (
    AntiPatternViolation,
    CheckRequest,
    CheckResult,
)
from ariadne_analyzer.l2_architecture.anti_patterns import AntiPatternDetector

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/knowledge/check", response_model=CheckResult, tags=["check"])
async def check_code(request: CheckRequest) -> CheckResult:
    """Perform live anti-pattern detection on code changes.

    Analyzes the provided code changes for architectural violations and
    anti-patterns. Returns violations, warnings, and suggestions.
    """
    with get_store() as store:
        detector = AntiPatternDetector(store)

        # Collect all violations
        all_violations: list[AntiPatternViolation] = []

        # For each change, check for violations
        for change in request.changes:
            # Check added symbols
            for symbol_fqn in change.added_symbols:
                # Run anti-pattern detection
                violations = _check_symbol(store, symbol_fqn)
                all_violations.extend(violations)

        # Separate by severity
        violations = [v for v in all_violations if v.severity == "error"]
        warnings = [v for v in all_violations if v.severity in ("warning", "info")]

        # Generate suggestions
        suggestions = _generate_suggestions(violations + warnings)

        return CheckResult(
            violations=violations,
            warnings=warnings,
            suggestions=suggestions,
        )


def _check_symbol(store, symbol_fqn: str) -> list[AntiPatternViolation]:
    """Check a single symbol for anti-patterns."""
    violations = []
    detector = AntiPatternDetector(store)

    # Get all anti-patterns and filter for this symbol
    all_patterns = detector.detect_all()
    for pattern in all_patterns:
        if pattern.from_fqn == symbol_fqn or pattern.to_fqn == symbol_fqn:
            violations.append(
                AntiPatternViolation(
                    rule_id=pattern.rule_id,
                    from_fqn=pattern.from_fqn,
                    to_fqn=pattern.to_fqn,
                    severity=pattern.severity,
                    message=pattern.message,
                    detected_at=pattern.detected_at,
                )
            )

    return violations


def _generate_suggestions(violations: list[AntiPatternViolation]) -> list[str]:
    """Generate suggestions for fixing violations."""
    suggestions = []

    for violation in violations:
        if "Controller->DAO" in violation.message or "Dao" in violation.rule_id:
            suggestions.append(
                f"Consider introducing a Service layer between {violation.from_fqn} and {violation.to_fqn}"
            )
        elif "Circular" in violation.rule_id:
            suggestions.append(
                f"Break circular dependency between {violation.from_fqn} and {violation.to_fqn} by introducing an interface"
            )
        elif "Transaction" in violation.rule_id:
            suggestions.append(
                f"Add @Transactional annotation to {violation.from_fqn}"
            )

    # Deduplicate
    return list(set(suggestions))
