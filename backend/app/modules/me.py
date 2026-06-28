from __future__ import annotations

import json
import uuid
from datetime import date, datetime
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Body, Depends, File, UploadFile
from pydantic import ValidationError
from sqlalchemy import distinct, func, select
from sqlalchemy.exc import DataError, IntegrityError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import ApiError
from app.core.pagination import (
    PaginationParams,
    apply_search,
    apply_sort,
    filters_echo,
    paginated_response,
    pagination_params,
)
from app.core.security import (
    current_user,
    hash_password_pbkdf2_sha256,
    verify_password,
)
from app.db.models import (
    Aliment,
    JournalAlimentaire,
    MesureBiometrique,
    MesureSommeilSante,
    ObjectifUtilisateur,
    Plat,
    ProgressionPhoto,
    SeanceEntrainement,
    SeanceExercice,
    Utilisateur,
)
from app.db.session import get_db
from app.modules.resources import serialize_model
from app.schemas.auth import ChangePasswordRequest, UpdateProfileRequest
from app.schemas.coach_posture import CoachPostureFeedbackRequest, CoachPostureValidationRequest
from app.schemas.me import ChartParams, chart_params, chart_params_no_metric
from app.schemas.meal_analysis import MealAnalysisRequest
from app.schemas.onboarding import OnboardingRequest
from app.schemas.recommendations import RecommendationEnvelope, RecommendationRequest
from app.services import document_store, me_metrics, me_nutrition, me_sport
from app.services.coach_posture import CoachPostureService
from app.services.meal_analysis import MealAnalysisService
from app.services.profile_setup import complete_user_profile
from app.services.recommendations import RecommendationEngine

router = APIRouter(prefix="/me", tags=["me"])
AVATAR_MAX_BYTES = 5 * 1024 * 1024
AVATAR_DIR_RELATIVE = "uploads/avatars"
AVATAR_MIME_EXTENSIONS = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
}
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
PROFILE_COMPLETION_FIELDS = {
    "poids_actuel_kg",
    "poids_cible_kg",
    "objectif_principal",
    "date_cible",
    "niveau_activite",
    "niveau_sportif",
    "allergies",
    "regime_alimentaire",
    "preferences_alimentaires",
    "aliments_evites",
    "budget",
    "equipements",
    "contraintes_sante",
    "preferences_sportives",
    "frequence_seances_hebdo",
    "duree_seance_min",
    "duree_sommeil_h",
    "qualite_sommeil_score",
}
DIRECT_PROFILE_FIELDS = {"nom", "prenom", "nom_utilisateur", "email", "organisation_id", "taille_cm", "genre", "date_naissance"}


ME_SORT_DEFAULTS: dict[type, dict[str, Any]] = {
    ObjectifUtilisateur: {
        "default": "objectif_id",
        "sortable": ("objectif_id", "date_debut", "date_fin", "type_objectif"),
        "searchable": ("type_objectif", "commentaire"),
    },
    ProgressionPhoto: {
        "default": "photo_id",
        "sortable": ("photo_id", "prise_le", "type_photo"),
        "searchable": ("type_photo",),
    },
    MesureBiometrique: {
        "default": "mesure_id",
        "sortable": ("mesure_id", "mesure_le", "poids_kg", "imc"),
        "searchable": (),
    },
    MesureSommeilSante: {
        "default": "mesure_sommeil_id",
        "sortable": ("mesure_sommeil_id", "mesure_le", "duree_sommeil_h", "qualite_sommeil_score"),
        "searchable": ("trouble_sommeil_normalise",),
    },
    SeanceEntrainement: {
        "default": "seance_id",
        "sortable": ("seance_id", "date_seance", "duree_seance_min", "calories_brulees_total"),
        "searchable": ("type_entrainement",),
    },
    Plat: {
        "default": "plat_id",
        "sortable": ("plat_id", "consomme_le", "calories_totales_kcal", "type_repas"),
        "searchable": ("nom_plat", "type_repas"),
    },
    JournalAlimentaire: {
        "default": "journal_id",
        "sortable": ("journal_id", "consomme_le", "calories_kcal", "type_repas"),
        "searchable": ("aliment_nom_libre", "type_repas"),
    },
}


def _media_root() -> Path:
    settings = get_settings()
    media_root = Path(settings.media_root)
    if media_root.is_absolute():
        return media_root
    for candidate in (Path.cwd() / media_root, Path.cwd().parent / media_root, Path("/app") / media_root):
        if candidate.exists():
            return candidate
    return Path.cwd() / media_root


def _avatar_dir() -> Path:
    target = _media_root() / AVATAR_DIR_RELATIVE
    target.mkdir(parents=True, exist_ok=True)
    return target


def _avatar_relative_path(filename: str) -> str:
    return f"{AVATAR_DIR_RELATIVE}/{filename}"


