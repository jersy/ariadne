"""FastAPI application for Ariadne Code Knowledge Graph."""

import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, AsyncGenerator

from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware

from ariadne_api.middleware import RequestContextMiddleware, setup_logging
from ariadne_api.routes.check import router as check_router
from ariadne_api.routes.constraints import router as constraints_router
from ariadne_api.routes.graph import router as graph_router
from ariadne_api.routes.health import router as health_router
from ariadne_api.routes.impact import router as impact_router
from ariadne_api.routes.jobs import router as jobs_router
from ariadne_api.routes.rebuild import router as rebuild_router
from ariadne_api.routes.search import router as search_router
from ariadne_api.routes.symbol import router as symbol_router
from ariadne_api.schemas.common import HealthResponse

# Get configuration from environment
ARIADNE_DB_PATH = os.environ.get("ARIADNE_DB_PATH", "ariadne.db")
ARIADNE_LOG_LEVEL = os.environ.get("ARIADNE_LOG_LEVEL", "INFO")
ARIADNE_LOG_FORMAT = os.environ.get("ARIADNE_LOG_FORMAT", "json") == "json"

# Set up logging
setup_logging(level=ARIADNE_LOG_LEVEL, json_format=ARIADNE_LOG_FORMAT)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan events.

    Initializes database connection and validates services on startup.
    """
    logger.info("Starting Ariadne API server")

    # Validate database path
    db_path = Path(ARIADNE_DB_PATH)
    if not db_path.exists():
        logger.warning(f"Database not found: {ARIADNE_DB_PATH}")

    # Additional service checks will be added as we implement more features
    logger.info(f"Using database: {ARIADNE_DB_PATH}")

    yield

    logger.info("Shutting down Ariadne API server")


# Create FastAPI application
app = FastAPI(
    title="Ariadne Code Knowledge Graph",
    description="AI-powered codebase intelligence for architect agents",
    version="0.4.0",
    lifespan=lifespan,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Request context middleware
app.add_middleware(RequestContextMiddleware)

# Include routers
app.include_router(health_router, tags=["health"])
app.include_router(search_router, tags=["search"])
app.include_router(graph_router, tags=["graph"])
app.include_router(symbol_router, tags=["symbol"])
app.include_router(impact_router, tags=["impact"])
app.include_router(rebuild_router, tags=["rebuild"])
app.include_router(jobs_router, tags=["jobs"])
app.include_router(constraints_router, tags=["constraints"])
app.include_router(check_router, tags=["check"])


@app.get("/", tags=["root"])
async def root() -> dict[str, str]:
    """Root endpoint with API information."""
    return {
        "name": "Ariadne API",
        "version": "0.4.0",
        "description": "AI-powered codebase intelligence for architect agents",
        "docs": "/docs",
    }


# Global exception handler
@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc: HTTPException) -> dict[str, Any]:
    """Handle HTTP exceptions with structured error responses."""
    from ariadne_api.middleware import create_error_response

    request_id = getattr(request.state, "request_id", None)
    return create_error_response(
        status_code=exc.status_code,
        title=exc.detail or "HTTP Error",
        detail=exc.detail,
        request_id=request_id,
    )


@app.exception_handler(Exception)
async def general_exception_handler(request, exc: Exception) -> dict[str, Any]:
    """Handle uncaught exceptions."""
    from ariadne_api.middleware import create_error_response

    logger.exception(f"Unhandled exception: {exc}")
    request_id = getattr(request.state, "request_id", None)
    return create_error_response(
        status_code=500,
        title="Internal Server Error",
        detail=str(exc) if os.environ.get("ARIADNE_DEBUG") else "An unexpected error occurred",
        request_id=request_id,
    )


def run_server(host: str = "0.0.0.0", port: int = 8080) -> None:
    """Run the FastAPI server with uvicorn.

    Args:
        host: Server host
        port: Server port
    """
    import uvicorn

    uvicorn.run(
        "ariadne_api.app:app",
        host=host,
        port=port,
        reload=os.environ.get("ARIADNE_RELOAD", "false").lower() == "true",
        log_config=None,  # Use our own logging configuration
    )


if __name__ == "__main__":
    run_server()
