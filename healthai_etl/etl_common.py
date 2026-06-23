from __future__ import annotations

import hashlib
import json
import math
import os
import random
import secrets
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from pathlib import Path
from typing import Any, Iterable, Optional

from dotenv import load_dotenv
from sqlalchemy import create_engine, text

load_dotenv()


@dataclass
class DbConfig:
    host: str = os.getenv("DB_HOST", "127.0.0.1")
    port: int = int(os.getenv("DB_PORT", "3306"))
    user: str = os.getenv("DB_USER", "root")
    password: str = os.getenv("DB_PASSWORD", "")
    db_name: str = os.getenv("DB_NAME", "healthai_coaching")


@dataclass
class ExecutionStats:
    lignes_lues: int = 0
    lignes_valides: int = 0
    lignes_invalides: int = 0
    nb_doublons_supprimes: int = 0
    nb_valeurs_corrigees: int = 0
    nb_rejets: int = 0

    @property
    def taux_qualite(self) -> float:
        if self.lignes_lues <= 0:
            return 0.0
        return round((self.lignes_valides / self.lignes_lues) * 100.0, 2)


FIRST_NAMES = [
    "Lucas", "Emma", "Nora", "Yanis", "Sarah", "Noah", "Ines", "Lina", "Adam", "Jade",
    "Milan", "Lea", "Sami", "Aya", "Rayan", "Maya", "Ethan", "Sofia", "Amine", "Lou",
    "Imran", "Camille", "Hugo", "Manon", "Nael", "Chloe", "Anas", "Yasmine", "Paul", "Elena",
    "Tom", "Louna", "Ilyes", "Mila", "Leo", "Nina", "Ismael", "Eva", "Arthur", "Salome",
]

LAST_NAMES = [
    "Martin", "Bernard", "Dubois", "Thomas", "Robert", "Richard", "Petit", "Durand", "Leroy", "Moreau",
    "Simon", "Laurent", "Lefebvre", "Michel", "Garcia", "David", "Bertrand", "Roux", "Vincent", "Fournier",
    "Morel", "Girard", "Andre", "Lefevre", "Mercier", "Dupont", "Lambert", "Bonnet", "Francois", "Martinez",
    "Legrand", "Garnier", "Faure", "Rousseau", "Blanc", "Chevalier", "Robin", "Masson", "Sanchez", "Muller",
]

ORGANISATIONS = [
    {
        "nom": "HealthAI Public",
        "adresse": "10 rue de la Sante, 75000 Paris",
        "image_path": r"C:/Users/aaljene/Downloads/healthai_etl_package/data/organisme/organisme1.jpg",
    },
    {
        "nom": "Vitality Lab Paris",
        "adresse": "18 avenue des Sports, 75015 Paris",
        "image_path": r"C:/Users/aaljene/Downloads/healthai_etl_package/data/organisme/organisme2.jpg",
    },
    {
        "nom": "Orion Fitness Center",
        "adresse": "25 boulevard du Stade, 69000 Lyon",
        "image_path": r"C:/Users/aaljene/Downloads/healthai_etl_package/data/organisme/organisme3.jpg",
    },
    {
        "nom": "Clinique Horizon Sante",
        "adresse": "7 rue du Bien-Etre, 31000 Toulouse",
        "image_path": r"C:/Users/aaljene/Downloads/healthai_etl_package/data/organisme/organisme4.jpg",
    },
    {
        "nom": "Nova Sleep Institute",
        "adresse": "3 impasse du Sommeil, 59000 Lille",
        "image_path": r"C:/Users/aaljene/Downloads/healthai_etl_package/data/organisme/organisme5.jpg",
    },
]

SOURCES = [
    ("Daily Food Nutrition Dataset", "Source CSV alimentation", "DATASET", "CSV"),
    ("Gym Members Exercise Tracking", "Source CSV sport/biometrie", "DATASET", "CSV"),
    ("Sleep Health and Lifestyle Dataset", "Source CSV sommeil/sante", "DATASET", "CSV"),
    ("ExerciseDB (JSON + GIFs)", "Source JSON exercices + assets", "DATASET", "JSON"),
    ("Synthetic User Seed", "Creation des comptes et organisations de demonstration", "SEED", "PYTHON"),
]

SOURCE_EXTERNAL_COLUMN = {
    "Gym Members Exercise Tracking": "gym_external_id",
    "Sleep Health and Lifestyle Dataset": "sleep_external_id",
}

QUALITY_TYPE_MAP = {
    "NULLABILITE": "NULLABILITE",
    "FORMAT": "FORMAT",
    "BORNE": "BORNE",
    "COHERENCE": "COHERENCE",
    "DUPLICAT": "DUPLICATION",
    "DUPLICATION": "DUPLICATION",
    "REFERENTIEL": "REFERENTIEL",
    "BUSINESS": "BUSINESS",
}


