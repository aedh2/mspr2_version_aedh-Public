"""
Service IA amélioré — Gemini Vision + Ollama LLM.
S'intègre en complément de MealAnalysisService et RecommendationEngine existants.
"""
from __future__ import annotations

import base64
import json
import logging
import re
from typing import Any

import httpx

from app.core.config import Settings

logger = logging.getLogger(__name__)


class GeminiVisionService:
    """Analyse photo de repas via Google Gemini Vision."""

    GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent"

    def __init__(self, settings: Settings) -> None:
        self.api_key = getattr(settings, "gemini_api_key", None) or ""

    def is_available(self) -> bool:
        return bool(self.api_key)

    async def analyze(self, image_bytes: bytes) -> list[dict[str, Any]]:
        """
        Retourne une liste d'aliments détectés avec macros estimées.
        Format: [{"name": str, "confidence": float, "quantity_g": float, "macros": {...}}]
        """
        if not self.is_available():
            return []

        b64 = base64.b64encode(image_bytes).decode("utf-8")
        payload = {
            "contents": [{
                "parts": [
                    {
                        "text": (
                            "Identifie tous les aliments visibles dans cette image et estime leurs macronutriments "
                            "pour la portion visible. "
                            "Réponds UNIQUEMENT avec une liste JSON (sans markdown, sans texte autour) : "
                            '[{"name": "nom_aliment", "confidence": 0.95, "quantity_g": 150, '
                            '"macros": {"calories": 200, "proteins_g": 25, "carbs_g": 10, "fats_g": 8, "fiber_g": 2}}, ...]. '
                            "Noms en français. Maximum 6 aliments."
                        )
                    },
                    {"inline_data": {"mime_type": "image/jpeg", "data": b64}},
                ]
            }],
            "generationConfig": {"temperature": 0.1, "maxOutputTokens": 2048},
        }

        try:
            async with httpx.AsyncClient(timeout=90.0) as client:
                response = await client.post(
                    f"{self.GEMINI_URL}?key={self.api_key}",
                    json=payload,
                )
            logger.info("Gemini status: %s", response.status_code)
            if response.status_code != 200:
                logger.error("Gemini error %s: %s", response.status_code, response.text[:200])
                return []

            parts = response.json()["candidates"][0]["content"]["parts"]
            text = "".join(p.get("text", "") for p in parts).strip()
            text = re.sub(r"```json\s*", "", text)
            text = re.sub(r"```\s*", "", text)

            # Extraire les objets JSON complets même si tronqués
            foods = re.findall(
                r'\{[^{}]*"name"[^{}]*"macros"\s*:\s*\{[^{}]*\}[^{}]*\}',
                text,
                re.DOTALL,
            )
            if not foods:
                foods = re.findall(r'\{[^{}]*"name"\s*:\s*"[^"]*"[^{}]*\}', text)

            parsed = []
            for f in foods:
                try:
                    parsed.append(json.loads(f))
                except Exception:
                    pass
            return parsed[:6]

        except Exception as exc:
            logger.error("Gemini vision error: %s: %s", type(exc).__name__, exc)
            return []


