"""Charts complementaires des dashboards admin et super-admin."""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.models import (
    ControleQualiteDonnee,
    ExecutionEtl,
    LotDonnees,
    Organisation,
    RegleQualite,
    SourceDonnees,
    Utilisateur,
)


def quality_by_source(db: Session) -> list[dict[str, Any]]:
    rows = db.execute(
        select(
            SourceDonnees.source_id,
            SourceDonnees.nom,
            func.avg(ExecutionEtl.taux_qualite).label("qualite_moy"),
            func.count(ExecutionEtl.execution_id).label("nb_executions"),
        )
        .join(ExecutionEtl, ExecutionEtl.source_id == SourceDonnees.source_id)
        .group_by(SourceDonnees.source_id, SourceDonnees.nom)
        .order_by(SourceDonnees.nom)
    ).all()
    return [
        {
            "source_id": r.source_id,
            "nom": r.nom,
            "qualite_moy": float(r.qualite_moy) if r.qualite_moy is not None else None,
            "nb_executions": int(r.nb_executions),
        }
        for r in rows
    ]


def rejects_by_lot(db: Session, limit: int = 20) -> list[dict[str, Any]]:
    rows = db.execute(
        select(
            LotDonnees.lot_id,
            LotDonnees.nom_lot,
            func.sum(case((func.upper(func.coalesce(ControleQualiteDonnee.decision_finale, "")) == "REJET", 1), else_=0)).label("nb_rejets"),
            func.count(ControleQualiteDonnee.controle_id).label("nb_anomalies"),
        )
        .join(ControleQualiteDonnee, ControleQualiteDonnee.lot_id == LotDonnees.lot_id)
        .group_by(LotDonnees.lot_id, LotDonnees.nom_lot)
        .order_by(
            func.sum(case((func.upper(func.coalesce(ControleQualiteDonnee.decision_finale, "")) == "REJET", 1), else_=0)).desc(),
            func.count(ControleQualiteDonnee.controle_id).desc(),
        )
        .limit(limit)
    ).all()
    data = [
        {
            "lot_id": r.lot_id,
            "nom_lot": r.nom_lot,
            "nb_rejets": int(r.nb_rejets or 0),
            "nb_anomalies": int(r.nb_anomalies or 0),
            "value": int(r.nb_rejets or 0) if int(r.nb_rejets or 0) > 0 else int(r.nb_anomalies or 0),
        }
        for r in rows
    ]
    if any(item["value"] > 0 for item in data):
        return [item for item in data if item["value"] > 0]
    return _demo_rejects_by_lot(data)


def imports_volume(db: Session, granularity: str = "day", days: int = 3650) -> list[dict[str, Any]]:
    fmt = "%Y-%m-%d" if granularity == "day" else ("%x-W%v" if granularity == "week" else "%Y-%m-01")
    bucket = func.date_format(ExecutionEtl.demarre_le, fmt).label("bucket")
    since = datetime.utcnow() - timedelta(days=days)
    rows = db.execute(
        select(
            bucket,
            func.coalesce(func.sum(ExecutionEtl.lignes_lues), 0).label("lignes_lues"),
            func.coalesce(func.sum(ExecutionEtl.lignes_valides), 0).label("lignes_valides"),
            func.coalesce(func.sum(ExecutionEtl.nb_rejets), 0).label("nb_rejets"),
        )
        .where(ExecutionEtl.demarre_le >= since)
        .group_by("bucket")
        .order_by("bucket")
    ).all()
    points = [
        {
            "bucket": str(r.bucket),
            "lignes_lues": int(r.lignes_lues),
            "lignes_valides": int(r.lignes_valides),
            "lignes_invalides": max(0, int(r.lignes_lues) - int(r.lignes_valides)),
            "nb_rejets": int(r.nb_rejets),
        }
        for r in rows
    ]
    return _demo_imports_volume(points)


def users_by_organisation(db: Session) -> list[dict[str, Any]]:
    rows = db.execute(
        select(
            Organisation.organisation_id,
            Organisation.nom,
            func.count(Utilisateur.utilisateur_id).label("nb_users"),
        )
        .join(Utilisateur, Utilisateur.organisation_id == Organisation.organisation_id, isouter=True)
        .group_by(Organisation.organisation_id, Organisation.nom)
        .order_by(func.count(Utilisateur.utilisateur_id).desc())
    ).all()
    return [
        {"organisation_id": r.organisation_id, "nom": r.nom, "nb_users": int(r.nb_users)} for r in rows
    ]


def top_broken_rules(db: Session, limit: int = 10) -> list[dict[str, Any]]:
    rows = db.execute(
        select(
            RegleQualite.regle_id,
            RegleQualite.code_regle,
            RegleQualite.severite,
            func.count(ControleQualiteDonnee.controle_id).label("nb"),
        )
        .join(ControleQualiteDonnee, ControleQualiteDonnee.regle_id == RegleQualite.regle_id)
        .group_by(RegleQualite.regle_id, RegleQualite.code_regle, RegleQualite.severite)
        .order_by(func.count(ControleQualiteDonnee.controle_id).desc())
        .limit(limit)
    ).all()
    return [
        {
            "regle_id": r.regle_id,
            "code_regle": r.code_regle,
            "severite": r.severite,
            "nb": int(r.nb),
        }
        for r in rows
    ]


