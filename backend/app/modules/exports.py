"""Endpoints d'export CSV (admin)."""
from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.core.errors import ApiError
from app.core.security import require_roles
from app.db.models import Utilisateur
from app.db.session import get_db
from app.services import exports as exports_service

router = APIRouter(prefix="/admin/exports", tags=["admin-exports"])


def _stream(name: str, generator) -> StreamingResponse:
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    filename = f"{name}_{timestamp}.csv"
    return StreamingResponse(
        generator,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/{dataset}")
def admin_export(
    dataset: str,
    db: Session = Depends(get_db),
    _: Utilisateur = Depends(require_roles("ADMIN", "SUPER_ADMIN")),
) -> StreamingResponse:
    exporter = exports_service.EXPORTERS.get(dataset)
    if exporter is None:
        raise ApiError(
            404,
            "not_found",
            f"Dataset inconnu. Disponibles: {', '.join(sorted(exports_service.EXPORTERS))}.",
        )
    return _stream(dataset, exporter(db))
