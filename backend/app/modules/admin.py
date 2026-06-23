"""Routes admin : utilisateurs, ETL workflow, qualité, dashboard charts."""
from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any, Literal

from fastapi import APIRouter, Body, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.errors import ApiError
from app.core.pagination import PaginationParams, paginated_response, pagination_params
from app.core.security import require_roles
from app.db import models
from app.db.models import Utilisateur
from app.db.session import get_db
from app.modules.resources import media_url
from app.services import (
    admin_dashboard,
    admin_etl,
    admin_quality,
    admin_users,
)


# Admin (ADMIN ou SUPER_ADMIN)
router = APIRouter(prefix="/admin", tags=["admin"])
ADMIN_ROLES = ("ADMIN", "SUPER_ADMIN")


# ----------- Utilisateurs admin -----------


@router.get("/utilisateurs")
def admin_list_users(
    pagination: PaginationParams = Depends(pagination_params),
    role: str | None = Query(None),
    statut: str | None = Query(None),
    organisation_id: int | None = Query(None),
    db: Session = Depends(get_db),
    _: Utilisateur = Depends(require_roles(*ADMIN_ROLES)),
) -> dict[str, Any]:
    filters = {
        "role": role,
        "statut": statut,
        "organisation_id": organisation_id,
        "search": pagination.search,
    }
    rows, total = admin_users.list_users(db, filters, pagination.page, pagination.page_size)
    return paginated_response(
        rows, pagination.page, pagination.page_size, total, filters={**filters, **{"sort_by": pagination.sort_by, "sort_order": pagination.sort_order}}
    )


@router.get("/utilisateurs/{utilisateur_id}/resume")
def admin_user_resume(
    utilisateur_id: int,
    db: Session = Depends(get_db),
    _: Utilisateur = Depends(require_roles(*ADMIN_ROLES)),
) -> dict[str, Any]:
    return {"data": admin_users.user_resume(db, utilisateur_id)}


@router.patch("/utilisateurs/{utilisateur_id}/statut")
def admin_patch_user_statut(
    utilisateur_id: int,
    statut: str = Body(..., embed=True),
    db: Session = Depends(get_db),
    _: Utilisateur = Depends(require_roles(*ADMIN_ROLES)),
) -> dict[str, Any]:
    return {"data": admin_users.patch_statut(db, utilisateur_id, statut)}


def _require_user(db: Session, utilisateur_id: int) -> models.Utilisateur:
    user = db.get(models.Utilisateur, utilisateur_id)
    if not user:
        raise ApiError(404, "not_found", "Utilisateur introuvable.")
    return user


@router.get("/utilisateurs/{utilisateur_id}/biometrie")
def admin_user_biometrie(
    utilisateur_id: int,
    db: Session = Depends(get_db),
    _: Utilisateur = Depends(require_roles(*ADMIN_ROLES)),
) -> dict[str, Any]:
    _require_user(db, utilisateur_id)
    rows = db.execute(
        select(models.MesureBiometrique)
        .where(models.MesureBiometrique.utilisateur_id == utilisateur_id)
        .order_by(models.MesureBiometrique.mesure_le.desc())
    ).scalars().all()
    items = [
        {
            "mesure_id": row.mesure_id,
            "mesure_le": row.mesure_le,
            "poids_kg": row.poids_kg,
            "imc": row.imc,
            "taux_masse_grasse": row.taux_masse_grasse,
            "bpm_repos": row.bpm_repos,
            "bpm_moyen": row.bpm_moyen,
            "bpm_max": row.bpm_max,
            "eau_l": row.eau_l,
        }
        for row in rows
    ]
    latest = items[0] if items else None
    charts = {
        "poids": [{"date": row.mesure_le, "value": row.poids_kg} for row in reversed(rows) if row.poids_kg is not None],
        "imc": [{"date": row.mesure_le, "value": row.imc} for row in reversed(rows) if row.imc is not None],
        "masse_grasse": [{"date": row.mesure_le, "value": row.taux_masse_grasse} for row in reversed(rows) if row.taux_masse_grasse is not None],
        "bpm": [{"date": row.mesure_le, "value": row.bpm_repos or row.bpm_moyen or row.bpm_max} for row in reversed(rows) if any(v is not None for v in (row.bpm_repos, row.bpm_moyen, row.bpm_max))],
        "hydratation": [{"date": row.mesure_le, "value": row.eau_l} for row in reversed(rows) if row.eau_l is not None],
    }
    return {"data": {"items": items, "latest": latest, "charts": charts}}