def _avatar_target_from_relative(relative_path: str | None) -> Path | None:
    if not relative_path:
        return None
    normalized = relative_path.replace("\\", "/").lstrip("/")
    if not normalized.startswith(f"{AVATAR_DIR_RELATIVE}/"):
        return None
    target = (_media_root() / normalized).resolve()
    avatar_root = _avatar_dir().resolve()
    try:
        target.relative_to(avatar_root)
    except ValueError:
        return None
    return target


def _delete_avatar_file(relative_path: str | None) -> None:
    target = _avatar_target_from_relative(relative_path)
    if target and target.is_file():
        target.unlink(missing_ok=True)


def _detect_avatar_extension(content: bytes, content_type: str | None) -> str:
    _ = content_type
    if content.startswith(b"\xff\xd8\xff"):
        return ".jpg"
    if content.startswith(b"\x89PNG\r\n\x1a\n"):
        return ".png"
    if len(content) >= 12 and content[:4] == b"RIFF" and content[8:12] == b"WEBP":
        return ".webp"
    raise ApiError(422, "validation_error", "Format avatar invalide. Formats acceptes: JPG, PNG ou WebP.")


def _json_dump_list(values: list[str]) -> str | None:
    cleaned = [str(value).strip() for value in values if str(value).strip()]
    return json.dumps(cleaned, ensure_ascii=False) if cleaned else None


def _normalize_objectif_type(value: str) -> str:
    normalized = value.strip().upper().replace("-", "_")
    normalized = OBJECTIF_TYPE_ALIASES.get(normalized, normalized)
    normalized = normalized.replace(" ", "_")
    normalized = OBJECTIF_TYPE_ALIASES.get(normalized, normalized)
    if normalized not in ALLOWED_OBJECTIF_TYPES:
        raise ApiError(422, "validation_error", "objectif_principal invalide.")
    return normalized


def _compute_age(birthdate: date | None, today: date | None = None) -> int | None:
    if birthdate is None:
        return None
    ref = today or date.today()
    return ref.year - birthdate.year - ((ref.month, ref.day) < (birthdate.month, birthdate.day))


def _compute_imc(weight_kg: float, height_cm: float) -> float | None:
    height_m = height_cm / 100
    if height_m <= 0:
        return None
    return round(weight_kg / (height_m * height_m), 2)


def _imc_category(imc: float | None) -> str | None:
    if imc is None:
        return None
    if imc < 18.5:
        return "Insuffisance ponderale"
    if imc < 25:
        return "Normal"
    if imc < 30:
        return "Surpoids"
    return "Obesite"


def _onboarding_objective_comment(objective_type: str, target_weight: float | None) -> str:
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
        return f"{label} personnalise via onboarding. Poids cible: {target_weight:.1f} kg."
    return f"{label} personnalise via onboarding."


def _list_owned(model: type, db: Session, user: Utilisateur, pagination: PaginationParams) -> dict[str, Any]:
    meta = ME_SORT_DEFAULTS.get(model, {})
    default_field = meta.get("default") or list(model.__table__.primary_key.columns)[0].name
    sortable = meta.get("sortable") or (default_field,)
    searchable = meta.get("searchable") or ()

    stmt = select(model).where(model.utilisateur_id == user.utilisateur_id)
    stmt = apply_search(stmt, model, pagination, searchable=searchable)
    stmt = apply_sort(stmt, model, pagination, sortable=sortable, default_field=default_field)
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = db.execute(stmt.offset(pagination.offset).limit(pagination.page_size)).scalars().all()
    return paginated_response(
        [serialize_model(row) for row in rows],
        pagination.page,
        pagination.page_size,
        int(total),
        filters=filters_echo(pagination),
    )


@router.get("/profile")
def get_profile(db: Session = Depends(get_db), user: Utilisateur = Depends(current_user)) -> dict[str, Any]:
    return {"data": me_metrics.profile_payload(db, user)}


def _parse_optional_date(value: str | date | None, field_name: str) -> date | None:
    if value in (None, ""):
        return None
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value))
    except ValueError as exc:
        raise ApiError(422, "validation_error", f"{field_name} doit etre au format YYYY-MM-DD.") from exc


