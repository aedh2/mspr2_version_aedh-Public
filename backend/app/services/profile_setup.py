from __future__ import annotations

import json
import unicodedata
from datetime import date, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import ApiError
from app.db.models import MesureBiometrique, MesureSommeilSante, ObjectifUtilisateur, Utilisateur


ACTIVITY_MINUTES = {
    "sedentaire": 15,
    "leger": 30,
    "modere": 45,
    "actif": 60,
    "tres_actif": 90,
}

OBJECTIF_TYPE_ALIASES = {
    "MUSCLE": "GAIN_MUSCLE",
    "PRISE_MUSCLE": "GAIN_MUSCLE",
    "PRISE_DE_MASSE": "GAIN_MUSCLE",
    "PRISE MASSE": "GAIN_MUSCLE",
    "PRISE DE MASSE": "GAIN_MUSCLE",
    "ACTIVITE": "MAINTIEN_FORME",
    "MAINTIEN": "MAINTIEN_FORME",
    "SANTE": "EQUILIBRE_VIE",
    "SANTÉ": "EQUILIBRE_VIE",
    "PERFORMANCE": "MAINTIEN_FORME",
    "PERTE DE POIDS": "PERTE_POIDS",
    "EQUILIBRE": "EQUILIBRE_VIE",
}

ALLOWED_OBJECTIF_TYPES = {"PERTE_POIDS", "GAIN_MUSCLE", "SOMMEIL", "EQUILIBRE_VIE", "MAINTIEN_FORME", "AUTRE"}


def json_dump_list(values: list[str]) -> str | None:
    cleaned = [str(value).strip() for value in values if str(value).strip()]
    return json.dumps(cleaned, ensure_ascii=False) if cleaned else None


def json_list(value: str | None) -> list[str]:
    if not value:
        return []
    try:
        parsed = json.loads(value)
    except (TypeError, ValueError, json.JSONDecodeError):
        return [part.strip() for part in str(value).replace(";", ",").split(",") if part.strip()]
    if isinstance(parsed, list):
        return [str(item).strip() for item in parsed if str(item).strip()]
    return []


def normalize_key(value: str) -> str:
    without_accents = "".join(
        char for char in unicodedata.normalize("NFKD", value.strip())
        if not unicodedata.combining(char)
    )
    return without_accents.upper().replace("-", "_")


def normalize_objectif_type(value: str) -> str:
    normalized = normalize_key(value)
    normalized = OBJECTIF_TYPE_ALIASES.get(normalized, normalized)
    normalized = normalized.replace(" ", "_")
    normalized = OBJECTIF_TYPE_ALIASES.get(normalized, normalized)
    if normalized not in ALLOWED_OBJECTIF_TYPES:
        raise ApiError(422, "validation_error", "objectif_principal invalide.")
    return normalized


def compute_age(birthdate: date | None, today: date | None = None) -> int | None:
    if birthdate is None:
        return None
    ref = today or date.today()
    return ref.year - birthdate.year - ((ref.month, ref.day) < (birthdate.month, birthdate.day))


def compute_imc(weight_kg: float, height_cm: float) -> float | None:
    height_m = height_cm / 100
    if height_m <= 0:
        return None
    return round(weight_kg / (height_m * height_m), 2)


def imc_category(imc: float | None) -> str | None:
    if imc is None:
        return None
    if imc < 18.5:
        return "Insuffisance ponderale"
    if imc < 25:
        return "Normal"
    if imc < 30:
        return "Surpoids"
    return "Obesite"


def onboarding_objective_comment(objective_type: str, target_weight: float | None) -> str:
    labels = {
        "PERTE_POIDS": "Perte de poids",
        "GAIN_MUSCLE": "Prise de masse",
        "SOMMEIL": "Sommeil",
        "EQUILIBRE_VIE": "Sante et equilibre",
        "MAINTIEN_FORME": "Maintien et performance",
        "AUTRE": "Objectif personnalise",
    }
    label = labels.get(objective_type, "Objectif personnalise")
    if target_weight is not None:
        return f"{label} personnalise via inscription. Poids cible: {target_weight:.1f} kg."
    return f"{label} personnalise via inscription."


