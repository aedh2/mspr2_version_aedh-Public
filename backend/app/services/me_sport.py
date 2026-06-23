"""Détail séance, exercices d'une séance, KPIs et charts sport."""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from app.core.errors import ApiError
from app.db.models import Exercice, SeanceEntrainement, SeanceExercice
from app.modules.resources import media_url
from app.schemas.me import ChartParams


def _serialize_seance(s: SeanceEntrainement) -> dict[str, Any]:
    return {
        "seance_id": s.seance_id,
        "utilisateur_id": s.utilisateur_id,
        "date_seance": s.date_seance,
        "type_entrainement": s.type_entrainement,
        "duree_seance_min": s.duree_seance_min,
        "calories_brulees_total": s.calories_brulees_total,
        "frequence_entrainement_j_sem": s.frequence_entrainement_j_sem,
        "niveau_experience": s.niveau_experience,
        "eau_l": s.eau_l,
        "commentaire": getattr(s, "commentaire", None),
    }


def get_seance(db: Session, utilisateur_id: int, seance_id: int) -> dict[str, Any]:
    s = db.get(SeanceEntrainement, seance_id)
    if not s or s.utilisateur_id != utilisateur_id:
        raise ApiError(404, "not_found", "Seance introuvable.")
    return _serialize_seance(s)


def list_seance_exercices(db: Session, utilisateur_id: int, seance_id: int) -> list[dict[str, Any]]:
    # ownership check via la séance d'abord
    s = db.get(SeanceEntrainement, seance_id)
    if not s or s.utilisateur_id != utilisateur_id:
        raise ApiError(404, "not_found", "Seance introuvable.")

    rows = db.execute(
        select(SeanceExercice, Exercice)
        .join(Exercice, Exercice.exercice_id == SeanceExercice.exercice_id)
        .where(SeanceExercice.seance_id == seance_id)
        .order_by(
            case((SeanceExercice.ordre_exercice.is_(None), 1), else_=0).asc(),
            SeanceExercice.ordre_exercice.asc(),
            SeanceExercice.seance_exercice_id.asc(),
        )
    ).all()

    return [
        {
            "seance_exercice_id": se.seance_exercice_id,
            "ordre_exercice": se.ordre_exercice,
            "series_nb": se.series_nb,
            "repetitions_nb": se.repetitions_nb,
            "charge_kg": se.charge_kg,
            "duree_min": se.duree_min,
            "calories_brulees_estimees": se.calories_brulees_estimees,
            "commentaire": se.commentaire,
            "exercice": {
                "exercice_id": ex.exercice_id,
                "nom": ex.nom,
                "body_part_principale": ex.body_part_principale,
                "muscle_cible_principal": ex.muscle_cible_principal,
                "equipement_principal": ex.equipement_principal,
                "gif_180_path": ex.gif_180_path,
                "gif_360_path": ex.gif_360_path,
                "gif_720_path": ex.gif_720_path,
                "gif_1080_path": ex.gif_1080_path,
                "gif_180_url": media_url("exercises", ex.gif_180_path),
                "gif_360_url": media_url("exercises", ex.gif_360_path),
                "gif_720_url": media_url("exercises", ex.gif_720_path),
                "gif_1080_url": media_url("exercises", ex.gif_1080_path),
            },
        }
        for se, ex in rows
    ]


def seances_kpis(db: Session, utilisateur_id: int) -> dict[str, Any]:
    today = datetime.utcnow()
    seven_days_ago = today - timedelta(days=7)
    thirty_days_ago = today - timedelta(days=30)

    nb_total = db.scalar(
        select(func.count(SeanceEntrainement.seance_id)).where(
            SeanceEntrainement.utilisateur_id == utilisateur_id,
        )
    ) or 0
    nb_7j = db.scalar(
        select(func.count(SeanceEntrainement.seance_id)).where(
            SeanceEntrainement.utilisateur_id == utilisateur_id,
            SeanceEntrainement.date_seance >= seven_days_ago,
        )
    ) or 0
    nb_30j = db.scalar(
        select(func.count(SeanceEntrainement.seance_id)).where(
            SeanceEntrainement.utilisateur_id == utilisateur_id,
            SeanceEntrainement.date_seance >= thirty_days_ago,
        )
    ) or 0

    duree_moy = db.scalar(
        select(func.avg(SeanceEntrainement.duree_seance_min)).where(
            SeanceEntrainement.utilisateur_id == utilisateur_id,
            SeanceEntrainement.date_seance >= thirty_days_ago,
        )
    )
    calories_30j = db.scalar(
        select(func.coalesce(func.sum(SeanceEntrainement.calories_brulees_total), 0)).where(
            SeanceEntrainement.utilisateur_id == utilisateur_id,
            SeanceEntrainement.date_seance >= thirty_days_ago,
        )
    ) or 0

    top_types = db.execute(
        select(
            SeanceEntrainement.type_entrainement,
            func.count(SeanceEntrainement.seance_id).label("nb"),
        )
        .where(
            SeanceEntrainement.utilisateur_id == utilisateur_id,
            SeanceEntrainement.date_seance >= thirty_days_ago,
        )
        .group_by(SeanceEntrainement.type_entrainement)
        .order_by(func.count(SeanceEntrainement.seance_id).desc())
        .limit(5)
    ).all()

    return {
        "nb_total": int(nb_total),
        "nb_7j": int(nb_7j),
        "nb_30j": int(nb_30j),
        "duree_moy_min": float(duree_moy) if duree_moy is not None else None,
        "calories_brulees_30j": float(calories_30j),
        "top_types_30j": [
            {"type": t or "inconnu", "nb": int(n)} for t, n in top_types
        ],
    }


def _bucket_expr(column: Any, granularity: str) -> Any:
    if granularity == "week":
        return func.date_format(column, "%x-W%v")
    if granularity == "month":
        return func.date_format(column, "%Y-%m-01")
    return func.date_format(column, "%Y-%m-%d")


def seances_chart(db: Session, utilisateur_id: int, params: ChartParams) -> dict[str, Any]:
    """Retourne par bucket : nb séances, calories totales, durée totale."""
    bucket = _bucket_expr(SeanceEntrainement.date_seance, params.granularity).label("bucket")

    stmt = select(
        bucket,
        func.count(SeanceEntrainement.seance_id).label("nb"),
        func.coalesce(func.sum(SeanceEntrainement.calories_brulees_total), 0).label("calories"),
        func.coalesce(func.sum(SeanceEntrainement.duree_seance_min), 0).label("duree_min"),
    ).where(SeanceEntrainement.utilisateur_id == utilisateur_id)

    if params.date_from:
        stmt = stmt.where(SeanceEntrainement.date_seance >= datetime.combine(params.date_from, datetime.min.time()))
    if params.date_to:
        stmt = stmt.where(SeanceEntrainement.date_seance < datetime.combine(params.date_to + timedelta(days=1), datetime.min.time()))

    stmt = stmt.group_by("bucket").order_by("bucket")
    rows = db.execute(stmt).all()
    points = [
        {
            "bucket": str(r.bucket),
            "nb": int(r.nb),
            "calories": float(r.calories),
            "duree_min": float(r.duree_min),
        }
        for r in rows
    ]
    return {"granularity": params.granularity, "points": points}