def _complete_payload_from_profile_update(db: Session, user: Utilisateur, data: dict[str, Any]) -> OnboardingRequest:
    current = me_metrics.profile_payload(db, user)

    def pick(name: str, fallback: Any = None) -> Any:
        value = data.get(name, current.get(name, fallback))
        return fallback if value is None else value

    return OnboardingRequest(
        prenom=pick("prenom", user.prenom or ""),
        nom=pick("nom", user.nom or ""),
        date_naissance=_parse_optional_date(pick("date_naissance", user.date_naissance), "date_naissance"),
        genre=pick("genre", user.genre or "Inconnu"),
        taille_cm=float(pick("taille_cm", user.taille_cm or 0)),
        poids_actuel_kg=float(pick("poids_actuel_kg", 0)),
        poids_cible_kg=pick("poids_cible_kg", None),
        objectif_principal=pick("objectif_principal", "MAINTIEN_FORME"),
        date_cible=_parse_optional_date(pick("date_cible", None), "date_cible"),
        niveau_activite=pick("niveau_activite", user.niveau_activite or "modere"),
        niveau_sportif=pick("niveau_sportif", user.niveau_sportif or "debutant"),
        allergies=pick("allergies", current.get("allergies") or []),
        regime_alimentaire=pick("regime_alimentaire", user.regime_alimentaire),
        preferences_alimentaires=pick("preferences_alimentaires", current.get("preferences_alimentaires") or []),
        aliments_evites=pick("aliments_evites", current.get("aliments_evites") or []),
        budget=pick("budget", user.budget_alimentaire),
        equipements=pick("equipements", current.get("equipements") or []),
        contraintes_sante=pick("contraintes_sante", current.get("contraintes_sante") or []),
        preferences_sportives=pick("preferences_sportives", current.get("preferences_sportives") or []),
        frequence_seances_hebdo=int(pick("frequence_seances_hebdo", user.frequence_seances_hebdo or 0)),
        duree_seance_min=int(pick("duree_seance_min", user.duree_seance_min or 30)),
        duree_sommeil_h=float(pick("duree_sommeil_h", current.get("duree_sommeil_h") or 0)),
        qualite_sommeil_score=int(pick("qualite_sommeil_score", current.get("qualite_sommeil_score") or 1)),
    )


def _save_avatar(
    file: UploadFile,
    db: Session,
    user: Utilisateur,
) -> dict[str, Any]:
    content = file.file.read(AVATAR_MAX_BYTES + 1)
    if not content:
        raise ApiError(422, "validation_error", "Le fichier avatar est vide.")
    if len(content) > AVATAR_MAX_BYTES:
        raise ApiError(413, "payload_too_large", "La photo de profil doit faire 5 Mo maximum.")
    extension = _detect_avatar_extension(content, file.content_type)
    filename = f"user-{user.utilisateur_id}-{uuid.uuid4().hex}{extension}"
    target = _avatar_dir() / filename
    relative_path = _avatar_relative_path(filename)
    old_path = user.photo_profil_path
    target.write_bytes(content)
    user.photo_profil_path = relative_path
    user.modifie_le = datetime.utcnow()
    try:
        db.commit()
    except Exception:
        db.rollback()
        target.unlink(missing_ok=True)
        raise
    if old_path and old_path != relative_path:
        _delete_avatar_file(old_path)
    db.refresh(user)
    return me_metrics.profile_payload(db, user)


@router.post("/avatar", status_code=201)
def add_avatar(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: Utilisateur = Depends(current_user),
) -> dict[str, Any]:
    return {"data": _save_avatar(file, db, user)}


@router.put("/avatar")
def replace_avatar(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: Utilisateur = Depends(current_user),
) -> dict[str, Any]:
    return {"data": _save_avatar(file, db, user)}


@router.delete("/avatar")
def delete_avatar(
    db: Session = Depends(get_db),
    user: Utilisateur = Depends(current_user),
) -> dict[str, Any]:
    old_path = user.photo_profil_path
    user.photo_profil_path = None
    user.modifie_le = datetime.utcnow()
    db.commit()
    _delete_avatar_file(old_path)
    db.refresh(user)
    return {"data": me_metrics.profile_payload(db, user)}


@router.put("/profile")
def update_profile(
    payload: UpdateProfileRequest,
    db: Session = Depends(get_db),
    user: Utilisateur = Depends(current_user),
) -> dict[str, Any]:
    data = payload.model_dump(exclude_unset=True)
    if "date_naissance" in data and data["date_naissance"] is not None:
        data["date_naissance"] = _parse_optional_date(data["date_naissance"], "date_naissance")
    has_completion_data = bool(PROFILE_COMPLETION_FIELDS.intersection(data.keys()))
    for field, value in data.items():
        if field in DIRECT_PROFILE_FIELDS:
            setattr(user, field, value)
    user.modifie_le = datetime.utcnow()
    try:
        if has_completion_data:
            complete_payload = _complete_payload_from_profile_update(db, user, data)
            complete_user_profile(db, user, complete_payload)
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise ApiError(409, "conflict", "Conflit d'unicite (nom_utilisateur deja pris).") from exc
    except ValidationError as exc:
        db.rollback()
        raise ApiError(422, "validation_error", "Profil invalide.", exc.errors(include_context=False)) from exc
    except DataError as exc:
        db.rollback()
        raise ApiError(422, "validation_error", "Profil invalide pour le schema actuel.") from exc
    db.refresh(user)
    return {"data": me_metrics.profile_payload(db, user)}


