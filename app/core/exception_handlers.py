import logging
from typing import Any

from fastapi import FastAPI, Request, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.core.exceptions import AppException

logger = logging.getLogger(__name__)


def _error_response(
    status_code: int,
    error: str,
    message: str,
    details: dict[str, Any] | None = None,
) -> JSONResponse:
    content: dict[str, Any] = {
        "success": False,
        "error": error,
        "message": message,
    }
    if details:
        content["details"] = details
    return JSONResponse(status_code=status_code, content=content)


async def app_exception_handler(_request: Request, exc: AppException) -> JSONResponse:
    """Handle all custom application exceptions."""
    return _error_response(
        status_code=exc.status_code,
        error=exc.error,
        message=exc.message,
        details=exc.details or None,
    )


async def http_exception_handler(_request: Request, exc: HTTPException) -> JSONResponse:
    """Handle FastAPI/Starlette HTTPException (e.g. 401 from OAuth2 scheme)."""
    return _error_response(
        status_code=exc.status_code,
        error="HTTP_ERROR",
        message=str(exc.detail) if exc.detail else "An HTTP error occurred",
    )


async def validation_exception_handler(_request: Request, exc: RequestValidationError) -> JSONResponse:
    """Handle Pydantic / request validation errors (422)."""
    errors = exc.errors()
    # Build a human-readable summary
    messages = []
    for err in errors:
        loc = " → ".join(str(part) for part in err.get("loc", []))
        messages.append(f"{loc}: {err.get('msg', '')}")
    return _error_response(
        status_code=422,
        error="VALIDATION_ERROR",
        message="Request validation failed",
        details={"errors": errors},
    )


async def generic_exception_handler(_request: Request, exc: Exception) -> JSONResponse:
    """Catch-all for unhandled exceptions – never leak internals."""
    logger.exception("Unhandled exception: %s", exc)
    return _error_response(
        status_code=500,
        error="INTERNAL_ERROR",
        message="An unexpected error occurred",
    )


def register_exception_handlers(app: FastAPI) -> None:
    """Register all exception handlers on the given FastAPI application."""
    app.add_exception_handler(AppException, app_exception_handler)  # type: ignore[arg-type]
    app.add_exception_handler(HTTPException, http_exception_handler)  # type: ignore[arg-type]
    app.add_exception_handler(RequestValidationError, validation_exception_handler)  # type: ignore[arg-type]
    app.add_exception_handler(Exception, generic_exception_handler)  # type: ignore[arg-type]
