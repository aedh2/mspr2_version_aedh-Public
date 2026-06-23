from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


Genre = Literal["Homme", "Femme", "Autre", "Inconnu"]
Budget = Literal["faible", "moyen", "eleve"]
NiveauSportif = Literal["debutant", "intermediaire", "avance"]
NiveauActivite = Literal["sedentaire", "leger", "modere", "actif", "tres_actif"]


class OnboardingRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    prenom: str = Field(min_length=1, max_length=120)
    nom: str = Field(min_length=1, max_length=120)
    date_naissance: date
    genre: Genre = "Inconnu"
    taille_cm: float = Field(ge=50, le=260)
    poids_actuel_kg: float = Field(ge=20, le=350)
    poids_cible_kg: float | None = Field(default=None, ge=20, le=350)
    objectif_principal: str = Field(min_length=1, max_length=80)
    date_cible: date | None = None
    niveau_activite: NiveauActivite
    niveau_sportif: NiveauSportif
    allergies: list[str] = Field(default_factory=list, max_length=30)
    regime_alimentaire: str | None = Field(default=None, max_length=120)
    preferences_alimentaires: list[str] = Field(default_factory=list, max_length=30)
    aliments_evites: list[str] = Field(default_factory=list, max_length=30)
    budget: Budget | None = None
    equipements: list[str] = Field(default_factory=list, max_length=30)
    contraintes_sante: list[str] = Field(default_factory=list, max_length=30)
    preferences_sportives: list[str] = Field(default_factory=list, max_length=30)
    frequence_seances_hebdo: int = Field(ge=0, le=14)
    duree_seance_min: int = Field(ge=5, le=240)
    duree_sommeil_h: float = Field(ge=0, le=24)
    qualite_sommeil_score: int = Field(ge=1, le=10)

    @model_validator(mode="after")
    def validate_dates_and_goal(self) -> OnboardingRequest:
        today = date.today()
        age = today.year - self.date_naissance.year - ((today.month, today.day) < (self.date_naissance.month, self.date_naissance.day))
        if age < 13 or age > 120:
            raise ValueError("Date de naissance incoherente.")
        if self.date_cible and self.date_cible <= today:
            raise ValueError("La date cible doit etre future.")
        objective = self.objectif_principal.upper().replace(" ", "_")
        if self.poids_cible_kg is not None:
            if "PERTE" in objective and self.poids_cible_kg >= self.poids_actuel_kg:
                raise ValueError("Le poids cible doit etre inferieur au poids actuel pour une perte de poids.")
            if ("GAIN" in objective or "MASSE" in objective) and self.poids_cible_kg <= self.poids_actuel_kg:
                raise ValueError("Le poids cible doit etre superieur au poids actuel pour une prise de masse.")
        return self

    @field_validator(
        "allergies",
        "preferences_alimentaires",
        "aliments_evites",
        "equipements",
        "contraintes_sante",
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
    def strip_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        text = value.strip()
        return text or None