@router.get("/utilisateurs/{utilisateur_id}/sommeil")
def admin_user_sommeil(
    utilisateur_id: int,
    db: Session = Depends(get_db),
    _: Utilisateur = Depends(require_roles(*ADMIN_ROLES)),
) -> dict[str, Any]:
    _require_user(db, utilisateur_id)
    rows = db.execute(
        select(models.MesureSommeilSante)
        .where(models.MesureSommeilSante.utilisateur_id == utilisateur_id)
        .order_by(models.MesureSommeilSante.mesure_le.desc())
    ).scalars().all()
    items = [
        {
            "mesure_sommeil_id": row.mesure_sommeil_id,
            "mesure_le": row.mesure_le,
            "duree_sommeil_h": row.duree_sommeil_h,
            "qualite_sommeil_score": row.qualite_sommeil_score,
            "stress_score": row.stress_score,
            "pas_jour": row.pas_jour,
            "frequence_cardiaque_bpm": row.frequence_cardiaque_bpm,
            "tension_systolique": row.tension_systolique,
            "tension_diastolique": row.tension_diastolique,
        }
        for row in rows
    ]
    latest = items[0] if items else None
    charts = {
        "sommeil": [{"date": row.mesure_le, "value": row.duree_sommeil_h} for row in reversed(rows) if row.duree_sommeil_h is not None],
        "stress": [{"date": row.mesure_le, "value": row.stress_score} for row in reversed(rows) if row.stress_score is not None],
        "pas": [{"date": row.mesure_le, "value": row.pas_jour} for row in reversed(rows) if row.pas_jour is not None],
        "qualite": [{"date": row.mesure_le, "value": row.qualite_sommeil_score} for row in reversed(rows) if row.qualite_sommeil_score is not None],
        "tension": [{"date": row.mesure_le, "value": row.tension_systolique} for row in reversed(rows) if row.tension_systolique is not None],
    }
    return {"data": {"items": items, "latest": latest, "charts": charts}}


@router.get("/utilisateurs/{utilisateur_id}/seances")
def admin_user_seances(
    utilisateur_id: int,
    db: Session = Depends(get_db),
    _: Utilisateur = Depends(require_roles(*ADMIN_ROLES)),
) -> dict[str, Any]:
    _require_user(db, utilisateur_id)
    seances = db.execute(
        select(models.SeanceEntrainement)
        .where(models.SeanceEntrainement.utilisateur_id == utilisateur_id)
        .order_by(models.SeanceEntrainement.date_seance.desc())
    ).scalars().all()
    items = []
    types_counter: dict[str, int] = {}
    calories_total = 0.0
    duree_totale = 0.0
    for seance in seances:
        exercices = db.execute(
            select(models.SeanceExercice, models.Exercice)
            .join(models.Exercice, models.Exercice.exercice_id == models.SeanceExercice.exercice_id)
            .where(models.SeanceExercice.seance_id == seance.seance_id)
            .order_by(models.SeanceExercice.ordre_exercice.asc(), models.SeanceExercice.seance_exercice_id.asc())
        ).all()
        items.append(
            {
                "seance_id": seance.seance_id,
                "date_seance": seance.date_seance,
                "type_entrainement": seance.type_entrainement,
                "duree_min": seance.duree_seance_min,
                "calories_brulees_estimees": seance.calories_brulees_total,
                "niveau_experience": seance.niveau_experience,
                "exercices": [
                    {
                        "nom": ex.nom,
                        "series_nb": se.series_nb,
                        "repetitions_nb": se.repetitions_nb,
                        "charge_kg": se.charge_kg,
                        "duree_min": se.duree_min,
                    }
                    for se, ex in exercices
                ],
            }
        )
        calories_total += float(seance.calories_brulees_total or 0)
        duree_totale += float(seance.duree_seance_min or 0)
        types_counter[seance.type_entrainement or "inconnu"] = types_counter.get(seance.type_entrainement or "inconnu", 0) + 1
    return {
        "data": {
            "items": items,
            "stats": {
                "total": len(items),
                "calories_brulees": calories_total,
                "duree_totale": duree_totale,
                "types": [{"name": key, "value": value} for key, value in types_counter.items()],
            },
        }
    }