def complete_user_profile(db: Session, user: Utilisateur, payload: Any, *, now: datetime | None = None) -> None:
    """Apply the complete HealthAI profile in the current transaction.

    The caller owns commit/rollback. This writes only to existing MSPR tables:
    utilisateur, mesure_biometrique, objectif_utilisateur and mesure_sommeil_sante.
    """

    current_time = now or datetime.utcnow()
    objective_type = normalize_objectif_type(payload.objectif_principal)
    imc = compute_imc(payload.poids_actuel_kg, payload.taille_cm)
    date_naissance = getattr(payload, "date_naissance", None)
    genre = getattr(payload, "genre", None) or "Inconnu"
    niveau_sportif = getattr(payload, "niveau_sportif", None) or "debutant"
    preferences_alimentaires = getattr(payload, "preferences_alimentaires", []) or []
    aliments_evites = getattr(payload, "aliments_evites", []) or []
    budget = getattr(payload, "budget", None)
    equipements = getattr(payload, "equipements", []) or []
    preferences_sportives = getattr(payload, "preferences_sportives", []) or []
    frequence_seances_hebdo = getattr(payload, "frequence_seances_hebdo", None)
    duree_seance_min = getattr(payload, "duree_seance_min", None)
    duree_sommeil_h = getattr(payload, "duree_sommeil_h", None)
    qualite_sommeil_score = getattr(payload, "qualite_sommeil_score", None)

    user.prenom = payload.prenom
    user.nom = payload.nom
    user.date_naissance = date_naissance
    user.genre = genre
    user.taille_cm = payload.taille_cm
    user.niveau_activite = payload.niveau_activite
    user.niveau_sportif = niveau_sportif
    user.allergies_json = json_dump_list(payload.allergies)
    user.regime_alimentaire = payload.regime_alimentaire
    user.preferences_alimentaires_json = json_dump_list(preferences_alimentaires)
    user.aliments_evites_json = json_dump_list(aliments_evites)
    user.budget_alimentaire = budget
    user.equipements_json = json_dump_list(equipements)
    user.contraintes_sante_json = json_dump_list(payload.contraintes_sante)
    user.preferences_sportives_json = json_dump_list(preferences_sportives)
    user.frequence_seances_hebdo = frequence_seances_hebdo
    user.duree_seance_min = duree_seance_min
    user.onboarding_complete = True
    user.onboarding_complete_le = current_time
    user.modifie_le = current_time

    manual_biometrie = db.execute(
        select(MesureBiometrique)
        .where(
            MesureBiometrique.utilisateur_id == user.utilisateur_id,
            MesureBiometrique.source_id.is_(None),
            MesureBiometrique.lot_id.is_(None),
        )
        .order_by(MesureBiometrique.mesure_le.desc(), MesureBiometrique.mesure_id.desc())
        .limit(1)
    ).scalar_one_or_none()
    if manual_biometrie is None:
        manual_biometrie = MesureBiometrique(
            utilisateur_id=user.utilisateur_id,
            mesure_le=current_time,
            cree_le=current_time,
        )
        db.add(manual_biometrie)
    manual_biometrie.mesure_le = current_time
    manual_biometrie.age_source = compute_age(date_naissance)
    manual_biometrie.genre_source = genre
    manual_biometrie.poids_kg = payload.poids_actuel_kg
    manual_biometrie.taille_cm = payload.taille_cm
    manual_biometrie.imc = imc

    active_objective = db.execute(
        select(ObjectifUtilisateur)
        .where(
            ObjectifUtilisateur.utilisateur_id == user.utilisateur_id,
            ObjectifUtilisateur.actif_unique.is_(True),
        )
        .order_by(ObjectifUtilisateur.objectif_id.desc())
        .limit(1)
    ).scalar_one_or_none()
    if active_objective is None:
        active_objective = ObjectifUtilisateur(
            utilisateur_id=user.utilisateur_id,
            type_objectif=objective_type,
            date_debut=date.today(),
            date_fin=payload.date_cible,
            actif_unique=True,
            statut_objectif="EN_COURS",
            poids_cible_kg=payload.poids_cible_kg,
            commentaire=onboarding_objective_comment(objective_type, payload.poids_cible_kg),
            cree_le=current_time,
        )
        db.add(active_objective)
        db.flush()
    else:
        active_objective.type_objectif = objective_type
        active_objective.poids_cible_kg = payload.poids_cible_kg
        active_objective.date_debut = active_objective.date_debut or date.today()
        active_objective.date_fin = payload.date_cible
        active_objective.actif_unique = True
        active_objective.statut_objectif = "EN_COURS"
        active_objective.commentaire = onboarding_objective_comment(objective_type, payload.poids_cible_kg)

    for other_objective in db.execute(
        select(ObjectifUtilisateur).where(
            ObjectifUtilisateur.utilisateur_id == user.utilisateur_id,
            ObjectifUtilisateur.actif_unique.is_(True),
            ObjectifUtilisateur.objectif_id != active_objective.objectif_id,
        )
    ).scalars():
        other_objective.actif_unique = False
        other_objective.statut_objectif = "ARCHIVE"

    if duree_sommeil_h is not None or qualite_sommeil_score is not None:
        manual_sleep = db.execute(
            select(MesureSommeilSante)
            .where(
                MesureSommeilSante.utilisateur_id == user.utilisateur_id,
                MesureSommeilSante.source_id.is_(None),
                MesureSommeilSante.lot_id.is_(None),
            )
            .order_by(MesureSommeilSante.mesure_le.desc(), MesureSommeilSante.mesure_sommeil_id.desc())
            .limit(1)
        ).scalar_one_or_none()
        if manual_sleep is None:
            manual_sleep = MesureSommeilSante(
                utilisateur_id=user.utilisateur_id,
                mesure_le=current_time,
                cree_le=current_time,
            )
            db.add(manual_sleep)
        manual_sleep.mesure_le = current_time
        manual_sleep.genre_source = genre
        manual_sleep.age_source = compute_age(date_naissance)
        manual_sleep.duree_sommeil_h = duree_sommeil_h
        manual_sleep.qualite_sommeil_score = qualite_sommeil_score
        manual_sleep.activite_physique_min_jour = ACTIVITY_MINUTES[payload.niveau_activite]
        manual_sleep.categorie_imc_source = imc_category(imc)
