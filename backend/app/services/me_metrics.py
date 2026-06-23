"""Agrégations & valeurs dérivées pour l'espace utilisateur.

Pas de logique HTTP ici : les fonctions reçoivent une `Session` + `utilisateur_id`
et renvoient des dicts. Les endpoints dans `app/modules/me.py` se contentent
d'appeler ces helpers et de les wrapper dans l'enveloppe `{data: ...}`.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.errors import ApiError
from app.db.models import (
    JournalAlimentaire,
    MesureBiometrique,
    MesureSommeilSante,
    ObjectifUtilisateur,
    Organisation,
    Plat,
    ProgressionPhoto,
    SeanceEntrainement,
    Utilisateur,
)
from app.modules.resources import media_url
from app.schemas.me import BIOMETRIE_METRICS, ChartParams, SOMMEIL_METRICS
from app.services.profile_setup import compute_age, json_list


# ---------- helpers ----------


def _bucket_expr(column: Any, granularity: str) -> Any:
    """Construit l'expression de troncature pour MySQL.

    day  -> DATE(col)
    week -> DATE(col - INTERVAL WEEKDAY(col) DAY)  approximé par YEARWEEK
    month -> DATE_FORMAT(col, '%Y-%m-01')
    """
    if granularity == "week":
        # YEARWEEK ISO (mode 3) -> "YYYYWW", on le re-formate côté Python.
        return func.date_format(column, "%x-W%v")
    if granularity == "month":
        return func.date_format(column, "%Y-%m-01")
    return func.date_format(column, "%Y-%m-%d")


def _validate_metric(metric: str, whitelist: tuple[str, ...]) -> None:
    if metric not in whitelist:
        raise ApiError(
            422,
            "validation_error",
            f"Metric '{metric}' invalide. Autorisees: {', '.join(whitelist)}.",
        )


def _apply_date_range(stmt, column, params: ChartParams):
    if params.date_from:
        stmt = stmt.where(column >= datetime.combine(params.date_from, datetime.min.time()))
    if params.date_to:
        stmt = stmt.where(column < datetime.combine(params.date_to + timedelta(days=1), datetime.min.time()))
    return stmt


# ---------- biométrie ----------


def latest_biometrie(db: Session, utilisateur_id: int) -> dict[str, Any] | None:
    row = db.execute(
        select(MesureBiometrique)
        .where(MesureBiometrique.utilisateur_id == utilisateur_id)
        .order_by(MesureBiometrique.mesure_le.desc())
        .limit(1)
    ).scalar_one_or_none()
    if not row:
        return None
    return {
        "mesure_id": row.mesure_id,
        "mesure_le": row.mesure_le,
        "poids_kg": row.poids_kg,
        "taille_cm": row.taille_cm,
        "imc": row.imc,
        "taux_masse_grasse": row.taux_masse_grasse,
        "bpm_repos": row.bpm_repos,
        "bpm_moyen": row.bpm_moyen,
        "bpm_max": row.bpm_max,
        "eau_l": row.eau_l,
    }


def biometrie_chart(db: Session, utilisateur_id: int, params: ChartParams) -> dict[str, Any]:
    _validate_metric(params.metric, BIOMETRIE_METRICS)
    metric_col = getattr(MesureBiometrique, params.metric)
    bucket = _bucket_expr(MesureBiometrique.mesure_le, params.granularity).label("bucket")

    stmt = select(
        bucket,
        func.avg(metric_col).label("value"),
        func.count(MesureBiometrique.mesure_id).label("count"),
    ).where(MesureBiometrique.utilisateur_id == utilisateur_id)
    stmt = _apply_date_range(stmt, MesureBiometrique.mesure_le, params)
    stmt = stmt.group_by("bucket").order_by("bucket")

    rows = db.execute(stmt).all()
    points = [
        {"bucket": str(r.bucket), "value": float(r.value) if r.value is not None else None, "count": int(r.count)}
        for r in rows
    ]
    return {"metric": params.metric, "granularity": params.granularity, "points": points}


# ---------- sommeil ----------


def latest_sommeil(db: Session, utilisateur_id: int) -> dict[str, Any] | None:
    row = db.execute(
        select(MesureSommeilSante)
        .where(MesureSommeilSante.utilisateur_id == utilisateur_id)
        .order_by(MesureSommeilSante.mesure_le.desc())
        .limit(1)
    ).scalar_one_or_none()
    if not row:
        return None
    return {
        "mesure_sommeil_id": row.mesure_sommeil_id,
        "mesure_le": row.mesure_le,
        "duree_sommeil_h": row.duree_sommeil_h,
        "qualite_sommeil_score": row.qualite_sommeil_score,
        "stress_score": row.stress_score,
        "pas_jour": row.pas_jour,
        "frequence_cardiaque_bpm": row.frequence_cardiaque_bpm,
        "activite_physique_min_jour": row.activite_physique_min_jour,
        "tension_systolique": row.tension_systolique,
        "tension_diastolique": row.tension_diastolique,
        "trouble_sommeil_normalise": row.trouble_sommeil_normalise,
    }


def sommeil_chart(db: Session, utilisateur_id: int, params: ChartParams) -> dict[str, Any]:
    _validate_metric(params.metric, SOMMEIL_METRICS)
    metric_col = getattr(MesureSommeilSante, params.metric)
    bucket = _bucket_expr(MesureSommeilSante.mesure_le, params.granularity).label("bucket")

    stmt = select(
        bucket,
        func.avg(metric_col).label("value"),
        func.count(MesureSommeilSante.mesure_sommeil_id).label("count"),
    ).where(MesureSommeilSante.utilisateur_id == utilisateur_id)
    stmt = _apply_date_range(stmt, MesureSommeilSante.mesure_le, params)
    stmt = stmt.group_by("bucket").order_by("bucket")

    rows = db.execute(stmt).all()
    points = [
        {"bucket": str(r.bucket), "value": float(r.value) if r.value is not None else None, "count": int(r.count)}
        for r in rows
    ]
    return {"metric": params.metric, "granularity": params.granularity, "points": points}


# ---------- objectif actif ----------


def objectif_actif(db: Session, utilisateur_id: int) -> dict[str, Any] | None:
    row = db.execute(
        select(ObjectifUtilisateur)
        .where(
            ObjectifUtilisateur.utilisateur_id == utilisateur_id,
            ObjectifUtilisateur.actif_unique.is_(True),
        )
        .order_by(ObjectifUtilisateur.objectif_id.desc())
        .limit(1)
    ).scalar_one_or_none()
    if not row:
        return None
    return {
        "objectif_id": row.objectif_id,
        "type_objectif": row.type_objectif,
        "poids_cible_kg": row.poids_cible_kg,
        "statut_objectif": row.statut_objectif,
        "date_debut": row.date_debut,
        "date_fin": row.date_fin,
        "actif_unique": bool(row.actif_unique),
        "commentaire": row.commentaire,
    }


def latest_progress_photo(
    db: Session,
    utilisateur_id: int,
    preferred_type: str | None = "AFTER",
) -> dict[str, Any] | None:
    stmt = (
        select(ProgressionPhoto)
        .where(ProgressionPhoto.utilisateur_id == utilisateur_id)
        .order_by(ProgressionPhoto.prise_le.desc(), ProgressionPhoto.photo_id.desc())
    )
    if preferred_type:
        preferred = db.execute(
            stmt.where(ProgressionPhoto.type_photo == preferred_type).limit(1)
        ).scalar_one_or_none()
        if preferred is not None:
            return {
                "photo_id": preferred.photo_id,
                "objectif_id": preferred.objectif_id,
                "type_photo": preferred.type_photo,
                "image_path": preferred.image_path,
                "image_url": media_url("progression", preferred.image_path),
                "photo_url": media_url("progression", preferred.image_path),
                "prise_le": preferred.prise_le,
                "commentaire": getattr(preferred, "commentaire", None),
            }
    row = db.execute(stmt.limit(1)).scalar_one_or_none()
    if row is None:
        return None
    return {
        "photo_id": row.photo_id,
        "objectif_id": row.objectif_id,
        "type_photo": row.type_photo,
        "image_path": row.image_path,
        "image_url": media_url("progression", row.image_path),
        "photo_url": media_url("progression", row.image_path),
        "prise_le": row.prise_le,
        "commentaire": getattr(row, "commentaire", None),
    }


def profile_payload(db: Session, user: Utilisateur) -> dict[str, Any]:
    organisation = None
    if user.organisation_id:
        org = db.get(Organisation, user.organisation_id)
        if org is not None:
            organisation = {"organisation_id": org.organisation_id, "nom": org.nom}
    photo = latest_progress_photo(db, user.utilisateur_id, preferred_type="AFTER")
    avatar_url = media_url("avatars", user.photo_profil_path)
    bio = latest_biometrie(db, user.utilisateur_id)
    sleep = latest_sommeil(db, user.utilisateur_id)
    objective = objectif_actif(db, user.utilisateur_id)
    return {
        "utilisateur_id": user.utilisateur_id,
        "organisation_id": user.organisation_id,
        "nom_utilisateur": user.nom_utilisateur,
        "prenom": user.prenom,
        "nom": user.nom,
        "email": user.email,
        "date_naissance": user.date_naissance,
        "genre": user.genre,
        "age": compute_age(user.date_naissance),
        "taille_cm": user.taille_cm,
        "poids_actuel_kg": bio["poids_kg"] if bio else None,
        "imc": bio["imc"] if bio else None,
        "photo_profil_path": user.photo_profil_path,
        "photo_profil_url": avatar_url or (photo["photo_url"] if photo else None),
        "niveau_activite": user.niveau_activite,
        "niveau_sportif": user.niveau_sportif,
        "allergies_json": user.allergies_json,
        "allergies": json_list(user.allergies_json),
        "regime_alimentaire": user.regime_alimentaire,
        "preferences_alimentaires_json": user.preferences_alimentaires_json,
        "preferences_alimentaires": json_list(user.preferences_alimentaires_json),
        "aliments_evites_json": user.aliments_evites_json,
        "aliments_evites": json_list(user.aliments_evites_json),
        "budget_alimentaire": user.budget_alimentaire,
        "equipements_json": user.equipements_json,
        "equipements": json_list(user.equipements_json),
        "contraintes_sante_json": user.contraintes_sante_json,
        "contraintes_sante": json_list(user.contraintes_sante_json),
        "preferences_sportives_json": user.preferences_sportives_json,
        "preferences_sportives": json_list(user.preferences_sportives_json),
        "frequence_seances_hebdo": user.frequence_seances_hebdo,
        "duree_seance_min": user.duree_seance_min,
        "duree_sommeil_h": sleep["duree_sommeil_h"] if sleep else None,
        "qualite_sommeil_score": sleep["qualite_sommeil_score"] if sleep else None,
        "objectif_principal": objective["type_objectif"] if objective else None,
        "poids_cible_kg": objective["poids_cible_kg"] if objective else None,
        "date_cible": objective["date_fin"] if objective else None,
        "onboarding_complete": bool(user.onboarding_complete),
        "onboarding_complete_le": user.onboarding_complete_le,
        "role": user.role,
        "statut": user.statut,
        "cree_le": user.cree_le,
        "modifie_le": user.modifie_le,
        "organisation": organisation,
        "organisation_nom": organisation["nom"] if organisation else None,
        "photo_profil": photo,
    }


# ---------- KPI synthèse ----------


def user_kpis(db: Session, utilisateur_id: int) -> dict[str, Any]:
    today = date.today()
    thirty_days_ago = datetime.combine(today - timedelta(days=30), datetime.min.time())
    start_of_day = datetime.combine(today, datetime.min.time())
    end_of_day = start_of_day + timedelta(days=1)

    bio = latest_biometrie(db, utilisateur_id)
    som = latest_sommeil(db, utilisateur_id)
    obj = objectif_actif(db, utilisateur_id)

    seances_30j = db.scalar(
        select(func.count(SeanceEntrainement.seance_id)).where(
            SeanceEntrainement.utilisateur_id == utilisateur_id,
            SeanceEntrainement.date_seance >= thirty_days_ago,
        )
    ) or 0

    calories_brulees_30j = db.scalar(
        select(func.coalesce(func.sum(SeanceEntrainement.calories_brulees_total), 0)).where(
            SeanceEntrainement.utilisateur_id == utilisateur_id,
            SeanceEntrainement.date_seance >= thirty_days_ago,
        )
    ) or 0

    calories_jour = db.scalar(
        select(func.coalesce(func.sum(JournalAlimentaire.calories_kcal), 0)).where(
            JournalAlimentaire.utilisateur_id == utilisateur_id,
            JournalAlimentaire.consomme_le >= start_of_day,
            JournalAlimentaire.consomme_le < end_of_day,
        )
    ) or 0

    photos_total = db.scalar(
        select(func.count(ProgressionPhoto.photo_id)).where(
            ProgressionPhoto.utilisateur_id == utilisateur_id,
        )
    ) or 0

    # nb plats sur 30j (utile pour le dashboard mais pas dans UserKpis ; on l'expose en bonus)
    plats_30j = db.scalar(
        select(func.count(Plat.plat_id)).where(
            Plat.utilisateur_id == utilisateur_id,
            Plat.consomme_le >= thirty_days_ago,
        )
    ) or 0

    return {
        "poids_kg": bio["poids_kg"] if bio else None,
        "imc": bio["imc"] if bio else None,
        "derniere_mesure_le": bio["mesure_le"] if bio else None,
        "duree_sommeil_h": som["duree_sommeil_h"] if som else None,
        "dernier_sommeil_le": som["mesure_le"] if som else None,
        "seances_30j": int(seances_30j),
        "calories_brulees_30j": float(calories_brulees_30j),
        "calories_consommees_jour": float(calories_jour),
        "objectif_actif": obj,
        "photos_total": int(photos_total),
        "plats_30j": int(plats_30j),
    }
