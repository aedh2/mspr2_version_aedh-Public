"""Détail plat (avec lignes), charts nutrition."""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.errors import ApiError
from app.db.models import Aliment, JournalAlimentaire, Plat
from app.schemas.me import ChartParams


def _serialize_plat(p: Plat) -> dict[str, Any]:
    return {
        "plat_id": p.plat_id,
        "utilisateur_id": p.utilisateur_id,
        "consomme_le": p.consomme_le,
        "type_repas": p.type_repas,
        "nom_plat": p.nom_plat,
        "calories_totales_kcal": p.calories_totales_kcal,
    }


def compute_line_from_aliment(
    aliment: Aliment | None,
    *,
    quantite: float | None,
    unite_quantite: str | None,
) -> dict[str, float | None]:
    if aliment is None:
        return {"calories_kcal": None, "eau_ml": None}

    quantity = float(quantite or 0)
    unit = (unite_quantite or "").strip().lower()
    factor = 1.0
    if quantity > 0:
        if unit in {"g", "gramme", "grammes", "ml"}:
            factor = quantity / 100.0
        elif unit in {"kg", "kilogramme", "kilogrammes", "l"}:
            factor = quantity * 10.0
        elif unit in {"portion", "piece", "pieces", "unit", "unite", "unites"}:
            factor = quantity
        else:
            factor = quantity / 100.0 if quantity > 5 else quantity

    return {
        "calories_kcal": round(float(aliment.calories_kcal or 0) * factor, 2),
        "eau_ml": None,
    }


def get_plat(db: Session, utilisateur_id: int, plat_id: int) -> dict[str, Any]:
    p = db.get(Plat, plat_id)
    if not p or p.utilisateur_id != utilisateur_id:
        raise ApiError(404, "not_found", "Plat introuvable.")

    # Cohérence : somme des lignes vs calories_totales_kcal — warning soft.
    somme_lignes = db.scalar(
        select(func.coalesce(func.sum(JournalAlimentaire.calories_kcal), 0)).where(
            JournalAlimentaire.plat_id == plat_id,
        )
    ) or 0

    payload = _serialize_plat(p)
    payload["somme_lignes_kcal"] = float(somme_lignes)
    payload["coherence_calories"] = (
        p.calories_totales_kcal is None
        or abs(float(p.calories_totales_kcal) - float(somme_lignes)) < 1.0
    )
    return payload


def list_plat_lignes(db: Session, utilisateur_id: int, plat_id: int) -> list[dict[str, Any]]:
    p = db.get(Plat, plat_id)
    if not p or p.utilisateur_id != utilisateur_id:
        raise ApiError(404, "not_found", "Plat introuvable.")

    rows = db.execute(
        select(JournalAlimentaire, Aliment)
        .join(Aliment, Aliment.aliment_id == JournalAlimentaire.aliment_id, isouter=True)
        .where(JournalAlimentaire.plat_id == plat_id)
        .order_by(JournalAlimentaire.journal_id.asc())
    ).all()

    return [
        {
            "journal_id": j.journal_id,
            "consomme_le": j.consomme_le,
            "type_repas": j.type_repas,
            "aliment_nom_libre": j.aliment_nom_libre,
            "quantite": j.quantite,
            "unite_quantite": j.unite_quantite,
            "calories_kcal": j.calories_kcal,
            "eau_ml": j.eau_ml,
            "aliment": (
                {
                    "aliment_id": a.aliment_id,
                    "nom": a.nom,
                    "categorie": a.categorie,
                    "calories_kcal": a.calories_kcal,
                    "proteines_g": a.proteines_g,
                    "glucides_g": a.glucides_g,
                    "lipides_g": a.lipides_g,
                }
                if a is not None
                else None
            ),
        }
        for j, a in rows
    ]


def _bucket_expr(column: Any, granularity: str) -> Any:
    if granularity == "week":
        return func.date_format(column, "%x-W%v")
    if granularity == "month":
        return func.date_format(column, "%Y-%m-01")
    return func.date_format(column, "%Y-%m-%d")


def calories_par_jour(db: Session, utilisateur_id: int, params: ChartParams) -> list[dict[str, Any]]:
    bucket = _bucket_expr(JournalAlimentaire.consomme_le, params.granularity).label("bucket")
    stmt = select(
        bucket,
        func.coalesce(func.sum(JournalAlimentaire.calories_kcal), 0).label("calories"),
        func.count(JournalAlimentaire.journal_id).label("nb_lignes"),
    ).where(JournalAlimentaire.utilisateur_id == utilisateur_id)

    if params.date_from:
        stmt = stmt.where(JournalAlimentaire.consomme_le >= datetime.combine(params.date_from, datetime.min.time()))
    if params.date_to:
        stmt = stmt.where(JournalAlimentaire.consomme_le < datetime.combine(params.date_to + timedelta(days=1), datetime.min.time()))

    stmt = stmt.group_by("bucket").order_by("bucket")
    rows = db.execute(stmt).all()
    return [
        {"bucket": str(r.bucket), "calories": float(r.calories), "nb_lignes": int(r.nb_lignes)}
        for r in rows
    ]


def top_aliments(db: Session, utilisateur_id: int, limit: int = 10) -> list[dict[str, Any]]:
    rows = db.execute(
        select(
            Aliment.aliment_id,
            Aliment.nom,
            func.count(JournalAlimentaire.journal_id).label("nb"),
            func.coalesce(func.sum(JournalAlimentaire.calories_kcal), 0).label("calories"),
        )
        .join(Aliment, Aliment.aliment_id == JournalAlimentaire.aliment_id)
        .where(JournalAlimentaire.utilisateur_id == utilisateur_id)
        .group_by(Aliment.aliment_id, Aliment.nom)
        .order_by(func.count(JournalAlimentaire.journal_id).desc())
        .limit(limit)
    ).all()
    return [
        {"aliment_id": r.aliment_id, "nom": r.nom, "nb": int(r.nb), "calories": float(r.calories)}
        for r in rows
    ]


def repartition_repas(db: Session, utilisateur_id: int) -> list[dict[str, Any]]:
    rows = db.execute(
        select(
            JournalAlimentaire.type_repas,
            func.count(JournalAlimentaire.journal_id).label("nb"),
            func.coalesce(func.sum(JournalAlimentaire.calories_kcal), 0).label("calories"),
        )
        .where(JournalAlimentaire.utilisateur_id == utilisateur_id)
        .group_by(JournalAlimentaire.type_repas)
        .order_by(func.count(JournalAlimentaire.journal_id).desc())
    ).all()
    return [
        {"type_repas": r.type_repas or "inconnu", "nb": int(r.nb), "calories": float(r.calories)}
        for r in rows
    ]


def nutrition_charts(db: Session, utilisateur_id: int, params: ChartParams) -> dict[str, Any]:
    return {
        "granularity": params.granularity,
        "calories_par_bucket": calories_par_jour(db, utilisateur_id, params),
        "top_aliments": top_aliments(db, utilisateur_id, limit=10),
        "repartition_repas": repartition_repas(db, utilisateur_id),
    }