def get_engine():
    cfg = DbConfig()
    url = (
        f"mysql+pymysql://{cfg.user}:{cfg.password}@{cfg.host}:{cfg.port}/"
        f"{cfg.db_name}?charset=utf8mb4"
    )
    return create_engine(url, future=True, pool_pre_ping=True)


def fetch_one(conn, sql: str, params: Optional[dict] = None):
    return conn.execute(text(sql), params or {}).mappings().first()


def fetch_all(conn, sql: str, params: Optional[dict] = None):
    return conn.execute(text(sql), params or {}).mappings().all()


def ensure_source(conn, nom: str, description: str = None, type_source: str = None, format_source: str = None) -> int:
    row = fetch_one(conn, "SELECT source_id FROM source_donnees WHERE nom = :n", {"n": nom})
    if row:
        conn.execute(
            text(
                """
                UPDATE source_donnees
                   SET description = COALESCE(:description, description),
                       type_source = COALESCE(:type_source, type_source),
                       format_source = COALESCE(:format_source, format_source),
                       actif = 1
                 WHERE source_id = :source_id
                """
            ),
            {
                "source_id": int(row["source_id"]),
                "description": description,
                "type_source": type_source,
                "format_source": format_source,
            },
        )
        return int(row["source_id"])

    result = conn.execute(
        text(
            """
            INSERT INTO source_donnees (nom, description, type_source, format_source, actif, cree_le)
            VALUES (:nom, :description, :type_source, :format_source, 1, NOW())
            """
        ),
        {
            "nom": nom,
            "description": description,
            "type_source": type_source,
            "format_source": format_source,
        },
    )
    return int(result.lastrowid)


def seed_default_sources(conn) -> dict[str, int]:
    ids: dict[str, int] = {}
    for nom, description, type_source, format_source in SOURCES:
        ids[nom] = ensure_source(conn, nom, description, type_source, format_source)
    return ids


def seed_default_organisations(conn) -> dict[str, int]:
    ids: dict[str, int] = {}
    for org in ORGANISATIONS:
        row = fetch_one(conn, "SELECT organisation_id FROM organisation WHERE nom = :n", {"n": org["nom"]})
        if row:
            org_id = int(row["organisation_id"])
            conn.execute(
                text(
                    """
                    UPDATE organisation
                       SET adresse = :adresse,
                           image_path = :image_path
                     WHERE organisation_id = :organisation_id
                    """
                ),
                {
                    "organisation_id": org_id,
                    "adresse": org["adresse"],
                    "image_path": org["image_path"],
                },
            )
        else:
            result = conn.execute(
                text(
                    """
                    INSERT INTO organisation (nom, adresse, image_path, cree_le)
                    VALUES (:nom, :adresse, :image_path, NOW())
                    """
                ),
                org,
            )
            org_id = int(result.lastrowid)
        ids[org["nom"]] = org_id
    return ids


def get_source_id(conn, exact_name: str) -> int:
    row = fetch_one(conn, "SELECT source_id FROM source_donnees WHERE nom = :n", {"n": exact_name})
    if not row:
        raise RuntimeError(f"Source introuvable: {exact_name}")
    return int(row["source_id"])


def get_source_name(conn, source_id: int) -> Optional[str]:
    row = fetch_one(conn, "SELECT nom FROM source_donnees WHERE source_id = :id", {"id": source_id})
    return None if not row else str(row["nom"])


def source_external_column(conn, source_id: int) -> Optional[str]:
    source_name = get_source_name(conn, source_id)
    return SOURCE_EXTERNAL_COLUMN.get(source_name or "")


def get_organisation_id(conn, exact_name: str = "HealthAI Public") -> int:
    row = fetch_one(conn, "SELECT organisation_id FROM organisation WHERE nom = :n", {"n": exact_name})
    if not row:
        raise RuntimeError(f"Organisation introuvable: {exact_name}")
    return int(row["organisation_id"])


def list_organisation_ids(conn) -> list[int]:
    rows = fetch_all(conn, "SELECT organisation_id FROM organisation ORDER BY organisation_id")
    return [int(r["organisation_id"]) for r in rows]


def create_execution(conn, source_id: int) -> int:
    result = conn.execute(
        text(
            """
            INSERT INTO execution_etl (
              source_id, statut, demarre_le, lignes_lues, lignes_valides,
              lignes_invalides, nb_doublons_supprimes, nb_valeurs_corrigees,
              nb_rejets, taux_qualite, message
            ) VALUES (
              :source_id, 'EN_COURS', NOW(), 0, 0, 0, 0, 0, 0, NULL, NULL
            )
            """
        ),
        {"source_id": source_id},
    )
    return int(result.lastrowid)


