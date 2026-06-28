"""
Endpoints IA améliorés — Gemini Vision + Ollama LLM.
Branche : feature/ai-recommendations-vision
"""
from __future__ import annotations

import logging
import re
import time
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.security import current_user
from app.db.models import Exercice, SeanceEntrainement, SeanceExercice, Utilisateur
from app.db.session import get_db
from app.modules.resources import media_url
from app.schemas.recommendations import RecommendationRequest
from app.services import document_store
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


class RecommendationFeedbackRequest(BaseModel):
    recommendation_id: str | None = None
    type: str | None = None  # sport | nutrition
    utile: bool | None = None
    note: int | None = None  # 1..5
    commentaire: str | None = None


# ─── Helpers ─────────────────────────────────────────────────────────────────

import json as _json

# body_part anglais BDD → libellé français lisible (pour le prompt et l'affichage)
_BODYPART_EN_TO_FR: dict[str, str] = {
    "back": "dos",
    "chest": "pectoraux",
    "lower arms": "avant-bras",
    "lower legs": "mollets",
    "shoulders": "epaules",
    "upper arms": "bras",
    "upper legs": "jambes / fessiers",
    "waist": "abdominaux",
    "cardio": "cardio",
    "neck": "cou",
}

# muscle ciblé par l'utilisateur (FR, formulaire) → body_part(s) BDD prioritaires
_TARGET_MUSCLE_TO_BODYPART: dict[str, list[str]] = {
    "jambes": ["upper legs", "lower legs"],
    "fessiers": ["upper legs"],
    "dos": ["back"],
    "poitrine": ["chest"],
    "pectoraux": ["chest"],
    "epaules": ["shoulders"],
    "épaules": ["shoulders"],
    "bras": ["upper arms", "lower arms"],
    "biceps": ["upper arms"],
    "triceps": ["upper arms"],
    "abdominaux": ["waist"],
    "abdos": ["waist"],
    "mollets": ["lower legs"],
}


# Mots-clés de douleur / blessure → body_parts BDD à ÉVITER absolument
_INJURY_TO_BODYPART: list[tuple[tuple[str, ...], list[str]]] = [
    (("genou", "genoux", "knee", "rotule", "menisque", "ménisque", "ligament"), ["upper legs", "lower legs"]),
    (("jambe", "cuisse", "quadriceps", "ischio", "mollet", "cheville", "ankle", "tibia", "courbature cuisse"), ["upper legs", "lower legs"]),
    (("hanche", "hip", "bassin"), ["upper legs"]),
    (("epaule", "épaule", "shoulder", "deltoid", "coiffe"), ["shoulders"]),
    (("dos", "lombaire", "colonne", "vertebr", "vertébr", "lumbago", "sciatique", "hernie"), ["back", "waist"]),
    (("poignet", "wrist"), ["lower arms"]),
    (("coude", "elbow"), ["upper arms"]),
    (("nuque", "cou ", "cervical", "neck"), ["shoulders", "neck"]),
    (("abdo", "ventre", "abdominaux"), ["waist"]),
]

# Exercices de secours au poids du corps (utilisés si la BDD n'offre rien d'adapté).
# parts = body_parts BDD sollicités (pour exclusion blessure) ; cardio = mouvement cardio.
_GENERIC_BODYWEIGHT: list[dict] = [
    {"nom": "Marche rapide sur place", "muscles": ["cardio", "jambes"], "parts": ["upper legs"], "cardio": True},
    {"nom": "Shadow boxing (boxe dans le vide)", "muscles": ["cardio", "epaules", "bras"], "parts": ["shoulders", "upper arms"], "cardio": True},
    {"nom": "Jumping jacks", "muscles": ["cardio", "jambes"], "parts": ["upper legs"], "cardio": True},
    {"nom": "Mountain climbers", "muscles": ["cardio", "abdominaux"], "parts": ["waist", "upper legs"], "cardio": True},
    {"nom": "Montées de genoux", "muscles": ["cardio", "jambes"], "parts": ["upper legs"], "cardio": True},
    {"nom": "Gainage (planche)", "muscles": ["abdominaux", "core"], "parts": ["waist"], "cardio": False},
    {"nom": "Crunch abdominal", "muscles": ["abdominaux"], "parts": ["waist"], "cardio": False},
    {"nom": "Pompes", "muscles": ["pectoraux", "triceps"], "parts": ["chest", "upper arms"], "cardio": False},
    {"nom": "Dips sur chaise", "muscles": ["triceps", "bras"], "parts": ["upper arms"], "cardio": False},
    {"nom": "Squats au poids du corps", "muscles": ["jambes", "fessiers"], "parts": ["upper legs"], "cardio": False},
    {"nom": "Fentes", "muscles": ["jambes", "fessiers"], "parts": ["upper legs"], "cardio": False},
    {"nom": "Superman (extension du dos)", "muscles": ["dos", "lombaires"], "parts": ["back"], "cardio": False},
]