@router.get("/utilisateurs/{utilisateur_id}/nutrition")
def admin_user_nutrition(
    utilisateur_id: int,
    db: Session = Depends(get_db),
    _: Utilisateur = Depends(require_roles(*ADMIN_ROLES)),
) -> dict[str, Any]:
    _require_user(db, utilisateur_id)
    plats = db.execute(
        select(models.Plat)
        .where(models.Plat.utilisateur_id == utilisateur_id)
        .order_by(models.Plat.consomme_le.desc())
    ).scalars().all()
    journal = db.execute(
        select(models.JournalAlimentaire)
        .where(models.JournalAlimentaire.utilisateur_id == utilisateur_id)
        .order_by(models.JournalAlimentaire.consomme_le.desc())
    ).scalars().all()
    repas_rows = db.execute(
        select(models.JournalAlimentaire.type_repas, func.count(models.JournalAlimentaire.journal_id))
        .where(models.JournalAlimentaire.utilisateur_id == utilisateur_id)
        .group_by(models.JournalAlimentaire.type_repas)
    ).all()
    calories_rows = db.execute(
        select(
            func.date_format(models.JournalAlimentaire.consomme_le, "%Y-%m-%d").label("bucket"),
            func.coalesce(func.sum(models.JournalAlimentaire.calories_kcal), 0).label("calories"),
        )
        .where(models.JournalAlimentaire.utilisateur_id == utilisateur_id)
        .group_by("bucket")
        .order_by("bucket")
    ).all()
    return {
        "data": {
            "plats": [
                {
                    "plat_id": row.plat_id,
                    "consomme_le": row.consomme_le,
                    "type_repas": row.type_repas,
                    "nom_plat": row.nom_plat,
                    "calories_totales_kcal": row.calories_totales_kcal,
                }
                for row in plats
            ],
            "journal": [
                {
                    "journal_id": row.journal_id,
                    "consomme_le": row.consomme_le,
                    "type_repas": row.type_repas,
                    "aliment_nom_libre": row.aliment_nom_libre,
                    "plat_id": row.plat_id,
                    "aliment_id": row.aliment_id,
                    "calories_kcal": row.calories_kcal,
                    "quantite": row.quantite,
                }
                for row in journal
            ],
            "stats": {
                "total_plats": len(plats),
                "calories_totales": sum(float(row.calories_kcal or 0) for row in journal),
                "repas_par_type": [{"name": row[0] or "inconnu", "value": int(row[1])} for row in repas_rows],
                "calories_par_jour": [{"date": str(row.bucket), "value": float(row.calories)} for row in calories_rows],
            },
        }
    }


@router.get("/utilisateurs/{utilisateur_id}/photos")
def admin_user_photos(
    utilisateur_id: int,
    db: Session = Depends(get_db),
    _: Utilisateur = Depends(require_roles(*ADMIN_ROLES)),
) -> dict[str, Any]:
    _require_user(db, utilisateur_id)
    rows = db.execute(
        select(models.ProgressionPhoto)
        .where(models.ProgressionPhoto.utilisateur_id == utilisateur_id)
        .order_by(models.ProgressionPhoto.prise_le.desc(), models.ProgressionPhoto.photo_id.desc())
    ).scalars().all()
    return {
        "data": {
            "items": [
                {
                    "photo_id": row.photo_id,
                    "date_photo": row.prise_le,
                    "photo_url": media_url("progression", row.image_path),
                    "type_photo": row.type_photo,
                    "commentaire": None,
                    "objectif_id": row.objectif_id,
                }
                for row in rows
            ]
        }
    }


