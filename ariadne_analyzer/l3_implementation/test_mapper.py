"""Test file mapper - Maps source symbols to test files using naming conventions."""

import logging
import os
from pathlib import Path

from ariadne_core.storage.sqlite_store import SQLiteStore

logger = logging.getLogger(__name__)


class TestMapper:
    """Maps source code symbols to their corresponding test files.

    Uses common naming conventions to find test files:
    - src/main/java/com/example/Foo.java -> src/test/java/com/example/FooTest.java
    - src/main/java/com/example/Foo.java -> src/test/java/com/example/FooTests.java
    - Pattern matching for *Test.java, *Tests.java, *IT.java
    """

    def __init__(self, store: SQLiteStore) -> None:
        """Initialize test mapper.

        Args:
            store: SQLite database store
        """
        self.store = store

    def find_tests_for_symbol(self, fqn: str) -> dict[str, object] | None:
        """Find test files for a given symbol FQN.

        Args:
            fqn: Fully qualified name of the symbol

        Returns:
            Dictionary with test file information, or None if no tests found
        """
        # Get source file path for symbol
        symbol = self.store.get_symbol(fqn)
        if not symbol or not symbol.get("file_path"):
            return None

        source_path = Path(symbol["file_path"])

        # Generate possible test file paths
        test_paths = self._generate_test_paths(source_path)

        # Check which test files exist
        existing_tests = []
        for test_path in test_paths:
            if test_path.exists():
                existing_tests.append(test_path)

        if not existing_tests:
            return None

        # Get test file details
        return {
            "path": str(existing_tests[0]),
            "covers": [fqn],
            "additional_tests": [str(p) for p in existing_tests[1:]],
        }

    def find_tests_for_file_path(
        self,
        file_path: str,
        fqns: list[str],
    ) -> dict[str, object] | None:
        """Find test files for symbols that share the same file path.

        This is an optimized version that processes multiple FQNs at once,
        avoiding redundant file system checks.

        Args:
            file_path: The source file path
            fqns: List of FQNs that are in this file

        Returns:
            Dictionary with test file information, or None if no tests found
        """
        source_path = Path(file_path)

        # Generate possible test file paths (once per file)
        test_paths = self._generate_test_paths(source_path)

        # Check which test files exist
        existing_tests = []
        for test_path in test_paths:
            if test_path.exists():
                existing_tests.append(test_path)

        if not existing_tests:
            return None

        # Get test file details
        return {
            "path": str(existing_tests[0]),
            "covers": fqns,  # All FQNs covered by this test file
            "additional_tests": [str(p) for p in existing_tests[1:]],
        }

    def _generate_test_paths(self, source_path: Path) -> list[Path]:
        """Generate possible test file paths from source path.

        Common patterns:
        - src/main/java/.../Foo.java -> src/test/java/.../FooTest.java
        - src/main/java/.../Foo.java -> src/test/java/.../FooTests.java
        - src/main/java/.../Foo.java -> src/test/java/.../FooIT.java (integration test)
        """
        path_str = str(source_path)

        # Replace main/java with test/java
        if "/main/java/" in path_str:
            test_base = path_str.replace("/main/java/", "/test/java/")
        elif "\\main\\java\\" in path_str:
            test_base = path_str.replace("\\main\\java\\", "\\test\\java\\")
        else:
            # No standard Maven/Gradle structure, try sibling directory
            parent = source_path.parent.parent
            test_dir = parent / "test"
            if test_dir.exists():
                test_base = str(test_dir / source_path.name)
            else:
                return []

        # Remove .java extension
        if test_base.endswith(".java"):
            test_base = test_base[:-5]

        # Generate test file names
        test_paths = []
        for suffix in ["Test", "Tests", "IT"]:
            test_path = Path(f"{test_base}{suffix}.java")
            test_paths.append(test_path)

        # Also check for same-name test in test directory
        base_class = Path(test_base + ".java")
        if "src/main/java" in path_str:
            base_class = Path(path_str.replace("src/main/java", "src/test/java"))

        test_paths.append(base_class)

        return test_paths

    def find_all_tests_for_package(self, package_fqn: str) -> list[dict[str, object]]:
        """Find all test files for a package.

        Args:
            package_fqn: Package FQN (e.g., com.example.service)

        Returns:
            List of test file information dictionaries
        """
        cursor = self.store.conn.cursor()

        # Find all symbols in package
        cursor.execute(
            """
            SELECT DISTINCT file_path FROM symbols
            WHERE fqn LIKE ?
            AND file_path IS NOT NULL
            """,
            (f"{package_fqn}%",),
        )

        test_files = []
        seen_paths = set()

        for row in cursor.fetchall():
            file_path = row["file_path"]
            if file_path in seen_paths:
                continue
            seen_paths.add(file_path)

            # Find tests for this file
            source_path = Path(file_path)
            test_paths = self._generate_test_paths(source_path)

            for test_path in test_paths:
                if test_path.exists() and str(test_path) not in seen_paths:
                    test_files.append(
                        {
                            "path": str(test_path),
                            "source_package": package_fqn,
                        }
                    )
                    seen_paths.add(str(test_path))

        return test_files
