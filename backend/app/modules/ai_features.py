"""
Endpoints IA améliorés — Gemini Vision + Ollama LLM.
Branche : feature/ai-recommendations-vision
"""
from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.security import current_user
from app.db.models import Utilisateur
from app.db.session import get_db
from app.schemas.recommendations import RecommendationRequest
from app.services.ai_enhanced import GeminiVisionService, OllamaLLMService
from app.services.recommendations import RecommendationEngine

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ai", tags=["IA Améliorée"])


# ─── Schemas ─────────────────────────────────────────────────────────────────

class FoodMacros(BaseModel):
    calories: float = 0.0
    proteins_g: float = 0.0
    carbs_g: float = 0.0
    fats_g: float = 0.0
    fiber_g: float = 0.0


class DetectedFood(BaseModel):
    name: str
    confidence: float = 0.0
    quantity_g: float | None = None
    macros: FoodMacros | None = None


class MealAnalysisResponse(BaseModel):
    foods: list[DetectedFood]
    total_macros: FoodMacros
    source: str
    error: str | None = None


class RecommendationResponse(BaseModel):
    sport_tips: list[str]
    nutrition_tips: list[str]
    meal_plan: list[dict[str, Any]]
    training_plan: list[dict[str, Any]] = []
    source: str


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _sum_macros(foods: list[dict]) -> FoodMacros:
    total = FoodMacros()
    for f in foods:
        m = f.get("macros") or {}
        total.calories += m.get("calories", 0)
        total.proteins_g += m.get("proteins_g", 0)
        total.carbs_g += m.get("carbs_g", 0)
        total.fats_g += m.get("fats_g", 0)
        total.fiber_g += m.get("fiber_g", 0)
    return total


# ─── Endpoints ───────────────────────────────────────────────────────────────

@router.post(
    "/analyse-repas",
    response_model=MealAnalysisResponse,
    summary="Analyse photo de repas via Gemini Vision",
    description=(
        "Envoie une photo de repas à Google Gemini 2.5 Flash. "
        "Retourne les aliments détectés avec macros estimées par portion."
    ),
)
async def analyse_repas(
    image: UploadFile = File(..., description="Photo du repas (JPEG/PNG)"),
    settings: Settings = Depends(get_settings),
    user: Utilisateur = Depends(current_user),
) -> MealAnalysisResponse:
    image_bytes = await image.read()
    if len(image_bytes) > 10_000_000:
        raise HTTPException(status_code=413, detail="Image trop grande (max 10 Mo)")

    service = GeminiVisionService(settings)
    if not service.is_available():
        raise HTTPException(
            status_code=503,
            detail="Gemini Vision non disponible — configurez GEMINI_API_KEY dans .env",
        )

    foods_raw = await service.analyze(image_bytes)

    foods = [
        DetectedFood(
            name=f.get("name", "inconnu"),
            confidence=float(f.get("confidence", 0.0)),
            quantity_g=f.get("quantity_g"),
            macros=FoodMacros(**f["macros"]) if f.get("macros") else None,
        )
        for f in foods_raw
    ]

    return MealAnalysisResponse(
        foods=foods,
        total_macros=_sum_macros(foods_raw),
        source="gemini-2.5-flash",
    )


@router.post(
    "/recommandations",
    response_model=RecommendationResponse,
    summary="Recommandations sport + nutrition via Ollama LLM",
    description=(
        "Génère des recommandations personnalisées en texte libre "
        "grâce à un LLM local (Ollama llama3.2). "
        "Complète les recommandations règle-based existantes."
    ),
)
async def recommandations_ia(
    request: RecommendationRequest,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    user: Utilisateur = Depends(current_user),
) -> RecommendationResponse:
    engine = RecommendationEngine()
    base = engine.build(db, user, request)

    allergies = request.allergies or []
    regime = request.regime_alimentaire or ""
    contraintes_sante = request.contraintes_sante or []

    profile = {
        "goal": request.objectif_principal or getattr(user, "objectif_principal", "santé"),
        "fitness_level": request.niveau_sportif or getattr(user, "niveau_activite", "débutant"),
        "poids_kg": getattr(user, "poids_kg", None),
        "daily_targets": {"calories": base.daily_calories_target, "proteins_g": base.daily_proteins_target_g} if hasattr(base, "daily_calories_target") else {},
        "imbalances": base.imbalances if hasattr(base, "imbalances") else [],
        "allergies": allergies,
        "regime": regime,
        "contraintes_sante": contraintes_sante,
    }
    sport_program = {
        "sessions": request.frequence_seances_hebdo or 3,
        "muscles": request.muscles_cibles or [],
        "duree_min": request.duree_seance_min or 60,
        "materiel": ", ".join(request.equipement_disponible) if request.equipement_disponible else "salle de sport",
        "type_seance": request.type_seance or "",
        "douleur": request.douleur_limitation or "",
    }

    llm = OllamaLLMService(settings)
    if not llm.is_available():
        return RecommendationResponse(
            sport_tips=[],
            nutrition_tips=[],
            meal_plan=[],
            source="unavailable",
        )

    sport_tips, nutrition_tips, meal_plan, training_plan = await _run_llm(llm, profile, sport_program)

    return RecommendationResponse(
        sport_tips=sport_tips,
        nutrition_tips=nutrition_tips,
        meal_plan=meal_plan,
        training_plan=training_plan,
        source="ollama-llama3.2",
    )


async def _run_llm(
    llm: OllamaLLMService,
    profile: dict,
    sport_program: dict,
) -> tuple[list[str], list[str], list[dict], list[dict]]:
    # Appels séquentiels — Ollama ne traite qu'une requête à la fois
    try:
        nutrition_tips = await llm.generate_nutrition_recommendations(profile)
    except Exception:
        nutrition_tips = []
    try:
        sport_tips = await llm.generate_sport_recommendations(profile, sport_program)
    except Exception:
        sport_tips = []
    try:
        meal_plan = await llm.generate_meal_plan(profile, profile.get("daily_targets", {}))
    except Exception:
        meal_plan = []
    try:
        training_plan = await llm.generate_training_plan(profile, sport_program)
    except Exception:
        training_plan = []
    return nutrition_tips, sport_tips, meal_plan, training_plan


@router.get(
    "/status",
    summary="Statut des services IA",
)
async def ai_status(settings: Settings = Depends(get_settings)) -> dict:
    gemini = GeminiVisionService(settings)
    ollama = OllamaLLMService(settings)
    return {
        "gemini_vision": "configured" if gemini.is_available() else "missing GEMINI_API_KEY",
        "ollama_llm": "configured" if ollama.is_available() else "unavailable",
        "ollama_model": ollama.model,
        "ollama_base_url": ollama.base_url,
    }
