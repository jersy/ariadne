"""Shared dependencies for API routes.

Provides context-managed database connections to prevent connection leaks.
Uses dependency injection for improved testability.
"""

import os
from contextlib import contextmanager

from fastapi import HTTPException

from ariadne_core.container import get_container
from ariadne_core.storage.sqlite_store import SQLiteStore


@contextmanager
def get_store():
    """Get a SQLite store with automatic cleanup.

    Creates a new store instance for each request to ensure
    proper connection lifecycle management. The container
    is used for configuration, but each request gets its own store.

    Yields:
        SQLiteStore: Database store

    Example:
        @router.get("/endpoint")
        def endpoint():
            with get_store() as store:
                return store.get_data()
            # Connection automatically closed
    """
    db_path = os.environ.get("ARIADNE_DB_PATH", "ariadne.db")
    if not os.path.exists(db_path):
        raise HTTPException(status_code=503, detail="Database not available")

    store = SQLiteStore(db_path)
    try:
        yield store
    finally:
        # Always close the connection to prevent leaks
        if store.conn:
            store.conn.close()


@contextmanager
def get_store_from_container():
    """Get a SQLite store from the DI container with automatic cleanup.

    Uses the singleton store from the container for cases where
    sharing state across requests is desired (with proper cleanup).

    Yields:
        SQLiteStore: Database store from container

    Example:
        @router.get("/endpoint")
        def endpoint():
            with get_store_from_container() as store:
                return store.get_data()
            # Connection automatically closed
    """
    container = get_container()
    store = container.get_store()

    if not store:
        db_path = os.environ.get("ARIADNE_DB_PATH", "ariadne.db")
        if not os.path.exists(db_path):
            raise HTTPException(status_code=503, detail="Database not available")
        store = SQLiteStore(db_path)

    try:
        yield store
    finally:
        # Always close the connection to prevent leaks
        if store and store.conn:
            store.conn.close()


@contextmanager
def get_vector_store():
    """Get the vector store with automatic cleanup.

    Yields:
        ChromaVectorStore | None: Vector store (may be None if unavailable)

    Example:
        @router.get("/endpoint")
        def endpoint():
            with get_vector_store() as vector_store:
                if vector_store:
                    return vector_store.search(query)
            # Connection automatically closed
    """
    container = get_container()
    vector_store = container.get_vector_store()
    yield vector_store
