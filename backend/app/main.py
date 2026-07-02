from __future__ import annotations

import json
import logging
import time
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.openapi.docs import get_redoc_html, get_swagger_ui_html
from fastapi.openapi.utils import get_openapi
from fastapi.responses import JSONResponse, Response

from app.core.config import get_settings
from app.core.errors import register_error_handlers
from app.core.logging import setup_logging
from app.core.middleware import RequestLogMiddleware
from app.core.rate_limit import install_rate_limiter
from app.db.demo_accounts import ensure_demo_accounts
from app.db.mongo import mongo_status
from app.db.session import get_session_factory
from app.modules.api import api_router

logger = logging.getLogger(__name__)

MEDIA_MOUNTS = {
    "/media/exercises": "exercisedb_v1_sample",
    "/media/organisations": "organisme",
    "/media/progression": "before after",
    "/media/avatars": "uploads/avatars",
}

try:
    from fastapi.middleware.cors import CORSMiddleware
except ImportError:  # pragma: no cover
    CORSMiddleware = None  # type: ignore[assignment]

try:  # Métriques Prometheus optionnelles (monitoring/supervision)
    from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest
except ImportError:  # pragma: no cover - l'app reste fonctionnelle sans la lib
    Counter = None  # type: ignore[assignment]

if Counter is not None:
    HTTP_REQUESTS = Counter(
        "http_requests_total", "Nombre total de requêtes HTTP", ["method", "handler", "status"]
    )
    HTTP_LATENCY = Histogram(
        "http_request_duration_seconds", "Latence des requêtes HTTP (s)", ["method", "handler"]
    )
else:  # pragma: no cover
    HTTP_REQUESTS = None
    HTTP_LATENCY = None


def create_app() -> FastAPI:
    settings = get_settings()
    setup_logging(level=settings.log_level, json_logs=settings.log_json)

    fastapi_app = FastAPI(
        title=settings.app_name,
        description="API REST francaise pour HealthAI Coaching.",
        version="0.1.0",
        openapi_url=None,  # Disable automatic OpenAPI schema generation
        docs_url=None,      # Disable automatic Swagger docs generation
        redoc_url=None,     # Disable automatic ReDoc generation
    )

    # Ordre conseillé : logging tout devant pour tracer même les erreurs CORS.
    fastapi_app.add_middleware(RequestLogMiddleware)
    if CORSMiddleware is not None:
        fastapi_app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.cors_origins,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    install_rate_limiter(fastapi_app)
    register_error_handlers(fastapi_app)

    media_root = Path(settings.media_root)
    if not media_root.is_absolute():
        for candidate in (Path.cwd() / media_root, Path.cwd().parent / media_root, Path("/app") / media_root):
            if candidate.exists():
                media_root = candidate
                break
    for mount_path, subdir in MEDIA_MOUNTS.items():
        target = media_root / subdir
        if mount_path == "/media/avatars":
            target.mkdir(parents=True, exist_ok=True)
        if target.exists() and target.is_dir():
            fastapi_app.mount(mount_path, StaticFiles(directory=str(target)), name=mount_path.strip("/"))
        else:
            logger.warning("Media directory missing for %s: %s", mount_path, target)

    fastapi_app.include_router(api_router, prefix=settings.api_prefix)

    @fastapi_app.get("/health", tags=["health"])
    def health() -> dict:
        return {
            "data": {
                "status": "ok",
                "databases": {
                    "relationnel": "mariadb",
                    "documentaire": mongo_status(),
                },
            }
        }

    @fastapi_app.on_event("startup")
    def ensure_local_demo_accounts() -> None:
        if settings.environment == "production":
            return
        try:
            with get_session_factory()() as db:
                ensure_demo_accounts(db)
        except Exception as exc:  # pragma: no cover - startup must still expose /health for diagnostics
            logger.warning("Unable to ensure demo accounts: %s", exc)

    # Manual OpenAPI endpoint that gracefully handles schema generation errors
    @fastapi_app.get(f"{settings.api_prefix}/openapi.json", include_in_schema=False)
    def get_openapi_schema():
        try:
            logger.info("Generating OpenAPI schema...")
            if fastapi_app.openapi_schema:
                logger.info("Using cached OpenAPI schema")
                return JSONResponse(fastapi_app.openapi_schema)

            logger.info("Building new OpenAPI schema from routes")
            openapi_schema = get_openapi(
                title=fastapi_app.title,
                version=fastapi_app.version,
                description=fastapi_app.description,
                routes=fastapi_app.routes,
            )
            fastapi_app.openapi_schema = openapi_schema
            logger.info("OpenAPI schema generated successfully")
            return JSONResponse(openapi_schema)
        except Exception as e:
            logger.error(f"OpenAPI schema generation failed: {type(e).__name__}: {str(e)[:200]}", exc_info=False)
            # Return minimal valid OpenAPI schema on error
            minimal_schema = {
                "openapi": "3.1.0",
                "info": {
                    "title": fastapi_app.title or "API",
                    "version": fastapi_app.version or "1.0.0",
                    "description": fastapi_app.description or "API Documentation",
                },
                "paths": {
                    "/health": {
                        "get": {
                            "summary": "Health Check",
                            "tags": ["health"],
                            "responses": {
                                "200": {
                                    "description": "OK",
                                }
                            },
                        }
                    },
                    f"{settings.api_prefix}/openapi.json": {
                        "get": {
                            "summary": "OpenAPI Schema",
                            "tags": ["openapi"],
                            "responses": {
                                "200": {
                                    "description": "OpenAPI schema (minimal due to schema generation error)",
                                }
                            },
                        }
                    }
                },
            }
            logger.warning("Returning minimal OpenAPI schema due to generation error")
            return JSONResponse(minimal_schema, status_code=200)

    # Manual Swagger UI page
    @fastapi_app.get(f"{settings.api_prefix}/docs", include_in_schema=False)
    def swagger_ui_page():
        return get_swagger_ui_html(
            openapi_url=f"{settings.api_prefix}/openapi.json",
            title=f"{fastapi_app.title} - Swagger UI",
        )

    @fastapi_app.get(f"{settings.api_prefix}/redoc", include_in_schema=False)
    def redoc_page():
        return get_redoc_html(
            openapi_url=f"{settings.api_prefix}/openapi.json",
            title=f"{fastapi_app.title} - ReDoc",
        )

    # Supervision : middleware de métriques + exposition sur /metrics (Prometheus).
    if HTTP_REQUESTS is not None:

        @fastapi_app.middleware("http")
        async def prometheus_metrics_middleware(request, call_next):
            start = time.perf_counter()
            response = await call_next(request)
            # Route déjà résolue : on prend son gabarit (faible cardinalité), sinon "unmatched".
            route = request.scope.get("route")
            handler = getattr(route, "path", "unmatched") if route is not None else "unmatched"
            status_group = f"{response.status_code // 100}xx"
            HTTP_REQUESTS.labels(request.method, handler, status_group).inc()
            HTTP_LATENCY.labels(request.method, handler).observe(time.perf_counter() - start)
            return response

        @fastapi_app.get("/metrics", include_in_schema=False)
        def metrics() -> Response:
            return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)

    return fastapi_app


app = create_app()
