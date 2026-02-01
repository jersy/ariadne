"""Middleware for Ariadne API - error handling, logging, and request tracking."""

import logging
import uuid
from typing import Any, Callable

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from ariadne_api.schemas.common import ErrorResponse

logger = logging.getLogger(__name__)


class RequestContextMiddleware(BaseHTTPMiddleware):
    """Add request ID and structured logging to all requests."""

    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)
        self.logger = logging.getLogger("ariadne.api")

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Generate request ID
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        request.state.request_id = request_id

        # Log request
        self.logger.info(
            "request_start",
            extra={
                "request_id": request_id,
                "method": request.method,
                "url": str(request.url),
                "client": request.client.host if request.client else None,
            },
        )

        # Process request
        try:
            response = await call_next(request)
            response.headers["X-Request-ID"] = request_id

            # Log response
            self.logger.info(
                "request_complete",
                extra={
                    "request_id": request_id,
                    "status_code": response.status_code,
                },
            )

            return response

        except Exception as e:
            self.logger.exception(
                "request_error",
                extra={
                    "request_id": request_id,
                    "error": str(e),
                },
            )
            raise


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
                "uvicorn": {"level": "WARNING"},
                "uvicorn.access": {"level": "WARNING"},
            },
        }

    logging.config.dictConfig(logging_config)
