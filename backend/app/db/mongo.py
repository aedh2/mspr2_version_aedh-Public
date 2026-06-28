"""Connecteur MongoDB (persistance documentaire / NoSQL).

La base relationnelle (MariaDB) reste la source de vérité structurée.
MongoDB stocke les documents à schéma variable produits par l'IA :
résultats d'analyse de plats et recommandations générées.

Le connecteur est volontairement tolérant aux pannes : si Mongo est
indisponible, les fonctions renvoient ``None`` sans lever d'exception,
afin que l'application reste fonctionnelle (mode dégradé).
"""
from __future__ import annotations

import logging
import time

from app.core.config import get_settings

try:
    from pymongo import MongoClient
    from pymongo.errors import PyMongoError
except ImportError:  # pragma: no cover - exercé seulement avant rebuild de l'image
    MongoClient = None  # type: ignore[assignment]
    PyMongoError = Exception  # type: ignore[assignment,misc]

logger = logging.getLogger(__name__)

_client: "MongoClient | None" = None
_database = None
_state = "unknown"  # unknown | ready | unavailable
_last_failure = 0.0
_RETRY_COOLDOWN_SECONDS = 20.0


def _connect():
    global _client, _database, _state, _last_failure
    settings = get_settings()
    if MongoClient is None:
        _state = "unavailable"
        _last_failure = time.monotonic()
        logger.warning("pymongo absent: persistance NoSQL desactivee.")
        return None
    try:
        client = MongoClient(
            settings.mongo_url,
            serverSelectionTimeoutMS=settings.mongo_timeout_ms,
            connectTimeoutMS=settings.mongo_timeout_ms,
            uuidRepresentation="standard",
        )
        client.admin.command("ping")
    except PyMongoError as exc:  # noqa: BLE001 - on degrade proprement
        _state = "unavailable"
        _last_failure = time.monotonic()
        logger.warning("MongoDB indisponible (%s): persistance NoSQL en mode degrade.", exc)
        return None

    _client = client
    _database = client[settings.mongo_db_name]
    _state = "ready"
    logger.info("MongoDB connecte: base=%s", settings.mongo_db_name)
    return _database


def get_mongo_db():
    """Retourne la base Mongo, ou ``None`` si indisponible (jamais d'exception)."""
    settings = get_settings()
    if not settings.mongo_enabled:
        return None
    if _database is not None and _state == "ready":
        return _database
    if _state == "unavailable" and (time.monotonic() - _last_failure) < _RETRY_COOLDOWN_SECONDS:
        return None
    return _connect()


def invalidate() -> None:
    """Force une reconnexion au prochain appel (apres une erreur d'I/O)."""
    global _database, _state
    _database = None
    _state = "unknown"


def mongo_status() -> str:
    """Statut lisible pour le healthcheck: ok | unavailable | disabled."""
    if not get_settings().mongo_enabled:
        return "disabled"
    return "ok" if get_mongo_db() is not None else "unavailable"