def finish_execution(conn, execution_id: int, statut: str, stats: ExecutionStats, message: Optional[str] = None) -> None:
    conn.execute(
        text(
            """
            UPDATE execution_etl
               SET statut = :statut,
                   termine_le = NOW(),
                   lignes_lues = :lues,
                   lignes_valides = :valides,
                   lignes_invalides = :invalides,
                   nb_doublons_supprimes = :doublons,
                   nb_valeurs_corrigees = :corrigees,
                   nb_rejets = :rejets,
                   taux_qualite = :taux,
                   message = :message
             WHERE execution_id = :execution_id
            """
        ),
        {
            "execution_id": execution_id,
            "statut": statut,
            "lues": stats.lignes_lues,
            "valides": stats.lignes_valides,
            "invalides": stats.lignes_invalides,
            "doublons": stats.nb_doublons_supprimes,
            "corrigees": stats.nb_valeurs_corrigees,
            "rejets": stats.nb_rejets,
            "taux": stats.taux_qualite,
            "message": message,
        },
    )


def create_lot(conn, execution_id: int, source_id: int, nom_lot: str, cree_par: Optional[int] = None) -> int:
    result = conn.execute(
        text(
            """
            INSERT INTO lot_donnees (
              execution_id, source_id, nom_lot, statut, cree_par_utilisateur_id, cree_le
            ) VALUES (
              :execution_id, :source_id, :nom_lot, 'TELEVERSE', :cree_par, NOW()
            )
            """
        ),
        {
            "execution_id": execution_id,
            "source_id": source_id,
            "nom_lot": nom_lot,
            "cree_par": cree_par,
        },
    )
    return int(result.lastrowid)


def set_lot_status(conn, lot_id: int, statut: str, valide_par: Optional[int] = None, commentaire: Optional[str] = None) -> None:
    conn.execute(
        text(
            """
            UPDATE lot_donnees
               SET statut = :statut,
                   valide_par_utilisateur_id = COALESCE(:valide_par, valide_par_utilisateur_id),
                   valide_le = CASE WHEN :valide_par IS NULL THEN valide_le ELSE NOW() END,
                   commentaire_validation = COALESCE(:commentaire, commentaire_validation)
             WHERE lot_id = :lot_id
            """
        ),
        {
            "lot_id": lot_id,
            "statut": statut,
            "valide_par": valide_par,
            "commentaire": commentaire,
        },
    )


def seed_quality_rules(conn) -> dict[str, int]:
    rules = [
        ("food", "Food_Item", "FOOD_REQUIRED_ITEM", "NULLABILITE", "ERREUR", "Nom aliment obligatoire"),
        ("food", "Calories (kcal)", "FOOD_CAL_RANGE", "BORNE", "AVERT", "Calories entre 0 et 3000"),
        ("food", "Meal_Type", "FOOD_MEAL_REF", "REFERENTIEL", "AVERT", "Type de repas connu"),
        ("gym", "Weight (kg)", "GYM_WEIGHT_RANGE", "BORNE", "ERREUR", "Poids plausible entre 20 et 350 kg"),
        ("gym", "Height (m)", "GYM_HEIGHT_RANGE", "BORNE", "ERREUR", "Taille plausible entre 0.8 m et 2.5 m"),
        ("gym", "BPM", "GYM_BPM_ORDER", "COHERENCE", "ERREUR", "bpm_max >= bpm_moyen >= bpm_repos"),
        ("gym", "BMI", "GYM_IMC_COH", "COHERENCE", "AVERT", "IMC coherent avec poids et taille"),
        ("sleep", "Blood Pressure", "SLEEP_BP_FORMAT", "FORMAT", "ERREUR", "Format SYS/DIA valide"),
        ("sleep", "Blood Pressure", "SLEEP_BP_ORDER", "COHERENCE", "ERREUR", "SYS > DIA"),
        ("sleep", "Sleep Duration", "SLEEP_HOURS_RANGE", "BORNE", "ERREUR", "Sommeil entre 0 et 24h"),
        ("sleep", "Sleep Disorder", "SLEEP_DISORDER_REF", "REFERENTIEL", "AVERT", "Trouble normalisable"),
        ("exercise", "exerciseId", "EX_REQUIRED_ID", "NULLABILITE", "ERREUR", "ID exercice obligatoire"),
        ("exercise", "bodyParts", "EX_BODY_PART_REF", "REFERENTIEL", "AVERT", "Body part connue"),
        ("exercise", "equipments", "EX_EQUIP_REF", "REFERENTIEL", "AVERT", "Equipement connu"),
        ("exercise", "targetMuscles", "EX_MUSCLE_REF", "REFERENTIEL", "AVERT", "Muscle connu"),
    ]
    ids: dict[str, int] = {}
    for entite, champ, code, type_regle, severite, description in rules:
        conn.execute(
            text(
                """
                INSERT INTO regle_qualite (
                  entite, nom_champ, code_regle, type_regle, severite, description, actif
                ) VALUES (
                  :entite, :champ, :code, :type_regle, :severite, :description, 1
                )
                ON DUPLICATE KEY UPDATE
                  nom_champ = VALUES(nom_champ),
                  type_regle = VALUES(type_regle),
                  severite = VALUES(severite),
                  description = VALUES(description),
                  actif = 1
                """
            ),
            {
                "entite": entite,
                "champ": champ,
                "code": code,
                "type_regle": type_regle,
                "severite": severite,
                "description": description,
            },
        )
    rows = fetch_all(conn, "SELECT regle_id, code_regle FROM regle_qualite")
    for row in rows:
        ids[str(row["code_regle"])] = int(row["regle_id"])
    return ids


