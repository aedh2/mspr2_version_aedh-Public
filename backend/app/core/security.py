from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import Cookie, Depends, Header
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import ApiError
from app.db.models import Utilisateur
from app.db.session import get_db


def _b64url_encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _b64url_decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode((value + padding).encode("ascii"))


def hash_password_pbkdf2_sha256(password: str, salt: str | None = None, iterations: int = 210000) -> str:
    salt = salt or secrets.token_urlsafe(12)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), iterations)
    digest_b64 = base64.b64encode(digest).decode("ascii").strip()
    return f"pbkdf2_sha256${iterations}${salt}${digest_b64}"


def verify_password(password: str, encoded: str | None) -> bool:
    if not encoded:
        return False
    try:
        algorithm, iterations_raw, salt, expected = encoded.split("$", 3)
        if algorithm != "pbkdf2_sha256":
            return False
        candidate = hash_password_pbkdf2_sha256(password, salt=salt, iterations=int(iterations_raw))
        return hmac.compare_digest(candidate, encoded)
    except (ValueError, TypeError):
        return False


def create_token(subject: str, token_type: str, expires_delta: timedelta, extra: dict[str, Any] | None = None) -> str:
    settings = get_settings()
    now = datetime.now(timezone.utc)
    payload = {
        "sub": subject,
        "type": token_type,
        "iat": int(now.timestamp()),
        "exp": int((now + expires_delta).timestamp()),
        **(extra or {}),
    }
    header = {"alg": settings.jwt_algorithm, "typ": "JWT"}
    signing_input = ".".join(
        [
            _b64url_encode(json.dumps(header, separators=(",", ":")).encode("utf-8")),
            _b64url_encode(json.dumps(payload, separators=(",", ":")).encode("utf-8")),
        ]
    )
    signature = hmac.new(settings.jwt_secret_key.encode("utf-8"), signing_input.encode("ascii"), hashlib.sha256).digest()
    return f"{signing_input}.{_b64url_encode(signature)}"


def decode_token(token: str, expected_type: str) -> dict[str, Any]:
    settings = get_settings()
    try:
        header_raw, payload_raw, signature_raw = token.split(".", 2)
        signing_input = f"{header_raw}.{payload_raw}"
        expected_signature = hmac.new(
            settings.jwt_secret_key.encode("utf-8"),
            signing_input.encode("ascii"),
            hashlib.sha256,
        ).digest()
        if not hmac.compare_digest(_b64url_decode(signature_raw), expected_signature):
            raise ValueError("signature")
        payload = json.loads(_b64url_decode(payload_raw))
        if payload.get("type") != expected_type:
            raise ValueError("type")
        if int(payload.get("exp", 0)) < int(datetime.now(timezone.utc).timestamp()):
            raise ValueError("exp")
        return payload
    except (ValueError, json.JSONDecodeError):
        raise ApiError(401, "unauthorized", "Token invalide ou expire.")


def authenticate_user(db: Session, identifiant: str, mot_de_passe: str) -> Utilisateur | None:
    user = db.execute(
        select(Utilisateur).where(
            or_(Utilisateur.email == identifiant, Utilisateur.nom_utilisateur == identifiant)
        )
    ).scalar_one_or_none()
    if not user or user.statut != "ACTIF" or not verify_password(mot_de_passe, user.mot_de_passe_hash):
        return None
    return user


def current_user(
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> Utilisateur:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise ApiError(401, "unauthorized", "Authentification requise.")
    payload = decode_token(authorization.split(" ", 1)[1], "access")
    user = db.get(Utilisateur, int(payload["sub"]))
    if not user or user.statut != "ACTIF":
        raise ApiError(401, "unauthorized", "Utilisateur introuvable ou inactif.")
    return user


def current_user_from_refresh(
    refresh_token: str | None = Cookie(default=None),
    db: Session = Depends(get_db),
) -> Utilisateur:
    if not refresh_token:
        raise ApiError(401, "unauthorized", "Refresh token manquant.")
    payload = decode_token(refresh_token, "refresh")
    user = db.get(Utilisateur, int(payload["sub"]))
    if not user or user.statut != "ACTIF":
        raise ApiError(401, "unauthorized", "Utilisateur introuvable ou inactif.")
    return user


def require_roles(*roles: str):
    def dependency(user: Utilisateur = Depends(current_user)) -> Utilisateur:
        if user.role not in roles:
            raise ApiError(403, "forbidden", "Droits insuffisants.")
        return user

    return dependency
