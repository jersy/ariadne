"""Unit tests for test mapping and coverage analysis functionality."""

import tempfile
from pathlib import Path

import pytest

from ariadne_core.models.types import EdgeData, RelationKind, SymbolData, SymbolKind
from ariadne_core.storage.sqlite_store import SQLiteStore


@pytest.fixture
def store_with_sample_data():
    """Create a temporary SQLite store with sample data for testing."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    store = SQLiteStore(db_path, init=True)

    # Insert sample symbols
    symbols = [
        SymbolData(
            fqn="com.example.service.UserService",
            kind=SymbolKind.CLASS,
            name="UserService",
            file_path="src/main/java/com/example/service/UserService.java",
            line_number=10,
        ),
        SymbolData(
            fqn="com.example.controller.UserController",
            kind=SymbolKind.CLASS,
            name="UserController",
            file_path="src/main/java/com/example/controller/UserController.java",
            line_number=5,
        ),
        SymbolData(
            fqn="com.example.service.UserServiceTest",
            kind=SymbolKind.CLASS,
            name="UserServiceTest",
            file_path="src/test/java/com/example/service/UserServiceTest.java",
            line_number=8,
        ),
    ]
    store.insert_symbols(symbols)

    # Insert edges (UserController -> UserService)
    edges = [
        EdgeData(
            from_fqn="com.example.controller.UserController",
            to_fqn="com.example.service.UserService",
            relation=RelationKind.CALLS,
        ),
    ]
    store.insert_edges(edges)

    yield store
    store.close()
    Path(db_path).unlink(missing_ok=True)


class TestTestMapping:
    """Tests for get_test_mapping method."""

    def test_get_test_mapping_with_valid_symbol(self, store_with_sample_data):
        """Test test mapping for a valid symbol."""
        mapping = store_with_sample_data.get_test_mapping("com.example.service.UserService")

        assert mapping["source_fqn"] == "com.example.service.UserService"
        assert mapping["source_file"] == "src/main/java/com/example/service/UserService.java"
        assert len(mapping["test_mappings"]) == 3  # Test, Tests, IT patterns

        # Check that test patterns are correct
        test_files = [tm["test_file"] for tm in mapping["test_mappings"]]
        assert any("UserServiceTest.java" in f for f in test_files)
        assert any("UserServiceTests.java" in f for f in test_files)
        assert any("UserServiceIT.java" in f for f in test_files)

    def test_get_test_mapping_nonexistent_symbol(self, store_with_sample_data):
        """Test test mapping for a non-existent symbol."""
        mapping = store_with_sample_data.get_test_mapping("com.example.NonExistent")

        assert mapping["source_fqn"] == "com.example.NonExistent"
        assert mapping["source_file"] is None
        assert len(mapping["test_mappings"]) == 0

    def test_get_test_mapping_symbol_without_file_path(self, store_with_sample_data):
        """Test test mapping for a symbol without file path."""
        # Insert symbol without file path
        symbol = SymbolData(
            fqn="com.example.NoPath",
            kind=SymbolKind.CLASS,
            name="NoPath",
        )
        store_with_sample_data.insert_symbols([symbol])

        mapping = store_with_sample_data.get_test_mapping("com.example.NoPath")

        assert mapping["source_fqn"] == "com.example.NoPath"
        assert mapping["source_file"] is None
        assert len(mapping["test_mappings"]) == 0


class TestGenerateTestPaths:
    """Tests for _generate_test_paths method."""

    def test_generate_test_paths_standard_maven_structure(self):
        """Test path generation for standard Maven structure."""
        store = SQLiteStore(":memory:", init=True)
        source_path = Path("src/main/java/com/example/service/UserService.java")

        test_paths = store._generate_test_paths(source_path)

        assert len(test_paths) == 3
        assert any("UserServiceTest.java" in p for p in test_paths)
        assert any("UserServiceTests.java" in p for p in test_paths)
        assert any("UserServiceIT.java" in p for p in test_paths)

        # Verify test/java is used
        for path in test_paths:
            assert "/test/java/" in path

    def test_generate_test_paths_windows_style(self):
        """Test path generation for Windows-style paths."""
        store = SQLiteStore(":memory:", init=True)
        source_path = Path("src\\main\\java\\com\\example\\service\\UserService.java")

        test_paths = store._generate_test_paths(source_path)

        assert len(test_paths) == 3
        for path in test_paths:
            assert "\\test\\java\\" in path

    def test_generate_test_paths_non_standard_structure(self):
        """Test path generation for non-standard directory structure."""
        store = SQLiteStore(":memory:", init=True)
        source_path = Path("src/code/com/example/service/UserService.java")

        test_paths = store._generate_test_paths(source_path)

        # Should return empty list for non-standard structure
        assert len(test_paths) == 0


class TestIsTestFile:
    """Tests for _is_test_file method."""

    def test_is_test_file_test_directory(self):
        """Test detection of test files by directory."""
        store = SQLiteStore(":memory:", init=True)

        assert store._is_test_file("src/test/java/UserServiceTest.java") is True
        assert store._is_test_file("src\\test\\java\\UserServiceTest.java") is True

    def test_is_test_file_naming_patterns(self):
        """Test detection of test files by naming patterns."""
        store = SQLiteStore(":memory:", init=True)

        # Test* prefix
        assert store._is_test_file("src/main/java/TestUserService.java") is True

        # *Test suffix
        assert store._is_test_file("src/main/java/UserServiceTest.java") is True

        # *Tests suffix
        assert store._is_test_file("src/main/java/UserServiceTests.java") is True

        # *IT suffix (integration test)
        assert store._is_test_file("src/main/java/UserServiceIT.java") is True

        # Non-test file
        assert store._is_test_file("src/main/java/UserService.java") is False

    def test_is_test_file_empty_path(self):
        """Test handling of empty file path."""
        store = SQLiteStore(":memory:", init=True)

        assert store._is_test_file("") is False
        assert store._is_test_file(None) is False


class TestAnalyzeCoverage:
    """Tests for analyze_coverage method."""

    def test_analyze_coverage_with_callers(self, store_with_sample_data):
        """Test coverage analysis with callers."""
        coverage = store_with_sample_data.analyze_coverage("com.example.service.UserService")

        assert coverage["target_fqn"] == "com.example.service.UserService"
        assert coverage["statistics"]["total_callers"] == 1

        # UserController is not a test file, so it's not covered
        assert coverage["statistics"]["tested_callers"] == 0
        assert coverage["statistics"]["coverage_percentage"] == 0.0

        # Should have one warning
        assert len(coverage["warnings"]) == 1
        assert coverage["warnings"][0]["type"] == "untested_caller"
        assert "UserController" in coverage["warnings"][0]["message"]

    def test_analyze_coverage_with_test_caller(self, store_with_sample_data):
        """Test coverage analysis when a caller is a test file."""
        # Add an edge from test to service
        edge = EdgeData(
            from_fqn="com.example.service.UserServiceTest",
            to_fqn="com.example.service.UserService",
            relation=RelationKind.CALLS,
        )
        store_with_sample_data.insert_edges([edge])

        coverage = store_with_sample_data.analyze_coverage("com.example.service.UserService")

        assert coverage["statistics"]["total_callers"] == 2
        # UserServiceTest is a test file, so it counts as covered
        assert coverage["statistics"]["tested_callers"] == 1
        assert coverage["statistics"]["coverage_percentage"] == 50.0

    def test_analyze_coverage_no_callers(self, store_with_sample_data):
        """Test coverage analysis for symbol with no callers."""
        coverage = store_with_sample_data.analyze_coverage("com.example.controller.UserController")

        assert coverage["target_fqn"] == "com.example.controller.UserController"
        assert coverage["statistics"]["total_callers"] == 0
        assert coverage["statistics"]["tested_callers"] == 0
        assert coverage["statistics"]["coverage_percentage"] == 0.0
        assert len(coverage["warnings"]) == 0

    def test_analyze_coverage_nonexistent_symbol(self, store_with_sample_data):
        """Test coverage analysis for non-existent symbol."""
        # Note: Current implementation returns empty results instead of raising
        coverage = store_with_sample_data.analyze_coverage("com.example.NonExistent")

        assert coverage["target_fqn"] == "com.example.NonExistent"
        assert coverage["statistics"]["total_callers"] == 0


class TestExtractTestMethods:
    """Tests for _extract_test_methods method."""

    def test_extract_test_methods_from_test_file(self, store_with_sample_data, tmp_path):
        """Test extracting test methods from a test file."""
        # Create a temporary test file
        test_file = tmp_path / "UserServiceTest.java"
        test_file.write_text("""
        public class UserServiceTest {
            @Test
            public void testCreateUser() {
                // test code
            }

            @Test
            public void testDeleteUser() {
                // test code
            }

            public void testFindByUsername() {
                // test without @Test annotation
            }
        }
        """)

        store = SQLiteStore(":memory:", init=True)
        methods = store._extract_test_methods(test_file)

        # Should find test methods with @Test and those starting with "test"
        assert len(methods) >= 2
        assert "testCreateUser" in methods
        assert "testDeleteUser" in methods

    def test_extract_test_methods_nonexistent_file(self, store_with_sample_data):
        """Test extracting test methods from non-existent file."""
        store = SQLiteStore(":memory:", init=True)
        methods = store._extract_test_methods(Path("nonexistent.java"))

        assert methods == []
