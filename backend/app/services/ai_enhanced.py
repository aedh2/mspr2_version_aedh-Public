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


def _safe_json(s: str):
    try:
        return json.loads(s)
    except Exception:
        return None


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
        muscles_str = ', '.join(program.get('muscles', [])) or 'corps complet'
        contraintes_str = ', '.join(program.get('contraintes_sante', [])) or 'aucune'
        prompt = (
            f"Tu es coach sportif expert. Reponds en francais. "
            f"Profil: objectif={program.get('objectif', 'sante')}, niveau={program.get('niveau', 'intermediaire')}, "
            f"seances={program.get('sessions', 3)}/semaine, duree={program.get('duree_min', 60)}min, "
            f"lieu={program.get('lieu', 'salle')}, type={program.get('type_seance', 'musculation')}, "
            f"muscles cibles={muscles_str}, materiel={program.get('materiel', 'salle')}, "
            f"contraintes sante={contraintes_str}, douleurs={program.get('douleur', 'aucune')}. "
            f"Donne exactement 5 conseils pratiques personnalises (un par ligne, commence par un verbe)."
        )
        return await self._generate_list(prompt)

    async def select_training_plan(
        self,
        profile: dict,
        program: dict,
        catalog: list[dict],
        nb_exercices: int = 5,
    ) -> list[dict]:
        """Sélectionne des exercices DANS le catalogue BDD fourni, adaptés au profil.

        `catalog` = [{"id": int, "nom": str, "groupe": str, "muscle": str, "materiel": str}]
        Retourne une liste de dicts contenant l'`id` choisi + séries/reps/justification.
        """
        if not catalog:
            return []

        muscles = ', '.join(program.get('muscles', [])) or 'corps complet'
        contraintes_str = ', '.join(program.get('contraintes_sante', [])) or 'aucune'
        duree_totale = program.get('duree_min', 60)
        douleur = program.get('douleur', 'aucune')
        lieu = program.get('lieu', 'salle')
        materiel = program.get('materiel', 'aucun')
        type_seance = program.get('type_seance', 'musculation')
        niveau = program.get('niveau', 'intermediaire')
        objectif = program.get('objectif', 'sante')

        # Liste numérotée du catalogue à présenter au LLM
        catalogue_lignes = "\n".join(
            f"- id={c['id']} | {c['nom']} | groupe: {c['groupe']} | muscle: {c['muscle']} | materiel: {c['materiel']}"
            for c in catalog
        ) or "(aucun exercice du catalogue n'est compatible avec ce profil)"

        prompt = (
            f"Reponds UNIQUEMENT avec un JSON valide, sans texte autour. "
            f"Tu es coach sportif certifie qui construit une seance 100% personnalisee.\n\n"
            f"CATALOGUE D'EXERCICES DISPONIBLES (id, nom, GROUPE musculaire, materiel). "
            f"Ces exercices ont deja ete filtres pour etre compatibles avec le lieu, le materiel et les douleurs de l'utilisateur:\n"
            f"{catalogue_lignes}\n\n"
            f"PROFIL DE L'UTILISATEUR (a respecter IMPERATIVEMENT):\n"
            f"- Objectif: {objectif}\n"
            f"- Niveau: {niveau}\n"
            f"- Type de seance: {type_seance}\n"
            f"- Lieu: {lieu}\n"
            f"- Materiel disponible: {materiel}\n"
            f"- Muscles cibles EN PRIORITE: {muscles}\n"
            f"- Duree totale de la seance: {duree_totale} minutes (repartir entre les exercices)\n"
            f"- Contraintes sante: {contraintes_str}\n"
            f"- Douleurs/limitations: {douleur}\n\n"
            f"CONSIGNES STRICTES:\n"
            f"1. Propose exactement {nb_exercices} exercices.\n"
            f"2. PRIVILEGIE les exercices DU CATALOGUE ci-dessus (via leur id) dont le GROUPE correspond aux muscles cibles ({muscles}).\n"
            f"3. Si le catalogue ne contient pas assez d'exercices adaptes (par ex. seance {type_seance}, a {lieu}, "
            f"sans materiel, ou en evitant {douleur}), tu DOIS INVENTER des exercices reels et adaptes toi-meme: "
            f'mets "id": null et donne un "nom" precis (en francais) et la liste "muscles".\n'
            f"4. Si le type de seance est 'cardio', propose surtout des mouvements cardio.\n"
            f"5. INTERDIT: tout exercice qui sollicite une zone douloureuse ({douleur}) ou aggrave une contrainte ({contraintes_str}). "
            f"Si la contrainte est cardiaque, garde une intensite faible a moderee (jamais maximale).\n"
            f"6. Respecte le lieu/materiel: a la maison sans materiel, propose uniquement des exercices au poids du corps.\n"
            f"7. Ne repete jamais deux fois le meme exercice.\n"
            f"8. La justification (1 phrase) doit citer EXPLICITEMENT les infos du profil qui motivent ce choix "
            f"(muscles cibles, objectif {objectif}, niveau {niveau}, lieu {lieu}, et la facon dont l'exercice respecte la douleur/contrainte).\n\n"
            f'Format JSON STRICT: {{"exercices":[{{"id":12,"nom":"<nom exact>","muscles":["<groupe>"],"series":3,'
            f'"repetitions":"10-12","repos":"90s","intensite":"moderee","duree_min":15,'
            f'"justification":"Choisi car il cible vos <muscles> pour <objectif>, realisable a <lieu>, et evite <douleur>."}}]}}'
        )

        try:
            raw = await self._call_ollama(prompt, json_mode=True, temperature=0.3)
            logger.info("Ollama select plan raw (first 600): %s", raw[:600])
            parsed = _safe_json(raw)
            items: list[dict] = []
            if isinstance(parsed, list):
                items = [d for d in parsed if isinstance(d, dict)]
            elif isinstance(parsed, dict):
                for key in ("exercices", "exercises", "plan", "selection", "seance"):
                    if isinstance(parsed.get(key), list):
                        items = [d for d in parsed[key] if isinstance(d, dict)]
                        break
                if not items and ("id" in parsed):
                    items = [parsed]
            return items
        except Exception as exc:
            logger.error("Ollama select plan error: %s", exc)
        return []

    async def generate_meal_plan(self, profile: dict, targets: dict) -> list[dict]:
        allergies_str = ', '.join(profile.get('allergies', [])) or 'aucune'
        aliments_evites_str = ', '.join(profile.get('aliments_evites', [])) or 'aucun'
        preferences_str = ', '.join(profile.get('preferences', [])) or 'aucune'
        contraintes_str = ', '.join(profile.get('contraintes_sante', [])) or 'aucune'
        regime_str = profile.get('regime', '') or 'aucun'
        culture_str = profile.get('culture', '') or 'non precise'
        budget_str = profile.get('budget', '') or 'non precise'
        temps_str = profile.get('temps_preparation', '') or 'non precise'
        type_repas = profile.get('type_repas', '') or ''
        goal = profile.get('goal', 'sante')

        # Filtrer par type de repas si spécifié
        if type_repas and type_repas not in ('', 'non_precise'):
            repas_label = type_repas.replace('_', '-').capitalize()
            nb_repas = "3 propositions"
            structure = (
                f'[{{"day":"Option 1","meals":[{{"name":"{repas_label}","description":"plat","justification":"pourquoi","recette":"etapes de preparation","calories":500,"proteins_g":35,"carbs_g":45,"fats_g":15}}]}},'
                f'{{"day":"Option 2","meals":[{{"name":"{repas_label}","description":"plat","justification":"pourquoi","recette":"etapes de preparation","calories":480,"proteins_g":32,"carbs_g":42,"fats_g":14}}]}},'
                f'{{"day":"Option 3","meals":[{{"name":"{repas_label}","description":"plat","justification":"pourquoi","recette":"etapes de preparation","calories":520,"proteins_g":38,"carbs_g":48,"fats_g":16}}]}}]'
            )
        else:
            repas_label = "Petit-dejeuner, Dejeuner, Diner"
            nb_repas = "3 jours (Lundi Mardi Mercredi) x 3 repas"
            structure = (
                f'[{{"day":"Lundi","meals":['
                f'{{"name":"Petit-dejeuner","description":"plat","justification":"pourquoi","recette":"etapes","calories":350,"proteins_g":20,"carbs_g":40,"fats_g":10}},'
                f'{{"name":"Dejeuner","description":"plat","justification":"pourquoi","recette":"etapes","calories":600,"proteins_g":40,"carbs_g":55,"fats_g":15}},'
                f'{{"name":"Diner","description":"plat","justification":"pourquoi","recette":"etapes","calories":500,"proteins_g":35,"carbs_g":40,"fats_g":18}}'
                f']}},'
                f'{{"day":"Mardi","meals":[...]}},'
                f'{{"day":"Mercredi","meals":[...]}}]'
            )

        prompt = (
            f"Reponds UNIQUEMENT avec un JSON valide sans texte autour. "
            f"Tu es nutritionniste. Genere {nb_repas} adaptes a ce profil:\n"
            f"- Objectif: {goal}\n"
            f"- Regime: {regime_str}\n"
            f"- Allergies a exclure absolument: {allergies_str}\n"
            f"- Aliments a eviter: {aliments_evites_str}\n"
            f"- Preferences: {preferences_str}\n"
            f"- Contraintes sante: {contraintes_str}\n"
            f"- Culture culinaire: {culture_str}\n"
            f"- Budget: {budget_str}\n"
            f"- Temps de preparation: {temps_str}\n"
            f"Chaque repas doit avoir: description (nom detaille du plat), justification (pourquoi ce plat repond a TOUS les criteres ci-dessus), recette (etapes de preparation numerotees), et les macros estimes.\n"
            f"Format JSON:\n{structure}"
        )

        try:
            raw = await self._call_ollama(prompt, json_mode=True)
            raw = re.sub(r"```json\s*", "", raw).strip()
            raw = re.sub(r"```\s*", "", raw).strip()

            parsed = _safe_json(raw)
            if parsed is not None:
                # Tableau direct
                if isinstance(parsed, list):
                    return parsed
                # Objet avec clé connue
                if isinstance(parsed, dict):
                    for key in ("days", "meal_plan", "plan", "repas", "options"):
                        if key in parsed and isinstance(parsed[key], list):
                            return parsed[key]
                    # Objet unique day/meals → on l'enveloppe
                    if "day" in parsed and "meals" in parsed:
                        return [parsed]
                    # Objet avec meals directement
                    if "meals" in parsed and isinstance(parsed["meals"], list):
                        return [{"day": "Option 1", "meals": parsed["meals"]}]

            logger.warning("Ollama meal plan: unrecognized JSON structure")
        except Exception as exc:
            logger.error("Ollama meal plan parse error: %s", exc)
        return []

    async def _generate_list(self, prompt: str) -> list[str]:
        try:
            text = await self._call_ollama(prompt)
            lines = [l.strip().lstrip("•-*0123456789. ") for l in text.split("\n")]
            return [l for l in lines if len(l) > 20][:5]
        except Exception as exc:
            logger.error("Ollama error: %s", exc)
            return []

    async def _call_ollama(self, prompt: str, json_mode: bool = False, temperature: float | None = None) -> str:
        payload: dict = {"model": self.model, "prompt": prompt, "stream": False}
        if json_mode:
            payload["format"] = "json"
        if temperature is not None:
            payload["options"] = {"temperature": temperature}
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(
                f"{self.base_url}/api/generate",
                json=payload,
            )
            response.raise_for_status()
            return response.json().get("response", "")