@router.get("/utilisateurs/{utilisateur_id}/objectifs")
def admin_user_objectifs(
    utilisateur_id: int,
    db: Session = Depends(get_db),
    _: Utilisateur = Depends(require_roles(*ADMIN_ROLES)),
) -> dict[str, Any]:
    _require_user(db, utilisateur_id)
    rows = db.execute(
        select(models.ObjectifUtilisateur)
        .where(models.ObjectifUtilisateur.utilisateur_id == utilisateur_id)
        .order_by(models.ObjectifUtilisateur.objectif_id.desc())
    ).scalars().all()
    active = next((row for row in rows if row.actif_unique), None)
    def objective_status(row: models.ObjectifUtilisateur) -> str:
        if row.statut_objectif:
            return row.statut_objectif
        if row.actif_unique:
            return "EN_COURS"
        return "TERMINE"
    items = [
        {
            "objectif_id": row.objectif_id,
            "type_objectif": row.type_objectif,
            "date_debut": row.date_debut,
            "date_fin": row.date_fin,
            "actif_unique": row.actif_unique,
            "statut_objectif": objective_status(row),
            "commentaire": row.commentaire,
        }
        for row in rows
    ]
    stats = {"total": len(items), "reussis": 0, "echoues": 0, "annules": 0, "en_cours": 0}
    for item in items:
        statut = (item["statut_objectif"] or "").upper()
        if "REUS" in statut:
            stats["reussis"] += 1
        elif "ECHO" in statut or "ECHEC" in statut:
            stats["echoues"] += 1
        elif "ANNUL" in statut:
            stats["annules"] += 1
        else:
            stats["en_cours"] += 1
    return {
        "data": {
            "active": (
                {
                    "objectif_id": active.objectif_id,
                    "type_objectif": active.type_objectif,
                    "date_debut": active.date_debut,
                    "date_fin": active.date_fin,
                    "actif_unique": active.actif_unique,
                    "statut_objectif": objective_status(active),
                    "commentaire": active.commentaire,
                }
                if active
                else None
            ),
            "items": items,
            "stats": stats,
        }
    }


# ----------- ETL : exécutions -----------


@router.get("/etl/executions")
def admin_executions(
    pagination: PaginationParams = Depends(pagination_params),
    statut: str | None = Query(None),
    source_id: int | None = Query(None),
    db: Session = Depends(get_db),
    _: Utilisateur = Depends(require_roles(*ADMIN_ROLES)),
) -> dict[str, Any]:
    query = db.query(models.ExecutionEtl)
    if statut:
        query = query.filter(models.ExecutionEtl.statut == statut)
    if source_id:
        query = query.filter(models.ExecutionEtl.source_id == source_id)
    total = query.count()
    rows = query.order_by(models.ExecutionEtl.execution_id.desc()).offset(pagination.offset).limit(pagination.page_size).all()
    return paginated_response(
        [
            {
                "execution_id": e.execution_id,
                "source_id": e.source_id,
                "statut": e.statut,
                "demarre_le": e.demarre_le,
                "termine_le": e.termine_le,
                "lignes_lues": e.lignes_lues,
                "lignes_valides": e.lignes_valides,
                "lignes_invalides": e.lignes_invalides,
                "nb_rejets": e.nb_rejets,
                "taux_qualite": e.taux_qualite,
                "message": e.message,
            }
            for e in rows
        ],
        pagination.page,
        pagination.page_size,
        total,
        filters={"statut": statut, "source_id": source_id},
    )


