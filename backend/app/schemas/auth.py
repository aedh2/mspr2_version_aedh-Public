from __future__ import annotations

from datetime import date
from typing import Literal
import unicodedata

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


def _text_key(value: object) -> str:
    text = str(value).strip().casefold().replace("-", " ").replace("_", " ")
    return "".join(
        char for char in unicodedata.normalize("NFKD", text)
        if not unicodedata.combining(char)
    )


ACTIVITY_ALIASES = {
    "sedentaire": "sedentaire",
    "leger": "leger",
    "modere": "modere",
    "actif": "actif",
    "tres actif": "tres_actif",
}

class LoginRequest(BaseModel):
    identifiant: str = Field(min_length=1)
    mot_de_passe: str = Field(min_length=1)


class RegisterRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    nom_utilisateur: str = Field(min_length=1, max_length=120)
    email: str = Field(min_length=3, max_length=255)
    mot_de_passe: str = Field(min_length=1, max_length=128)
    prenom: str | None = Field(default=None, max_length=120)
    nom: str | None = Field(default=None, max_length=120)
    date_naissance: date | None = None
    genre: Literal["Homme", "Femme", "Autre", "Inconnu"] | None = "Inconnu"
    taille_cm: float | None = Field(default=None, ge=50, le=260)
    organisation_id: int | None = Field(default=None, ge=1)

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        normalized = value.strip().lower()
        if "@" not in normalized or "." not in normalized.rsplit("@", 1)[-1]:
            raise ValueError("Email invalide.")
        return normalized


class RegisterCompleteRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    nom_utilisateur: str = Field(min_length=1, max_length=120)
    email: str = Field(min_length=3, max_length=255)
    mot_de_passe: str = Field(min_length=8, max_length=128)
    confirmation: str = Field(min_length=8, max_length=128)
    prenom: str = Field(min_length=1, max_length=120)
    nom: str = Field(min_length=1, max_length=120)
    taille_cm: float = Field(ge=50, le=260)
    poids_actuel_kg: float = Field(ge=20, le=350)
    poids_cible_kg: float = Field(ge=20, le=350)
    date_cible: date
    objectif_principal: str = Field(min_length=1, max_length=80)
    niveau_activite: Literal["sedentaire", "leger", "modere", "actif", "tres_actif"]
    allergies: list[str] = Field(min_length=1, max_length=30)
    regime_alimentaire: str = Field(min_length=1, max_length=120)
    contraintes_sante: list[str] = Field(min_length=1, max_length=30)
    organisation_id: int | None = Field(default=None, ge=1)
    date_naissance: date | None = None
    genre: Literal["Homme", "Femme", "Autre", "Inconnu"] = "Inconnu"
    niveau_sportif: Literal["debutant", "intermediaire", "avance"] = "debutant"
    preferences_alimentaires: list[str] = Field(default_factory=list, max_length=30)
    aliments_evites: list[str] = Field(default_factory=list, max_length=30)
    budget: Literal["faible", "moyen", "eleve"] | None = None
    equipements: list[str] = Field(default_factory=list, max_length=30)
    preferences_sportives: list[str] = Field(default_factory=list, max_length=30)
    frequence_seances_hebdo: int | None = Field(default=None, ge=0, le=14)
    duree_seance_min: int | None = Field(default=None, gt=0, le=240)
    duree_sommeil_h: float | None = Field(default=None, ge=0, le=24)
    qualite_sommeil_score: int | None = Field(default=None, ge=1, le=10)

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        normalized = value.strip().lower()
        if "@" not in normalized or "." not in normalized.rsplit("@", 1)[-1]:
            raise ValueError("Email invalide.")
        return normalized

    @field_validator("nom_utilisateur")
    @classmethod
    def validate_nom_utilisateur(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("Identifiant requis.")
        return normalized

    @field_validator("taille_cm", "poids_actuel_kg", "poids_cible_kg", "duree_sommeil_h", mode="before")
    @classmethod
    def normalize_decimal(cls, value: object) -> object:
        if isinstance(value, str):
            text = value.strip().replace(",", ".")
            return text if text else value
        return value

    @field_validator("niveau_activite", mode="before")
    @classmethod
    def normalize_activity(cls, value: object) -> object:
        key = _text_key(value)
        return ACTIVITY_ALIASES.get(key, value)

    @field_validator(
        "allergies",
        "contraintes_sante",
        "preferences_alimentaires",
        "aliments_evites",
        "equipements",
        "preferences_sportives",
        mode="before",
    )
    @classmethod
    def normalize_list(cls, value: object) -> list[str]:
        if value is None or value == "":
            return []
        if isinstance(value, str):
            candidates = value.replace("\n", ",").split(",")
        elif isinstance(value, list):
            candidates = value
        else:
            raise ValueError("Liste invalide.")
        cleaned: list[str] = []
        seen: set[str] = set()
        for item in candidates:
            text = str(item).strip()
            if not text:
                continue
            key = text.casefold()
            if key in seen:
                continue
            seen.add(key)
            cleaned.append(text[:120])
        return cleaned

    @field_validator("prenom", "nom", "objectif_principal", "regime_alimentaire")
    @classmethod
    def strip_required_text(cls, value: str) -> str:
        text = value.strip()
        if not text:
            raise ValueError("Champ requis.")
        return text

    @field_validator("mot_de_passe")
    @classmethod
    def validate_password_strength(cls, value: str) -> str:
        if len(value) < 8:
            raise ValueError("Le mot de passe doit contenir au moins 8 caracteres.")
        checks = [
            any(char.islower() for char in value),
            any(char.isupper() for char in value),
            any(char.isdigit() for char in value),
        ]
        if sum(checks) < 3:
            raise ValueError("Le mot de passe doit contenir majuscule, minuscule et chiffre.")
        return value

    @model_validator(mode="after")
    def validate_confirmation(self) -> RegisterCompleteRequest:
        if self.mot_de_passe != self.confirmation:
            raise ValueError("Les mots de passe ne correspondent pas.")
        today = date.today()
        if self.date_cible <= today:
            raise ValueError("La date cible doit etre future.")
        objective = self.objectif_principal.upper().replace(" ", "_")
        if "PERTE" in objective and self.poids_cible_kg >= self.poids_actuel_kg:
            raise ValueError("Le poids cible doit etre inferieur au poids actuel pour une perte de poids.")
        if ("GAIN" in objective or "MASSE" in objective) and self.poids_cible_kg <= self.poids_actuel_kg:
            raise ValueError("Le poids cible doit etre superieur au poids actuel pour une prise de masse.")
        return self


class RegisterAvailabilityResponse(BaseModel):
    nom_utilisateur_disponible: bool | None = None
    email_disponible: bool | None = None
    nom_utilisateur_compte_incomplet: bool = False
    email_compte_incomplet: bool = False
    nom_utilisateur_suppression_sure_possible: bool = False
    email_suppression_sure_possible: bool = False
    nom_utilisateur_message: str | None = None
    email_message: str | None = None


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class LogoutResponse(BaseModel):
    message: str


class ForgotPasswordRequest(BaseModel):
    email: str = Field(min_length=3, max_length=255, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class ResetPasswordRequest(BaseModel):
    reset_token: str = Field(min_length=10)
    nouveau_mot_de_passe: str = Field(min_length=8, max_length=128)


class ChangePasswordRequest(BaseModel):
    ancien_mot_de_passe: str = Field(min_length=1)
    nouveau_mot_de_passe: str = Field(min_length=8, max_length=128)


class UpdateProfileRequest(BaseModel):
    """Champs autorisés pour l'auto-modification du profil utilisateur.

    Volontairement restrictif : pas de role/statut modifiables ici.
    """

    model_config = ConfigDict(extra="forbid")

    nom: str | None = Field(default=None, max_length=120)
    prenom: str | None = Field(default=None, max_length=120)
    nom_utilisateur: str | None = Field(default=None, max_length=80)
    email: str | None = Field(default=None, max_length=255)
    organisation_id: int | None = None
    taille_cm: float | None = Field(default=None, ge=50, le=260)
    genre: str | None = Field(default=None, max_length=20)
    date_naissance: str | None = None  # ISO date au format YYYY-MM-DD
    poids_actuel_kg: float | None = Field(default=None, ge=20, le=350)
    poids_cible_kg: float | None = Field(default=None, ge=20, le=350)
    objectif_principal: str | None = Field(default=None, max_length=80)
    date_cible: str | None = None
    niveau_activite: str | None = Field(default=None, max_length=80)
    niveau_sportif: str | None = Field(default=None, max_length=80)
    allergies: list[str] | None = None
    regime_alimentaire: str | None = Field(default=None, max_length=120)
    preferences_alimentaires: list[str] | None = None
    aliments_evites: list[str] | None = None
    budget: str | None = Field(default=None, max_length=80)
    equipements: list[str] | None = None
    contraintes_sante: list[str] | None = None
    preferences_sportives: list[str] | None = None
    frequence_seances_hebdo: int | None = Field(default=None, ge=0, le=14)
    duree_seance_min: int | None = Field(default=None, gt=0, le=240)
    duree_sommeil_h: float | None = Field(default=None, ge=0, le=24)
    qualite_sommeil_score: int | None = Field(default=None, ge=1, le=10)