@router.post("/onboarding")
def complete_onboarding(
    payload: OnboardingRequest,
    db: Session = Depends(get_db),
    user: Utilisateur = Depends(current_user),
) -> dict[str, Any]:
    now = datetime.utcnow()
    try:
        complete_user_profile(db, user, payload, now=now)
        db.commit()
    except ApiError:
        db.rollback()
        raise
    except (DataError, IntegrityError) as exc:
        db.rollback()
        raise ApiError(422, "validation_error", "Impossible d'enregistrer l'onboarding avec le schema actuel.") from exc

    db.refresh(user)
    return {"data": me_metrics.profile_payload(db, user)}


@router.put("/password")
def update_password(
    payload: ChangePasswordRequest,
    db: Session = Depends(get_db),
    user: Utilisateur = Depends(current_user),
) -> dict[str, Any]:
    if not verify_password(payload.ancien_mot_de_passe, user.mot_de_passe_hash):
        raise ApiError(401, "unauthorized", "Ancien mot de passe incorrect.")
    if payload.ancien_mot_de_passe == payload.nouveau_mot_de_passe:
        raise ApiError(422, "validation_error", "Le nouveau mot de passe doit differer de l'ancien.")
    user.mot_de_passe_hash = hash_password_pbkdf2_sha256(payload.nouveau_mot_de_passe)
    user.modifie_le = datetime.utcnow()
    db.commit()
    return {"data": {"message": "Mot de passe mis a jour."}}


@router.get("/kpis")
def kpis(db: Session = Depends(get_db), user: Utilisateur = Depends(current_user)) -> dict[str, Any]:
    return {"data": me_metrics.user_kpis(db, user.utilisateur_id)}


@router.get("/objectifs/actif")
def objectif_actif(db: Session = Depends(get_db), user: Utilisateur = Depends(current_user)) -> dict[str, Any]:
    obj = me_metrics.objectif_actif(db, user.utilisateur_id)
    if obj is None:
        raise ApiError(404, "not_found", "Aucun objectif actif.")
    return {"data": obj}


def _ensure_owned(db: Session, model: type, item_id: int, user: Utilisateur, pk: str):
    _ = pk
    item = db.get(model, item_id)
    if not item or getattr(item, "utilisateur_id", None) != user.utilisateur_id:
        raise ApiError(404, "not_found", "Ressource introuvable.")
    return item


def _finish_active_objectives(db: Session, utilisateur_id: int) -> None:
    rows = db.execute(
        select(ObjectifUtilisateur).where(
            ObjectifUtilisateur.utilisateur_id == utilisateur_id,
            ObjectifUtilisateur.actif_unique.is_(True),
        )
    ).scalars().all()
    for row in rows:
        row.actif_unique = False
        if row.date_fin is None:
            row.date_fin = date.today()
        if hasattr(row, "statut_objectif") and not row.statut_objectif:
            row.statut_objectif = "ANNULE"


@router.post("/objectifs", status_code=201)
def create_objectif(
    payload: dict[str, Any] = Body(...),
    db: Session = Depends(get_db),
    user: Utilisateur = Depends(current_user),
) -> dict[str, Any]:
    if not payload.get("type_objectif"):
        raise ApiError(422, "validation_error", "type_objectif est requis.")
    type_objectif = str(payload["type_objectif"]).strip().upper()
    type_objectif = OBJECTIF_TYPE_ALIASES.get(type_objectif, type_objectif)
    allowed_types = {"PERTE_POIDS", "GAIN_MUSCLE", "SOMMEIL", "EQUILIBRE_VIE", "MAINTIEN_FORME", "AUTRE"}
    if type_objectif not in allowed_types:
        raise ApiError(422, "validation_error", "type_objectif invalide.")
    _finish_active_objectives(db, user.utilisateur_id)
    obj = ObjectifUtilisateur(
        utilisateur_id=user.utilisateur_id,
        type_objectif=type_objectif,
        date_debut=date.fromisoformat(payload["date_debut"]) if payload.get("date_debut") else date.today(),
        date_fin=date.fromisoformat(payload["date_fin"]) if payload.get("date_fin") else None,
        actif_unique=True,
        statut_objectif="EN_COURS",
        commentaire=payload.get("commentaire"),
        cree_le=datetime.utcnow(),
    )
    db.add(obj)
    try:
        db.commit()
    except DataError as exc:
        db.rollback()
        raise ApiError(422, "validation_error", "type_objectif incompatible avec la base.") from exc
    db.refresh(obj)
    return {"data": serialize_model(obj)}


