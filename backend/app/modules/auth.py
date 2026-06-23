from __future__ import annotations

from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, Query, Request, Response
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import ApiError
from app.core.logging import bind_context
from app.core.rate_limit import limiter
from app.core.security import (
    authenticate_user,
    create_token,
    current_user,
    current_user_from_refresh,
    decode_token,
    hash_password_pbkdf2_sha256,
)
from app.db.models import (
    CoachPostureSession,
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
from app.db.session import get_db
from app.modules.resources import serialize_model
from app.schemas.auth import (
    ForgotPasswordRequest,
    LoginRequest,
    RegisterAvailabilityResponse,
    RegisterCompleteRequest,
    RegisterRequest,
    ResetPasswordRequest,
)
from app.services import me_metrics
from app.services.profile_setup import complete_user_profile

router = APIRouter(prefix="/auth", tags=["auth"])


def _set_refresh_cookie(response: Response, user: Utilisateur) -> None:
    settings = get_settings()
    refresh_token = create_token(
        str(user.utilisateur_id),
        "refresh",
        timedelta(days=settings.refresh_token_days),
        {"role": user.role},
    )
    response.set_cookie(
        "refresh_token",
        refresh_token,
        httponly=True,
        secure=settings.environment == "production",
        samesite="strict",
        max_age=settings.refresh_token_days * 24 * 60 * 60,
    )


def _token_response(user: Utilisateur, *, include_user: bool = False) -> dict:
    settings = get_settings()
    token = create_token(
        str(user.utilisateur_id),
        "access",
        timedelta(minutes=settings.access_token_minutes),
        {"role": user.role},
    )
    data = {"access_token": token, "token_type": "bearer"}
    if include_user:
        data["user"] = serialize_model(user)
    return {"data": data}


def _resolve_organisation_id(db: Session, organisation_id: int | None) -> int | None:
    if organisation_id is not None:
        if db.get(Organisation, organisation_id) is None:
            raise ApiError(422, "validation_error", "Organisation introuvable.")
        return organisation_id
    if db.get(Organisation, 1) is not None:
        return 1
    return None


def _related_user_rows_count(db: Session, utilisateur_id: int) -> int:
    related_models = (
        MesureBiometrique,
        MesureSommeilSante,
        ObjectifUtilisateur,
        Plat,
        JournalAlimentaire,
        SeanceEntrainement,
        ProgressionPhoto,
        CoachPostureSession,
    )
    total = 0
    for model in related_models:
        total += int(db.scalar(select(func.count()).where(model.utilisateur_id == utilisateur_id)) or 0)
    return total


def _is_incomplete_registration(user: Utilisateur) -> bool:
    return user.role == "UTILISATEUR" and not bool(user.onboarding_complete)


def _safe_deletion_possible(db: Session, user: Utilisateur) -> bool:
    return _is_incomplete_registration(user) and _related_user_rows_count(db, user.utilisateur_id) == 0


def _credential_error_for_user(db: Session, user: Utilisateur, field: str) -> ApiError:
    if _is_incomplete_registration(user):
        safe = _safe_deletion_possible(db, user)
        suffix = " Suppression sure possible via la procedure de nettoyage." if safe else " Reprise ou analyse manuelle recommandee."
        if field == "username":
            return ApiError(
                409,
                "username_incomplete",
                "Cet identifiant correspond a un compte incomplet existant." + suffix,
                {"safe_deletion_possible": safe},
            )
        return ApiError(
            409,
            "email_incomplete",
            "Cet email correspond a un compte incomplet existant." + suffix,
            {"safe_deletion_possible": safe},
        )
    if field == "username":
        return ApiError(409, "username_taken", "Cet identifiant est deja utilise.")
    return ApiError(409, "email_taken", "Cet email est deja utilise.")


def _ensure_credentials_available(db: Session, nom_utilisateur: str, email: str) -> None:
    username_user = db.execute(
        select(Utilisateur).where(Utilisateur.nom_utilisateur == nom_utilisateur).limit(1)
    ).scalar_one_or_none()
    if username_user:
        raise _credential_error_for_user(db, username_user, "username")

    email_user = db.execute(
        select(Utilisateur).where(Utilisateur.email == email).limit(1)
    ).scalar_one_or_none()
    if email_user:
        raise _credential_error_for_user(db, email_user, "email")


def _raise_integrity_error(db: Session, exc: IntegrityError, nom_utilisateur: str, email: str) -> None:
    text = str(exc.orig).lower()
    if "nom_utilisateur" in text or "username" in text:
        user = db.execute(select(Utilisateur).where(Utilisateur.nom_utilisateur == nom_utilisateur).limit(1)).scalar_one_or_none()
        if user:
            raise _credential_error_for_user(db, user, "username") from exc
        raise ApiError(409, "username_taken", "Cet identifiant est deja utilise.") from exc
    if "email" in text:
        user = db.execute(select(Utilisateur).where(Utilisateur.email == email).limit(1)).scalar_one_or_none()
        if user:
            raise _credential_error_for_user(db, user, "email") from exc
        raise ApiError(409, "email_taken", "Cet email est deja utilise.") from exc
    raise ApiError(
        422,
        "profile_integrity_error",
        "La creation du profil ne respecte pas le schema de base. Consultez les logs backend.",
    ) from exc


@router.post("/login")
@limiter.limit("10/minute")
def login(
    request: Request,
    payload: LoginRequest,
    response: Response,
    db: Session = Depends(get_db),
) -> dict:
    user = authenticate_user(db, payload.identifiant, payload.mot_de_passe)
    if not user:
        raise ApiError(401, "unauthorized", "Identifiants invalides.")
    _set_refresh_cookie(response, user)
    return _token_response(user)


@router.get("/register-availability")
def register_availability(
    nom_utilisateur: str | None = Query(default=None, min_length=1, max_length=120),
    email: str | None = Query(default=None, min_length=3, max_length=255),
    db: Session = Depends(get_db),
) -> dict:
    if not nom_utilisateur and not email:
        raise ApiError(422, "validation_error", "Renseignez un nom d'utilisateur ou un email.")

    response = RegisterAvailabilityResponse()
    if nom_utilisateur:
        user = db.execute(
            select(Utilisateur)
            .where(Utilisateur.nom_utilisateur == nom_utilisateur.strip())
            .limit(1)
        ).scalar_one_or_none()
        response.nom_utilisateur_disponible = user is None
        if user is not None:
            response.nom_utilisateur_compte_incomplet = _is_incomplete_registration(user)
            response.nom_utilisateur_suppression_sure_possible = _safe_deletion_possible(db, user)
            response.nom_utilisateur_message = (
                "Compte incomplet existant pour cet identifiant."
                if response.nom_utilisateur_compte_incomplet
                else "Identifiant deja utilise."
            )
    if email:
        normalized_email = email.strip().lower()
        user = db.execute(
            select(Utilisateur)
            .where(Utilisateur.email == normalized_email)
            .limit(1)
        ).scalar_one_or_none()
        response.email_disponible = user is None
        if user is not None:
            response.email_compte_incomplet = _is_incomplete_registration(user)
            response.email_suppression_sure_possible = _safe_deletion_possible(db, user)
            response.email_message = (
                "Compte incomplet existant pour cet email."
                if response.email_compte_incomplet
                else "Email deja utilise."
            )
    return {"data": response.model_dump()}


@router.post("/register-complete", status_code=201)
@limiter.limit("10/minute")
def register_complete(
    request: Request,
    payload: RegisterCompleteRequest,
    response: Response,
    db: Session = Depends(get_db),
) -> dict:
    log = bind_context(request_id=getattr(request.state, "request_id", "-"))
    _ensure_credentials_available(db, payload.nom_utilisateur, payload.email)
    organisation_id = _resolve_organisation_id(db, payload.organisation_id)

    now = datetime.utcnow()
    user = Utilisateur(
        organisation_id=organisation_id,
        nom_utilisateur=payload.nom_utilisateur,
        email=payload.email,
        prenom=payload.prenom,
        nom=payload.nom,
        date_naissance=getattr(payload, "date_naissance", None),
        genre=getattr(payload, "genre", None) or "Inconnu",
        taille_cm=payload.taille_cm,
        role="UTILISATEUR",
        statut="ACTIF",
        mot_de_passe_hash=hash_password_pbkdf2_sha256(payload.mot_de_passe),
        cree_le=now,
        modifie_le=now,
    )
    try:
        db.add(user)
        db.flush()
        complete_user_profile(db, user, payload, now=now)
        db.commit()
        db.refresh(user)
        log.info("register-complete success user_id={} username={}", user.utilisateur_id, user.nom_utilisateur)
    except ApiError:
        db.rollback()
        log.info("register-complete rejected username={} email={}", payload.nom_utilisateur, payload.email)
        raise
    except IntegrityError as exc:
        db.rollback()
        log.warning("register-complete integrity error username={} email={} detail={}", payload.nom_utilisateur, payload.email, exc.orig)
        _raise_integrity_error(db, exc, payload.nom_utilisateur, payload.email)
    except Exception as exc:
        db.rollback()
        log.exception("register-complete internal error username={} email={}", payload.nom_utilisateur, payload.email)
        raise ApiError(422, "validation_error", "Impossible de creer le compte complet.") from exc

    _set_refresh_cookie(response, user)
    return _token_response(user, include_user=True)


@router.post("/register", status_code=201)
@limiter.limit("10/minute")
def register(
    request: Request,
    payload: RegisterRequest,
    response: Response,
    db: Session = Depends(get_db),
) -> dict:
    if len(payload.mot_de_passe) < 6:
        raise ApiError(422, "validation_error", "Le mot de passe doit contenir au moins 6 caractères.")

    existing_user = db.execute(
        select(Utilisateur).where(
            or_(
                Utilisateur.nom_utilisateur == payload.nom_utilisateur,
                Utilisateur.email == payload.email,
            )
        )
    ).scalar_one_or_none()
    if existing_user:
        raise ApiError(409, "conflict", "Cet identifiant ou cet email est déjà utilisé.")

    organisation_id = payload.organisation_id
    if organisation_id is not None:
        if db.get(Organisation, organisation_id) is None:
            raise ApiError(422, "validation_error", "Organisation introuvable.")
    elif db.get(Organisation, 1) is not None:
        organisation_id = 1

    now = datetime.utcnow()
    user = Utilisateur(
        organisation_id=organisation_id,
        nom_utilisateur=payload.nom_utilisateur,
        prenom=payload.prenom or None,
        nom=payload.nom or None,
        email=payload.email,
        date_naissance=payload.date_naissance,
        genre=payload.genre or "Inconnu",
        taille_cm=payload.taille_cm,
        role="UTILISATEUR",
        statut="ACTIF",
        mot_de_passe_hash=hash_password_pbkdf2_sha256(payload.mot_de_passe),
        cree_le=now,
        modifie_le=now,
    )
    try:
        db.add(user)
        db.commit()
        db.refresh(user)
    except IntegrityError:
        db.rollback()
        raise ApiError(409, "conflict", "Cet identifiant ou cet email est déjà utilisé.")

    _set_refresh_cookie(response, user)
    return _token_response(user, include_user=True)


@router.post("/logout")
def logout(response: Response) -> dict:
    response.delete_cookie("refresh_token")
    return {"data": {"message": "Deconnexion effectuee."}}


@router.post("/refresh")
def refresh(user: Utilisateur = Depends(current_user_from_refresh)) -> dict:
    return _token_response(user)


@router.get("/me")
def me(db: Session = Depends(get_db), user: Utilisateur = Depends(current_user)) -> dict:
    return {"data": me_metrics.profile_payload(db, user)}


@router.post("/forgot-password")
@limiter.limit("5/minute")
def forgot_password(
    request: Request,
    payload: ForgotPasswordRequest,
    db: Session = Depends(get_db),
) -> dict:
    """Génère un token de reset court et le journalise.

    Réponse anti-énumération : succès systématique. En non-production, le token
    est inclus dans la réponse pour permettre le test ; en production, il faut
    le router via email (TODO Sprint 6).
    """
    settings = get_settings()
    user = db.execute(select(Utilisateur).where(Utilisateur.email == payload.email)).scalar_one_or_none()
    log = bind_context(request_id=getattr(request.state, "request_id", "-"))

    if not user or user.statut != "ACTIF":
        log.info("forgot-password requested for unknown/inactive email={}", payload.email)
        return {"data": {"message": "Si le compte existe, un lien a ete envoye."}}

    reset_token = create_token(
        str(user.utilisateur_id),
        "reset",
        timedelta(minutes=settings.password_reset_token_minutes),
    )
    log.info("forgot-password token issued user_id={}", user.utilisateur_id)

    payload_response: dict = {"message": "Si le compte existe, un lien a ete envoye."}
    if settings.environment != "production":
        payload_response["reset_token"] = reset_token
        payload_response["expires_in_minutes"] = settings.password_reset_token_minutes
    return {"data": payload_response}


@router.post("/reset-password")
@limiter.limit("10/minute")
def reset_password(
    request: Request,
    payload: ResetPasswordRequest,
    db: Session = Depends(get_db),
) -> dict:
    decoded = decode_token(payload.reset_token, "reset")
    user = db.get(Utilisateur, int(decoded["sub"]))
    if not user or user.statut != "ACTIF":
        raise ApiError(401, "unauthorized", "Token invalide.")
    user.mot_de_passe_hash = hash_password_pbkdf2_sha256(payload.nouveau_mot_de_passe)
    db.commit()

    log = bind_context(request_id=getattr(request.state, "request_id", "-"))
    log.info("password reset success user_id={}", user.utilisateur_id)
    return {"data": {"message": "Mot de passe mis a jour."}}
