"""Qualite admin : KPIs et charts (levels, decisions, top-rules, top-fields, by-source, by-lot, timeline)."""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.models import (
    ControleQualiteDonnee,
    LotDonnees,
    RegleQualite,
    SourceDonnees,
)


def _serialize_controle(c: ControleQualiteDonnee) -> dict[str, Any]:
    return {
        "controle_id": c.controle_id,
        "execution_id": c.execution_id,
        "lot_id": c.lot_id,
        "regle_id": c.regle_id,
        "entite": c.entite,
        "ref_externe": c.ref_externe,
        "ref_ligne": c.ref_ligne,
        "nom_champ": c.nom_champ,
        "valeur_observee": c.valeur_observee,
        "valeur_corrigee": c.valeur_corrigee,
        "niveau": c.niveau,
        "type_controle": c.type_controle,
        "decision_finale": c.decision_finale,
        "est_bloquant": c.est_bloquant,
        "code_controle": c.code_controle,
        "etape_pipeline": c.etape_pipeline,
        "description": c.description,
        "cree_le": c.cree_le,
    }


def _normalized_filters(filters: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(filters)
    for key in ("niveau", "decision_finale", "entite"):
        value = normalized.get(key)
        if isinstance(value, str):
            normalized[key] = value.strip()
    return normalized


def _apply_filters(stmt: Select[Any], filters: dict[str, Any]) -> Select[Any]:
    filters = _normalized_filters(filters)
    if filters.get("niveau"):
        stmt = stmt.where(func.upper(func.coalesce(ControleQualiteDonnee.niveau, "")) == filters["niveau"].upper())
    if filters.get("type_controle"):
        stmt = stmt.where(ControleQualiteDonnee.type_controle == filters["type_controle"])
    if filters.get("decision_finale"):
        stmt = stmt.where(
            func.upper(func.coalesce(ControleQualiteDonnee.decision_finale, "")) == filters["decision_finale"].upper()
        )
    if filters.get("entite"):
        stmt = stmt.where(func.lower(func.coalesce(ControleQualiteDonnee.entite, "")) == filters["entite"].lower())
    if filters.get("lot_id"):
        stmt = stmt.where(ControleQualiteDonnee.lot_id == filters["lot_id"])
    if filters.get("execution_id"):
        stmt = stmt.where(ControleQualiteDonnee.execution_id == filters["execution_id"])
    if filters.get("regle_id"):
        stmt = stmt.where(ControleQualiteDonnee.regle_id == filters["regle_id"])
    if filters.get("nom_champ"):
        stmt = stmt.where(ControleQualiteDonnee.nom_champ == filters["nom_champ"])
    if filters.get("etape_pipeline"):
        stmt = stmt.where(ControleQualiteDonnee.etape_pipeline == filters["etape_pipeline"])
    if filters.get("source_id"):
        stmt = stmt.join(LotDonnees, LotDonnees.lot_id == ControleQualiteDonnee.lot_id).where(
            LotDonnees.source_id == filters["source_id"]
        )
    if filters.get("date_from"):
        stmt = stmt.where(ControleQualiteDonnee.cree_le >= filters["date_from"])
    if filters.get("date_to"):
        stmt = stmt.where(ControleQualiteDonnee.cree_le < filters["date_to"])
    return stmt


def list_controles(
    db: Session, filters: dict[str, Any], page: int, page_size: int
) -> tuple[list[dict[str, Any]], int]:
    stmt = _apply_filters(select(ControleQualiteDonnee), filters)
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = db.execute(
        stmt.order_by(ControleQualiteDonnee.controle_id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).scalars().all()
    return [_serialize_controle(c) for c in rows], int(total)


def get_controle(db: Session, controle_id: int) -> dict[str, Any] | None:
    c = db.get(ControleQualiteDonnee, controle_id)
    if not c:
        return None
    return _serialize_controle(c)


def kpis(db: Session, filters: dict[str, Any]) -> dict[str, Any]:
    base = _apply_filters(select(ControleQualiteDonnee), filters)
    nb_total = db.scalar(select(func.count()).select_from(base.subquery())) or 0

    bloquants_stmt = _apply_filters(
        select(ControleQualiteDonnee).where(ControleQualiteDonnee.est_bloquant.is_(True)),
        filters,
    )
    nb_bloquants = db.scalar(select(func.count()).select_from(bloquants_stmt.subquery())) or 0

    rejets_stmt = _apply_filters(
        select(ControleQualiteDonnee).where(func.upper(func.coalesce(ControleQualiteDonnee.decision_finale, "")) == "REJET"),
        filters,
    )
    nb_rejets = db.scalar(select(func.count()).select_from(rejets_stmt.subquery())) or 0

    nb_entites_distinctes = db.scalar(
        select(func.count(func.distinct(ControleQualiteDonnee.entite))).select_from(base.subquery())
    ) or 0

    return {
        "nb_total": int(nb_total),
        "nb_bloquants": int(nb_bloquants),
        "nb_rejets": int(nb_rejets),
        "ratio_bloquants": (float(nb_bloquants) / float(nb_total)) if nb_total else 0.0,
        "ratio_rejets": (float(nb_rejets) / float(nb_total)) if nb_total else 0.0,
        "nb_entites_distinctes": int(nb_entites_distinctes),
    }


def filter_options(db: Session) -> dict[str, Any]:
    niveaux = [
        row[0]
        for row in db.execute(
            select(ControleQualiteDonnee.niveau)
            .where(ControleQualiteDonnee.niveau.is_not(None))
            .distinct()
            .order_by(func.upper(ControleQualiteDonnee.niveau))
        ).all()
        if row[0]
    ]
    decisions = [
        row[0]
        for row in db.execute(
            select(ControleQualiteDonnee.decision_finale)
            .where(ControleQualiteDonnee.decision_finale.is_not(None))
            .distinct()
            .order_by(func.upper(ControleQualiteDonnee.decision_finale))
        ).all()
        if row[0]
    ]
    entites = [
        row[0]
        for row in db.execute(
            select(ControleQualiteDonnee.entite)
            .where(ControleQualiteDonnee.entite.is_not(None))
            .distinct()
            .order_by(func.lower(ControleQualiteDonnee.entite))
        ).all()
        if row[0]
    ]
    sources = [
        {"id": row.source_id, "nom": row.nom}
        for row in db.execute(
            select(SourceDonnees.source_id, SourceDonnees.nom)
            .join(LotDonnees, LotDonnees.source_id == SourceDonnees.source_id)
            .join(ControleQualiteDonnee, ControleQualiteDonnee.lot_id == LotDonnees.lot_id)
            .distinct()
            .order_by(SourceDonnees.nom)
        ).all()
    ]
    lots = [
        {"id": row.lot_id, "nom": row.nom_lot}
        for row in db.execute(
            select(LotDonnees.lot_id, LotDonnees.nom_lot)
            .join(ControleQualiteDonnee, ControleQualiteDonnee.lot_id == LotDonnees.lot_id)
            .distinct()
            .order_by(LotDonnees.lot_id.desc())
            .limit(200)
        ).all()
    ]
    return {"niveaux": niveaux, "decisions": decisions, "entites": entites, "sources": sources, "lots": lots}


def _group_count(
    db: Session,
    column: Any,
    filters: dict[str, Any],
    *,
    label: str = "label",
    limit: int | None = None,
) -> list[dict[str, Any]]:
    stmt = _apply_filters(
        select(column.label(label), func.count(ControleQualiteDonnee.controle_id).label("nb")),
        filters,
    ).group_by(column).order_by(func.count(ControleQualiteDonnee.controle_id).desc())
    if limit:
        stmt = stmt.limit(limit)
    rows = db.execute(stmt).all()
    return [{label: getattr(r, label) or "inconnu", "nb": int(r.nb)} for r in rows]


def chart_levels(db: Session, filters: dict[str, Any]) -> list[dict[str, Any]]:
    return _group_count(db, ControleQualiteDonnee.niveau, filters, label="niveau")


def chart_decisions(db: Session, filters: dict[str, Any]) -> list[dict[str, Any]]:
    return _group_count(db, ControleQualiteDonnee.decision_finale, filters, label="decision_finale")


def chart_top_rules(db: Session, filters: dict[str, Any], limit: int = 10) -> list[dict[str, Any]]:
    stmt = _apply_filters(
        select(
            RegleQualite.regle_id,
            RegleQualite.code_regle,
            RegleQualite.severite,
            func.count(ControleQualiteDonnee.controle_id).label("nb"),
        ).join(RegleQualite, RegleQualite.regle_id == ControleQualiteDonnee.regle_id),
        filters,
    ).group_by(RegleQualite.regle_id, RegleQualite.code_regle, RegleQualite.severite)
    stmt = stmt.order_by(func.count(ControleQualiteDonnee.controle_id).desc()).limit(limit)
    rows = db.execute(stmt).all()
    return [
        {
            "regle_id": r.regle_id,
            "code_regle": r.code_regle,
            "severite": r.severite,
            "nb": int(r.nb),
        }
        for r in rows
    ]


def chart_top_fields(db: Session, filters: dict[str, Any], limit: int = 10) -> list[dict[str, Any]]:
    return _group_count(db, ControleQualiteDonnee.nom_champ, filters, label="nom_champ", limit=limit)


def chart_by_source(db: Session, filters: dict[str, Any]) -> list[dict[str, Any]]:
    stmt = _apply_filters(
        select(
            SourceDonnees.source_id,
            SourceDonnees.nom,
            func.count(ControleQualiteDonnee.controle_id).label("nb"),
        )
        .join(LotDonnees, LotDonnees.lot_id == ControleQualiteDonnee.lot_id)
        .join(SourceDonnees, SourceDonnees.source_id == LotDonnees.source_id),
        filters,
    ).group_by(SourceDonnees.source_id, SourceDonnees.nom).order_by(
        func.count(ControleQualiteDonnee.controle_id).desc()
    )
    rows = db.execute(stmt).all()
    return [{"source_id": r.source_id, "nom": r.nom, "nb": int(r.nb)} for r in rows]


def chart_by_lot(db: Session, filters: dict[str, Any], limit: int = 20) -> list[dict[str, Any]]:
    stmt = _apply_filters(
        select(
            LotDonnees.lot_id,
            LotDonnees.nom_lot,
            func.count(ControleQualiteDonnee.controle_id).label("nb"),
        ).join(LotDonnees, LotDonnees.lot_id == ControleQualiteDonnee.lot_id),
        filters,
    ).group_by(LotDonnees.lot_id, LotDonnees.nom_lot).order_by(
        func.count(ControleQualiteDonnee.controle_id).desc()
    ).limit(limit)
    rows = db.execute(stmt).all()
    return [{"lot_id": r.lot_id, "nom_lot": r.nom_lot, "nb": int(r.nb)} for r in rows]


def chart_timeline(db: Session, filters: dict[str, Any], granularity: str = "day") -> list[dict[str, Any]]:
    if granularity == "week":
        bucket = func.date_format(ControleQualiteDonnee.cree_le, "%x-W%v")
    elif granularity == "month":
        bucket = func.date_format(ControleQualiteDonnee.cree_le, "%Y-%m-01")
    else:
        bucket = func.date_format(ControleQualiteDonnee.cree_le, "%Y-%m-%d")
    stmt = _apply_filters(
        select(bucket.label("bucket"), func.count(ControleQualiteDonnee.controle_id).label("nb")),
        filters,
    ).group_by("bucket").order_by("bucket")
    rows = db.execute(stmt).all()
    points = [{"bucket": str(r.bucket), "nb": int(r.nb)} for r in rows]
    return _with_demo_timeline(points)


def _with_demo_timeline(points: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if get_settings().environment == "production" or len(points) != 1:
        return points
    anchor = datetime.strptime(points[0]["bucket"], "%Y-%m-%d")
    base = int(points[0]["nb"])
    demo_points: list[dict[str, Any]] = []
    for offset in range(6, -1, -1):
        demo_points.append(
            {
                "bucket": (anchor - timedelta(days=offset)).strftime("%Y-%m-%d"),
                "nb": max(1, base - ((6 - offset) % 3) - (0 if offset == 6 else 1)),
                "is_demo": True,
            }
        )
    return demo_points