def _patch_objectif_status(db: Session, user: Utilisateur, objectif_id: int, statut: str) -> dict[str, Any]:
    obj = _ensure_owned(db, ObjectifUtilisateur, objectif_id, user, "objectif_id")
    obj.actif_unique = False
    obj.statut_objectif = statut
    obj.date_fin = date.today()
    db.commit()
    db.refresh(obj)
    return {"data": serialize_model(obj)}


@router.patch("/objectifs/{objectif_id}/reussir")
def reussir_objectif(objectif_id: int, db: Session = Depends(get_db), user: Utilisateur = Depends(current_user)):
    return _patch_objectif_status(db, user, objectif_id, "REUSSI")


@router.patch("/objectifs/{objectif_id}/echouer")
def echouer_objectif(objectif_id: int, db: Session = Depends(get_db), user: Utilisateur = Depends(current_user)):
    return _patch_objectif_status(db, user, objectif_id, "ECHOUE")


@router.patch("/objectifs/{objectif_id}/annuler")
def annuler_objectif(objectif_id: int, db: Session = Depends(get_db), user: Utilisateur = Depends(current_user)):
    return _patch_objectif_status(db, user, objectif_id, "ANNULE")


@router.get("/mesures-biometriques/latest")
def biometrie_latest(db: Session = Depends(get_db), user: Utilisateur = Depends(current_user)) -> dict[str, Any]:
    row = me_metrics.latest_biometrie(db, user.utilisateur_id)
    if row is None:
        raise ApiError(404, "not_found", "Aucune mesure biometrique.")
    return {"data": row}


@router.post("/mesures-biometriques", status_code=201)
def create_biometrie(
    payload: dict[str, Any] = Body(...),
    db: Session = Depends(get_db),
    user: Utilisateur = Depends(current_user),
) -> dict[str, Any]:
    if not payload.get("mesure_le"):
        raise ApiError(422, "validation_error", "mesure_le est requis.")
    data = {k: v for k, v in payload.items() if k in MesureBiometrique.__table__.columns.keys()}
    data.pop("mesure_id", None)
    data["utilisateur_id"] = user.utilisateur_id
    if isinstance(data.get("mesure_le"), str):
        data["mesure_le"] = datetime.fromisoformat(data["mesure_le"].replace("Z", "+00:00")).replace(tzinfo=None)
    if not data.get("taille_cm") and user.taille_cm:
        data["taille_cm"] = user.taille_cm
    if not data.get("imc") and data.get("poids_kg") and data.get("taille_cm"):
        taille_m = float(data["taille_cm"]) / 100
        if taille_m > 0:
            data["imc"] = round(float(data["poids_kg"]) / (taille_m * taille_m), 2)
    data.setdefault("cree_le", datetime.utcnow())
    item = MesureBiometrique(**data)
    db.add(item)
    db.commit()
    db.refresh(item)
    return {"data": serialize_model(item)}


@router.get("/mesures-biometriques/charts")
def biometrie_charts(
    params: ChartParams = Depends(chart_params),
    db: Session = Depends(get_db),
    user: Utilisateur = Depends(current_user),
) -> dict[str, Any]:
    return {"data": me_metrics.biometrie_chart(db, user.utilisateur_id, params)}


@router.get("/sommeil-sante/latest")
def sommeil_latest(db: Session = Depends(get_db), user: Utilisateur = Depends(current_user)) -> dict[str, Any]:
    row = me_metrics.latest_sommeil(db, user.utilisateur_id)
    if row is None:
        raise ApiError(404, "not_found", "Aucune mesure de sommeil.")
    return {"data": row}


@router.get("/sommeil/latest")
def sommeil_latest_alias(db: Session = Depends(get_db), user: Utilisateur = Depends(current_user)) -> dict[str, Any]:
    return sommeil_latest(db, user)


@router.post("/sommeil-sante", status_code=201)
def create_sommeil(
    payload: dict[str, Any] = Body(...),
    db: Session = Depends(get_db),
    user: Utilisateur = Depends(current_user),
) -> dict[str, Any]:
    if not payload.get("mesure_le"):
        raise ApiError(422, "validation_error", "mesure_le est requis.")
    data = {k: v for k, v in payload.items() if k in MesureSommeilSante.__table__.columns.keys()}
    data.pop("mesure_sommeil_id", None)
    data["utilisateur_id"] = user.utilisateur_id
    if isinstance(data.get("mesure_le"), str):
        data["mesure_le"] = datetime.fromisoformat(data["mesure_le"].replace("Z", "+00:00")).replace(tzinfo=None)
    data.setdefault("cree_le", datetime.utcnow())
    item = MesureSommeilSante(**data)
    db.add(item)
    db.commit()
    db.refresh(item)
    return {"data": serialize_model(item)}