@router.get("/etl/executions/{execution_id}")
def admin_execution_detail(
    execution_id: int,
    db: Session = Depends(get_db),
    _: Utilisateur = Depends(require_roles(*ADMIN_ROLES)),
) -> dict[str, Any]:
    return {"data": admin_etl.execution_detail(db, execution_id)}


# ----------- ETL : lots workflow -----------


@router.get("/etl/lots")
def admin_lots(
    pagination: PaginationParams = Depends(pagination_params),
    statut: str | None = Query(None),
    source_id: int | None = Query(None),
    execution_id: int | None = Query(None),
    db: Session = Depends(get_db),
    _: Utilisateur = Depends(require_roles(*ADMIN_ROLES)),
) -> dict[str, Any]:
    query = db.query(models.LotDonnees)
    if statut:
        query = query.filter(models.LotDonnees.statut == statut)
    if source_id:
        query = query.filter(models.LotDonnees.source_id == source_id)
    if execution_id:
        query = query.filter(models.LotDonnees.execution_id == execution_id)
    total = query.count()
    rows = query.order_by(models.LotDonnees.lot_id.desc()).offset(pagination.offset).limit(pagination.page_size).all()
    return paginated_response(
        [
            {
                "lot_id": l.lot_id,
                "execution_id": l.execution_id,
                "source_id": l.source_id,
                "nom_lot": l.nom_lot,
                "statut": l.statut,
                "valide_le": l.valide_le,
                "commentaire_validation": l.commentaire_validation,
                "cree_le": l.cree_le,
            }
            for l in rows
        ],
        pagination.page,
        pagination.page_size,
        total,
        filters={"statut": statut, "source_id": source_id, "execution_id": execution_id},
    )


@router.get("/etl/lots/{lot_id}")
def admin_lot_detail(
    lot_id: int,
    db: Session = Depends(get_db),
    _: Utilisateur = Depends(require_roles(*ADMIN_ROLES)),
) -> dict[str, Any]:
    return {"data": admin_etl.lot_resume(db, lot_id)}


@router.patch("/etl/lots/{lot_id}/statut")
def admin_patch_lot_statut(
    lot_id: int,
    statut: str = Body(..., embed=True),
    commentaire: str | None = Body(default=None, embed=True),
    db: Session = Depends(get_db),
    user: Utilisateur = Depends(require_roles(*ADMIN_ROLES)),
) -> dict[str, Any]:
    return {
        "data": admin_etl.patch_lot_statut(
            db, lot_id, statut, valide_par_id=user.utilisateur_id, commentaire=commentaire
        )
    }


@router.get("/etl/lots/{lot_id}/resume")
def admin_lot_resume(
    lot_id: int,
    db: Session = Depends(get_db),
    _: Utilisateur = Depends(require_roles(*ADMIN_ROLES)),
) -> dict[str, Any]:
    return {"data": admin_etl.lot_resume(db, lot_id)}


@router.get("/etl/lots/{lot_id}/raw")
def admin_lot_raw(
    lot_id: int,
    pagination: PaginationParams = Depends(pagination_params),
    entite: str | None = Query(None),
    db: Session = Depends(get_db),
    _: Utilisateur = Depends(require_roles(*ADMIN_ROLES)),
) -> dict[str, Any]:
    rows, total = admin_etl.list_raw(db, lot_id, entite, pagination.page, pagination.page_size)
    return paginated_response(
        rows, pagination.page, pagination.page_size, total, filters={"entite": entite}
    )


@router.get("/etl/lots/{lot_id}/staging")
def admin_lot_staging(
    lot_id: int,
    pagination: PaginationParams = Depends(pagination_params),
    entite: str | None = Query(None),
    db: Session = Depends(get_db),
    _: Utilisateur = Depends(require_roles(*ADMIN_ROLES)),
) -> dict[str, Any]:
    rows, total = admin_etl.list_staging(db, lot_id, entite, pagination.page, pagination.page_size)
    return paginated_response(
        rows, pagination.page, pagination.page_size, total, filters={"entite": entite}
    )