def _avoided_bodyparts(program: dict) -> set[str]:
    """Body_parts BDD à éviter d'après les douleurs et contre-indications saisies."""
    text = " ".join(
        [*(program.get("contraintes_sante") or []), program.get("douleur") or ""]
    ).lower()
    avoid: set[str] = set()
    for keys, parts in _INJURY_TO_BODYPART:
        if any(k in text for k in keys):
            avoid.update(parts)
    return avoid


def _is_bodyweight(materiel: str) -> bool:
    m = (materiel or "").strip().lower()
    return (
        m == ""
        or "body weight" in m
        or "bodyweight" in m
        or "poids du corps" in m
        or m in {"aucun", "none", "sans materiel", "sans matériel"}
    )


def _has_equipment(program: dict) -> bool:
    """L'utilisateur a-t-il du matériel ? (liste fournie OU lieu = salle)."""
    equip = [e for e in (program.get("equipement_disponible") or []) if str(e).strip()]
    if equip:
        return True
    return (program.get("lieu") or "").lower() == "salle"


def _filter_catalog(catalog: list[dict], program: dict) -> list[dict]:
    """Garde uniquement les exercices BDD compatibles avec lieu/matériel et sans risque pour les zones douloureuses."""
    avoid = _avoided_bodyparts(program)
    has_equip = _has_equipment(program)
    equip_list = [str(e).lower() for e in (program.get("equipement_disponible") or []) if str(e).strip()]

    out: list[dict] = []
    for c in catalog:
        bp = (c.get("body_part") or "").lower()
        if bp in avoid:
            continue  # zone blessée → on exclut
        mat = (c.get("materiel") or "").lower()
        bw = _is_bodyweight(mat)
        if not has_equip:
            if not bw:
                continue  # sans matériel → poids du corps seulement
        elif equip_list:
            # matériel précis listé → poids du corps + matériel correspondant
            if not bw and not any(e in mat or mat in e for e in equip_list):
                continue
        out.append(c)
    return out


# Estimation des calories brûlées : MET (équivalent métabolique) selon l'intensité
_MET_BY_INTENSITE: dict[str, float] = {
    "faible": 3.5,
    "legere": 3.5,
    "légère": 3.5,
    "moderee": 5.0,
    "modérée": 5.0,
    "modere": 5.0,
    "elevee": 7.5,
    "élevée": 7.5,
    "eleve": 7.5,
    "forte": 7.5,
    "intense": 8.0,
    "maximale": 9.0,
}


def _estimate_calories(duree_min: float, intensite: str | None, poids_kg: float | None) -> int:
    """Calories brûlées ≈ MET × poids(kg) × durée(h). Poids par défaut 70 kg."""
    met = _MET_BY_INTENSITE.get((intensite or "moderee").lower().strip(), 5.0)
    poids = poids_kg if poids_kg and poids_kg > 0 else 70.0
    minutes = max(float(duree_min or 0), 0.0)
    return round(met * poids * (minutes / 60.0))


def _db_muscles(ex_db: Exercice) -> list[str]:
    """Liste lisible des muscles ciblés par un exercice BDD."""
    muscles: list[str] = []
    if ex_db.target_muscles_json:
        try:
            parsed = _json.loads(ex_db.target_muscles_json)
            if isinstance(parsed, list):
                muscles.extend(str(m) for m in parsed if m)
        except Exception:
            pass
    if not muscles and ex_db.muscle_cible_principal:
        muscles.append(ex_db.muscle_cible_principal)
    if ex_db.body_part_principale:
        fr = _BODYPART_EN_TO_FR.get(ex_db.body_part_principale.lower())
        if fr and fr not in muscles:
            muscles.append(fr)
    return muscles