def quality_by_organisation(db: Session) -> list[dict[str, Any]]:
    return quality_by_source(db)


def volumes_by_source(db: Session) -> list[dict[str, Any]]:
    rows = db.execute(
        select(
            SourceDonnees.source_id,
            SourceDonnees.nom,
            func.coalesce(func.sum(ExecutionEtl.lignes_lues), 0).label("lignes_lues"),
            func.coalesce(func.sum(ExecutionEtl.lignes_valides), 0).label("lignes_valides"),
            func.coalesce(func.sum(ExecutionEtl.lignes_invalides), 0).label("lignes_invalides"),
            func.coalesce(func.sum(ExecutionEtl.nb_rejets), 0).label("nb_rejets"),
        )
        .join(ExecutionEtl, ExecutionEtl.source_id == SourceDonnees.source_id, isouter=True)
        .group_by(SourceDonnees.source_id, SourceDonnees.nom)
        .order_by(func.coalesce(func.sum(ExecutionEtl.lignes_lues), 0).desc())
    ).all()
    return [
        {
            "source_id": r.source_id,
            "nom": r.nom,
            "name": r.nom,
            "lignes_lues": int(r.lignes_lues or 0),
            "lignes_valides": int(r.lignes_valides or 0),
            "lignes_invalides": int(r.lignes_invalides or 0),
            "nb_rejets": int(r.nb_rejets or 0),
            "lues": int(r.lignes_lues or 0),
            "valides": int(r.lignes_valides or 0),
            "invalides": int(r.lignes_invalides or 0),
        }
        for r in rows
    ]


def failed_executions(db: Session, limit: int = 20) -> list[dict[str, Any]]:
    rows = db.execute(
        select(ExecutionEtl)
        .where(ExecutionEtl.statut.in_(["ECHEC", "ERREUR", "FAILED"]))
        .order_by(ExecutionEtl.demarre_le.desc())
        .limit(limit)
    ).scalars().all()
    return [
        {
            "execution_id": e.execution_id,
            "source_id": e.source_id,
            "statut": e.statut,
            "demarre_le": e.demarre_le,
            "termine_le": e.termine_le,
            "nb_rejets": e.nb_rejets,
            "taux_qualite": e.taux_qualite,
            "message": e.message,
        }
        for e in rows
    ]


def blocked_lots(db: Session, limit: int = 20) -> list[dict[str, Any]]:
    nb_bloquants_subq = (
        select(func.count(ControleQualiteDonnee.controle_id))
        .where(
            ControleQualiteDonnee.lot_id == LotDonnees.lot_id,
            ControleQualiteDonnee.est_bloquant.is_(True),
        )
        .correlate(LotDonnees)
        .scalar_subquery()
    )
    rows = db.execute(
        select(LotDonnees, nb_bloquants_subq.label("nb_bloquants"))
        .where(LotDonnees.statut.in_(["EN_ATTENTE", "REJETE", "BLOQUE"]))
        .order_by(LotDonnees.lot_id.desc())
        .limit(limit)
    ).all()
    return [
        {
            "lot_id": l.lot_id,
            "nom_lot": l.nom_lot,
            "statut": l.statut,
            "execution_id": l.execution_id,
            "source_id": l.source_id,
            "cree_le": l.cree_le,
            "nb_bloquants": int(nb or 0),
        }
        for l, nb in rows
    ]


def _demo_imports_volume(points: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if get_settings().environment == "production" or len(points) != 1:
        return points
    anchor = datetime.strptime(points[0]["bucket"], "%Y-%m-%d")
    base = points[0]
    demo_points: list[dict[str, Any]] = []
    for offset in range(6, -1, -1):
        factor = 0.65 + ((6 - offset) * 0.08)
        lignes_lues = max(10, int(base["lignes_lues"] * factor))
        lignes_valides = max(5, int(base["lignes_valides"] * factor))
        nb_rejets = max(1, int(base["nb_rejets"] or 1) + (offset % 3))
        demo_points.append(
            {
                "bucket": (anchor - timedelta(days=offset)).strftime("%Y-%m-%d"),
                "lignes_lues": lignes_lues,
                "lignes_valides": min(lignes_lues, lignes_valides),
                "lignes_invalides": max(0, lignes_lues - min(lignes_lues, lignes_valides)),
                "nb_rejets": nb_rejets,
                "is_demo": True,
            }
        )
    return demo_points


def _demo_rejects_by_lot(data: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if get_settings().environment == "production" or not data:
        return data
    demo: list[dict[str, Any]] = []
    for index, item in enumerate(data[:5]):
        demo.append(
            {
                **item,
                "nb_rejets": 0,
                "nb_anomalies": max(1, index + 1),
                "value": max(1, index + 1),
                "is_demo": True,
            }
        )
    return demo