@router.get("/etl/lots/{lot_id}/controles")
def admin_lot_controles(
    lot_id: int,
    pagination: PaginationParams = Depends(pagination_params),
    db: Session = Depends(get_db),
    _: Utilisateur = Depends(require_roles(*ADMIN_ROLES)),
) -> dict[str, Any]:
    rows, total = admin_etl.list_controles_lot(db, lot_id, pagination.page, pagination.page_size)
    return paginated_response(rows, pagination.page, pagination.page_size, total)


@router.get("/etl/lots/{lot_id}/impacts")
def admin_lot_impacts(
    lot_id: int,
    db: Session = Depends(get_db),
    _: Utilisateur = Depends(require_roles(*ADMIN_ROLES)),
) -> dict[str, Any]:
    return {"data": admin_etl.lot_impacts(db, lot_id)}


@router.get("/etl/compare")
def admin_etl_compare(
    lot_id: int | None = Query(None),
    lotId: int | None = Query(None),
    entite: str = Query(...),
    ref_externe: str | None = Query(None),
    refExterne: str | None = Query(None),
    db: Session = Depends(get_db),
    _: Utilisateur = Depends(require_roles(*ADMIN_ROLES)),
) -> dict[str, Any]:
    resolved_lot_id = lot_id or lotId
    resolved_ref = ref_externe or refExterne
    if not resolved_lot_id:
        raise ApiError(422, "validation_error", "lotId/lot_id est requis.")
    if not resolved_ref:
        first = (
            db.query(models.EnregistrementBrut.ref_externe)
            .filter(models.EnregistrementBrut.lot_id == resolved_lot_id, models.EnregistrementBrut.entite == entite)
            .filter(models.EnregistrementBrut.ref_externe.isnot(None))
            .first()
        )
        if not first:
            raise ApiError(404, "not_found", "Aucune ref_externe disponible pour ce lot et cette entite.")
        resolved_ref = first[0]
    payload = admin_etl.compare_avant_apres(db, resolved_lot_id, entite, resolved_ref)
    refs = (
        db.query(models.EnregistrementBrut.ref_externe)
        .filter(models.EnregistrementBrut.lot_id == resolved_lot_id, models.EnregistrementBrut.entite == entite)
        .filter(models.EnregistrementBrut.ref_externe.isnot(None))
        .distinct()
        .limit(50)
        .all()
    )
    payload["available_refs"] = [r[0] for r in refs if r[0]]
    payload["quality_controls"] = payload.get("controles", [])
    return {"data": payload}


@router.get("/etl/compare/changes")
def admin_etl_compare_changes(
    lotId: int | None = Query(None),
    entite: str | None = Query(None),
    sourceId: int | None = Query(None),
    refExterne: str | None = Query(None),
    changedOnly: bool = Query(False),
    page: int = Query(1, ge=1),
    pageSize: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    _: Utilisateur = Depends(require_roles(*ADMIN_ROLES)),
) -> dict[str, Any]:
    data, total = admin_etl.compare_changes(
        db,
        lot_id=lotId,
        entite=entite,
        source_id=sourceId,
        ref_externe=refExterne,
        changed_only=changedOnly,
        page=page,
        page_size=pageSize,
    )
    return {"data": data, "meta": {"page": page, "pageSize": pageSize, "total": total}}


@router.get("/etl/compare/options")
def admin_etl_compare_options(
    lotId: int | None = Query(None),
    lot_id: int | None = Query(None),
    entite: str | None = Query(None),
    sourceId: int | None = Query(None),
    refExterne: str | None = Query(None),
    db: Session = Depends(get_db),
    _: Utilisateur = Depends(require_roles(*ADMIN_ROLES)),
) -> dict[str, Any]:
    resolved_lot_id = lot_id or lotId
    options = admin_etl.compare_options(
        db,
        lot_id=resolved_lot_id,
        entite=entite,
        source_id=sourceId,
        ref_externe=refExterne,
    )
    return {"data": options}


