"""FastAPI application for Ariadne Code Knowledge Graph."""

import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, AsyncGenerator

from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware

from ariadne_api.middleware import RequestContextMiddleware, TracingMiddleware, setup_logging
from ariadne_api.rate_limiter import RateLimitConfig, RateLimitMiddleware, get_rate_limiter
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

# API versioning configuration
API_VERSION = os.environ.get("ARIADNE_API_VERSION", "v1")

# Rate limiting configuration
# Can be overridden via environment variables
RATE_LIMIT_PER_MINUTE = int(os.environ.get("ARIADNE_RATE_LIMIT_MINUTE", "60"))
RATE_LIMIT_PER_HOUR = int(os.environ.get("ARIADNE_RATE_LIMIT_HOUR", "1000"))
RATE_LIMIT_BURST = int(os.environ.get("ARIADNE_RATE_LIMIT_BURST", "10"))

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

# Rate limiting middleware (before request context middleware)
rate_limit_config = RateLimitConfig(
    requests_per_minute=RATE_LIMIT_PER_MINUTE,
    requests_per_hour=RATE_LIMIT_PER_HOUR,
    burst_limit=RATE_LIMIT_BURST,
)
app.add_middleware(RateLimitMiddleware, config=rate_limit_config)

# Request context middleware
app.add_middleware(RequestContextMiddleware)

# Distributed tracing middleware
app.add_middleware(TracingMiddleware, service_name="ariadne-api")

# Include routers with API versioning
# Health check endpoint is unversioned (always available)
app.include_router(health_router, tags=["health"])

# Versioned API endpoints
app.include_router(search_router, prefix=f"/api/{API_VERSION}", tags=["search"])
app.include_router(graph_router, prefix=f"/api/{API_VERSION}", tags=["graph"])
app.include_router(symbol_router, prefix=f"/api/{API_VERSION}", tags=["symbol"])
app.include_router(impact_router, prefix=f"/api/{API_VERSION}", tags=["impact"])
app.include_router(rebuild_router, prefix=f"/api/{API_VERSION}", tags=["rebuild"])
app.include_router(jobs_router, prefix=f"/api/{API_VERSION}", tags=["jobs"])
app.include_router(constraints_router, prefix=f"/api/{API_VERSION}", tags=["constraints"])
app.include_router(check_router, prefix=f"/api/{API_VERSION}", tags=["check"])

# Legacy unversioned endpoints for backward compatibility (deprecated)
# TODO: Add deprecation warning headers
_app_include_legacy = os.environ.get("ARIADNE_LEGACY_ENDPOINTS", "true").lower() == "true"
if _app_include_legacy:
    app.include_router(search_router, tags=["search (deprecated)"])
    app.include_router(graph_router, tags=["graph (deprecated)"])
    app.include_router(symbol_router, tags=["symbol (deprecated)"])
    app.include_router(impact_router, tags=["impact (deprecated)"])
    app.include_router(rebuild_router, tags=["rebuild (deprecated)"])
    app.include_router(jobs_router, tags=["jobs (deprecated)"])
    app.include_router(constraints_router, tags=["constraints (deprecated)"])
    app.include_router(check_router, tags=["check (deprecated)"])


@app.get("/", tags=["root"])
async def root() -> dict[str, Any]:
    """Root endpoint with API information."""
    return {
        "name": "Ariadne API",
        "version": "0.4.0",
        "description": "AI-powered codebase intelligence for architect agents",
        "docs": "/docs",
        "api_version": API_VERSION,
        "endpoints": {
            "current": f"/api/{API_VERSION}",
            "health": "/health",
        },
    }


@app.get(f"/api/{API_VERSION}", tags=["root"])
async def api_root() -> dict[str, str]:
    """API v1 root endpoint."""
    return {
        "name": "Ariadne API",
        "version": API_VERSION,
        "description": f"API version {API_VERSION} endpoints",
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
