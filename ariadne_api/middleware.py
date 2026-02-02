"""Middleware for Ariadne API - error handling, logging, and request tracking."""

import logging
import time
import uuid
from typing import Any, Callable

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from ariadne_api.schemas.common import ErrorResponse

logger = logging.getLogger(__name__)


class RequestContextMiddleware(BaseHTTPMiddleware):
    """Add request ID and structured logging to all requests.

    Provides distributed tracing capabilities with:
    - Correlation/request ID for tracking across services
    - Request timing for performance monitoring
    - Structured logging with context for observability
    """

    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)
        self.logger = logging.getLogger("ariadne.api")

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Generate/request ID - support external correlation IDs
        request_id = (
            request.headers.get("X-Request-ID") or
            request.headers.get("X-Correlation-ID") or
            str(uuid.uuid4())
        )
        request.state.request_id = request_id

        # Get client info
        client_host = request.client.host if request.client else None
        user_agent = request.headers.get("user-agent", "unknown")

        # Start timing
        start_time = time.time()

        # Extract additional context
        path_params = dict(request.path_params)
        query_params = dict(request.query_params)

        # Log request with enhanced context
        self.logger.info(
            "request_start",
            extra={
                "request_id": request_id,
                "method": request.method,
                "url": str(request.url),
                "path": request.url.path,
                "client": client_host,
                "user_agent": user_agent,
                "path_params": path_params if path_params else None,
                "query_params": query_params if query_params else None,
            },
        )

        # Track metrics
        from ariadne_api.metrics import get_metrics_collector
        metrics_collector = get_metrics_collector()
        metrics_collector.increment_active_requests()

        # Process request
        try:
            response = await call_next(request)
            response.headers["X-Request-ID"] = request_id

            # Calculate duration
            duration_ms = (time.time() - start_time) * 1000

            # Record metrics
            metrics_collector.record_request(
                method=request.method,
                path=request.url.path,
                duration_ms=duration_ms,
                status_code=response.status_code,
            )

            # Log response with timing
            self.logger.info(
                "request_complete",
                extra={
                    "request_id": request_id,
                    "method": request.method,
                    "path": request.url.path,
                    "status_code": response.status_code,
                    "duration_ms": f"{duration_ms:.2f}",
                    "client": client_host,
                },
            )

            # Add timing header for debugging
            response.headers["X-Process-Time-ms"] = f"{duration_ms:.2f}"

            return response

        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000

            # Record error metrics
            metrics_collector.record_request(
                method=request.method,
                path=request.url.path,
                duration_ms=duration_ms,
                status_code=500,
            )

            self.logger.exception(
                "request_error",
                extra={
                    "request_id": request_id,
                    "method": request.method,
                    "path": request.url.path,
                    "client": client_host,
                    "error": str(e),
                    "duration_ms": f"{duration_ms:.2f}",
                    "error_type": type(e).__name__,
                },
            )
            raise
        finally:
            metrics_collector.decrement_active_requests()


class TracingMiddleware(BaseHTTPMiddleware):
    """Middleware for distributed tracing support.

    Adds W3C trace context headers for integration with tracing systems.
    """

    def __init__(self, app: ASGIApp, service_name: str = "ariadne-api") -> None:
        super().__init__(app)
        self.service_name = service_name

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Extract traceparent header (W3C Trace Context)
        traceparent = request.headers.get("traceparent")
        tracestate = request.headers.get("tracestate")

        # Generate new trace ID if not provided
        if not traceparent:
            trace_id = uuid.uuid4().hex[:16]
            span_id = uuid.uuid4().hex[:8]
            traceparent = f"00-{trace_id}-{span_id}-01"

        # Pass through trace headers
        response = await call_next(request)

        # Add trace context to response for debugging
        if traceparent:
            response.headers["X-Trace-Id"] = traceparent.split("-")[1] if len(traceparent.split("-")) > 1 else traceparent

        return response


def create_error_response(
    status_code: int,
    title: str,
    detail: str | None = None,
    request_id: str | None = None,
) -> JSONResponse:
    """Create RFC 7807 Problem Details error response."""
    error = ErrorResponse(
        type=f"https://httpstatuses.com/{status_code}",
        title=title,
        status=status_code,
        detail=detail,
        instance=request_id,
    )
    return JSONResponse(
        status_code=status_code,
        content=error.model_dump(exclude_none=True),
        headers={"X-Request-ID": request_id} if request_id else {},
    )


def setup_logging(level: str = "INFO", json_format: bool = True) -> None:
    """Configure structured logging for the API.

    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR)
        json_format: If True, output JSON logs; otherwise plain text
    """
    import logging.config
    import sys

    log_level = getattr(logging, level.upper(), logging.INFO)

    if json_format:
        # JSON structured logging
        logging_config: dict[str, Any] = {
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {
                "json": {
                    "()": "pythonjsonlogger.jsonlogger.JsonFormatter",
                    "format": "%(asctime)s %(name)s %(levelname)s %(message)s",
                },
            },
            "handlers": {
                "console": {
                    "class": "logging.StreamHandler",
                    "formatter": "json",
                    "stream": sys.stdout,
                },
            },
            "root": {
                "level": log_level,
                "handlers": ["console"],
            },
            "loggers": {
                "ariadne": {"level": log_level},
                "ariadne_api": {"level": log_level},
                "ariadne_core": {"level": log_level},
                "ariadne_analyzer": {"level": log_level},
                "uvicorn": {"level": "WARNING"},
                "uvicorn.access": {"level": "WARNING"},
            },
        }
    else:
        # Plain text logging
        logging_config = {
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {
                "standard": {
                    "format": "%(asctime)s [%(levelname)8s] %(name)s: %(message)s",
                    "datefmt": "%Y-%m-%d %H:%M:%S",
                },
            },
            "handlers": {
                "console": {
                    "class": "logging.StreamHandler",
                    "formatter": "standard",
                    "stream": sys.stdout,
                },
            },
            "root": {
                "level": log_level,
                "handlers": ["console"],
            },
            "loggers": {
                "ariadne": {"level": log_level},
                "ariadne_api": {"level": log_level},
                "ariadne_core": {"level": log_level},
                "ariadne_analyzer": {"level": log_level},
                "uvicorn": {"level": "WARNING"},
                "uvicorn.access": {"level": "WARNING"},
            },
        }

    logging.config.dictConfig(logging_config)
