from __future__ import annotations

import json
import os
from pathlib import Path

from etl_common import (
    ExecutionStats,
    as_text,
    build_anomaly,
    build_reject,
    create_execution,
    create_lot,
    ensure_exercise,
    finish_execution,
    get_engine,
    get_source_id,
    insert_anomalies,
    insert_raw_records,
    insert_rejects,
    insert_stg_records,
    safe_json_dumps,
    seed_quality_rules,
    set_lot_status,
)


def load_json_list(path: Path, key: str = "name") -> set[str]:
    if not path.exists():
        return set()
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    out = set()
    for item in data:
        value = item.get(key) if isinstance(item, dict) else None
        if value:
            out.add(str(value).strip().lower())
    return out


def infer_gif_path(dataset_dir: Path, subdir: str, gif_name: str) -> str | None:
    candidate = dataset_dir / subdir / gif_name
    if candidate.exists():
        return f"{subdir}/{gif_name}".replace("\\", "/")
    return None


def main() -> None:
    dataset_dir = Path(os.getenv("EXERCISE_DATASET_DIR", str(Path(__file__).resolve().parent.parent)))
    json_path = Path(os.getenv("EXERCISES_JSON", str(dataset_dir / "exercises.json")))
    bodyparts_path = Path(os.getenv("BODYPARTS_JSON", str(dataset_dir / "bodyParts.json")))
    equipments_path = Path(os.getenv("EQUIPMENTS_JSON", str(dataset_dir / "equipments.json")))
    muscles_path = Path(os.getenv("MUSCLES_JSON", str(dataset_dir / "muscles.json")))

    engine = get_engine()
    stats = ExecutionStats()
    anomalies: list[dict] = []
    rejects: list[dict] = []

    with engine.begin() as conn:
        source_id = get_source_id(conn, "ExerciseDB (JSON + GIFs)")
        execution_id = create_execution(conn, source_id)
        rule_ids = seed_quality_rules(conn)

    try:
        with open(json_path, "r", encoding="utf-8") as f:
            exercises = json.load(f)
        if not isinstance(exercises, list):
            raise RuntimeError("exercises.json doit contenir une liste")

        ref_bodyparts = load_json_list(bodyparts_path)
        ref_equipments = load_json_list(equipments_path)
        ref_muscles = load_json_list(muscles_path)
        stats.lignes_lues = len(exercises)

        with engine.begin() as conn:
            lot_id = create_lot(conn, execution_id, source_id, f"exercise_{Path(json_path).stem}_{os.getpid()}")
            set_lot_status(conn, lot_id, "VALIDE")
            insert_raw_records(conn, lot_id, "exercise", exercises, ref_key="exerciseId")

            stg_records: list[dict] = []
            seen_ids: set[str] = set()

            for index, ex in enumerate(exercises, start=1):
                ref_line = str(index)
                exercise_id = as_text(ex.get("exerciseId") or ex.get("id"))
                if exercise_id and exercise_id in seen_ids:
                    stats.nb_doublons_supprimes += 1
                    anomalies.append(build_anomaly(execution_id, lot_id, None, "AVERT", "exercise", ref_line, "exerciseId", "EX_DUPLICATE_ID", f"ID exercice duplique: {exercise_id}", exercise_id))
                    continue
                if exercise_id:
                    seen_ids.add(exercise_id)

                gif_name = as_text(ex.get("gifUrl")) or (f"{exercise_id}.gif" if exercise_id else None)
                body_parts = [str(v).strip() for v in ex.get("bodyParts", []) if str(v).strip()]
                target_muscles = [str(v).strip() for v in ex.get("targetMuscles", []) if str(v).strip()]
                secondary_muscles = [str(v).strip() for v in ex.get("secondaryMuscles", []) if str(v).strip()]
                equipments = [str(v).strip() for v in ex.get("equipments", []) if str(v).strip()]
                instructions = [str(v).strip() for v in ex.get("instructions", []) if str(v).strip()]

                normalized = {
                    "external_id": exercise_id,
                    "nom": as_text(ex.get("name")),
                    "gif_180_path": infer_gif_path(dataset_dir, "gifs_180x180", gif_name) if gif_name else None,
                    "gif_360_path": infer_gif_path(dataset_dir, "gifs_360x360", gif_name) if gif_name else None,
                    "gif_720_path": infer_gif_path(dataset_dir, "gifs_720x720", gif_name) if gif_name else None,
                    "gif_1080_path": infer_gif_path(dataset_dir, "gifs_1080x1080", gif_name) if gif_name else None,
                    "body_part_principale": body_parts[0] if body_parts else None,
                    "muscle_cible_principal": target_muscles[0] if target_muscles else None,
                    "equipement_principal": equipments[0] if equipments else None,
                    "body_parts_json": safe_json_dumps(body_parts),
                    "target_muscles_json": safe_json_dumps(target_muscles),
                    "secondary_muscles_json": safe_json_dumps(secondary_muscles),
                    "equipments_json": safe_json_dumps(equipments),
                    "instructions_json": safe_json_dumps(instructions),
                }

                parseable = True
                status = "VALIDE"
                reject_code = None

                if not exercise_id:
                    parseable = False
                    status = "REJETE"
                    reject_code = "EX_REQUIRED_ID"
                    anomalies.append(build_anomaly(execution_id, lot_id, rule_ids.get("EX_REQUIRED_ID"), "ERREUR", "exercise", ref_line, "exerciseId", "EX_REQUIRED_ID", "ID exercice manquant"))

                for bodypart in body_parts:
                    if ref_bodyparts and bodypart.lower() not in ref_bodyparts:
                        anomalies.append(build_anomaly(execution_id, lot_id, rule_ids.get("EX_BODY_PART_REF"), "AVERT", "exercise", ref_line, "bodyParts", "EX_BODY_PART_REF", f"Body part non trouvee dans le referentiel: {bodypart}", bodypart))
                        if status == "VALIDE":
                            status = "AVERTISSEMENT"
                for equipment in equipments:
                    if ref_equipments and equipment.lower() not in ref_equipments:
                        anomalies.append(build_anomaly(execution_id, lot_id, rule_ids.get("EX_EQUIP_REF"), "AVERT", "exercise", ref_line, "equipments", "EX_EQUIP_REF", f"Equipement non trouve dans le referentiel: {equipment}", equipment))
                        if status == "VALIDE":
                            status = "AVERTISSEMENT"
                for muscle in target_muscles + secondary_muscles:
                    if ref_muscles and muscle.lower() not in ref_muscles:
                        anomalies.append(build_anomaly(execution_id, lot_id, rule_ids.get("EX_MUSCLE_REF"), "AVERT", "exercise", ref_line, "targetMuscles", "EX_MUSCLE_REF", f"Muscle non trouve dans le referentiel: {muscle}", muscle))
                        if status == "VALIDE":
                            status = "AVERTISSEMENT"

                stg_records.append({
                    "lot_id": lot_id,
                    "entite": "exercise",
                    "ref_externe": exercise_id,
                    "source_payload_json": safe_json_dumps(ex),
                    "payload_normalise_json": safe_json_dumps(normalized),
                    "est_parseable": 1 if parseable else 0,
                    "statut_validation": status,
                    "code_rejet_potentiel": reject_code,
                })

                if status == "REJETE":
                    stats.lignes_invalides += 1
                    stats.nb_rejets += 1
                    rejects.append(build_reject(execution_id, lot_id, "exercise", exercise_id, ex, reject_code or "EX_REJECT", "Exercice rejete pendant validation"))
                    continue

                ensure_exercise(conn, source_id, normalized)
                stats.lignes_valides += 1

            insert_stg_records(conn, stg_records)
            insert_anomalies(conn, anomalies)
            insert_rejects(conn, rejects)
            set_lot_status(conn, lot_id, "NETTOYE", commentaire="ETL exercises termine")

        with engine.begin() as conn:
            finish_execution(conn, execution_id, "SUCCES", stats, message="ETL exercises termine")

        print(f"[EXERCISES] OK - lues={stats.lignes_lues} valides={stats.lignes_valides} invalides={stats.lignes_invalides} doublons={stats.nb_doublons_supprimes}")
    except Exception as exc:
        with engine.begin() as conn:
            finish_execution(conn, execution_id, "ECHEC", stats, message=str(exc)[:500])
        raise


if __name__ == "__main__":
    main()