@router.post("/sommeil", status_code=201)
def create_sommeil_alias(
    payload: dict[str, Any] = Body(...),
    db: Session = Depends(get_db),
    user: Utilisateur = Depends(current_user),
) -> dict[str, Any]:
    return create_sommeil(payload, db, user)


@router.get("/sommeil-sante/charts")
def sommeil_charts(
    params: ChartParams = Depends(chart_params),
    db: Session = Depends(get_db),
    user: Utilisateur = Depends(current_user),
) -> dict[str, Any]:
    return {"data": me_metrics.sommeil_chart(db, user.utilisateur_id, params)}


@router.get("/sommeil/charts")
def sommeil_charts_alias(
    params: ChartParams = Depends(chart_params),
    db: Session = Depends(get_db),
    user: Utilisateur = Depends(current_user),
) -> dict[str, Any]:
    return sommeil_charts(params, db, user)


@router.get("/seances/kpis")
def seances_kpis(db: Session = Depends(get_db), user: Utilisateur = Depends(current_user)) -> dict[str, Any]:
    return {"data": me_sport.seances_kpis(db, user.utilisateur_id)}


@router.get("/seances/charts")
def seances_charts(
    params: ChartParams = Depends(chart_params_no_metric),
    db: Session = Depends(get_db),
    user: Utilisateur = Depends(current_user),
) -> dict[str, Any]:
    return {"data": me_sport.seances_chart(db, user.utilisateur_id, params)}


@router.get("/seances/filters")
def seances_filters(db: Session = Depends(get_db), user: Utilisateur = Depends(current_user)) -> dict[str, Any]:
    types_entrainement = sorted(
        v[0]
        for v in db.execute(
            select(distinct(SeanceEntrainement.type_entrainement)).where(
                SeanceEntrainement.utilisateur_id == user.utilisateur_id,
                SeanceEntrainement.type_entrainement.is_not(None),
            )
        ).all()
        if v[0]
    )
    niveaux = sorted(
        v[0]
        for v in db.execute(
            select(distinct(SeanceEntrainement.niveau_experience)).where(
                SeanceEntrainement.utilisateur_id == user.utilisateur_id,
                SeanceEntrainement.niveau_experience.is_not(None),
            )
        ).all()
        if v[0]
    )
    return {"data": {"types_entrainement": types_entrainement, "niveaux_experience": niveaux}}


@router.post("/seances", status_code=201)
def create_seance(
    payload: dict[str, Any] = Body(...),
    db: Session = Depends(get_db),
    user: Utilisateur = Depends(current_user),
) -> dict[str, Any]:
    if not payload.get("date_seance"):
        raise ApiError(422, "validation_error", "date_seance est requis.")
    data = {k: v for k, v in payload.items() if k in SeanceEntrainement.__table__.columns.keys()}
    data.pop("seance_id", None)
    data["utilisateur_id"] = user.utilisateur_id
    if isinstance(data.get("date_seance"), str):
        data["date_seance"] = datetime.fromisoformat(data["date_seance"].replace("Z", "+00:00")).replace(tzinfo=None)
    data.setdefault("cree_le", datetime.utcnow())
    item = SeanceEntrainement(**data)
    db.add(item)
    db.commit()
    db.refresh(item)
    return {"data": serialize_model(item)}


@router.get("/seances/{seance_id}/exercices")
def seance_exercices(
    seance_id: int,
    db: Session = Depends(get_db),
    user: Utilisateur = Depends(current_user),
) -> dict[str, Any]:
    return {"data": me_sport.list_seance_exercices(db, user.utilisateur_id, seance_id)}


@router.post("/seances/{seance_id}/exercices", status_code=201)
def add_seance_exercice(
    seance_id: int,
    payload: dict[str, Any] = Body(...),
    db: Session = Depends(get_db),
    user: Utilisateur = Depends(current_user),
) -> dict[str, Any]:
    _ensure_owned(db, SeanceEntrainement, seance_id, user, "seance_id")
    if not payload.get("exercice_id"):
        raise ApiError(422, "validation_error", "exercice_id est requis.")
    data = {k: v for k, v in payload.items() if k in SeanceExercice.__table__.columns.keys()}
    data.pop("seance_exercice_id", None)
    data["seance_id"] = seance_id
    numeric_int_fields = {"exercice_id", "ordre_exercice", "series_nb", "repetitions_nb"}
    numeric_float_fields = {"charge_kg", "duree_min", "calories_brulees_estimees"}
    for field in numeric_int_fields:
        value = data.get(field)
        if value in ("", None):
            data[field] = None
        elif isinstance(value, str):
            data[field] = int(value)
    for field in numeric_float_fields:
        value = data.get(field)
        if value in ("", None):
            data[field] = None
        elif isinstance(value, str):
            data[field] = float(value)
    if data.get("ordre_exercice") is None:
        current_max = db.scalar(select(func.max(SeanceExercice.ordre_exercice)).where(SeanceExercice.seance_id == seance_id))
        data["ordre_exercice"] = int(current_max or 0) + 1
    data.setdefault("cree_le", datetime.utcnow())
    item = SeanceExercice(**data)
    db.add(item)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise ApiError(409, "conflict", "Impossible d'ajouter cet exercice a la seance.", str(exc.orig)) from exc
    db.refresh(item)
    return {"data": serialize_model(item)}


