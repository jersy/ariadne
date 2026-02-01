"""Utility functions for architectural layer detection.

Provides shared layer detection logic to eliminate code duplication
across impact analyzer, graph routes, and other components.
"""

from typing import Any


def determine_layer(symbol: dict[str, Any]) -> str | None:
    """Determine architectural layer from symbol annotations.

    Checks for common Java/Spring annotations to identify layer:
    - Controller: @Controller, @RestController
    - Service: @Service
    - Repository: @Repository

    Args:
        symbol: Symbol dictionary from the knowledge graph

    Returns:
        Layer name ("controller", "service", "repository", "domain", or None)
    """
    # Normalize annotations to a list
    annotations = symbol.get("annotations")
    if annotations is None:
        annotations = []
    elif isinstance(annotations, str):
        # Handle comma-separated annotations
        annotations = [a.strip() for a in annotations.split(",") if a.strip()]
    elif not isinstance(annotations, list):
        annotations = []

    # Check annotations for layer indicators
    for annotation in annotations:
        if "Controller" in annotation or "RestController" in annotation:
            return "controller"
        elif "Service" in annotation:
            return "service"
        elif "Repository" in annotation:
            return "repository"

    # Default layer based on kind (for classes without explicit annotations)
    kind = symbol.get("kind", "")
    if kind == "class":
        return "domain"

    return None


def determine_layer_or_unknown(symbol: dict[str, Any]) -> str:
    """Determine architectural layer, returning 'unknown' instead of None.

    This is a compatibility wrapper for code that expects a string value.

    Args:
        symbol: Symbol dictionary from the knowledge graph

    Returns:
        Layer name ("controller", "service", "repository", "domain", or "unknown")
    """
    return determine_layer(symbol) or "unknown"


def is_controller(symbol: dict[str, Any]) -> bool:
    """Check if symbol is a controller layer component."""
    return determine_layer(symbol) == "controller"


def is_service(symbol: dict[str, Any]) -> bool:
    """Check if symbol is a service layer component."""
    return determine_layer(symbol) == "service"


def is_repository(symbol: dict[str, Any]) -> bool:
    """Check if symbol is a repository layer component."""
    return determine_layer(symbol) == "repository"


def get_layer_priority(layer: str | None) -> int:
    """Get priority for layer (for sorting/filtering).

    Lower number = higher priority (Controller > Service > Repository).

    Args:
        layer: Layer name

    Returns:
        Priority value (0-4, where 0 is highest priority)
    """
    priorities = {
        "controller": 0,
        "service": 1,
        "repository": 2,
        "domain": 3,
    }
    return priorities.get(layer, 4)
