"""Rate limiting basé sur slowapi.

Si slowapi n'est pas installé (env de dev minimal), on expose un `limiter` no-op
pour ne pas casser les imports — la décoration devient inerte mais le code tourne.
"""
from __future__ import annotations

from typing import Any, Callable

from fastapi import FastAPI

try:
    from slowapi import Limiter, _rate_limit_exceeded_handler
    from slowapi.errors import RateLimitExceeded
    from slowapi.middleware import SlowAPIMiddleware
    from slowapi.util import get_remote_address

    _SLOWAPI_AVAILABLE = True
except ImportError:  # pragma: no cover
    _SLOWAPI_AVAILABLE = False
    Limiter = None  # type: ignore[assignment]
    RateLimitExceeded = None  # type: ignore[assignment]
    SlowAPIMiddleware = None  # type: ignore[assignment]
    _rate_limit_exceeded_handler = None  # type: ignore[assignment]
    get_remote_address = None  # type: ignore[assignment]


class _NoopLimiter:
    """Substitut neutre quand slowapi n'est pas dispo : `@limiter.limit(...)` devient l'identité."""

    def limit(self, _expr: str, **_kwargs: Any) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
        def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
            return func

        return decorator


if _SLOWAPI_AVAILABLE:
    limiter = Limiter(key_func=get_remote_address, default_limits=[])
else:
    limiter = _NoopLimiter()  # type: ignore[assignment]


def install_rate_limiter(app: FastAPI) -> None:
    if not _SLOWAPI_AVAILABLE:
        return
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    app.add_middleware(SlowAPIMiddleware)
