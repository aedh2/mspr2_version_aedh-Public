"""Admin users : vue enrichie + transition de statut + résumé 360°."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.errors import ApiError
from app.db.models import (
    JournalAlimentaire,
    MesureBiometrique,
    MesureSommeilSante,
    Organisation,
    Plat,
    ProgressionPhoto,
    SeanceEntrainement,
    Utilisateur,
)


_STATUTS_AUTORISES = {"ACTIF", "INACTIF", "SUSPENDU"}


def _serialize_user(u: Utilisateur, organisation: Organisation | None = None) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "utilisateur_id": u.utilisateur_id,
        "organisation_id": u.organisation_id,
        "nom_utilisateur": u.nom_utilisateur,
        "prenom": u.prenom,
        "nom": u.nom,
        "email": u.email,
        "date_naissance": u.date_naissance,
        "genre": u.genre,
        "taille_cm": u.taille_cm,
        "role": u.role,
        "statut": u.statut,
        "gym_external_id": u.gym_external_id,
        "sleep_external_id": u.sleep_external_id,
        "cree_le": u.cree_le,
        "modifie_le": u.modifie_le,
    }
    if organisation:
        payload["organisation"] = {
            "organisation_id": organisation.organisation_id,
            "nom": organisation.nom,
        }
    return payload


def list_users(
    db: Session,
    filters: dict[str, Any],
    page: int,
    page_size: int,
) -> tuple[list[dict[str, Any]], int]:
    stmt = select(Utilisateur, Organisation).join(
        Organisation, Organisation.organisation_id == Utilisateur.organisation_id, isouter=True
    )
    if filters.get("role"):
        stmt = stmt.where(Utilisateur.role == filters["role"])
    if filters.get("statut"):
        stmt = stmt.where(Utilisateur.statut == filters["statut"])
    if filters.get("organisation_id"):
        stmt = stmt.where(Utilisateur.organisation_id == filters["organisation_id"])
    if filters.get("search"):
        like = f"%{filters['search']}%"
        stmt = stmt.where(
            Utilisateur.email.ilike(like)
            | Utilisateur.nom_utilisateur.ilike(like)
            | Utilisateur.prenom.ilike(like)
            | Utilisateur.nom.ilike(like)
        )

    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = db.scalar(count_stmt) or 0

    rows = db.execute(
        stmt.order_by(Utilisateur.utilisateur_id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()

    return [_serialize_user(u, org) for u, org in rows], int(total)


def patch_statut(db: Session, utilisateur_id: int, nouveau_statut: str) -> dict[str, Any]:
    if nouveau_statut not in _STATUTS_AUTORISES:
        raise ApiError(
            422,
            "validation_error",
            f"Statut invalide. Autorisés: {', '.join(sorted(_STATUTS_AUTORISES))}.",
        )
    user = db.get(Utilisateur, utilisateur_id)
    if not user:
        raise ApiError(404, "not_found", "Utilisateur introuvable.")
    user.statut = nouveau_statut
    user.modifie_le = datetime.utcnow()
    db.commit()
    db.refresh(user)
    return _serialize_user(user)


def user_resume(db: Session, utilisateur_id: int) -> dict[str, Any]:
    """Snapshot 360° d'un utilisateur pour la fiche admin."""
    user = db.get(Utilisateur, utilisateur_id)
    if not user:
        raise ApiError(404, "not_found", "Utilisateur introuvable.")
    org = db.get(Organisation, user.organisation_id) if user.organisation_id else None

    nb_mesures_bio = db.scalar(
        select(func.count(MesureBiometrique.mesure_id)).where(MesureBiometrique.utilisateur_id == utilisateur_id)
    ) or 0
    nb_mesures_som = db.scalar(
        select(func.count(MesureSommeilSante.mesure_sommeil_id)).where(MesureSommeilSante.utilisateur_id == utilisateur_id)
    ) or 0
    nb_seances = db.scalar(
        select(func.count(SeanceEntrainement.seance_id)).where(SeanceEntrainement.utilisateur_id == utilisateur_id)
    ) or 0
    nb_plats = db.scalar(
        select(func.count(Plat.plat_id)).where(Plat.utilisateur_id == utilisateur_id)
    ) or 0
    nb_photos = db.scalar(
        select(func.count(ProgressionPhoto.photo_id)).where(ProgressionPhoto.utilisateur_id == utilisateur_id)
    ) or 0
    nb_journal = db.scalar(
        select(func.count(JournalAlimentaire.journal_id)).where(JournalAlimentaire.utilisateur_id == utilisateur_id)
    ) or 0

    derniere_mesure_le = db.scalar(
        select(func.max(MesureBiometrique.mesure_le)).where(MesureBiometrique.utilisateur_id == utilisateur_id)
    )
    dernier_sommeil_le = db.scalar(
        select(func.max(MesureSommeilSante.mesure_le)).where(MesureSommeilSante.utilisateur_id == utilisateur_id)
    )
    derniere_seance_le = db.scalar(
        select(func.max(SeanceEntrainement.date_seance)).where(SeanceEntrainement.utilisateur_id == utilisateur_id)
    )

    return {
        "utilisateur": _serialize_user(user, org),
        "compteurs": {
            "mesures_biometriques": int(nb_mesures_bio),
            "mesures_sommeil": int(nb_mesures_som),
            "seances": int(nb_seances),
            "plats": int(nb_plats),
            "photos": int(nb_photos),
            "lignes_journal": int(nb_journal),
        },
        "derniers_evenements": {
            "derniere_mesure_le": derniere_mesure_le,
            "dernier_sommeil_le": dernier_sommeil_le,
            "derniere_seance_le": derniere_seance_le,
        },
    }
