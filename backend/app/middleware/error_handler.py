"""
Structured error handling middleware for the Ethical AI Platform.

Provides:
- Consistent JSON error response format across all endpoints
- Structured error types for domain-specific errors
- Request-aware error context (request ID, timestamp, path)
"""

import time
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from fastapi import Request, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response

from app.config import settings


# ---------------------------------------------------------------------------
# Structured error response helper
# ---------------------------------------------------------------------------

def error_response(
    status_code: int,
    error: str,
    message: str,
    details: Optional[Any] = None,
    request_id: Optional[str] = None,
) -> JSONResponse:
    """
    Build a consistent JSON error response.

    Format:
        {
            "error": "ValidationError",
            "message": "Dataset not found",
            "details": {...},
            "timestamp": "2026-03-02T...",
            "request_id": "abc-123"
        }
    """
    body: Dict[str, Any] = {
        "error": error,
        "message": message,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    if details is not None:
        body["details"] = details
    if request_id:
        body["request_id"] = request_id
    return JSONResponse(status_code=status_code, content=body)


# ---------------------------------------------------------------------------
# Domain exception classes
# ---------------------------------------------------------------------------

class AppError(Exception):
    """Base application error with structured fields."""

    def __init__(
        self,
        message: str,
        status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR,
        error: str = "InternalError",
        details: Optional[Any] = None,
    ):
        self.message = message
        self.status_code = status_code
        self.error = error
        self.details = details
        super().__init__(message)


class NotFoundError(AppError):
    def __init__(self, resource: str, resource_id: Any = None):
        details = {"resource": resource}
        if resource_id is not None:
            details["id"] = str(resource_id)
        super().__init__(
            message=f"{resource} not found",
            status_code=status.HTTP_404_NOT_FOUND,
            error="NotFoundError",
            details=details,
        )


class AccessDeniedError(AppError):
    def __init__(self, message: str = "Access denied"):
        super().__init__(
            message=message,
            status_code=status.HTTP_403_FORBIDDEN,
            error="AccessDenied",
        )


class ValidationError(AppError):
    def __init__(self, message: str, details: Optional[Any] = None):
        super().__init__(
            message=message,
            status_code=status.HTTP_400_BAD_REQUEST,
            error="ValidationError",
            details=details,
        )


# ---------------------------------------------------------------------------
# Request-ID middleware
# ---------------------------------------------------------------------------

class RequestIdMiddleware(BaseHTTPMiddleware):
    """Attach a unique request-id to every request for tracing."""

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        request.state.request_id = request_id
        request.state.start_time = time.time()

        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id

        return response


# ---------------------------------------------------------------------------
# Exception handlers (registered on the FastAPI app)
# ---------------------------------------------------------------------------

async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    """Handle domain-specific AppError exceptions."""
    request_id = getattr(request.state, "request_id", None)
    return error_response(
        status_code=exc.status_code,
        error=exc.error,
        message=exc.message,
        details=exc.details,
        request_id=request_id,
    )


async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    """Handle Pydantic / FastAPI validation errors with structured format."""
    request_id = getattr(request.state, "request_id", None)
    errors = []
    for err in exc.errors():
        errors.append({
            "field": ".".join(str(loc) for loc in err["loc"]),
            "message": err["msg"],
            "type": err["type"],
        })
    return error_response(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        error="ValidationError",
        message="Request validation failed",
        details=errors,
        request_id=request_id,
    )


async def general_exception_handler(
    request: Request, exc: Exception
) -> JSONResponse:
    """Catch-all handler for unhandled exceptions."""
    import logging
    logger = logging.getLogger("ethical_ai.error")
    request_id = getattr(request.state, "request_id", None)
    logger.exception("Unhandled exception [request_id=%s]: %s", request_id, exc)

    detail = str(exc) if settings.debug else "An unexpected error occurred"
    return error_response(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        error="InternalError",
        message=detail,
        request_id=request_id,
    )
