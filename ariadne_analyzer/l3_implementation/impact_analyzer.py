"""L3 Impact Analyzer - Reverse call graph traversal for change impact analysis."""

from dataclasses import dataclass
from typing import Any

from ariadne_core.storage.sqlite_store import SQLiteStore
from ariadne_core.utils.layer import determine_layer_or_unknown


@dataclass
class ImpactResult:
    """Result of impact analysis.

    Attributes:
        target_fqn: The symbol being analyzed
        affected_callers: List of callers that would be affected
        affected_entry_points: List of entry points that would be affected
        related_tests: List of test files that cover affected symbols
        missing_test_coverage: List of affected symbols without test coverage
        risk_level: Overall risk level (LOW, MEDIUM, HIGH, CRITICAL)
        confidence: Confidence score (0-1)
    """

    target_fqn: str
    affected_callers: list[dict[str, Any]]
    affected_entry_points: list[dict[str, Any]]
    related_tests: list[dict[str, Any]]
    missing_test_coverage: list[dict[str, Any]]
    risk_level: str
    confidence: float


class ImpactAnalyzer:
    """Analyzes the impact of changing a specific symbol.

    Uses reverse call graph traversal to find all callers, maps them to
    entry points, identifies test coverage, and calculates risk level.
    """

    def __init__(self, store: SQLiteStore) -> None:
        """Initialize impact analyzer.

        Args:
            store: SQLite database store
        """
        self.store = store

    def analyze_impact(
        self,
        target_fqn: str,
        depth: int = 5,
        include_tests: bool = True,
        include_transitive: bool = False,
    ) -> ImpactResult:
        """Analyze impact of changing a symbol.

        Args:
            target_fqn: Fully qualified name of the symbol to analyze
            depth: Maximum reverse traversal depth
            include_tests: Whether to include test mapping
            include_transitive: Whether to include N-order dependencies

        Returns:
            ImpactResult with analysis results
        """
        # Validate target exists
        target = self.store.get_symbol(target_fqn)
        if not target:
            raise ValueError(f"Symbol not found: {target_fqn}")

        # 1. Find all callers via reverse traversal
        callers = self._find_callers(target_fqn, depth)

        # 2. Map callers to entry points
        entry_points = self._map_to_entry_points(callers)

        # 3. Find related tests
        tests = self._find_related_tests(callers) if include_tests else []

        # 4. Detect missing coverage
        missing_coverage = self._detect_missing_coverage(callers, tests) if include_tests else []

        # 5. Calculate risk
        risk_level = self._calculate_risk(
            len(callers),
            len(entry_points),
            len(missing_coverage),
        )

        # 6. Calculate confidence
        confidence = self._calculate_confidence(target_fqn, callers, tests)

        return ImpactResult(
            target_fqn=target_fqn,
            affected_callers=callers,
            affected_entry_points=entry_points,
            related_tests=tests,
            missing_test_coverage=missing_coverage,
            risk_level=risk_level,
            confidence=confidence,
        )

    def _find_callers(self, target_fqn: str, max_depth: int) -> list[dict[str, Any]]:
        """Find all callers of target_fqn using reverse traversal."""
        cursor = self.store.conn.cursor()

        cursor.execute(
            """
            WITH RECURSIVE callers(depth, from_fqn, to_fqn, from_kind, from_name) AS (
                SELECT 0, e.from_fqn, e.to_fqn, s.kind, s.name
                FROM edges e
                JOIN symbols s ON e.from_fqn = s.fqn
                WHERE e.to_fqn = ? AND e.relation = 'calls'

                UNION ALL

                SELECT c.depth + 1, e.from_fqn, e.to_fqn, s.kind, s.name
                FROM edges e
                JOIN callers c ON e.to_fqn = c.from_fqn
                JOIN symbols s ON e.from_fqn = s.fqn
                WHERE c.depth < ? AND e.relation = 'calls'
            )
            SELECT DISTINCT * FROM callers ORDER BY depth
            """,
            (target_fqn, max_depth),
        )

        callers = []
        for row in cursor.fetchall():
            caller = dict(row)
            # Get layer information
            symbol = self.store.get_symbol(caller["from_fqn"])
            if symbol:
                layer = determine_layer_or_unknown(symbol)
                caller["layer"] = layer
            callers.append(caller)

        return callers

    def _map_to_entry_points(self, callers: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Map callers to entry points."""
        if not callers:
            return []

        cursor = self.store.conn.cursor()

        # Get all caller FQNs
        caller_fqns = [c["from_fqn"] for c in callers]
        placeholders = ",".join("?" * len(caller_fqns))

        # Find entry points for callers
        cursor.execute(
            f"""
            SELECT ep.*, s.kind as symbol_kind
            FROM entry_points ep
            JOIN symbols s ON ep.symbol_fqn = s.fqn
            WHERE ep.symbol_fqn IN ({placeholders})
            """,
            caller_fqns,
        )

        entry_points = []
        for row in cursor.fetchall():
            ep = dict(row)
            entry_points.append(
                {
                    "fqn": ep["symbol_fqn"],
                    "entry_type": ep["entry_type"],
                    "http_method": ep.get("http_method"),
                    "http_path": ep.get("http_path"),
                    "cron_expression": ep.get("cron_expression"),
                    "mq_queue": ep.get("mq_queue"),
                }
            )

        return entry_points

    def _find_related_tests(self, callers: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Find test files related to callers using file path heuristics."""
        from ariadne_analyzer.l3_implementation.test_mapper import TestMapper

        test_mapper = TestMapper(self.store)
        tests = []

        for caller in callers:
            caller_fqn = caller["from_fqn"]
            test_info = test_mapper.find_tests_for_symbol(caller_fqn)
            if test_info:
                tests.append(test_info)

        return tests

    def _detect_missing_coverage(
        self,
        callers: list[dict[str, Any]],
        tests: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Detect callers without test coverage."""
        covered_callers = set()
        for test in tests:
            for covers in test.get("covers", []):
                covered_callers.add(covers)

        missing = []
        for caller in callers:
            caller_fqn = caller["from_fqn"]
            if caller_fqn not in covered_callers:
                missing.append(
                    {
                        "fqn": caller_fqn,
                        "kind": caller.get("from_kind"),
                        "name": caller.get("from_name"),
                        "layer": caller.get("layer"),
                        "depth": caller["depth"],
                    }
                )

        return missing

    def _calculate_risk(
        self,
        caller_count: int,
        entry_point_count: int,
        missing_coverage_count: int,
    ) -> str:
        """Calculate risk level based on multiple factors.

        Risk factors:
        - caller_count: More callers = higher risk
        - entry_point_count: Closer to entry points = higher risk
        - missing_coverage_count: Less test coverage = higher risk
        """
        # Calculate raw risk score (0-100)
        risk_score = 0

        # Caller count contribution (0-30 points)
        if caller_count > 20:
            risk_score += 30
        elif caller_count > 10:
            risk_score += 20
        elif caller_count > 5:
            risk_score += 10

        # Entry point proximity (0-50 points)
        if entry_point_count > 0:
            if entry_point_count > 5:
                risk_score += 50
            elif entry_point_count > 2:
                risk_score += 40
            else:
                risk_score += 30

        # Missing test coverage (0-20 points)
        if missing_coverage_count > 0:
            if missing_coverage_count > 5:
                risk_score += 20
            elif missing_coverage_count > 2:
                risk_score += 15
            else:
                risk_score += 10

        # Map to risk level
        if risk_score >= 70:
            return "CRITICAL"
        elif risk_score >= 50:
            return "HIGH"
        elif risk_score >= 30:
            return "MEDIUM"
        else:
            return "LOW"

    def _calculate_confidence(
        self,
        target_fqn: str,
        callers: list[dict[str, Any]],
        tests: list[dict[str, Any]],
    ) -> float:
        """Calculate confidence score (0-1).

        Higher confidence when:
        - More callers found (better analysis)
        - More tests found (better coverage understanding)
        """
        base_confidence = 0.5

        # Caller count increases confidence
        caller_bonus = min(len(callers) * 0.05, 0.3)

        # Test coverage increases confidence
        test_bonus = min(len(tests) * 0.1, 0.2)

        return min(base_confidence + caller_bonus + test_bonus, 1.0)