class OllamaLLMService:
    """Génération de recommandations via Ollama (LLM local)."""

    def __init__(self, settings: Settings) -> None:
        self.base_url = getattr(settings, "ollama_base_url", "http://localhost:11434")
        self.model = getattr(settings, "ollama_model", "llama3.2:1b")

    def is_available(self) -> bool:
        return bool(self.base_url)

    async def generate_nutrition_recommendations(self, profile: dict) -> list[str]:
        prompt = f"""Tu es un nutritionniste expert. Réponds en français. Donne 5 recommandations concrètes.

PROFIL : objectif={profile.get('goal', 'santé')}, poids={profile.get('poids_kg', '?')}kg
CIBLES : {profile.get('daily_targets', {})}
DÉSÉQUILIBRES : {', '.join(profile.get('imbalances', [])) or 'aucun'}

Donne exactement 5 recommandations courtes (une par ligne, commence par un verbe)."""
        return await self._generate_list(prompt)

    async def generate_sport_recommendations(self, profile: dict, program: dict) -> list[str]:
        prompt = f"""Tu es un coach sportif expert. Réponds en français. Donne 5 conseils personnalisés.

PROFIL : objectif={profile.get('goal', 'santé')}, niveau={profile.get('fitness_level', 'débutant')}
PROGRAMME : {program.get('sessions', 3)} séances/semaine

Donne exactement 5 conseils pratiques (un par ligne, commence par un verbe)."""
        return await self._generate_list(prompt)

    async def generate_training_plan(self, profile: dict, program: dict) -> list[dict]:
        """Génère un plan d'entraînement structuré avec exercices, séries et répétitions."""
        muscles = ', '.join(program.get('muscles', [])) or 'corps complet'
        prompt = f"""Tu es un coach sportif expert. Génère un plan d'entraînement en JSON. Réponds UNIQUEMENT avec le JSON, sans texte autour.

PROFIL : objectif={profile.get('goal', 'prise de masse')}, niveau={profile.get('fitness_level', 'intermédiaire')}
MUSCLES CIBLÉS : {muscles}
DURÉE SÉANCE : {program.get('duree_min', 60)} minutes
MATÉRIEL : {program.get('materiel', 'salle de sport')}

FORMAT ATTENDU (liste de 4 à 6 exercices) :
[{{"nom": "Développé couché", "muscles": ["pectoraux", "triceps"], "series": 4, "repetitions": "8-12", "repos": "90s", "intensite": "moderee", "description": "Allongé sur le banc, poussez la barre vers le haut en contrôlant la descente."}}]"""

        try:
            raw = await self._call_ollama(prompt)
            start = raw.find("[")
            end = raw.rfind("]")
            if start != -1 and end != -1:
                return json.loads(raw[start:end + 1])
        except Exception as exc:
            logger.error("Ollama training plan error: %s", exc)
        return []

    async def generate_meal_plan(self, profile: dict, targets: dict) -> list[dict]:
        prompt = f"""Génère un plan repas pour 3 jours en JSON. Réponds UNIQUEMENT avec le JSON, sans texte autour.

OBJECTIF : {profile.get('goal', 'santé')}
CALORIES CIBLES : {targets.get('calories', 2000)} kcal/jour
PROTÉINES CIBLES : {targets.get('proteins_g', 120)}g/jour

Génère exactement 3 jours (Lundi, Mardi, Mercredi), chaque jour avec 3 repas (Petit-déjeuner, Déjeuner, Dîner).
Chaque repas doit avoir une description détaillée, une justification nutritionnelle, et les macros estimées.

EXEMPLE DE FORMAT (respecte exactement cette structure pour chaque repas) :
[{{"day": "Lundi", "meals": [
  {{"name": "Petit-déjeuner", "description": "Flocons d'avoine avec fruits rouges et yaourt grec", "justification": "Apport en fibres et protéines pour bien démarrer la journée", "calories": 350, "proteins_g": 18, "carbs_g": 45, "fats_g": 8}},
  {{"name": "Déjeuner", "description": "Poulet grillé avec quinoa et légumes vapeur", "justification": "Protéines complètes et glucides complexes pour l'énergie de l'après-midi", "calories": 600, "proteins_g": 40, "carbs_g": 55, "fats_g": 15}},
  {{"name": "Dîner", "description": "Saumon au four avec patates douces et brocoli", "justification": "Oméga-3 pour la récupération musculaire et glucides pour reconstituer les réserves", "calories": 500, "proteins_g": 35, "carbs_g": 40, "fats_g": 18}}
]}},
{{"day": "Mardi", "meals": [...]}}
]"""

        try:
            raw = await self._call_ollama(prompt)
            start = raw.find("[")
            end = raw.rfind("]")
            if start != -1 and end != -1:
                return json.loads(raw[start:end + 1])
        except Exception:
            pass
        return []

    async def _generate_list(self, prompt: str) -> list[str]:
        try:
            text = await self._call_ollama(prompt)
            lines = [l.strip().lstrip("•-*0123456789. ") for l in text.split("\n")]
            return [l for l in lines if len(l) > 20][:5]
        except Exception as exc:
            logger.error("Ollama error: %s", exc)
            return []

    async def _call_ollama(self, prompt: str) -> str:
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f"{self.base_url}/api/generate",
                json={"model": self.model, "prompt": prompt, "stream": False},
            )
            response.raise_for_status()
            return response.json().get("response", "")