def insert_raw_records(conn, lot_id: int, entite: str, rows: Iterable[dict], ref_key: Optional[str] = None) -> None:
    payloads = []
    for row in rows:
        payloads.append(
            {
                "lot_id": lot_id,
                "entite": entite,
                "ref_externe": None if ref_key is None else as_text(row.get(ref_key)),
                "payload_json": safe_json_dumps(row),
            }
        )
    if payloads:
        conn.execute(
            text(
                """
                INSERT INTO enregistrement_brut (lot_id, entite, ref_externe, payload_json, cree_le)
                VALUES (:lot_id, :entite, :ref_externe, :payload_json, NOW())
                """
            ),
            payloads,
        )


def insert_stg_records(conn, records: list[dict]) -> None:
    if not records:
        return
    conn.execute(
        text(
            """
            INSERT INTO stg_import (
              lot_id, entite, ref_externe, source_payload_json, payload_normalise_json,
              est_parseable, statut_validation, code_rejet_potentiel, cree_le
            ) VALUES (
              :lot_id, :entite, :ref_externe, :source_payload_json, :payload_normalise_json,
              :est_parseable, :statut_validation, :code_rejet_potentiel, NOW()
            )
            """
        ),
        records,
    )


def _normalize_quality_type(value: Optional[str]) -> str:
    if not value:
        return "AUTRE"
    return QUALITY_TYPE_MAP.get(value, value if value in {"FORMAT", "NULLABILITE", "BORNE", "COHERENCE", "DUPLICATION", "REFERENTIEL", "BUSINESS", "AUTRE"} else "AUTRE")


def _rule_type_map(conn, regle_ids: set[int]) -> dict[int, str]:
    if not regle_ids:
        return {}
    placeholders = ", ".join(str(int(v)) for v in sorted(regle_ids))
    rows = fetch_all(conn, f"SELECT regle_id, type_regle FROM regle_qualite WHERE regle_id IN ({placeholders})")
    return {int(r["regle_id"]): _normalize_quality_type(str(r["type_regle"])) for r in rows}


def insert_quality_controls(conn, records: list[dict]) -> None:
    if not records:
        return
    regle_ids = {int(r["regle_id"]) for r in records if r.get("regle_id") is not None}
    regle_type_by_id = _rule_type_map(conn, regle_ids)

    payloads = []
    for record in records:
        regle_id = record.get("regle_id")
        type_controle = record.get("type_controle")
        if not type_controle and regle_id is not None:
            type_controle = regle_type_by_id.get(int(regle_id))
        payloads.append(
            {
                "execution_id": record["execution_id"],
                "lot_id": record.get("lot_id"),
                "regle_id": regle_id,
                "entite": record["entite"],
                "ref_externe": as_text(record.get("ref_externe")),
                "ref_ligne": as_text(record.get("ref_ligne")),
                "nom_champ": as_text(record.get("nom_champ")),
                "valeur_observee": as_text(record.get("valeur_observee")),
                "valeur_corrigee": as_text(record.get("valeur_corrigee")),
                "payload_json": safe_json_dumps(record.get("payload_json")) if isinstance(record.get("payload_json"), (dict, list)) else record.get("payload_json"),
                "niveau": record.get("niveau", "INFO"),
                "type_controle": _normalize_quality_type(type_controle),
                "decision_finale": record.get("decision_finale", "ACCEPTEE"),
                "est_bloquant": 1 if record.get("est_bloquant") else 0,
                "code_controle": record["code_controle"],
                "description": record["description"],
                "etape_pipeline": record.get("etape_pipeline", "VALIDATION"),
            }
        )

    conn.execute(
        text(
            """
            INSERT INTO controle_qualite_donnee (
              execution_id, lot_id, regle_id, entite, ref_externe, ref_ligne, nom_champ,
              valeur_observee, valeur_corrigee, payload_json, niveau, type_controle,
              decision_finale, est_bloquant, code_controle, description, etape_pipeline, cree_le
            ) VALUES (
              :execution_id, :lot_id, :regle_id, :entite, :ref_externe, :ref_ligne, :nom_champ,
              :valeur_observee, :valeur_corrigee, :payload_json, :niveau, :type_controle,
              :decision_finale, :est_bloquant, :code_controle, :description, :etape_pipeline, NOW()
            )
            """
        ),
        payloads,
    )


