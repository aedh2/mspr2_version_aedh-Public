"""Repository documentaire MongoDB (couche NoSQL).

Quatre collections alimentees par les fonctionnalites IA :
  - ``food_analyses``           : resultats d'analyse de plats (vision IA, schema variable)
  - ``recommendations``         : recommandations sport/nutrition generees
  - ``ai_provider_calls``       : journal de chaque appel IA (provider, modele, duree, statut)
  - ``recommendation_feedback`` : retours utilisateurs sur les recommandations

Chaque fonction est tolerante aux pannes : en l'absence de Mongo, les
ecritures renvoient ``None`` et les lectures renvoient une liste vide,
sans jamais interrompre la requete HTTP en cours.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from app.db import mongo

try:
    from pymongo import DESCENDING
    from pymongo.errors import PyMongoError
except ImportError:  # pragma: no cover
    DESCENDING = -1  # type: ignore[assignment]
    PyMongoError = Exception  # type: ignore[assignment,misc]

logger = logging.getLogger(__name__)

MEAL_ANALYSES = "food_analyses"
RECOMMENDATIONS = "recommendations"
AI_CALLS = "ai_provider_calls"
FEEDBACK = "recommendation_feedback"

_indexed: set[str] = set()


def _collection(name: str):
    db = mongo.get_mongo_db()
    if db is None:
        return None
    collection = db[name]
    if name not in _indexed:
        try:
            collection.create_index([("utilisateur_id", 1), ("created_at", DESCENDING)])
            _indexed.add(name)
        except PyMongoError as exc:  # noqa: BLE001
            logger.warning("Index Mongo non cree sur %s: %s", name, exc)
    return collection


def _save(name: str, utilisateur_id: int, source: str, payload: dict[str, Any]) -> str | None:
    collection = _collection(name)
    if collection is None:
        return None
    document = {
        "utilisateur_id": utilisateur_id,
        "source": source,
        "created_at": datetime.now(timezone.utc),
        "payload": payload,
    }
    try:
        result = collection.insert_one(document)
        return str(result.inserted_id)
    except PyMongoError as exc:  # noqa: BLE001
        logger.warning("Ecriture Mongo echouee sur %s: %s", name, exc)
        mongo.invalidate()
        return None


def _recent(name: str, utilisateur_id: int, limit: int) -> list[dict[str, Any]]:
    collection = _collection(name)
    if collection is None:
        return []
    try:
        cursor = (
            collection.find({"utilisateur_id": utilisateur_id})
            .sort("created_at", DESCENDING)
            .limit(max(1, min(limit, 50)))
        )
        items: list[dict[str, Any]] = []
        for doc in cursor:
            doc["id"] = str(doc.pop("_id"))
            created = doc.get("created_at")
            if isinstance(created, datetime):
                doc["created_at"] = created.isoformat()
            items.append(doc)
        return items
    except PyMongoError as exc:  # noqa: BLE001
        logger.warning("Lecture Mongo echouee sur %s: %s", name, exc)
        mongo.invalidate()
        return []


def save_meal_analysis(utilisateur_id: int, payload: dict[str, Any], source: str = "vision") -> str | None:
    return _save(MEAL_ANALYSES, utilisateur_id, source, payload)


def recent_meal_analyses(utilisateur_id: int, limit: int = 10) -> list[dict[str, Any]]:
    return _recent(MEAL_ANALYSES, utilisateur_id, limit)


def save_recommendation(utilisateur_id: int, payload: dict[str, Any], source: str = "moteur") -> str | None:
    return _save(RECOMMENDATIONS, utilisateur_id, source, payload)


def recent_recommendations(utilisateur_id: int, limit: int = 10) -> list[dict[str, Any]]:
    return _recent(RECOMMENDATIONS, utilisateur_id, limit)


def log_ai_call(
    utilisateur_id: int,
    provider: str,
    model: str,
    status: str,
    duration_ms: int,
    meta: dict[str, Any] | None = None,
) -> str | None:
    """Journalise un appel IA pour l'observabilite (KPI: repli, latence, dispo)."""
    payload = {
        "provider": provider,
        "model": model,
        "status": status,
        "duration_ms": duration_ms,
        "meta": meta or {},
    }
    return _save(AI_CALLS, utilisateur_id, provider, payload)


def recent_ai_calls(utilisateur_id: int, limit: int = 20) -> list[dict[str, Any]]:
    return _recent(AI_CALLS, utilisateur_id, limit)


def save_feedback(utilisateur_id: int, payload: dict[str, Any]) -> str | None:
    return _save(FEEDBACK, utilisateur_id, "utilisateur", payload)


def recent_feedback(utilisateur_id: int, limit: int = 20) -> list[dict[str, Any]]:
    return _recent(FEEDBACK, utilisateur_id, limit)
