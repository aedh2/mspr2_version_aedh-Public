from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


BudgetLevel = Literal["faible", "moyen", "eleve"]
SportLevel = Literal["debutant", "intermediaire", "avance"]


class RecommendationRequest(BaseModel):
    objectif_principal: str | None = Field(
        default=None,
        description="Objectif principal si l'utilisateur veut surcharger l'objectif actif.",
    )
    allergies: list[str] = Field(default_factory=list)
    regime_alimentaire: str | None = None
    aliments_evites: list[str] = Field(default_factory=list)
    budget: BudgetLevel | None = None
    niveau_sportif: SportLevel | None = None
    niveau_activite: str | None = None
    equipement_disponible: list[str] = Field(default_factory=list)
    contraintes_sante: list[str] = Field(default_factory=list)
    preferences_alimentaires: list[str] = Field(default_factory=list)
    preferences_sportives: list[str] = Field(default_factory=list)
    culture_alimentaire: str | None = None
    type_repas: str | None = None
    temps_preparation: str | None = None
    lieu: str | None = None
    type_seance: str | None = None
    muscles_cibles: list[str] = Field(default_factory=list)
    douleur_limitation: str | None = None
    frequence_seances_hebdo: int | None = Field(default=None, ge=0, le=14)
    duree_seance_min: int | None = Field(default=None, gt=0, le=240)
    max_nutrition: int = Field(default=5, ge=1, le=10)
    max_sport: int = Field(default=5, ge=1, le=10)


class RecommendationContext(BaseModel):
    utilisateur_id: int
    age: int | None
    sexe: str | None
    taille_cm: float | None
    poids_kg: float | None
    imc: float | None
    objectif_principal: str
    budget: str | None
    niveau_sportif: str
    niveau_activite: str | None = None
    frequence_seances_hebdo: int | None = None
    duree_seance_min: int | None = None
    donnees_utilisees: list[str] = Field(default_factory=list)


class NutritionRecommendation(BaseModel):
    aliment_id: int | None = None
    source: str
    type: Literal["plat", "recette", "aliment"]
    nom: str
    recette: str
    calories_estimees: float | None = None
    proteines_g: float | None = None
    glucides_g: float | None = None
    lipides_g: float | None = None
    score_nutritionnel: int
    score_pertinence: int
    score_securite: int
    justification: str
    ingredients: list[str] = Field(default_factory=list)
    preparation: str | None = None
    budget_estime: str | None = None
    allergenes_exclus: list[str] = Field(default_factory=list)
    contraintes_respectees: list[str] = Field(default_factory=list)
    alternatives: list[str] = Field(default_factory=list)
    badges: list[str] = Field(default_factory=list)


class SportExerciseRecommendation(BaseModel):
    exercice_id: int
    nom: str
    duree_min: int
    intensite: str
    frequence: str
    equipement_necessaire: list[str] = Field(default_factory=list)
    muscles_cibles: list[str] = Field(default_factory=list)
    niveau_adapte: str
    score_pertinence: int
    score_securite: int
    justification: str
    series: int | None = None
    repetitions: str | None = None
    repos: str | None = None
    adaptations: list[str] = Field(default_factory=list)
    contre_indications: list[str] = Field(default_factory=list)
    contraintes_respectees: list[str] = Field(default_factory=list)


class SportSessionRecommendation(BaseModel):
    nom: str
    duree_min: int
    intensite: str
    frequence: str
    exercices: list[SportExerciseRecommendation] = Field(default_factory=list)
    materiel_necessaire: list[str] = Field(default_factory=list)
    muscles_cibles: list[str] = Field(default_factory=list)
    contre_indications: list[str] = Field(default_factory=list)
    justification: str


class SportRecommendations(BaseModel):
    exercices: list[SportExerciseRecommendation] = Field(default_factory=list)
    seances: list[SportSessionRecommendation] = Field(default_factory=list)


class RecommendationResponse(BaseModel):
    generated_at: datetime
    source: Literal["local_rules", "external_ai"]
    fallback_utilise: bool
    fallback_message: str | None = None
    contexte: RecommendationContext
    contraintes_prises_en_compte: list[str] = Field(default_factory=list)
    nutrition: list[NutritionRecommendation] = Field(default_factory=list)
    sport: SportRecommendations
    messages: list[str] = Field(default_factory=list)


class RecommendationEnvelope(BaseModel):
    data: RecommendationResponse
