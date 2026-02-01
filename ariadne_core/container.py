"""Dependency injection container for Ariadne services.

Provides centralized service management and lifecycle control.
Improves testability by allowing services to be mocked or replaced.
"""

import logging
import os
from contextlib import contextmanager
from typing import Any, Callable, TypeVar

from ariadne_core.storage.vector_store import ChromaVectorStore
from ariadne_core.storage.sqlite_store import SQLiteStore

logger = logging.getLogger(__name__)

T = TypeVar("T")


class ServiceContainer:
    """Simple dependency injection container.

    Manages service lifecycle and provides lazy initialization.
    Services are registered as factory functions and created on first use.
    """

    def __init__(self) -> None:
        """Initialize the container with default services."""
        self._services: dict[str, Any] = {}
        self._factories: dict[str, Callable[[], Any]] = {}
        self._singletons: set[str] = set()

        # Register default services
        self._register_default_services()

    def _register_default_services(self) -> None:
        """Register default service factories."""

        # SQLiteStore - singleton by default
        def create_sqlite_store() -> SQLiteStore:
            db_path = os.environ.get("ARIADNE_DB_PATH", "ariadne.db")
            return SQLiteStore(db_path)

        self.register_factory("store", create_sqlite_store, singleton=True)

        # ChromaVectorStore - singleton by default
        def create_vector_store() -> ChromaVectorStore | None:
            try:
                vector_path = os.environ.get("ARIADNE_VECTOR_PATH", "ariadne_vectors")
                return ChromaVectorStore(vector_path)
            except Exception as e:
                logger.warning(f"Vector store unavailable: {e}")
                return None

        self.register_factory("vector_store", create_vector_store, singleton=True)

    def register_factory(
        self,
        name: str,
        factory: Callable[[], T],
        singleton: bool = True,
    ) -> None:
        """Register a service factory.

        Args:
            name: Service name
            factory: Function that creates the service
            singleton: Whether to cache the service (default: True)
        """
        self._factories[name] = factory
        if singleton:
            self._singletons.add(name)

    def register_instance(self, name: str, instance: T) -> None:
        """Register a service instance directly.

        Useful for testing with mock instances.

        Args:
            name: Service name
            instance: Service instance
        """
        self._services[name] = instance

    def get(self, name: str, default: T | None = None) -> T | None:
        """Get a service by name.

        Args:
            name: Service name
            default: Default value if service not found

        Returns:
            Service instance or default

        Raises:
            KeyError: If service not found and no default provided
        """
        # Return cached instance if available
        if name in self._services:
            return self._services[name]

        # Check if factory exists
        if name not in self._factories:
            if default is not None:
                return default
            raise KeyError(f"Service not found: {name}")

        # Create service
        factory = self._factories[name]
        instance = factory()

        # Cache if singleton
        if name in self._singletons:
            self._services[name] = instance

        return instance

    def get_store(self) -> SQLiteStore:
        """Get the SQLite store (convenience method)."""
        return self.get("store")

    def get_vector_store(self) -> ChromaVectorStore | None:
        """Get the vector store (convenience method)."""
        return self.get("vector_store")

    @contextmanager
    def override(self, name: str, instance: Any):
        """Temporarily override a service instance.

        Useful for testing.

        Args:
            name: Service name
            instance: Override instance

        Example:
            with container.override("store", mock_store):
                # Use mock_store
            pass
            # Original service restored
        """
        original = None
        if name in self._services:
            original = self._services[name]

        self._services[name] = instance
        try:
            yield
        finally:
            if original is not None:
                self._services[name] = original
            else:
                del self._services[name]

    def clear(self) -> None:
        """Clear all cached services.

        Useful for testing or re-initialization.
        """
        self._services.clear()

    def reset(self) -> None:
        """Reset the container to initial state.

        Clears cached services and keeps factories.
        """
        self.clear()


# Global container instance
_global_container: ServiceContainer | None = None


def get_container() -> ServiceContainer:
    """Get the global service container.

    Returns:
        The global ServiceContainer instance
    """
    global _global_container
    if _global_container is None:
        _global_container = ServiceContainer()
    return _global_container


def reset_container() -> None:
    """Reset the global container.

    Useful for testing to ensure clean state between tests.
    """
    global _global_container
    if _global_container is not None:
        _global_container.reset()
    _global_container = None
