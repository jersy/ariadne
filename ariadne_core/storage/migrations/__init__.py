"""Database migrations for Ariadne knowledge graph."""

from .migration_001_cascade_deletes import migration_001_cascade_deletes

ALL_MIGRATIONS = [
    migration_001_cascade_deletes,
]

__all__ = ["ALL_MIGRATIONS"]