@router.get("/seances/{seance_id}")
def seance_detail(
    seance_id: int,
    db: Session = Depends(get_db),
    user: Utilisateur = Depends(current_user),
) -> dict[str, Any]:
    return {"data": me_sport.get_seance(db, user.utilisateur_id, seance_id)}


@router.get("/nutrition/charts")
def nutrition_charts(
    params: ChartParams = Depends(chart_params_no_metric),
    db: Session = Depends(get_db),
    user: Utilisateur = Depends(current_user),
) -> dict[str, Any]:
    return {"data": me_nutrition.nutrition_charts(db, user.utilisateur_id, params)}


@router.get("/analyse-plat/config")
def analyse_plat_config(user: Utilisateur = Depends(current_user)) -> dict[str, Any]:
    _ = user.utilisateur_id
    service = MealAnalysisService(get_settings())
    return {"data": service.config_payload().model_dump()}


@router.post("/analyse-plat")
def analyse_plat(
    payload: MealAnalysisRequest,
    db: Session = Depends(get_db),
    user: Utilisateur = Depends(current_user),
) -> dict[str, Any]:
    service = MealAnalysisService(get_settings())
    result = service.analyze(db, payload.image_base64, payload.mime_type).model_dump()
    # Persistance NoSQL (MongoDB): trace documentaire de l'analyse.
    analyse_id = document_store.save_meal_analysis(user.utilisateur_id, result, source="huggingface")
    if analyse_id:
        result["analyse_id"] = analyse_id
    return {"data": result}


@router.post("/coach-posture/feedback")
def coach_posture_feedback(
    payload: CoachPostureFeedbackRequest,
    user: Utilisateur = Depends(current_user),
) -> dict[str, Any]:
    _ = user.utilisateur_id
    service = CoachPostureService(get_settings())
    return {"data": service.feedback(payload).model_dump()}


@router.get("/coach-posture/history")
def coach_posture_history(
    db: Session = Depends(get_db),
    user: Utilisateur = Depends(current_user),
) -> dict[str, Any]:
    service = CoachPostureService(get_settings())
    return {"data": [item.model_dump(mode="json") for item in service.recent_history(db, user)]}


@router.post("/coach-posture/validate")
def coach_posture_validate(
    payload: CoachPostureValidationRequest,
    db: Session = Depends(get_db),
    user: Utilisateur = Depends(current_user),
) -> dict[str, Any]:
    service = CoachPostureService(get_settings())
    return {"data": service.validate_exercise(db, user, payload).model_dump()}


@router.post("/recommandations", response_model=RecommendationEnvelope)
def recommandations(
    payload: RecommendationRequest | None = Body(default=None),
    db: Session = Depends(get_db),
    user: Utilisateur = Depends(current_user),
) -> dict[str, Any]:
    request = payload or RecommendationRequest()
    service = RecommendationEngine()
    result = service.build(db, user, request)
    # Persistance NoSQL (MongoDB): document de recommandation complet.
    document_store.save_recommendation(user.utilisateur_id, result.model_dump(mode="json"), source="local_rules")
    return {"data": result}


@router.post("/plats", status_code=201)
def create_plat(
    payload: dict[str, Any] = Body(...),
    db: Session = Depends(get_db),
    user: Utilisateur = Depends(current_user),
) -> dict[str, Any]:
    if not payload.get("consomme_le"):
        raise ApiError(422, "validation_error", "consomme_le est requis.")
    data = {k: v for k, v in payload.items() if k in Plat.__table__.columns.keys()}
    data.pop("plat_id", None)
    data["utilisateur_id"] = user.utilisateur_id
    if isinstance(data.get("consomme_le"), str):
        data["consomme_le"] = datetime.fromisoformat(data["consomme_le"].replace("Z", "+00:00")).replace(tzinfo=None)
    data.setdefault("cree_le", datetime.utcnow())
    item = Plat(**data)
    db.add(item)
    db.commit()
    db.refresh(item)
    return {"data": serialize_model(item)}


@router.get("/plats/{plat_id}/lignes")
def plat_lignes(
    plat_id: int,
    db: Session = Depends(get_db),
    user: Utilisateur = Depends(current_user),
) -> dict[str, Any]:
    return {"data": me_nutrition.list_plat_lignes(db, user.utilisateur_id, plat_id)}