def _build_exercise_catalog(db: Session) -> tuple[list[dict], dict[int, Exercice]]:
    """Construit le catalogue d'exercices BDD (avec GIF) à proposer au LLM."""
    from sqlalchemy import select as sa_select

    rows: list[Exercice] = db.execute(
        sa_select(Exercice).where(Exercice.gif_180_path.is_not(None))
    ).scalars().all()

    catalog: list[dict] = []
    id_map: dict[int, Exercice] = {}
    for ex_db in rows:
        id_map[ex_db.exercice_id] = ex_db
        bp = (ex_db.body_part_principale or "").lower()
        catalog.append({
            "id": ex_db.exercice_id,
            "nom": ex_db.nom,
            "body_part": bp,
            "groupe": _BODYPART_EN_TO_FR.get(bp, bp or "general"),
            "muscle": ex_db.muscle_cible_principal or "general",
            "materiel": ex_db.equipement_principal or "poids du corps",
        })
    return catalog, id_map


def _finalize_exercise(ex_db: Exercice, meta: dict, duree_defaut: int) -> dict:
    """Transforme un exercice BDD + métadonnées LLM en item d'affichage."""
    try:
        duree = int(meta.get("duree_min") or 0)
    except (TypeError, ValueError):
        duree = 0
    if duree <= 0:
        duree = duree_defaut
    try:
        series = int(meta.get("series") or 3)
    except (TypeError, ValueError):
        series = 3
    materiel = [ex_db.equipement_principal] if ex_db.equipement_principal else []
    return {
        "nom": ex_db.nom,
        "muscles": _db_muscles(ex_db),
        "series": series,
        "repetitions": str(meta.get("repetitions") or "10-12"),
        "repos": str(meta.get("repos") or "60s"),
        "intensite": str(meta.get("intensite") or "moderee"),
        "duree_min": duree,
        "justification": str(meta.get("justification") or "").strip(),
        "equipement_necessaire": materiel,
        "gif_url": media_url("exercises", ex_db.gif_180_path),
        "nom_db": ex_db.nom,
        "exercice_id_db": ex_db.exercice_id,
        "body_part": ex_db.body_part_principale,
    }


def _muscle_to_parts(muscle: str) -> list[str]:
    """Convertit un libellé muscle (FR ou body_part EN) en body_parts BDD candidats."""
    ml = (muscle or "").lower().strip()
    parts = list(_TARGET_MUSCLE_TO_BODYPART.get(ml, []))
    if ml in _BODYPART_EN_TO_FR and ml not in parts:
        parts.append(ml)
    return parts


def _danger_keywords(avoid: set[str]) -> set[str]:
    """Mots-clés (FR) interdits dans un exercice, déduits des zones blessées à éviter."""
    kws: set[str] = set()
    for keys, parts in _INJURY_TO_BODYPART:
        if any(p in avoid for p in parts):
            kws.update(k.strip() for k in keys)
    return kws


def _finalize_invented(
    meta: dict,
    by_part: dict[str, list[Exercice]],
    used: set[int],
    avoid: set[str],
    duree_defaut: int,
) -> dict | None:
    """Construit un exercice INVENTÉ par le LLM (hors catalogue), avec un GIF similaire si possible."""
    nom = str(meta.get("nom") or "").strip()
    if not nom:
        return None
    muscles = [str(m) for m in (meta.get("muscles") or []) if str(m).strip()]

    # Sécurité : rejeter un exercice inventé qui sollicite une zone douloureuse
    danger = _danger_keywords(avoid)
    if danger:
        text = (nom + " " + " ".join(muscles)).lower()
        if any(k in text for k in danger):
            return None

    try:
        duree = int(meta.get("duree_min") or 0)
    except (TypeError, ValueError):
        duree = 0
    if duree <= 0:
        duree = duree_defaut
    try:
        series = int(meta.get("series") or 3)
    except (TypeError, ValueError):
        series = 3

    # GIF d'un exercice BDD du même groupe (non blessé), sinon aucun
    gif_url: str | None = None
    nom_db: str | None = None
    ex_id_db: int | None = None
    target_parts: list[str] = []
    for m in muscles:
        for p in _muscle_to_parts(m):
            if p not in target_parts:
                target_parts.append(p)
    for part in target_parts:
        if part in avoid:
            continue
        for cand in by_part.get(part, []):
            if cand.exercice_id not in used:
                used.add(cand.exercice_id)
                gif_url = media_url("exercises", cand.gif_180_path)
                nom_db = cand.nom
                ex_id_db = cand.exercice_id
                break
        if gif_url:
            break

    return {
        "nom": nom,
        "muscles": muscles,
        "series": series,
        "repetitions": str(meta.get("repetitions") or "12-15"),
        "repos": str(meta.get("repos") or "60s"),
        "intensite": str(meta.get("intensite") or "moderee"),
        "duree_min": duree,
        "justification": str(meta.get("justification") or "").strip(),
        "equipement_necessaire": [],
        "gif_url": gif_url,
        "nom_db": nom_db,
        "exercice_id_db": ex_id_db,
        "body_part": None,
    }


