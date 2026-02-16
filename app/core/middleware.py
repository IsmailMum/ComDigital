"""
HTTP request / response logging middleware.

Logs every incoming request and its outcome (status code, duration).
"""

import logging
import time
import uuid

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

logger = logging.getLogger("app.access")


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Log each HTTP request with method, path, status code and duration."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        request_id = str(uuid.uuid4())[:8]
        client_ip = request.client.host if request.client else "unknown"
        method = request.method
        path = request.url.path
        query = str(request.url.query) if request.url.query else ""

        start_time = time.perf_counter()

        # Log the incoming request
        logger.info(
            "Request started: %s %s%s",
            method,
            path,
            f"?{query}" if query else "",
            extra={
                "request_id": request_id,
                "method": method,
                "path": path,
                "client_ip": client_ip,
            },
        )

        try:
            response = await call_next(request)
        except Exception:
            duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
            logger.exception(
                "Request failed: %s %s — unhandled exception after %.2fms",
                method,
                path,
                duration_ms,
                extra={
                    "request_id": request_id,
                    "method": method,
                    "path": path,
                    "duration_ms": duration_ms,
                    "client_ip": client_ip,
                },
            )
            raise

        duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
        status_code = response.status_code

        # Choose the right log level based on status code
        if status_code >= 500:
            log_fn = logger.error
        elif status_code >= 400:
            log_fn = logger.warning
        else:
            log_fn = logger.info

        log_fn(
            "Request completed: %s %s — %d in %.2fms",
            method,
            path,
            status_code,
            duration_ms,
            extra={
                "request_id": request_id,
                "method": method,
                "path": path,
                "status_code": status_code,
                "duration_ms": duration_ms,
                "client_ip": client_ip,
            },
        )

        # Propagate request_id to the response headers for traceability
        response.headers["X-Request-ID"] = request_id
        return response
