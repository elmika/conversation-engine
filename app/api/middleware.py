"""Request ID and timing middleware."""

import logging
import time
import uuid
from typing import Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

logger = logging.getLogger(__name__)


def get_request_id(request: Request) -> str:
    """Use X-Request-Id header if present, otherwise generate UUID."""
    header = request.headers.get("X-Request-Id")
    return header.strip() if header else str(uuid.uuid4())


class RequestIdAndTimingMiddleware(BaseHTTPMiddleware):
    """Set request_id on state and log request with latency and status."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        request_id = get_request_id(request)
        request.state.request_id = request_id
        start = time.perf_counter()
        endpoint = f"{request.method} {request.url.path}"
        try:
            response = await call_next(request)
        except Exception as exc:
            latency_ms = round((time.perf_counter() - start) * 1000)
            logger.exception(
                "request failed",
                extra={
                    "request_id": request_id,
                    "endpoint": endpoint,
                    "latency_ms": latency_ms,
                    "error": str(exc),
                },
            )
            raise
        latency_ms = round((time.perf_counter() - start) * 1000)
        logger.info(
            "request",
            extra={
                "request_id": request_id,
                "endpoint": endpoint,
                "status_code": response.status_code,
                "latency_ms": latency_ms,
            },
        )
        return response