# ----------- Qualité -----------


def _quality_filters(
    niveau: str | None = Query(None),
    type_controle: str | None = Query(None),
    decision: str | None = Query(None),
    decision_finale: str | None = Query(None),
    entite: str | None = Query(None),
    lotId: int | None = Query(None),
    lot_id: int | None = Query(None),
    execution_id: int | None = Query(None),
    regle_id: int | None = Query(None),
    nom_champ: str | None = Query(None),
    etape_pipeline: str | None = Query(None),
    sourceId: int | None = Query(None),
    source_id: int | None = Query(None),
    dateFrom: date | None = Query(None),
    date_from: date | None = Query(None),
    dateTo: date | None = Query(None),
    date_to: date | None = Query(None),
) -> dict[str, Any]:
    resolved_lot_id = lot_id or lotId
    resolved_source_id = source_id or sourceId
    resolved_date_from = date_from or dateFrom
    resolved_date_to = date_to or dateTo
    return {
        "niveau": niveau,
        "type_controle": type_controle,
        "decision_finale": decision_finale or decision,
        "entite": entite,
        "lot_id": resolved_lot_id,
        "execution_id": execution_id,
        "regle_id": regle_id,
        "nom_champ": nom_champ,
        "etape_pipeline": etape_pipeline,
        "source_id": resolved_source_id,
        "date_from": datetime.combine(resolved_date_from, datetime.min.time()) if resolved_date_from else None,
        "date_to": datetime.combine(resolved_date_to + timedelta(days=1), datetime.min.time()) if resolved_date_to else None,
    }


@router.get("/qualite/filters")
def admin_quality_filters(
    db: Session = Depends(get_db),
    _: Utilisateur = Depends(require_roles(*ADMIN_ROLES)),
) -> dict[str, Any]:
    return {"data": admin_quality.filter_options(db)}


@router.get("/qualite/controles")
def admin_quality_controles(
    pagination: PaginationParams = Depends(pagination_params),
    filters: dict[str, Any] = Depends(_quality_filters),
    db: Session = Depends(get_db),
    _: Utilisateur = Depends(require_roles(*ADMIN_ROLES)),
) -> dict[str, Any]:
    rows, total = admin_quality.list_controles(db, filters, pagination.page, pagination.page_size)
    # Filtres datetime ne sont pas sérialisables ; on les rétroconvertit en str ISO pour l'echo.
    echo_filters = {
        k: (v.isoformat() if hasattr(v, "isoformat") else v)
        for k, v in filters.items()
        if v is not None
    }
    return paginated_response(rows, pagination.page, pagination.page_size, total, filters=echo_filters)


@router.get("/qualite/controles/{controle_id}")
def admin_quality_controle_detail(
    controle_id: int,
    db: Session = Depends(get_db),
    _: Utilisateur = Depends(require_roles(*ADMIN_ROLES)),
) -> dict[str, Any]:
    payload = admin_quality.get_controle(db, controle_id)
    if payload is None:
        raise ApiError(404, "not_found", "Controle introuvable.")
    return {"data": payload}


@router.get("/qualite/kpis")
def admin_quality_kpis(
    filters: dict[str, Any] = Depends(_quality_filters),
    db: Session = Depends(get_db),
    _: Utilisateur = Depends(require_roles(*ADMIN_ROLES)),
) -> dict[str, Any]:
    return {"data": admin_quality.kpis(db, filters)}


@router.get("/qualite/charts/levels")
def admin_quality_chart_levels(
    filters: dict[str, Any] = Depends(_quality_filters),
    db: Session = Depends(get_db),
    _: Utilisateur = Depends(require_roles(*ADMIN_ROLES)),
) -> dict[str, Any]:
    return {"data": admin_quality.chart_levels(db, filters)}


@router.get("/qualite/charts/decisions")
def admin_quality_chart_decisions(
    filters: dict[str, Any] = Depends(_quality_filters),
    db: Session = Depends(get_db),
    _: Utilisateur = Depends(require_roles(*ADMIN_ROLES)),
) -> dict[str, Any]:
    return {"data": admin_quality.chart_decisions(db, filters)}