def insert_anomalies(conn, anomalies: list[dict]) -> None:
    if not anomalies:
        return
    records = []
    for anomaly in anomalies:
        niveau = str(anomaly.get("severite") or "INFO").upper()
        if niveau == "CRITIQUE":
            niveau = "ERREUR"
        if niveau not in {"INFO", "AVERT", "ERREUR"}:
            niveau = "INFO"
        records.append(
            {
                "execution_id": anomaly["execution_id"],
                "lot_id": anomaly.get("lot_id"),
                "regle_id": anomaly.get("regle_id"),
                "entite": anomaly["entite"],
                "ref_externe": anomaly.get("ref_externe"),
                "ref_ligne": anomaly.get("ref_ligne"),
                "nom_champ": anomaly.get("nom_champ"),
                "valeur_observee": anomaly.get("valeur_observee"),
                "valeur_corrigee": anomaly.get("valeur_corrigee"),
                "payload_json": anomaly.get("payload_json"),
                "niveau": niveau,
                "type_controle": anomaly.get("type_controle"),
                "decision_finale": anomaly.get(
                    "decision_finale",
                    "REJETEE" if niveau == "ERREUR" else "ACCEPTEE_AVEC_AVERTISSEMENT" if niveau == "AVERT" else "ACCEPTEE",
                ),
                "est_bloquant": anomaly.get("est_bloquant", 1 if niveau == "ERREUR" else 0),
                "code_controle": anomaly.get("code_anomalie") or anomaly.get("code_controle") or "ANOMALIE",
                "description": anomaly.get("description") or "Controle qualite",
                "etape_pipeline": anomaly.get("etape_pipeline", "VALIDATION"),
            }
        )
    insert_quality_controls(conn, records)


def insert_rejects(conn, rejects: list[dict]) -> None:
    if not rejects:
        return
    records = []
    for reject in rejects:
        records.append(
            {
                "execution_id": reject["execution_id"],
                "lot_id": reject.get("lot_id"),
                "regle_id": reject.get("regle_id"),
                "entite": reject["entite"],
                "ref_externe": reject.get("ref_externe"),
                "ref_ligne": reject.get("ref_ligne"),
                "nom_champ": reject.get("nom_champ"),
                "valeur_observee": reject.get("valeur_observee"),
                "valeur_corrigee": reject.get("valeur_corrigee"),
                "payload_json": reject.get("payload_json"),
                "niveau": "ERREUR",
                "type_controle": reject.get("type_controle", "AUTRE"),
                "decision_finale": "REJETEE",
                "est_bloquant": 1,
                "code_controle": reject.get("code_rejet") or reject.get("code_controle") or "REJET",
                "description": reject.get("description_rejet") or reject.get("description") or "Enregistrement rejete",
                "etape_pipeline": reject.get("etape_pipeline", "VALIDATION"),
            }
        )
    insert_quality_controls(conn, records)


def build_anomaly(
    execution_id: int,
    lot_id: int,
    regle_id: Optional[int],
    severite: str,
    entite: str,
    ref_ligne: Optional[str],
    nom_champ: Optional[str],
    code_anomalie: str,
    description: str,
    valeur_observee: Optional[Any] = None,
) -> dict:
    return {
        "execution_id": execution_id,
        "lot_id": lot_id,
        "regle_id": regle_id,
        "severite": severite,
        "entite": entite,
        "ref_ligne": ref_ligne,
        "nom_champ": nom_champ,
        "code_anomalie": code_anomalie,
        "valeur_observee": as_text(valeur_observee),
        "description": description,
    }