def _resolve_selection(
    selection: list[dict],
    id_map: dict[int, Exercice],
    filtered_catalog: list[dict],
    program: dict,
    duree_defaut: int,
) -> list[dict]:
    """Résout la sélection du LLM : id du catalogue filtré (avec GIF) OU exercice inventé."""
    avoid = _avoided_bodyparts(program)
    filtered_ids = {c["id"] for c in filtered_catalog}
    by_part: dict[str, list[Exercice]] = {}
    for c in filtered_catalog:
        by_part.setdefault((c.get("body_part") or "").lower(), []).append(id_map[c["id"]])

    result: list[dict] = []
    used: set[int] = set()
    for meta in selection:
        raw_id = meta.get("id")
        try:
            ex_id: int | None = int(raw_id)
        except (TypeError, ValueError):
            ex_id = None
        # id valide ET autorisé par le filtre → exercice BDD avec GIF
        if ex_id is not None and ex_id in id_map and ex_id in filtered_ids and ex_id not in used:
            used.add(ex_id)
            result.append(_finalize_exercise(id_map[ex_id], meta, duree_defaut))
        else:
            # id absent ou exercice filtré (interdit) → traité comme inventé (sinon ignoré)
            inv = _finalize_invented(meta, by_part, used, avoid, duree_defaut)
            if inv:
                result.append(inv)
    return result


