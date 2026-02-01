"""Configuration and fixtures for API tests."""

import os
import tempfile
from pathlib import Path

import pytest

from ariadne_core.container import reset_container


@pytest.fixture(autouse=True)
def reset_di_container():
    """Reset the dependency injection container between tests."""
    reset_container()
    yield
    reset_container()


@pytest.fixture
def temp_db_path():
    """Create a temporary database path for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        yield str(db_path)


@pytest.fixture
def api_client(temp_db_path):
    """Create a test API client."""
    from fastapi.testclient import TestClient

    # Set environment variables
    os.environ["ARIADNE_DB_PATH"] = temp_db_path
    os.environ["ARIADNE_LOG_LEVEL"] = "WARNING"  # Reduce noise in tests
    os.environ["ARIADNE_RATE_LIMIT_ENABLED"] = "false"  # Disable rate limiting in tests
    os.environ["ARIADNE_API_VERSION"] = "v1"  # Use consistent API version in tests

    # Initialize the database with schema
    from ariadne_core.storage.sqlite_store import SQLiteStore
    SQLiteStore(temp_db_path, init=True)

    from ariadne_api.app import app

    client = TestClient(app)
    yield client

    # Cleanup
    if "ARIADNE_DB_PATH" in os.environ:
        del os.environ["ARIADNE_DB_PATH"]
    if "ARIADNE_RATE_LIMIT_ENABLED" in os.environ:
        del os.environ["ARIADNE_RATE_LIMIT_ENABLED"]
    if "ARIADNE_API_VERSION" in os.environ:
        del os.environ["ARIADNE_API_VERSION"]


@pytest.fixture
def sample_db(temp_db_path):
    """Create a sample database with test data."""
    from ariadne_core.models.types import SymbolData, SymbolKind
    from ariadne_core.storage.sqlite_store import SQLiteStore

    store = SQLiteStore(temp_db_path, init=True)

    # Add sample symbols
    store.insert_symbols([
        SymbolData(
            fqn="com.example.UserService",
            kind=SymbolKind.CLASS,
            name="UserService",
            file_path="/src/main/java/com/example/UserService.java",
            line_number=10,
            modifiers=["public"],
            annotations=["Service"],
        ),
        SymbolData(
            fqn="com.example.UserController",
            kind=SymbolKind.CLASS,
            name="UserController",
            file_path="/src/main/java/com/example/UserController.java",
            line_number=5,
            modifiers=["public"],
            annotations=["RestController"],
        ),
    ])

    return store
