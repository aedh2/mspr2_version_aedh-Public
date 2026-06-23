"""Schemas Pydantic pour les endpoints /me métier (charts, latest, kpis).

DTOs explicites pour ne pas dépendre de l'introspection SQLAlchemy générique.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Any, Literal

from fastapi import Query
from pydantic import BaseModel, Field


# Métriques whitelistées pour les charts. L'endpoint refuse tout autre nom.
BIOMETRIE_METRICS: tuple[str, ...] = (
    "poids_kg",
    "imc",
    "taux_masse_grasse",
    "bpm_repos",
    "bpm_moyen",
    "bpm_max",
    "eau_l",
)

SOMMEIL_METRICS: tuple[str, ...] = (
    "duree_sommeil_h",
    "qualite_sommeil_score",
    "stress_score",
    "pas_jour",
    "frequence_cardiaque_bpm",
    "activite_physique_min_jour",
)

Granularity = Literal["day", "week", "month"]


class ChartParams(BaseModel):
    """Paramètres communs aux endpoints /charts."""

    metric: str
    date_from: date | None = None
    date_to: date | None = None
    granularity: Granularity = "day"


def chart_params(
    metric: str = Query(..., description="Nom de la métrique (whitelist par ressource)."),
    date_from: date | None = Query(None),
    date_to: date | None = Query(None),
    granularity: Granularity = Query("day"),
) -> ChartParams:
    return ChartParams(metric=metric, date_from=date_from, date_to=date_to, granularity=granularity)


def chart_params_no_metric(
    date_from: date | None = Query(None),
    date_to: date | None = Query(None),
    granularity: Granularity = Query("day"),
) -> ChartParams:
    """Variante sans `metric` requise (charts agrégeant plusieurs métriques)."""
    return ChartParams(metric="_aggregate_", date_from=date_from, date_to=date_to, granularity=granularity)


class ChartPoint(BaseModel):
    bucket: str  # ISO date "YYYY-MM-DD" (ou semaine/mois)
    value: float | None
    count: int


class ChartResponse(BaseModel):
    metric: str
    granularity: Granularity
    points: list[ChartPoint] = Field(default_factory=list)


class LatestBiometrie(BaseModel):
    mesure_id: int
    mesure_le: datetime
    poids_kg: float | None
    taille_cm: float | None
    imc: float | None
    taux_masse_grasse: float | None
    bpm_repos: int | None
    bpm_moyen: int | None
    bpm_max: int | None
    eau_l: float | None


class LatestSommeil(BaseModel):
    mesure_sommeil_id: int
    mesure_le: datetime
    duree_sommeil_h: float | None
    qualite_sommeil_score: int | None
    stress_score: int | None
    pas_jour: int | None
    frequence_cardiaque_bpm: int | None
    activite_physique_min_jour: int | None
    tension_systolique: int | None
    tension_diastolique: int | None
    trouble_sommeil_normalise: str | None


class ObjectifActif(BaseModel):
    objectif_id: int
    type_objectif: str
    date_debut: date | None
    date_fin: date | None
    actif_unique: bool
    commentaire: str | None


class UserKpis(BaseModel):
    poids_kg: float | None
    imc: float | None
    derniere_mesure_le: datetime | None
    duree_sommeil_h: float | None
    dernier_sommeil_le: datetime | None
    seances_30j: int
    calories_brulees_30j: float
    calories_consommees_jour: float
    objectif_actif: ObjectifActif | None
    photos_total: int


# Réponses enveloppe {data: ...} -> les endpoints continuent de wrapper manuellement
# pour rester cohérents avec le reste du code. Ces modèles servent la doc OpenAPI.