@router.post("/plats/{plat_id}/lignes", status_code=201)
def add_plat_ligne(
    plat_id: int,
    payload: dict[str, Any] = Body(...),
    db: Session = Depends(get_db),
    user: Utilisateur = Depends(current_user),
) -> dict[str, Any]:
    plat = _ensure_owned(db, Plat, plat_id, user, "plat_id")
    if not payload.get("aliment_id") and not payload.get("aliment_nom_libre"):
        raise ApiError(422, "validation_error", "aliment_id ou aliment_nom_libre est requis.")
    data = {k: v for k, v in payload.items() if k in JournalAlimentaire.__table__.columns.keys()}
    data.pop("journal_id", None)
    data["utilisateur_id"] = user.utilisateur_id
    data["plat_id"] = plat_id
    data.setdefault("consomme_le", plat.consomme_le)
    data.setdefault("type_repas", plat.type_repas)
    aliment = None
    if data.get("aliment_id"):
        aliment = db.get(Aliment, int(data["aliment_id"]))
        if aliment is None:
            raise ApiError(404, "not_found", "Aliment introuvable.")
        computed = me_nutrition.compute_line_from_aliment(
            aliment,
            quantite=float(data.get("quantite") or 0) if data.get("quantite") is not None else None,
            unite_quantite=str(data.get("unite_quantite") or ""),
        )
        if data.get("calories_kcal") in (None, "", 0):
            data["calories_kcal"] = computed["calories_kcal"]
        if data.get("eau_ml") in (None, "", 0):
            data["eau_ml"] = computed["eau_ml"]
        data.setdefault("aliment_nom_libre", aliment.nom)
    if isinstance(data.get("consomme_le"), str):
        data["consomme_le"] = datetime.fromisoformat(data["consomme_le"].replace("Z", "+00:00")).replace(tzinfo=None)
    data.setdefault("cree_le", datetime.utcnow())
    item = JournalAlimentaire(**data)
    db.add(item)
    db.flush()
    total = db.scalar(
        select(func.coalesce(func.sum(JournalAlimentaire.calories_kcal), 0)).where(
            JournalAlimentaire.plat_id == plat_id
        )
    ) or 0
    plat.calories_totales_kcal = float(total)
    db.commit()
    db.refresh(item)
    return {"data": serialize_model(item)}


@router.get("/plats/{plat_id}")
def plat_detail(
    plat_id: int,
    db: Session = Depends(get_db),
    user: Utilisateur = Depends(current_user),
) -> dict[str, Any]:
    return {"data": me_nutrition.get_plat(db, user.utilisateur_id, plat_id)}


@router.get("/objectifs")
def objectifs(
    pagination: PaginationParams = Depends(pagination_params),
    db: Session = Depends(get_db),
    user: Utilisateur = Depends(current_user),
):
    return _list_owned(ObjectifUtilisateur, db, user, pagination)


@router.get("/photos")
def photos(
    pagination: PaginationParams = Depends(pagination_params),
    db: Session = Depends(get_db),
    user: Utilisateur = Depends(current_user),
):
    return _list_owned(ProgressionPhoto, db, user, pagination)


@router.get("/photos-progression")
def photos_progression(
    pagination: PaginationParams = Depends(pagination_params),
    db: Session = Depends(get_db),
    user: Utilisateur = Depends(current_user),
):
    return _list_owned(ProgressionPhoto, db, user, pagination)


@router.get("/mesures-biometriques")
def mesures_biometriques(
    pagination: PaginationParams = Depends(pagination_params),
    db: Session = Depends(get_db),
    user: Utilisateur = Depends(current_user),
):
    return _list_owned(MesureBiometrique, db, user, pagination)


@router.get("/sommeil-sante")
def sommeil_sante(
    pagination: PaginationParams = Depends(pagination_params),
    db: Session = Depends(get_db),
    user: Utilisateur = Depends(current_user),
):
    return _list_owned(MesureSommeilSante, db, user, pagination)


@router.get("/seances")
def seances(
    pagination: PaginationParams = Depends(pagination_params),
    db: Session = Depends(get_db),
    user: Utilisateur = Depends(current_user),
):
    return _list_owned(SeanceEntrainement, db, user, pagination)


@router.get("/plats")
def plats(
    pagination: PaginationParams = Depends(pagination_params),
    db: Session = Depends(get_db),
    user: Utilisateur = Depends(current_user),
):
    return _list_owned(Plat, db, user, pagination)


@router.get("/journal-alimentaire")
def journal_alimentaire(
    pagination: PaginationParams = Depends(pagination_params),
    db: Session = Depends(get_db),
    user: Utilisateur = Depends(current_user),
):
    return _list_owned(JournalAlimentaire, db, user, pagination)
