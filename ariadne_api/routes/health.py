"""Health check endpoint for Ariadne API."""

import logging
import os
from pathlib import Path

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from ariadne_api.schemas.common import HealthResponse

router = APIRouter()
logger = logging.getLogger(__name__)


class ServiceStatus(BaseModel):
    """Status of individual services."""

    database: str = "unknown"
    vector_db: str = "unknown"
    llm: str = "unknown"


def get_db_status(db_path: str) -> str:
    """Check database status."""
    path = Path(db_path)
    if not path.exists():
        return "missing"
    if not path.is_file():
        return "invalid"
    return "ok"


def get_vector_db_status() -> str:
    """Check vector database status (ChromaDB)."""
    try:
        from ariadne_core.storage.vector_store import ChromaVectorStore

        # Try to connect to the vector store
        # We'll just check if the module is available for now
        return "ok"
    except Exception as e:
        logger.debug(f"Vector DB check failed: {e}")
        return "unavailable"


def get_llm_status() -> str:
    """Check LLM service status."""
    try:
        from ariadne_llm import LLMConfig

        # Check if LLM config is available
        provider = os.environ.get("ARIADNE_LLM_PROVIDER", "")
        if provider:
            return "ok"
        return "not_configured"
    except Exception as e:
        logger.debug(f"LLM check failed: {e}")
        return "unavailable"


@router.get("/health", response_model=HealthResponse, tags=["health"])
async def health_check() -> HealthResponse:
    """Health check endpoint.

    Returns the status of all Ariadne services:
    - database: SQLite knowledge graph storage
    - vector_db: ChromaDB vector storage for semantic search
    - llm: LLM service for summarization and semantic analysis
    """
    db_path = os.environ.get("ARIADNE_DB_PATH", "ariadne.db")

    services = {
        "database": get_db_status(db_path),
        "vector_db": get_vector_db_status(),
        "llm": get_llm_status(),
    }

    # Determine overall status
    if all(s == "ok" for s in services.values()):
        overall_status = "healthy"
    elif any(s in ("missing", "unavailable") for s in services.values()):
        overall_status = "unhealthy"
    else:
        overall_status = "degraded"

    return HealthResponse(status=overall_status, services=services)
