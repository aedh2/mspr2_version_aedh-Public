"""Routes super-admin : monitoring + dashboards globaux.

L'admin générique CRUD sur organisations / sources-donnees est conservé via
api.py — on ajoute ici les vues d'agrégation et le monitoring.
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.security import require_roles
from app.db.models import ControleQualiteDonnee, ExecutionEtl, LotDonnees, Organisation, SourceDonnees, Utilisateur
from app.db.session import get_db
from app.services import admin_dashboard

router = APIRouter(prefix="/super-admin", tags=["super-admin"])


@router.get("/monitoring/etl")
def monitoring_etl(
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    _: Utilisateur = Depends(require_roles("SUPER_ADMIN")),
) -> dict[str, Any]:
    executions_par_statut = db.execute(
        select(ExecutionEtl.statut, func.count(ExecutionEtl.execution_id)).group_by(ExecutionEtl.statut)
    ).all()
    recent = db.execute(select(ExecutionEtl).order_by(ExecutionEtl.execution_id.desc()).limit(limit)).scalars().all()
    total = db.scalar(select(func.count(ExecutionEtl.execution_id))) or 0
    failed_count = db.scalar(select(func.count(ExecutionEtl.execution_id)).where(ExecutionEtl.statut.in_(["ECHEC", "ERREUR", "FAILED"]))) or 0
    lots_total = db.scalar(select(func.count(LotDonnees.lot_id))) or 0
    lines_read = db.scalar(select(func.coalesce(func.sum(ExecutionEtl.lignes_lues), 0))) or 0
    lines_valid = db.scalar(select(func.coalesce(func.sum(ExecutionEtl.lignes_valides), 0))) or 0
    lines_invalid = db.scalar(select(func.coalesce(func.sum(ExecutionEtl.lignes_invalides), 0))) or 0
    avg_quality = db.scalar(select(func.avg(ExecutionEtl.taux_qualite))) or 0
    lots_bloques = admin_dashboard.blocked_lots(db, limit)
    return {"data": {
        "kpis": {
            "total_executions": int(total),
            "executions_succes": int(total - failed_count),
            "executions_echec": int(failed_count),
            "total_lots": int(lots_total),
            "lots_bloques": len(lots_bloques),
            "lignes_lues_total": int(lines_read),
            "lignes_valides_total": int(lines_valid),
            "lignes_invalides_total": int(lines_invalid),
            "taux_qualite_moyen": float(avg_quality or 0),
            "taux_rejet_global": float(lines_invalid or 0) / float(lines_read or 1) * 100,
        },
        "executions_echec": admin_dashboard.failed_executions(db, limit),
        "lots_bloques": lots_bloques,
        "executions_par_statut": [{"name": s or "INCONNU", "value": int(n)} for s, n in executions_par_statut],
        "executions_recentes": [
            {"execution_id": e.execution_id, "source_id": e.source_id, "statut": e.statut, "demarre_le": e.demarre_le, "termine_le": e.termine_le, "taux_qualite": e.taux_qualite, "nb_rejets": e.nb_rejets}
            for e in recent
        ],
        "lots_recents": [
            {"lot_id": l.lot_id, "nom_lot": l.nom_lot, "statut": l.statut, "cree_le": l.cree_le, "execution_id": l.execution_id, "source_id": l.source_id}
            for l in db.execute(select(LotDonnees).order_by(LotDonnees.lot_id.desc()).limit(limit)).scalars().all()
        ],
    }}


@router.get("/monitoring/qualite")
def monitoring_qualite(
    db: Session = Depends(get_db),
    _: Utilisateur = Depends(require_roles("SUPER_ADMIN")),
) -> dict[str, Any]:
    controls = db.execute(select(ControleQualiteDonnee).order_by(ControleQualiteDonnee.controle_id.desc()).limit(20)).scalars().all()
    lots_anomalies = db.execute(
        select(LotDonnees.nom_lot, func.count(ControleQualiteDonnee.controle_id).label("nb"))
        .join(ControleQualiteDonnee, ControleQualiteDonnee.lot_id == LotDonnees.lot_id)
        .group_by(LotDonnees.lot_id, LotDonnees.nom_lot)
        .order_by(func.count(ControleQualiteDonnee.controle_id).desc())
        .limit(10)
    ).all()
    qualite = admin_dashboard.quality_by_source(db)
    volumes = admin_dashboard.volumes_by_source(db)
    return {"data": {
        "qualite_par_source": [{"name": r["nom"], "value": r["qualite_moy"] or 0, **r} for r in qualite],
        "volumes_par_source": volumes,
        "rejet_par_source": [{"name": r["nom"], "value": (r["nb_rejets"] / (r["lignes_lues"] or 1)) * 100} for r in volumes],
        "lots_anomalies": [{"name": name or "Lot", "value": int(nb)} for name, nb in lots_anomalies],
        "controles_qualite_recents": [
            {"controle_id": c.controle_id, "entite": c.entite, "niveau": c.niveau, "decision_finale": c.decision_finale, "code_controle": c.code_controle, "description": c.description}
            for c in controls
        ],
        "lots_avec_anomalies": [{"name": name or "Lot", "value": int(nb)} for name, nb in lots_anomalies],
        "sources_problematiques": sorted(
            [{"name": r["nom"], "value": (r["nb_rejets"] / (r["lignes_lues"] or 1)) * 100} for r in volumes],
            key=lambda x: x["value"],
            reverse=True,
        )[:5],
    }}


@router.get("/organisations/{organisation_id}/stats")
def organisation_stats(
    organisation_id: int,
    db: Session = Depends(get_db),
    _: Utilisateur = Depends(require_roles("SUPER_ADMIN")),
) -> dict[str, Any]:
    users = db.execute(select(Utilisateur).where(Utilisateur.organisation_id == organisation_id)).scalars().all()
    return {"data": {
        "organisation_id": organisation_id,
        "nb_utilisateurs": len(users),
        "nb_admins": len([u for u in users if u.role in ("ADMIN", "SUPER_ADMIN")]),
        "nb_utilisateurs_actifs": len([u for u in users if u.statut == "ACTIF"]),
        "dernieres_inscriptions": [
            {"utilisateur_id": u.utilisateur_id, "nom_utilisateur": u.nom_utilisateur, "role": u.role, "cree_le": u.cree_le}
            for u in sorted(users, key=lambda x: x.cree_le or 0, reverse=True)[:5]
        ],
    }}


@router.get("/dashboard/charts/quality-by-organisation")
def super_admin_quality_by_organisation(
    db: Session = Depends(get_db),
    _: Utilisateur = Depends(require_roles("SUPER_ADMIN")),
) -> dict[str, Any]:
    return {"data": admin_dashboard.quality_by_organisation(db)}


@router.get("/dashboard/charts/volumes-by-source")
def super_admin_volumes_by_source(
    db: Session = Depends(get_db),
    _: Utilisateur = Depends(require_roles("SUPER_ADMIN")),
) -> dict[str, Any]:
    return {"data": admin_dashboard.volumes_by_source(db)}