def _fallback_selection(
    program: dict,
    filtered_catalog: list[dict],
    id_map: dict[int, Exercice],
    nb: int,
    duree_defaut: int,
) -> list[dict]:
    """Repli déterministe : catalogue filtré ciblé sur les muscles, complété au poids du corps."""
    avoid = _avoided_bodyparts(program)
    objectif = program.get("objectif", "sante")
    niveau = program.get("niveau", "intermediaire")
    type_seance = (program.get("type_seance") or "").lower()
    lieu = program.get("lieu") or "votre lieu d'entrainement"
    douleur = (program.get("douleur") or "").strip()
    cardiac = "cardiaque" in " ".join(program.get("contraintes_sante") or []).lower()

    by_part: dict[str, list[Exercice]] = {}
    for c in filtered_catalog:
        by_part.setdefault((c.get("body_part") or "").lower(), []).append(id_map[c["id"]])

    wanted_parts: list[str] = []
    for m in program.get("muscles", []):
        for part in _TARGET_MUSCLE_TO_BODYPART.get(str(m).lower().strip(), []):
            if part not in wanted_parts:
                wanted_parts.append(part)
    if not wanted_parts:
        wanted_parts = list(by_part.keys())

    chosen: list[Exercice] = []
    used: set[int] = set()
    progressed = True
    while len(chosen) < nb and progressed:
        progressed = False
        for part in wanted_parts:
            if len(chosen) >= nb:
                break
            for cand in by_part.get(part, []):
                if cand.exercice_id not in used:
                    used.add(cand.exercice_id)
                    chosen.append(cand)
                    progressed = True
                    break
    if len(chosen) < nb:
        for c in filtered_catalog:
            if len(chosen) >= nb:
                break
            ex_db = id_map[c["id"]]
            if ex_db.exercice_id not in used:
                used.add(ex_db.exercice_id)
                chosen.append(ex_db)

    result: list[dict] = []
    for ex_db in chosen:
        groupe_fr = _BODYPART_EN_TO_FR.get((ex_db.body_part_principale or "").lower(), "ce groupe musculaire")
        meta = {
            "series": 3,
            "repetitions": "10-12" if niveau != "debutant" else "12-15",
            "repos": "90s",
            "intensite": "faible" if cardiac else "moderee",
            "justification": (
                f"Choisi dans le catalogue pour travailler {groupe_fr}, adapté à votre objectif "
                f"{objectif} (niveau {niveau}) et réalisable à {lieu}."
            ),
        }
        result.append(_finalize_exercise(ex_db, meta, duree_defaut))

    # Compléter avec des exercices au poids du corps si le catalogue filtré est insuffisant
    if len(result) < nb:
        existing = {r["nom"].lower() for r in result}
        pool = [g for g in _GENERIC_BODYWEIGHT if not any(p in avoid for p in g["parts"])]
        pool.sort(key=lambda g: 0 if g["cardio"] == (type_seance == "cardio") else 1)
        for g in pool:
            if len(result) >= nb:
                break
            if g["nom"].lower() in existing:
                continue
            justif = (
                f"Exercice au poids du corps {'cardio ' if g['cardio'] else ''}réalisable à {lieu} sans matériel, "
                f"adapté à votre objectif {objectif} et à votre niveau {niveau}"
            )
            if douleur:
                justif += f", choisi pour ne pas solliciter la zone douloureuse ({douleur})"
            if cardiac:
                justif += ", à intensité maîtrisée compte tenu de votre contrainte cardiaque"
            justif += "."
            meta = {
                "nom": g["nom"],
                "muscles": g["muscles"],
                "series": 3,
                "repetitions": "30s" if g["cardio"] else ("12-15" if niveau != "avance" else "15-20"),
                "repos": "30s" if g["cardio"] else "60s",
                "intensite": "faible" if cardiac else "moderee",
                "duree_min": duree_defaut,
                "justification": justif,
            }
            inv = _finalize_invented(meta, by_part, used, avoid, duree_defaut)
            if inv:
                result.append(inv)
                existing.add(g["nom"].lower())

    return result[:nb]


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
        document_store.log_ai_call(
            user.utilisateur_id, "gemini", "gemini-2.5-flash", "unavailable", 0,
            {"reason": "GEMINI_API_KEY manquante"},
        )
        raise HTTPException(
            status_code=503,
            detail="Gemini Vision non disponible — configurez GEMINI_API_KEY dans .env",
        )

    started = time.perf_counter()
    try:
        foods_raw = await service.analyze(image_bytes)
    except Exception as exc:  # noqa: BLE001 - on journalise puis on relaie l'erreur
        document_store.log_ai_call(
            user.utilisateur_id, "gemini", "gemini-2.5-flash", "error",
            int((time.perf_counter() - started) * 1000), {"error": type(exc).__name__},
        )
        raise
    # Liste vide = Gemini n'a rien renvoye d'exploitable (erreur HTTP, parse, timeout) -> fallback.
    document_store.log_ai_call(
        user.utilisateur_id, "gemini", "gemini-2.5-flash",
        "success" if foods_raw else "fallback",
        int((time.perf_counter() - started) * 1000),
        {"foods_count": len(foods_raw), "fallback": not foods_raw},
    )

    foods = [
        DetectedFood(
            name=f.get("name", "inconnu"),
            confidence=float(f.get("confidence", 0.0)),
            quantity_g=f.get("quantity_g"),
            macros=FoodMacros(**f["macros"]) if f.get("macros") else None,
        )
        for f in foods_raw
    ]

    response = MealAnalysisResponse(
        foods=foods,
        total_macros=_sum_macros(foods_raw),
        source="gemini-2.5-flash",
    )

    # Persistance NoSQL: le resultat de vision a un schema variable -> MongoDB.
    document_store.save_meal_analysis(
        user.utilisateur_id,
        response.model_dump(mode="json"),
        source="gemini-2.5-flash",
    )

    return response


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

    profile = {
        "goal": request.objectif_principal or getattr(user, "objectif_principal", "santé"),
        "fitness_level": request.niveau_sportif or getattr(user, "niveau_activite", "débutant"),
        "poids_kg": getattr(user, "poids_kg", None),
        "daily_targets": {"calories": base.daily_calories_target, "proteins_g": base.daily_proteins_target_g} if hasattr(base, "daily_calories_target") else {},
        "imbalances": base.imbalances if hasattr(base, "imbalances") else [],
        "allergies": request.allergies or [],
        "regime": request.regime_alimentaire or "",
        "contraintes_sante": request.contraintes_sante or [],
        "preferences": request.preferences_alimentaires or [],
        "aliments_evites": request.aliments_evites or [],
        "culture": request.culture_alimentaire or "",
        "budget": request.budget or "",
        "temps_preparation": request.temps_preparation or "",
        "type_repas": request.type_repas or "",
    }
    equipement_disponible = request.equipement_disponible or []
    if equipement_disponible:
        materiel_label = ", ".join(equipement_disponible)
    elif (request.lieu or "").lower() == "salle":
        materiel_label = "salle de sport (équipée)"
    else:
        materiel_label = "aucun (poids du corps)"
    sport_program = {
        "sessions": request.frequence_seances_hebdo or 3,
        "muscles": request.muscles_cibles or [],
        "duree_min": request.duree_seance_min or 60,
        "materiel": materiel_label,
        "equipement_disponible": equipement_disponible,
        "type_seance": request.type_seance or "",
        "douleur": request.douleur_limitation or "",
        "lieu": request.lieu or "",
        "niveau": request.niveau_sportif or "",
        "contraintes_sante": request.contraintes_sante or [],
        "objectif": request.objectif_principal or getattr(user, "objectif_principal", "santé"),
    }

    llm = OllamaLLMService(settings)
    ollama_model = settings.ollama_model
    if not llm.is_available():
        document_store.log_ai_call(
            user.utilisateur_id, "ollama", ollama_model, "unavailable", 0,
            {"reason": "service Ollama injoignable"},
        )
        return RecommendationResponse(
            sport_tips=[],
            nutrition_tips=[],
            meal_plan=[],
            source="unavailable",
        )
    started = time.perf_counter()

    # Catalogue BDD filtré selon lieu / matériel / zones douloureuses
    catalog, id_map = _build_exercise_catalog(db)
    filtered_catalog = _filter_catalog(catalog, sport_program)
    duree_totale = request.duree_seance_min or 60
    nb_exercices = max(4, min(7, duree_totale // 20))
    duree_defaut = max(5, duree_totale // nb_exercices) if nb_exercices else 15
    logger.info(
        "Sport reco: catalogue=%d filtré=%d (lieu=%s matériel=%s douleur=%s) nb=%d",
        len(catalog), len(filtered_catalog), sport_program["lieu"],
        materiel_label, sport_program["douleur"], nb_exercices,
    )

    sport_tips, nutrition_tips, meal_plan, selection = await _run_llm(
        llm, profile, sport_program, filtered_catalog, nb_exercices,
    )

    # Résolution : id du catalogue filtré (GIF réel) ou exercice inventé par le LLM
    clean_training = _resolve_selection(selection, id_map, filtered_catalog, sport_program, duree_defaut)
    used_training_fallback = len(clean_training) < nb_exercices
    if used_training_fallback:
        # Compléter / remplacer par un repli déterministe ciblé (catalogue + poids du corps)
        clean_training = _fallback_selection(sport_program, filtered_catalog, id_map, nb_exercices, duree_defaut)
    # Le LLM a-t-il vraiment produit du contenu ? (sinon repli deterministe)
    llm_failed = not (sport_tips or nutrition_tips or meal_plan)

    # Estimation des calories brûlées par exercice (selon intensité, durée et poids)
    poids_kg = getattr(user, "poids_kg", None)
    for item in clean_training:
        item["calories"] = _estimate_calories(item.get("duree_min") or 0, item.get("intensite"), poids_kg)

    response = RecommendationResponse(
        sport_tips=sport_tips,
        nutrition_tips=nutrition_tips,
        meal_plan=[d for d in meal_plan if isinstance(d, dict)],
        training_plan=clean_training,
        source="ollama-llama3.2",
    )

    # Persistance NoSQL: recommandations + contexte utilisateur -> MongoDB.
    payload = response.model_dump(mode="json")
    payload["contexte_utilisateur"] = {
        "utilisateur_id": user.utilisateur_id,
        "objectif": profile.get("goal"),
        "niveau_sportif": profile.get("fitness_level"),
        "allergies": profile.get("allergies"),
        "regime": profile.get("regime"),
        "contraintes_sante": profile.get("contraintes_sante"),
        "preferences": profile.get("preferences"),
        "aliments_evites": profile.get("aliments_evites"),
        "culture": profile.get("culture"),
        "budget": profile.get("budget"),
        "type_repas": profile.get("type_repas"),
        "programme_sport": {
            "sessions": sport_program.get("sessions"),
            "muscles": sport_program.get("muscles"),
            "duree_min": sport_program.get("duree_min"),
            "materiel": sport_program.get("materiel"),
            "type_seance": sport_program.get("type_seance"),
            "lieu": sport_program.get("lieu"),
            "douleur": sport_program.get("douleur"),
        },
    }
    document_store.save_recommendation(user.utilisateur_id, payload, source="ollama-llama3.2")

    # Journal technique de l'appel IA: latence, erreurs, fallback.
    document_store.log_ai_call(
        user.utilisateur_id, "ollama", ollama_model,
        "fallback" if (llm_failed or used_training_fallback) else "success",
        int((time.perf_counter() - started) * 1000),
        {
            "fallback": llm_failed or used_training_fallback,
            "llm_failed": llm_failed,
            "training_fallback": used_training_fallback,
            "sport_tips": len(sport_tips),
            "nutrition_tips": len(nutrition_tips),
            "exercices": len(clean_training),
        },
    )

    return response


@router.get(
    "/analyse-repas/history",
    summary="Historique NoSQL des analyses de plats",
    description="Relit les derniers documents d'analyse stockes dans MongoDB (collection food_analyses).",
)
def analyse_repas_history(
    user: Utilisateur = Depends(current_user),
) -> dict[str, Any]:
    return {"data": document_store.recent_meal_analyses(user.utilisateur_id)}


@router.get(
    "/recommandations/history",
    summary="Historique NoSQL des recommandations",
    description="Relit les dernieres recommandations stockees dans MongoDB (collection recommendations).",
)
def recommandations_history(
    user: Utilisateur = Depends(current_user),
) -> dict[str, Any]:
    return {"data": document_store.recent_recommendations(user.utilisateur_id)}


@router.post(
    "/recommandations/feedback",
    status_code=201,
    summary="Retour utilisateur sur une recommandation (NoSQL)",
    description="Enregistre un feedback dans MongoDB (collection recommendation_feedback).",
)
def recommandations_feedback(
    payload: RecommendationFeedbackRequest,
    user: Utilisateur = Depends(current_user),
) -> dict[str, Any]:
    feedback_id = document_store.save_feedback(user.utilisateur_id, payload.model_dump())
    return {"data": {"feedback_id": feedback_id, "saved": feedback_id is not None}}


@router.get(
    "/recommandations/feedback/history",
    summary="Historique NoSQL des retours utilisateurs",
    description="Relit les feedbacks stockes dans MongoDB (collection recommendation_feedback).",
)
def recommandations_feedback_history(
    user: Utilisateur = Depends(current_user),
) -> dict[str, Any]:
    return {"data": document_store.recent_feedback(user.utilisateur_id)}


@router.get(
    "/ai-calls/history",
    summary="Journal NoSQL des appels IA (observabilite)",
    description="Relit le journal des appels IA dans MongoDB (collection ai_provider_calls): provider, modele, duree, statut.",
)
def ai_calls_history(
    user: Utilisateur = Depends(current_user),
) -> dict[str, Any]:
    return {"data": document_store.recent_ai_calls(user.utilisateur_id)}


async def _run_llm(
    llm: OllamaLLMService,
    profile: dict,
    sport_program: dict,
    catalog: list[dict],
    nb_exercices: int,
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
        selection = await llm.select_training_plan(profile, sport_program, catalog, nb_exercices)
    except Exception:
        selection = []
    return nutrition_tips, sport_tips, meal_plan, selection


class SeanceExerciceInput(BaseModel):
    nom: str
    exercice_id_db: int | None = None
    series: int | None = None
    repetitions: str | None = None
    repos: str | None = None
    duree_min: float | None = None
    intensite: str | None = None
    calories: float | None = None
    justification: str | None = None
    muscles: list[str] = []


class SaveSeanceRequest(BaseModel):
    type_seance: str | None = None
    duree_min: int | None = None
    niveau: str | None = None
    frequence: int | None = None
    objectif: str | None = None
    exercices: list[SeanceExerciceInput]


def _parse_reps(rep: str | None) -> int | None:
    """Extrait le premier nombre de répétitions/durée (ex: '10-12' → 10, '30s' → 30)."""
    if not rep:
        return None
    m = re.search(r"\d+", str(rep))
    return int(m.group()) if m else None


@router.post(
    "/seances",
    status_code=201,
    summary="Enregistre une séance recommandée dans l'historique",
    description=(
        "Crée une séance d'entraînement et lie chaque exercice recommandé. "
        "Les exercices issus du catalogue gardent leur GIF ; les exercices générés "
        "au poids du corps sont rattachés à un exercice représentatif avec leur nom en commentaire."
    ),
)
def save_seance(
    req: SaveSeanceRequest,
    db: Session = Depends(get_db),
    user: Utilisateur = Depends(current_user),
) -> dict[str, Any]:
    if not req.exercices:
        raise HTTPException(status_code=422, detail="Aucun exercice à enregistrer.")

    # Index du catalogue pour rattacher les exercices inventés (FK exercice_id obligatoire)
    _, id_map = _build_exercise_catalog(db)
    by_part: dict[str, list[Exercice]] = {}
    for ex_db in id_map.values():
        by_part.setdefault((ex_db.body_part_principale or "").lower(), []).append(ex_db)
    anchor_default = next(iter(id_map.values()), None)

    now = datetime.utcnow()
    seance = SeanceEntrainement(
        utilisateur_id=user.utilisateur_id,
        date_seance=now,
        type_entrainement=(req.type_seance or "MUSCULATION").upper()[:80],
        duree_seance_min=req.duree_min,
        frequence_entrainement_j_sem=req.frequence,
        niveau_experience=(req.niveau or None),
        cree_le=now,
    )
    db.add(seance)
    db.flush()  # récupère seance_id

    poids_kg = getattr(user, "poids_kg", None)
    saved = 0
    total_calories = 0.0
    for ordre, ex in enumerate(req.exercices, start=1):
        # Choix de l'exercice BDD à lier
        target = None
        if ex.exercice_id_db and ex.exercice_id_db in id_map:
            target = id_map[ex.exercice_id_db]
            commentaire = ex.nom
        else:
            # Exercice généré : rattacher à un exercice représentatif du même groupe
            for m in ex.muscles:
                for part in _muscle_to_parts(m):
                    if by_part.get(part):
                        target = by_part[part][0]
                        break
                if target:
                    break
            if target is None:
                target = anchor_default
            commentaire = f"{ex.nom} (au poids du corps)"

        if target is None:
            continue  # aucun exercice en base, impossible de lier

        if ex.justification:
            commentaire = f"{commentaire} — {ex.justification}"

        # Calories : valeur fournie sinon estimée (MET × poids × durée)
        calories = ex.calories
        if calories is None or calories <= 0:
            calories = _estimate_calories(ex.duree_min or 0, ex.intensite, poids_kg)
        total_calories += calories or 0

        db.add(SeanceExercice(
            seance_id=seance.seance_id,
            exercice_id=target.exercice_id,
            ordre_exercice=ordre,
            series_nb=ex.series,
            repetitions_nb=_parse_reps(ex.repetitions),
            duree_min=ex.duree_min,
            calories_brulees_estimees=calories,
            commentaire=commentaire[:255],
            cree_le=now,
        ))
        saved += 1

    seance.calories_brulees_total = round(total_calories, 1)
    db.commit()
    db.refresh(seance)
    logger.info("Séance %d enregistrée (%d exercices) pour user %d", seance.seance_id, saved, user.utilisateur_id)
    return {"seance_id": seance.seance_id, "exercices_enregistres": saved}


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