@router.get("/qualite/charts/top-rules")
def admin_quality_chart_top_rules(
    filters: dict[str, Any] = Depends(_quality_filters),
    limit: int = Query(10, ge=1, le=50),
    db: Session = Depends(get_db),
    _: Utilisateur = Depends(require_roles(*ADMIN_ROLES)),
) -> dict[str, Any]:
    return {"data": admin_quality.chart_top_rules(db, filters, limit)}


@router.get("/qualite/charts/top-fields")
def admin_quality_chart_top_fields(
    filters: dict[str, Any] = Depends(_quality_filters),
    limit: int = Query(10, ge=1, le=50),
    db: Session = Depends(get_db),
    _: Utilisateur = Depends(require_roles(*ADMIN_ROLES)),
) -> dict[str, Any]:
    return {"data": admin_quality.chart_top_fields(db, filters, limit)}


@router.get("/qualite/charts/by-source")
def admin_quality_chart_by_source(
    filters: dict[str, Any] = Depends(_quality_filters),
    db: Session = Depends(get_db),
    _: Utilisateur = Depends(require_roles(*ADMIN_ROLES)),
) -> dict[str, Any]:
    return {"data": admin_quality.chart_by_source(db, filters)}


@router.get("/qualite/charts/by-lot")
def admin_quality_chart_by_lot(
    filters: dict[str, Any] = Depends(_quality_filters),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    _: Utilisateur = Depends(require_roles(*ADMIN_ROLES)),
) -> dict[str, Any]:
    return {"data": admin_quality.chart_by_lot(db, filters, limit)}


@router.get("/qualite/charts/timeline")
def admin_quality_chart_timeline(
    filters: dict[str, Any] = Depends(_quality_filters),
    granularity: Literal["day", "week", "month"] = Query("day"),
    db: Session = Depends(get_db),
    _: Utilisateur = Depends(require_roles(*ADMIN_ROLES)),
) -> dict[str, Any]:
    return {"data": admin_quality.chart_timeline(db, filters, granularity)}


# ----------- Dashboard admin charts -----------


@router.get("/dashboard/charts/quality-by-source")
def admin_dash_quality_by_source(
    db: Session = Depends(get_db),
    _: Utilisateur = Depends(require_roles(*ADMIN_ROLES)),
) -> dict[str, Any]:
    return {"data": admin_dashboard.quality_by_source(db)}


@router.get("/dashboard/charts/rejects-by-lot")
def admin_dash_rejects_by_lot(
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    _: Utilisateur = Depends(require_roles(*ADMIN_ROLES)),
) -> dict[str, Any]:
    return {"data": admin_dashboard.rejects_by_lot(db, limit)}


@router.get("/dashboard/charts/imports-volume")
def admin_dash_imports_volume(
    granularity: Literal["day", "week", "month"] = Query("day"),
    days: int = Query(3650, ge=1, le=3650),
    db: Session = Depends(get_db),
    _: Utilisateur = Depends(require_roles(*ADMIN_ROLES)),
) -> dict[str, Any]:
    return {"data": admin_dashboard.imports_volume(db, granularity, days)}


@router.get("/dashboard/charts/users-by-organisation")
def admin_dash_users_by_organisation(
    db: Session = Depends(get_db),
    _: Utilisateur = Depends(require_roles(*ADMIN_ROLES)),
) -> dict[str, Any]:
    return {"data": admin_dashboard.users_by_organisation(db)}


@router.get("/dashboard/charts/top-rules")
def admin_dash_top_rules(
    limit: int = Query(10, ge=1, le=50),
    db: Session = Depends(get_db),
    _: Utilisateur = Depends(require_roles(*ADMIN_ROLES)),
) -> dict[str, Any]:
    return {"data": admin_dashboard.top_broken_rules(db, limit)}
