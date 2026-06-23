from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class MealAnalysisRequest(BaseModel):
    image_base64: str = Field(..., description="Image capturee en base64 brute ou data URL.")
    mime_type: str | None = Field(default=None, description="Type MIME de l'image si connu.")


class VisionPrediction(BaseModel):
    label: str
    score: float = Field(ge=0, le=1)


class DetectedFood(BaseModel):
    nom: str
    label_source: str
    confidence: float | None = Field(default=None, ge=0, le=1)
    matched_aliment_id: int | None = None
    matched_aliment_nom: str | None = None
    portion_estimee: str | None = None
    calories_kcal: float | None = None
    proteines_g: float | None = None
    glucides_g: float | None = None
    lipides_g: float | None = None
    fibres_g: float | None = None
    sucres_g: float | None = None
    sodium_mg: float | None = None
    cholesterol_mg: float | None = None
    details: str | None = None


class PortionEstimate(BaseModel):
    nom: str
    portion: str
    grammes_estimes: float | None = None


class Macronutrients(BaseModel):
    proteines_g: float | None = None
    glucides_g: float | None = None
    lipides_g: float | None = None


class MealAnalysisResponse(BaseModel):
    source_analyse: Literal["huggingface", "huggingface_plus_local_reasoning", "local_mock"] = "local_mock"
    mode: Literal["external", "mock"] = "mock"
    plat_detecte: str
    confidence: float = Field(ge=0, le=1)
    aliments_detectes: list[DetectedFood] = Field(default_factory=list)
    portions_estimees: list[PortionEstimate] = Field(default_factory=list)
    calories_estimees: float | None = None
    macronutriments: Macronutrients = Field(default_factory=Macronutrients)
    hypotheses: list[str] = Field(default_factory=list)
    commentaire: str
    limites_estimation: list[str] = Field(default_factory=list)
    raw_vision_predictions: list[VisionPrediction] = Field(default_factory=list)


class MealAnalysisConfigResponse(BaseModel):
    external_ai_enabled: bool
    force_mock: bool
    huggingface_configured: bool
    deepseek_configured: bool
    vision_model: str
    vision_fallback_models: list[str] = Field(default_factory=list)
    provider: str = "huggingface"
