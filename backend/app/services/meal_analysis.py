from __future__ import annotations

import base64
import binascii
import logging
import re
from dataclasses import dataclass
from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

try:
    from huggingface_hub import InferenceClient
    try:
        from huggingface_hub.errors import HfHubHTTPError, InferenceTimeoutError
    except ImportError:  # pragma: no cover - compatibility with older huggingface_hub releases
        from huggingface_hub.utils import HfHubHTTPError, InferenceTimeoutError
except ImportError:  # pragma: no cover - exercised only before backend image rebuild
    InferenceClient = None  # type: ignore[assignment]
    HfHubHTTPError = None  # type: ignore[assignment]
    InferenceTimeoutError = None  # type: ignore[assignment]

from app.core.config import Settings
from app.core.errors import ApiError
from app.db.models import Aliment
from app.schemas.meal_analysis import (
    MealAnalysisConfigResponse,
    MealAnalysisResponse,
    VisionPrediction,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class DishProfile:
    key: str
    label: str
    portion: str
    grammes: float
    calories: float
    proteines: float
    glucides: float
    lipides: float


@dataclass(frozen=True)
class LabelProfile:
    key: str
    display_name: str
    dish_key: str
    db_terms: tuple[str, ...]
    portion: str
    grammes: float
    aliases: tuple[str, ...] = ()


DISH_PROFILES: dict[str, DishProfile] = {
    "pizza": DishProfile("pizza", "Pizza", "1 part standard (~125 g)", 125, 330, 13, 38, 14),
    "omelette": DishProfile("omelette", "Omelette", "2 a 3 oeufs (~180 g)", 180, 260, 19, 3, 20),
    "riz": DishProfile("riz", "Assiette riz / bowl", "1 bol moyen (~180 g)", 180, 230, 5, 48, 1),
    "poulet": DishProfile("poulet", "Poulet", "1 portion standard (~150 g)", 150, 260, 32, 0, 12),
    "soupe": DishProfile("soupe", "Soupe", "1 bol standard (~300 ml)", 300, 170, 6, 22, 6),
    "poisson": DishProfile("poisson", "Poisson", "1 filet standard (~150 g)", 150, 240, 28, 0, 12),
    "saumon": DishProfile("saumon", "Saumon", "1 pave standard (~150 g)", 150, 290, 30, 0, 18),
    "pates": DishProfile("pates", "Pates", "1 assiette standard (~320 g)", 320, 520, 18, 72, 16),
    "burger": DishProfile("burger", "Burger", "1 burger standard (~250 g)", 250, 620, 29, 43, 36),
    "sandwich": DishProfile("sandwich", "Sandwich", "1 sandwich (~220 g)", 220, 430, 20, 42, 18),
    "salade": DishProfile("salade", "Salade composee", "1 grande assiette (~280 g)", 280, 320, 14, 18, 19),
    "sushi": DishProfile("sushi", "Assortiment de sushi", "8 pieces (~240 g)", 240, 390, 20, 52, 9),
    "dessert": DishProfile("dessert", "Dessert", "1 part standard (~140 g)", 140, 360, 5, 42, 18),
    "default": DishProfile("default", "Plat compose", "1 assiette standard (~330 g)", 330, 500, 24, 44, 22),
}

LABEL_PROFILES: tuple[LabelProfile, ...] = (
    LabelProfile("pizza", "Pizza", "pizza", ("pizza",), DISH_PROFILES["pizza"].portion, DISH_PROFILES["pizza"].grammes),
    LabelProfile("omelette", "Omelette", "omelette", ("omelette", "egg", "oeuf", "oeufs", "œuf"), DISH_PROFILES["omelette"].portion, DISH_PROFILES["omelette"].grammes),
    LabelProfile("rice", "Riz", "riz", ("rice", "riz", "white rice"), DISH_PROFILES["riz"].portion, DISH_PROFILES["riz"].grammes),
    LabelProfile("fried rice", "Riz frit", "riz", ("fried rice", "rice", "riz"), "1 assiette de riz frit (~260 g)", 260, aliases=("riz frit",)),
    LabelProfile("chicken", "Poulet", "poulet", ("chicken", "poulet", "grilled chicken"), DISH_PROFILES["poulet"].portion, DISH_PROFILES["poulet"].grammes),
    LabelProfile("soup", "Soupe", "soupe", ("soup", "soupe", "broth"), DISH_PROFILES["soupe"].portion, DISH_PROFILES["soupe"].grammes),
    LabelProfile("fish", "Poisson", "poisson", ("fish", "poisson"), DISH_PROFILES["poisson"].portion, DISH_PROFILES["poisson"].grammes),
    LabelProfile("salmon", "Saumon", "saumon", ("salmon", "saumon"), DISH_PROFILES["saumon"].portion, DISH_PROFILES["saumon"].grammes),
    LabelProfile("pasta", "Pates", "pates", ("pasta", "spaghetti", "pates", "pâtes"), DISH_PROFILES["pates"].portion, DISH_PROFILES["pates"].grammes),
    LabelProfile("spaghetti bolognese", "Spaghetti bolognaise", "pates", ("spaghetti bolognese", "spaghetti", "bolognaise", "pates"), "1 assiette de spaghetti bolognaise (~320 g)", 320),
    LabelProfile("burger", "Burger", "burger", ("burger", "hamburger", "cheeseburger"), DISH_PROFILES["burger"].portion, DISH_PROFILES["burger"].grammes),
    LabelProfile("sandwich", "Sandwich", "sandwich", ("sandwich", "panini", "wrap"), DISH_PROFILES["sandwich"].portion, DISH_PROFILES["sandwich"].grammes),
    LabelProfile("salad", "Salade", "salade", ("salad", "salade", "lettuce"), DISH_PROFILES["salade"].portion, DISH_PROFILES["salade"].grammes),
    LabelProfile("sushi", "Sushi", "sushi", ("sushi", "maki", "nigiri"), DISH_PROFILES["sushi"].portion, DISH_PROFILES["sushi"].grammes),
    LabelProfile("french fries", "Frites", "default", ("french fries", "fries", "frites", "potatoes"), "1 portion de frites (~150 g)", 150, aliases=("fries",)),
    LabelProfile("steak", "Steak", "default", ("steak", "beef", "boeuf"), "1 piece standard (~170 g)", 170, aliases=("beef", "boeuf")),
    LabelProfile("ice cream", "Glace", "dessert", ("ice cream", "glace"), "1 coupe standard (~120 g)", 120),
    LabelProfile("cake", "Gateau", "dessert", ("cake", "gateau", "tarte"), DISH_PROFILES["dessert"].portion, DISH_PROFILES["dessert"].grammes),
    LabelProfile("ramen", "Soupe de nouilles", "soupe", ("ramen", "nouilles", "soup"), "1 bol de nouilles en soupe (~380 g)", 380, aliases=("noodles",)),
)

HUGGINGFACE_TOP_K = 5
RELEVANT_PREDICTIONS_LIMIT = 3


class MealAnalysisService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def config_payload(self) -> MealAnalysisConfigResponse:
        payload = MealAnalysisConfigResponse(
            external_ai_enabled=bool(self.settings.ai_enable_external_calls),
            force_mock=bool(self.settings.meal_ai_force_mock),
            huggingface_configured=bool(self.settings.effective_huggingface_token),
            deepseek_configured=bool(self.settings.deepseek_api_key),
            vision_model=self.settings.effective_vision_model,
            vision_fallback_models=self.settings.effective_vision_fallback_models,
            provider="huggingface",
        )
        logger.info(
            "Meal analysis config: external_ai_enabled=%s force_mock=%s huggingface_configured=%s deepseek_configured=%s vision_model=%s fallback_count=%s provider=%s",
            payload.external_ai_enabled,
            payload.force_mock,
            payload.huggingface_configured,
            payload.deepseek_configured,
            payload.vision_model,
            len(payload.vision_fallback_models),
            payload.provider,
        )
        return payload

    def hf_status_payload(self) -> dict[str, Any]:
        token_configured = bool(self.settings.effective_huggingface_token)
        return {
            "huggingface_configured": token_configured,
            "model": self.settings.effective_vision_model,
            "status": "configured" if token_configured else "missing_token",
        }

    def analyze(self, db: Session, image_base64: str, mime_type: str | None = None) -> MealAnalysisResponse:
        image_bytes, normalized_mime = self._decode_image(image_base64, mime_type)
        provider_notes: list[str] = []

        if self.settings.meal_ai_force_mock:
            provider_notes.append("Mode mock force via configuration.")
            return self._local_mock(provider_notes, normalized_mime)

        if not self.settings.ai_enable_external_calls:
            provider_notes.append("Les appels IA externes sont desactives via AI_ENABLE_EXTERNAL_CALLS=false.")
            return self._local_mock(provider_notes, normalized_mime)

        token = self.settings.effective_huggingface_token
        if not token:
            provider_notes.append("HF_TOKEN / HUGGINGFACE_API_TOKEN absent: passage en mode demonstration.")
            return self._local_mock(provider_notes, normalized_mime)

        predictions = self._try_huggingface_classification(image_bytes, token, provider_notes)
        if not predictions:
            return self._local_mock(provider_notes, normalized_mime)

        return self._build_external_response(db, predictions, provider_notes)

    def _decode_image(self, image_base64: str, mime_type: str | None) -> tuple[bytes, str]:
        value = (image_base64 or "").strip()
        if not value:
            raise ApiError(422, "validation_error", "image_base64 est requis.")

        extracted_mime = mime_type
        if value.startswith("data:"):
            try:
                header, value = value.split(",", 1)
            except ValueError as exc:
                raise ApiError(422, "validation_error", "image_base64 n'est pas une data URL valide.") from exc
            if ";base64" not in header:
                raise ApiError(422, "validation_error", "L'image doit etre encodee en base64.")
            extracted_mime = header[5:].split(";", 1)[0] or extracted_mime

        compact = re.sub(r"\s+", "", value)
        padding = "=" * (-len(compact) % 4)
        try:
            image_bytes = base64.b64decode(compact + padding, validate=True)
        except (binascii.Error, ValueError) as exc:
            raise ApiError(422, "validation_error", "image_base64 est invalide.") from exc

        if not image_bytes:
            raise ApiError(422, "validation_error", "L'image fournie est vide.")
        if len(image_bytes) > self.settings.meal_ai_max_image_bytes:
            raise ApiError(
                413,
                "payload_too_large",
                f"Image trop volumineuse ({len(image_bytes)} octets). Maximum: {self.settings.meal_ai_max_image_bytes}.",
            )

        normalized_mime = extracted_mime or self._guess_mime_type(image_bytes)
        return image_bytes, normalized_mime

    def _guess_mime_type(self, image_bytes: bytes) -> str:
        if image_bytes.startswith(b"\xff\xd8\xff"):
            return "image/jpeg"
        if image_bytes.startswith(b"\x89PNG\r\n\x1a\n"):
            return "image/png"
        if image_bytes.startswith((b"GIF87a", b"GIF89a")):
            return "image/gif"
        return "image/jpeg"

    def _try_huggingface_classification(
        self,
        image_bytes: bytes,
        token: str,
        provider_notes: list[str],
    ) -> list[VisionPrediction] | None:
        if InferenceClient is None:
            provider_notes.append("Bibliotheque huggingface_hub indisponible dans l'image backend.")
            return None

        client = InferenceClient(token=token, timeout=self.settings.meal_ai_timeout_seconds)
        models = self.settings.effective_vision_models
        primary_model = self.settings.effective_vision_model

        for model in models:
            try:
                logger.info("Hugging Face image-classification attempt with model=%s.", model)
                output = client.image_classification(image_bytes, model=model, top_k=HUGGINGFACE_TOP_K)
            except Exception as exc:  # noqa: BLE001 - provider errors vary between hub versions
                note, should_retry = self._huggingface_failure_note(exc, model)
                provider_notes.append(note)
                if not should_retry:
                    return None
                continue

            predictions = self._parse_predictions(output)
            if predictions:
                if model != primary_model:
                    provider_notes.append(f"Modele principal indisponible; fallback Hugging Face utilise: {model}.")
                return predictions

            logger.warning("Hugging Face image-classification returned an empty response for model=%s.", model)
            provider_notes.append(f"Reponse Hugging Face vide pour le modele {model}.")

        return None

    def _huggingface_failure_note(self, exc: Exception, model: str) -> tuple[str, bool]:
        if InferenceTimeoutError is not None and isinstance(exc, InferenceTimeoutError):
            logger.warning("Hugging Face image-classification timed out for model=%s.", model)
            return f"Timeout Hugging Face pour le modele {model}.", True

        if HfHubHTTPError is not None and isinstance(exc, HfHubHTTPError):
            status = getattr(getattr(exc, "response", None), "status_code", None)
            logger.warning("Hugging Face image-classification failed with status %s for model=%s.", status, model)
            if status in (401, 403):
                return "Token Hugging Face invalide ou non autorise.", False
            if status == 404:
                return f"Modele Hugging Face introuvable ou non disponible via l'endpoint utilise: {model}.", True
            if status == 503:
                return f"Modele Hugging Face temporairement indisponible: {model}.", True
            if status is not None:
                return f"Erreur Hugging Face ({status}) pour le modele {model}.", True

        if isinstance(exc, TimeoutError):
            logger.warning("Hugging Face image-classification timed out for model=%s.", model)
            return f"Timeout Hugging Face pour le modele {model}.", True

        logger.warning(
            "Hugging Face image-classification failed for model=%s with %s.",
            model,
            type(exc).__name__,
        )
        return f"Erreur reseau Hugging Face pour le modele {model}.", True

    def _parse_predictions(self, payload: Any) -> list[VisionPrediction]:
        raw_items = payload
        if isinstance(payload, list) and payload and isinstance(payload[0], list):
            raw_items = payload[0]

        predictions: list[VisionPrediction] = []
        if not isinstance(raw_items, list):
            return predictions

        for item in raw_items:
            if isinstance(item, dict):
                label = str(item.get("label") or "").strip()
                score = self._normalize_confidence(item.get("score"))
            else:
                label = str(getattr(item, "label", "") or "").strip()
                score = self._normalize_confidence(getattr(item, "score", None))

            if not label or score is None:
                continue
            predictions.append(VisionPrediction(label=label, score=score))

        predictions.sort(key=lambda prediction: prediction.score, reverse=True)
        return predictions[:HUGGINGFACE_TOP_K]

    def _build_external_response(
        self,
        db: Session,
        predictions: list[VisionPrediction],
        provider_notes: list[str],
    ) -> MealAnalysisResponse:
        relevant_predictions = self._select_relevant_predictions(predictions)
        top_prediction = predictions[0]
        top_profile = self._resolve_label_profile(top_prediction.label)
        dish_profile = DISH_PROFILES.get(top_profile.dish_key, DISH_PROFILES["default"])

        aliments_detectes: list[dict[str, Any]] = []
        portions_estimees: list[dict[str, Any]] = []
        hypotheses: list[str] = [
            f"Prediction principale Hugging Face: {self._normalize_label(top_prediction.label)} ({round(top_prediction.score * 100)}%)."
        ]
        matched_any = False
        total_calories = 0.0
        total_proteines = 0.0
        total_glucides = 0.0
        total_lipides = 0.0
        seen_portion_names: set[str] = set()

        for prediction in relevant_predictions:
            profile = self._resolve_label_profile(prediction.label)
            matched = self._find_aliment_match(db, profile.db_terms)
            nutrients = self._scaled_nutrients(matched, profile.grammes) if matched else {}
            if matched:
                matched_any = True
                total_calories += nutrients.get("calories_kcal") or 0
                total_proteines += nutrients.get("proteines_g") or 0
                total_glucides += nutrients.get("glucides_g") or 0
                total_lipides += nutrients.get("lipides_g") or 0

            aliments_detectes.append(
                {
                    "nom": profile.display_name,
                    "label_source": self._normalize_label(prediction.label),
                    "confidence": prediction.score,
                    "matched_aliment_id": getattr(matched, "aliment_id", None),
                    "matched_aliment_nom": getattr(matched, "nom", None),
                    "portion_estimee": profile.portion,
                    "calories_kcal": nutrients.get("calories_kcal"),
                    "proteines_g": nutrients.get("proteines_g"),
                    "glucides_g": nutrients.get("glucides_g"),
                    "lipides_g": nutrients.get("lipides_g"),
                    "fibres_g": nutrients.get("fibres_g"),
                    "sucres_g": nutrients.get("sucres_g"),
                    "sodium_mg": nutrients.get("sodium_mg"),
                    "cholesterol_mg": nutrients.get("cholesterol_mg"),
                    "details": (
                        f"Correspondance base: {matched.nom}" if matched else "Aucune correspondance exacte trouvee dans la base locale."
                    ),
                }
            )

            if profile.display_name not in seen_portion_names:
                portions_estimees.append(
                    {
                        "nom": profile.display_name,
                        "portion": profile.portion,
                        "grammes_estimes": round(profile.grammes, 1),
                    }
                )
                seen_portion_names.add(profile.display_name)

        if matched_any:
            hypotheses.append("Les calories et macronutriments proviennent de la base locale `aliment`, mis a l'echelle par portion standard.")
        else:
            total_calories = dish_profile.calories
            total_proteines = dish_profile.proteines
            total_glucides = dish_profile.glucides
            total_lipides = dish_profile.lipides
            hypotheses.append("Aucun aliment local exact n'a ete trouve; profil nutritionnel standard du plat applique.")
            if not portions_estimees:
                portions_estimees.append(
                    {
                        "nom": dish_profile.label,
                        "portion": dish_profile.portion,
                        "grammes_estimes": dish_profile.grammes,
                    }
                )

        if len(relevant_predictions) > 1:
            hypotheses.append("Plusieurs labels visuels plausibles ont ete combines pour une estimation prudente.")

        commentaire = (
            f"Analyse Hugging Face active - modele : {self.settings.effective_vision_model}. "
            "Les resultats nutritionnels s'appuient sur les aliments retrouves dans la base HealthAI quand une correspondance existe."
        )

        limites = [
            "Le modele nateraw/food est entraine sur Food-101 et peut confondre des plats visuellement proches.",
            "Les portions restent standards et ne remplacent pas une pesee reelle.",
            "Une photo unique ne permet pas toujours d'identifier sauces, huiles ou ingredients caches.",
            *provider_notes[:3],
        ]

        return MealAnalysisResponse.model_validate(
            {
                "source_analyse": "huggingface_plus_local_reasoning",
                "mode": "external",
                "plat_detecte": dish_profile.label if top_profile.display_name == dish_profile.label else top_profile.display_name,
                "confidence": top_prediction.score,
                "aliments_detectes": aliments_detectes,
                "portions_estimees": portions_estimees,
                "calories_estimees": round(total_calories, 1) if total_calories else None,
                "macronutriments": {
                    "proteines_g": round(total_proteines, 1) if total_proteines else None,
                    "glucides_g": round(total_glucides, 1) if total_glucides else None,
                    "lipides_g": round(total_lipides, 1) if total_lipides else None,
                },
                "hypotheses": hypotheses,
                "commentaire": commentaire,
                "limites_estimation": [item for item in limites if item],
                "raw_vision_predictions": [prediction.model_dump() for prediction in predictions],
            }
        )

    def _select_relevant_predictions(self, predictions: list[VisionPrediction]) -> list[VisionPrediction]:
        if not predictions:
            return []
        top_score = predictions[0].score
        threshold = max(0.12, round(top_score * 0.18, 2))
        selected: list[VisionPrediction] = []
        seen_labels: set[str] = set()
        for prediction in predictions:
            profile = self._resolve_label_profile(prediction.label)
            unique_key = profile.display_name.lower()
            if prediction.score < threshold or unique_key in seen_labels:
                continue
            selected.append(prediction)
            seen_labels.add(unique_key)
            if len(selected) >= RELEVANT_PREDICTIONS_LIMIT:
                break
        return selected or predictions[:1]

    def _resolve_label_profile(self, label: str) -> LabelProfile:
        normalized = self._normalize_label(label)
        for profile in LABEL_PROFILES:
            if normalized == profile.key or normalized in profile.aliases:
                return profile
        for profile in LABEL_PROFILES:
            if profile.key in normalized or any(alias in normalized for alias in profile.aliases):
                return profile
        guessed_dish = self._guess_dish_key(normalized)
        dish = DISH_PROFILES.get(guessed_dish, DISH_PROFILES["default"])
        db_terms = tuple(term for term in {normalized, *normalized.split()} if len(term) >= 3)
        return LabelProfile(
            key=normalized,
            display_name=self._display_label(normalized),
            dish_key=dish.key,
            db_terms=db_terms or (normalized,),
            portion=dish.portion,
            grammes=dish.grammes,
        )

    def _guess_dish_key(self, normalized_label: str) -> str:
        lowered = normalized_label.lower()
        if "pizza" in lowered:
            return "pizza"
        if any(token in lowered for token in ("omelette", "omelet", "egg", "oeuf")):
            return "omelette"
        if any(token in lowered for token in ("rice", "riz")):
            return "riz"
        if any(token in lowered for token in ("chicken", "poulet")):
            return "poulet"
        if any(token in lowered for token in ("soup", "soupe", "ramen")):
            return "soupe"
        if any(token in lowered for token in ("fish", "poisson")):
            return "poisson"
        if "salmon" in lowered or "saumon" in lowered:
            return "saumon"
        if any(token in lowered for token in ("pasta", "spaghetti", "pates", "pâtes")):
            return "pates"
        if "burger" in lowered:
            return "burger"
        if any(token in lowered for token in ("sandwich", "panini", "wrap")):
            return "sandwich"
        if any(token in lowered for token in ("salad", "salade")):
            return "salade"
        if any(token in lowered for token in ("sushi", "maki", "nigiri")):
            return "sushi"
        if any(token in lowered for token in ("cake", "tarte", "glace", "ice cream")):
            return "dessert"
        return "default"

    def _find_aliment_match(self, db: Session, terms: tuple[str, ...]) -> Aliment | None:
        exact_terms = [self._normalize_label(term) for term in terms if term]
        if exact_terms:
            exact_rows = db.execute(
                select(Aliment).where(func.lower(Aliment.nom).in_(exact_terms))
            ).scalars().all()
            best_exact = self._best_aliment_match(exact_rows, exact_terms)
            if best_exact is not None:
                return best_exact

        like_terms = [term for term in exact_terms if len(term) >= 3]
        if not like_terms:
            return None

        like_clauses = [func.lower(Aliment.nom).like(f"%{term}%") for term in like_terms]
        like_rows = db.execute(
            select(Aliment).where(or_(*like_clauses)).limit(25)
        ).scalars().all()
        return self._best_aliment_match(like_rows, like_terms)

    def _best_aliment_match(self, rows: list[Aliment], terms: list[str]) -> Aliment | None:
        best_row: Aliment | None = None
        best_score = -1
        for row in rows:
            row_name = self._normalize_label(row.nom)
            score = 0
            for term in terms:
                if row_name == term:
                    score = max(score, 100)
                elif row_name.startswith(term):
                    score = max(score, 80)
                elif term in row_name:
                    score = max(score, 60 + min(len(term), 15))
                else:
                    overlap = len(set(row_name.split()) & set(term.split()))
                    score = max(score, overlap * 10)
            if score > best_score:
                best_score = score
                best_row = row
        return best_row if best_score > 0 else None

    def _scaled_nutrients(self, aliment: Aliment | None, grammes: float) -> dict[str, float | None]:
        if aliment is None:
            return {}
        ratio = grammes / 100.0 if grammes else 1.0
        return {
            "calories_kcal": self._scale(getattr(aliment, "calories_kcal", None), ratio),
            "proteines_g": self._scale(getattr(aliment, "proteines_g", None), ratio),
            "glucides_g": self._scale(getattr(aliment, "glucides_g", None), ratio),
            "lipides_g": self._scale(getattr(aliment, "lipides_g", None), ratio),
            "fibres_g": self._scale(getattr(aliment, "fibres_g", None), ratio),
            "sucres_g": self._scale(getattr(aliment, "sucres_g", None), ratio),
            "sodium_mg": self._scale(getattr(aliment, "sodium_mg", None), ratio),
            "cholesterol_mg": self._scale(getattr(aliment, "cholesterol_mg", None), ratio),
        }

    def _scale(self, value: Any, ratio: float) -> float | None:
        if value in (None, ""):
            return None
        try:
            return round(float(value) * ratio, 1)
        except (TypeError, ValueError):
            return None

    def _local_mock(self, provider_notes: list[str], mime_type: str) -> MealAnalysisResponse:
        dish = DISH_PROFILES["default"]
        fallback_message = self._fallback_message(provider_notes)
        return MealAnalysisResponse.model_validate(
            {
                "source_analyse": "local_mock",
                "mode": "mock",
                "plat_detecte": dish.label,
                "confidence": 0.22,
                "aliments_detectes": [
                    {
                        "nom": "Ingredients non determines",
                        "label_source": "local_mock",
                        "confidence": 0.22,
                        "matched_aliment_id": None,
                        "matched_aliment_nom": None,
                        "portion_estimee": dish.portion,
                        "calories_kcal": None,
                        "proteines_g": None,
                        "glucides_g": None,
                        "lipides_g": None,
                        "details": "Aucune reconnaissance visuelle exploitable n'etait disponible.",
                    }
                ],
                "portions_estimees": [
                    {
                        "nom": dish.label,
                        "portion": dish.portion,
                        "grammes_estimes": dish.grammes,
                    }
                ],
                "calories_estimees": dish.calories,
                "macronutriments": {
                    "proteines_g": dish.proteines,
                    "glucides_g": dish.glucides,
                    "lipides_g": dish.lipides,
                },
                "hypotheses": [
                    fallback_message,
                    "Portion standard appliquee faute de prediction externe exploitable.",
                ],
                "commentaire": (
                    f"{fallback_message} L'estimation actuelle repose sur une portion standard de plat compose."
                ),
                "limites_estimation": [
                    "Aucune prediction Hugging Face exploitable n'a pu etre obtenue.",
                    "Les valeurs nutritionnelles sont des estimations prudentes par defaut.",
                    f"Type MIME detecte: {mime_type}.",
                    *provider_notes[:3],
                ],
                "raw_vision_predictions": [],
            }
        )

    def _fallback_message(self, provider_notes: list[str]) -> str:
        if any("HF_TOKEN / HUGGINGFACE_API_TOKEN absent" in note for note in provider_notes):
            return "Mode demonstration: configurez HF_TOKEN pour activer la reconnaissance reelle."
        if any("AI_ENABLE_EXTERNAL_CALLS=false" in note for note in provider_notes):
            return "Mode fallback local: activez AI_ENABLE_EXTERNAL_CALLS=true pour autoriser Hugging Face."
        if any("Mode mock force" in note for note in provider_notes):
            return "Mode mock force: MEAL_AI_FORCE_MOCK=true."
        return "Mode fallback local: Hugging Face n'a pas fourni de prediction exploitable."

    def _normalize_label(self, value: str) -> str:
        normalized = value.strip().lower()
        normalized = normalized.replace("_", " ").replace("-", " ")
        normalized = re.sub(r"\s+", " ", normalized)
        return normalized

    def _display_label(self, value: str) -> str:
        words = self._normalize_label(value).split()
        if not words:
            return "Plat compose"
        return " ".join(word.capitalize() for word in words)

    def _normalize_confidence(self, value: Any) -> float | None:
        if value in (None, ""):
            return None
        try:
            score = float(value)
        except (TypeError, ValueError):
            return None
        if score > 1:
            score = score / 100 if score <= 100 else 1
        return round(max(0, min(1, score)), 4)
