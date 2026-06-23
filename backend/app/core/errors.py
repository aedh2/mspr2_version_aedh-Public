from __future__ import annotations

from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError
from starlette.exceptions import HTTPException as StarletteHTTPException


class ApiError(Exception):
    def __init__(self, status_code: int, code: str, message: str, details: Any = None) -> None:
        self.status_code = status_code
        self.code = code
        self.message = message
        self.details = details


def error_payload(code: str, message: str, details: Any = None) -> dict[str, Any]:
    return {"error": {"code": code, "message": message, "details": details}}


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(ApiError)
    async def api_error_handler(_: Request, exc: ApiError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content=error_payload(exc.code, exc.message, exc.details),
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(_: Request, exc: RequestValidationError) -> JSONResponse:
        errs = exc.errors()
        message = "La requete est invalide."
        if errs:
            first = errs[0]
            loc = [str(part) for part in first.get("loc", []) if part not in ("body", "query", "path")]
            field = ".".join(loc) if loc else "?"
            reason = first.get("msg", "invalide")
            message = f"Champ '{field}' : {reason}."
        return JSONResponse(
            status_code=422,
            content=error_payload("validation_error", message, errs),
        )

    @app.exception_handler(StarletteHTTPException)
    async def http_error_handler(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        code_by_status = {401: "unauthorized", 403: "forbidden", 404: "not_found", 409: "conflict"}
        message = exc.detail if isinstance(exc.detail, str) else "Erreur HTTP."
        return JSONResponse(
            status_code=exc.status_code,
            content=error_payload(code_by_status.get(exc.status_code, "http_error"), message),
            headers=getattr(exc, "headers", None),
        )

    @app.exception_handler(IntegrityError)
    async def integrity_error_handler(_: Request, exc: IntegrityError) -> JSONResponse:
        return JSONResponse(
            status_code=409,
            content=error_payload("conflict", "La contrainte de donnees est violee.", str(exc.orig)),
        )