def build_reject(
    execution_id: int,
    lot_id: int,
    entite: str,
    ref_externe: Optional[Any],
    payload: dict,
    code_rejet: str,
    description_rejet: str,
) -> dict:
    return {
        "execution_id": execution_id,
        "lot_id": lot_id,
        "entite": entite,
        "ref_externe": as_text(ref_externe),
        "payload_json": safe_json_dumps(payload),
        "code_rejet": code_rejet,
        "description_rejet": description_rejet,
    }


def safe_json_dumps(value: Any) -> str:
    def normalize(obj: Any):
        if obj is None:
            return None
        if isinstance(obj, float) and math.isnan(obj):
            return None
        if isinstance(obj, dict):
            return {str(k): normalize(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [normalize(v) for v in obj]
        return obj

    return json.dumps(normalize(value), ensure_ascii=False)


def is_blank(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, float) and math.isnan(value):
        return True
    if isinstance(value, str) and value.strip().lower() in {"", "nan", "none", "null", "n/a", "na"}:
        return True
    return False


def as_text(value: Any) -> Optional[str]:
    if is_blank(value):
        return None
    return str(value).strip()


def to_float(value: Any) -> Optional[float]:
    if is_blank(value):
        return None
    try:
        return float(str(value).strip().replace(",", "."))
    except Exception:
        return None


def to_int(value: Any) -> Optional[int]:
    number = to_float(value)
    if number is None:
        return None
    return int(round(number))


def normalize_gender_fr(value: Any) -> str:
    if is_blank(value):
        return "Inconnu"
    v = str(value).strip().lower()
    if v in {"male", "m", "homme"}:
        return "Homme"
    if v in {"female", "f", "femme"}:
        return "Femme"
    return "Autre"


def normalize_meal_type(value: Any) -> str:
    if is_blank(value):
        return "Inconnu"
    v = str(value).strip().lower()
    if v in {"breakfast", "petitdejeuner", "petit déjeuner", "petit-dejeuner"}:
        return "PetitDejeuner"
    if v in {"lunch", "dejeuner", "déjeuner"}:
        return "Dejeuner"
    if v in {"dinner", "diner", "dîner"}:
        return "Diner"
    if v in {"snack", "collation"}:
        return "Collation"
    return "Autre"


def normalize_sleep_disorder(value: Any) -> str:
    if is_blank(value):
        return "Aucun"
    v = str(value).strip().lower()
    if v in {"none", "aucun", "no", "nan"}:
        return "Aucun"
    if "insom" in v:
        return "Insomnie"
    if "apnea" in v or "apnée" in v or "apnee" in v:
        return "Apnee"
    return "Autre"


def parse_blood_pressure(value: Any) -> tuple[Optional[int], Optional[int]]:
    if is_blank(value):
        return None, None
    raw = str(value).strip().replace(" ", "")
    if "/" not in raw:
        return None, None
    left, right = raw.split("/", 1)
    sys = to_int(left)
    dia = to_int(right)
    return sys, dia


def hours_to_minutes(value: Any) -> Optional[int]:
    number = to_float(value)
    if number is None:
        return None
    return int(round(number * 60))


def stable_hash(parts: Iterable[Any], length: int = 12) -> str:
    payload = "||".join("" if p is None else str(p) for p in parts)
    return hashlib.sha1(payload.encode("utf-8")).hexdigest()[:length]


def build_demo_datetime(base_date: Optional[date], default_hour: int, row_index: int, slot_minutes: int = 3) -> datetime:
    target_date = base_date or date.today()
    base_dt = datetime.combine(target_date, time(default_hour, 0, 0))
    return base_dt + timedelta(minutes=row_index * slot_minutes)


def parse_env_date(name: str) -> Optional[date]:
    raw = os.getenv(name)
    if not raw:
        return None
    return datetime.strptime(raw, "%Y-%m-%d").date()


def birthdate_from_age(age: Optional[int], reference_date: Optional[date] = None) -> Optional[date]:
    if age is None or age <= 0:
        return None
    ref = reference_date or date.today()
    return date(ref.year - age, 6, 15)


def unique_username(conn, base_username: str) -> str:
    row = fetch_one(conn, "SELECT utilisateur_id FROM utilisateur WHERE nom_utilisateur = :u", {"u": base_username})
    if not row:
        return base_username
    suffix = 2
    while True:
        candidate = f"{base_username}{suffix}"
        row = fetch_one(conn, "SELECT utilisateur_id FROM utilisateur WHERE nom_utilisateur = :u", {"u": candidate})
        if not row:
            return candidate
        suffix += 1


def unique_email(conn, base_email: str) -> str:
    row = fetch_one(conn, "SELECT utilisateur_id FROM utilisateur WHERE email = :e", {"e": base_email})
    if not row:
        return base_email
    local, domain = base_email.split("@", 1)
    suffix = 2
    while True:
        candidate = f"{local}{suffix}@{domain}"
        row = fetch_one(conn, "SELECT utilisateur_id FROM utilisateur WHERE email = :e", {"e": candidate})
        if not row:
            return candidate
        suffix += 1


def hash_password_demo(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), bytes.fromhex(salt), 210000)
    return f"pbkdf2_sha256$210000${salt}${digest.hex()}"


def generate_demo_password(prenom: str, nom: str, naissance: Optional[date], rng: random.Random) -> str:
    year = naissance.year if naissance else rng.randint(1960, 2006)
    suffix = rng.randint(10, 9999)
    return f"{nom}{year}{prenom}{suffix}"


def build_random_identity(rng: random.Random, conn, age: Optional[int], genre: str = "Inconnu") -> dict:
    prenom = rng.choice(FIRST_NAMES)
    nom = rng.choice(LAST_NAMES)
    naissance = birthdate_from_age(age)
    base_username = f"@{prenom.lower()}.{nom.lower()}"
    pseudo = unique_username(conn, base_username)
    base_email = f"{prenom.lower()}.{nom.lower()}@healthai.local"
    email = unique_email(conn, base_email)
    plain_password = generate_demo_password(prenom, nom, naissance, rng)
    return {
        "prenom": prenom,
        "nom": nom,
        "nom_utilisateur": pseudo,
        "email": email,
        "date_naissance": naissance,
        "genre": genre,
        "mot_de_passe_hash": hash_password_demo(plain_password),
        "mot_de_passe_clair": plain_password,
    }


def find_user_by_source_identity(conn, source_id: int, external_id: str) -> Optional[int]:
    column = source_external_column(conn, source_id)
    if not column or is_blank(external_id):
        return None
    row = fetch_one(conn, f"SELECT utilisateur_id FROM utilisateur WHERE {column} = :external_id LIMIT 1", {"external_id": external_id})
    return None if not row else int(row["utilisateur_id"])


def ensure_user_by_source_identity(
    conn,
    source_id: int,
    external_id: str,
    base_username: str,
    organisation_id: int,
    defaults: Optional[dict] = None,
) -> int:
    existing_user_id = find_user_by_source_identity(conn, source_id, external_id)
    if existing_user_id is not None:
        return existing_user_id

    defaults = defaults or {}
    username = unique_username(conn, base_username)
    email = defaults.get("email")
    if email:
        email = unique_email(conn, email)
    ext_column = source_external_column(conn, source_id)
    if not ext_column:
        raise RuntimeError(f"Aucune colonne externe definie pour la source_id={source_id}")

    payload = {
        "organisation_id": organisation_id,
        "nom_utilisateur": username,
        "prenom": defaults.get("prenom"),
        "nom": defaults.get("nom"),
        "email": email,
        "date_naissance": defaults.get("date_naissance"),
        "genre": defaults.get("genre", "Inconnu"),
        "taille_cm": defaults.get("taille_cm"),
        "role": defaults.get("role", "UTILISATEUR"),
        "statut": defaults.get("statut", "ACTIF"),
        "mot_de_passe_hash": defaults.get("mot_de_passe_hash"),
        "gym_external_id": external_id if ext_column == "gym_external_id" else None,
        "sleep_external_id": external_id if ext_column == "sleep_external_id" else None,
    }

    result = conn.execute(
        text(
            """
            INSERT INTO utilisateur (
              organisation_id, gym_external_id, sleep_external_id, nom_utilisateur,
              prenom, nom, email, date_naissance, genre, taille_cm,
              role, statut, mot_de_passe_hash, cree_le, modifie_le
            ) VALUES (
              :organisation_id, :gym_external_id, :sleep_external_id, :nom_utilisateur,
              :prenom, :nom, :email, :date_naissance, :genre, :taille_cm,
              :role, :statut, :mot_de_passe_hash, NOW(), NOW()
            )
            """
        ),
        payload,
    )
    return int(result.lastrowid)


def ensure_demo_user(conn, username: str, organisation_id: int, genre: str = "Inconnu", role: str = "UTILISATEUR") -> int:
    row = fetch_one(conn, "SELECT utilisateur_id FROM utilisateur WHERE nom_utilisateur = :u", {"u": username})
    if row:
        return int(row["utilisateur_id"])
    result = conn.execute(
        text(
            """
            INSERT INTO utilisateur (
              organisation_id, nom_utilisateur, genre, role, statut, cree_le, modifie_le
            ) VALUES (
              :organisation_id, :username, :genre, :role, 'ACTIF', NOW(), NOW()
            )
            """
        ),
        {
            "organisation_id": organisation_id,
            "username": username,
            "genre": genre,
            "role": role,
        },
    )
    return int(result.lastrowid)


def ensure_aliment(conn, source_id: int, nom: str, payload: dict) -> int:
    existing = fetch_one(conn, "SELECT aliment_id FROM aliment WHERE nom = :nom LIMIT 1", {"nom": nom})
    if existing:
        conn.execute(
            text(
                """
                UPDATE aliment
                   SET source_id = COALESCE(source_id, :source_id),
                       categorie = :categorie,
                       calories_kcal = :calories_kcal,
                       proteines_g = :proteines_g,
                       glucides_g = :glucides_g,
                       lipides_g = :lipides_g,
                       fibres_g = :fibres_g,
                       sucres_g = :sucres_g,
                       sodium_mg = :sodium_mg,
                       cholesterol_mg = :cholesterol_mg
                 WHERE aliment_id = :aliment_id
                """
            ),
            {**payload, "source_id": source_id, "aliment_id": int(existing["aliment_id"]), "nom": nom},
        )
        return int(existing["aliment_id"])

    result = conn.execute(
        text(
            """
            INSERT INTO aliment (
              source_id, nom, categorie, calories_kcal, proteines_g, glucides_g,
              lipides_g, fibres_g, sucres_g, sodium_mg, cholesterol_mg, cree_le
            ) VALUES (
              :source_id, :nom, :categorie, :calories_kcal, :proteines_g, :glucides_g,
              :lipides_g, :fibres_g, :sucres_g, :sodium_mg, :cholesterol_mg, NOW()
            )
            """
        ),
        {**payload, "source_id": source_id, "nom": nom},
    )
    return int(result.lastrowid)


def ensure_exercise(conn, source_id: int, exercise: dict) -> int:
    existing = fetch_one(conn, "SELECT exercice_id FROM exercice WHERE external_id = :eid", {"eid": exercise["external_id"]})
    payload = {**exercise, "source_id": source_id}
    if existing:
        conn.execute(
            text(
                """
                UPDATE exercice
                   SET source_id = :source_id,
                       nom = :nom,
                       gif_180_path = :gif_180_path,
                       gif_360_path = :gif_360_path,
                       gif_720_path = :gif_720_path,
                       gif_1080_path = :gif_1080_path,
                       body_part_principale = :body_part_principale,
                       muscle_cible_principal = :muscle_cible_principal,
                       equipement_principal = :equipement_principal,
                       body_parts_json = :body_parts_json,
                       target_muscles_json = :target_muscles_json,
                       secondary_muscles_json = :secondary_muscles_json,
                       equipments_json = :equipments_json,
                       instructions_json = :instructions_json
                 WHERE exercice_id = :exercice_id
                """
            ),
            {**payload, "exercice_id": int(existing["exercice_id"])}
        )
        return int(existing["exercice_id"])

    result = conn.execute(
        text(
            """
            INSERT INTO exercice (
              source_id, external_id, nom, gif_180_path, gif_360_path, gif_720_path,
              gif_1080_path, body_part_principale, muscle_cible_principal,
              equipement_principal, body_parts_json, target_muscles_json,
              secondary_muscles_json, equipments_json, instructions_json, cree_le
            ) VALUES (
              :source_id, :external_id, :nom, :gif_180_path, :gif_360_path, :gif_720_path,
              :gif_1080_path, :body_part_principale, :muscle_cible_principal,
              :equipement_principal, :body_parts_json, :target_muscles_json,
              :secondary_muscles_json, :equipments_json, :instructions_json, NOW()
            )
            """
        ),
        payload,
    )
    return int(result.lastrowid)


def ensure_plat(conn, utilisateur_id: int, source_id: int, lot_id: int, consomme_le: datetime, type_repas: str, nom_plat: Optional[str], calories_totales_kcal: Optional[float]) -> int:
    result = conn.execute(
        text(
            """
            INSERT INTO plat (
              utilisateur_id, source_id, lot_id, consomme_le, type_repas,
              nom_plat, calories_totales_kcal, cree_le
            ) VALUES (
              :utilisateur_id, :source_id, :lot_id, :consomme_le, :type_repas,
              :nom_plat, :calories_totales_kcal, NOW()
            )
            """
        ),
        {
            "utilisateur_id": utilisateur_id,
            "source_id": source_id,
            "lot_id": lot_id,
            "consomme_le": consomme_le,
            "type_repas": type_repas,
            "nom_plat": nom_plat,
            "calories_totales_kcal": calories_totales_kcal,
        },
    )
    return int(result.lastrowid)


def file_exists_or_none(path: Path) -> Optional[str]:
    return str(path).replace("\\", "/") if path.exists() else None
