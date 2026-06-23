from __future__ import annotations

import time
import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.core.logging import bind_context


class RequestLogMiddleware(BaseHTTPMiddleware):
    """Attache un request_id et émet une ligne de log par requête HTTP."""

    async def dispatch(self, request: Request, call_next) -> Response:
        request_id = request.headers.get("x-request-id") or uuid.uuid4().hex[:12]
        request.state.request_id = request_id
        log = bind_context(request_id=request_id)

        start = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            duration_ms = (time.perf_counter() - start) * 1000
            log.exception(
                "request_failed method={} path={} duration_ms={:.1f}",
                request.method,
                request.url.path,
                duration_ms,
            )
            raise

        duration_ms = (time.perf_counter() - start) * 1000
        response.headers["x-request-id"] = request_id
        log.info(
            "{} {} -> {} ({:.1f} ms)",
            request.method,
            request.url.path,
            response.status_code,
            duration_ms,
        )
        return response
