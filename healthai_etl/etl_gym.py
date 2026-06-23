from __future__ import annotations

import os
import random
from pathlib import Path

import pandas as pd
from sqlalchemy import text

from etl_common import (
    ExecutionStats,
    as_text,
    birthdate_from_age,
    build_anomaly,
    build_demo_datetime,
    build_reject,
    create_execution,
    create_lot,
    ensure_user_by_source_identity,
    finish_execution,
    get_engine,
    get_source_id,
    hours_to_minutes,
    insert_anomalies,
    insert_raw_records,
    insert_rejects,
    insert_stg_records,
    list_organisation_ids,
    normalize_gender_fr,
    parse_env_date,
    safe_json_dumps,
    seed_quality_rules,
    set_lot_status,
    stable_hash,
    to_float,
)

GYM_REQUIRED = [
    "Age", "Gender", "Weight (kg)", "Height (m)", "Max_BPM", "Avg_BPM", "Resting_BPM",
    "Session_Duration (hours)", "Calories_Burned", "Workout_Type", "Fat_Percentage",
    "Water_Intake (liters)", "Workout_Frequency (days/week)", "Experience_Level", "BMI",
]


def pick_demo_exercises(conn, workout_type: str, limit: int = 3) -> list[int]:
    workout = (workout_type or "").strip().lower()
    if workout == "strength":
        body_parts = {"upper arms", "chest", "back", "upper legs", "shoulders"}
    elif workout == "cardio":
        body_parts = {"upper legs", "waist", "back"}
    elif workout == "hiit":
        body_parts = {"upper legs", "back", "waist", "shoulders"}
    elif workout == "yoga":
        body_parts = {"waist", "back", "upper legs", "shoulders"}
    else:
        body_parts = {"upper legs", "back", "shoulders"}

    rows = conn.execute(text("SELECT exercice_id, body_part_principale FROM exercice ORDER BY exercice_id")).mappings().all()
    ids = [int(r["exercice_id"]) for r in rows if str(r.get("body_part_principale") or "").strip().lower() in body_parts]
    if ids:
        return ids[:limit]
    return [int(r["exercice_id"]) for r in rows[:limit]]


def split_total(total: float | None, n: int) -> list[float | None]:
    if n <= 0:
        return []
    if total is None:
        return [None] * n
    total = round(float(total), 2)
    if n == 1:
        return [total]
    base = round(total / n, 2)
    values = []
    remaining = total
    for i in range(n):
        if i == n - 1:
            part = round(remaining, 2)
        else:
            part = base
            remaining = round(remaining - part, 2)
        values.append(part)
    return values


def random_comment(rng: random.Random) -> str:
    comments = [
        "Cet exercice a ete un peu challengeant au debut, mais j'ai pu le surmonter et le realiser.",
        "Le mouvement demandait de la concentration, mais l'execution est devenue plus fluide au fil de la seance.",
        "Exercice bien realise apres quelques ajustements sur le rythme et la posture.",
        "Le debut etait exigeant, puis l'exercice a ete mieux maitrise avec une bonne regularite.",
    ]
    return rng.choice(comments)


def main() -> None:
    csv_path = os.getenv("GYM_CSV", str(Path(__file__).resolve().parent.parent / "gym_members_exercise_tracking.csv"))
    session_date = parse_env_date("GYM_SESSION_DATE")
    rng = random.Random(20260430)

    engine = get_engine()
    stats = ExecutionStats()
    anomalies: list[dict] = []
    rejects: list[dict] = []

    with engine.begin() as conn:
        source_id = get_source_id(conn, "Gym Members Exercise Tracking")
        execution_id = create_execution(conn, source_id)
        rule_ids = seed_quality_rules(conn)
        organisation_ids = list_organisation_ids(conn)

    try:
        df = pd.read_csv(csv_path)
        stats.lignes_lues = len(df)
        missing = [c for c in GYM_REQUIRED if c not in df.columns]
        if missing:
            raise RuntimeError(f"Colonnes manquantes: {missing}")

        df = df.reset_index(drop=True)
        df["__line_number"] = df.index + 2
        raw_rows = df[GYM_REQUIRED + ["__line_number"]].to_dict(orient="records")

        with engine.begin() as conn:
            lot_id = create_lot(conn, execution_id, source_id, f"gym_{pd.Timestamp.now():%Y%m%d_%H%M%S}")
            set_lot_status(conn, lot_id, "VALIDE")
            insert_raw_records(conn, lot_id, "gym", raw_rows)

            stg_records: list[dict] = []
            seen_rows: set[str] = set()

            for row_idx, row in enumerate(raw_rows, start=1):
                ref_line = str(row["__line_number"])
                raw_hash = stable_hash([row.get(c) for c in GYM_REQUIRED])
                if raw_hash in seen_rows:
                    stats.nb_doublons_supprimes += 1
                    anomalies.append(build_anomaly(execution_id, lot_id, None, "AVERT", "gym", ref_line, None, "GYM_DUPLICATE_ROW", "Ligne exacte dupliquee dans le lot gym"))
                    continue
                seen_rows.add(raw_hash)

                age = to_float(row.get("Age"))
                weight_kg = to_float(row.get("Weight (kg)"))
                height_m = to_float(row.get("Height (m)"))
                height_cm = None if height_m is None else round(height_m * 100.0, 2)
                bpm_max = to_float(row.get("Max_BPM"))
                bpm_avg = to_float(row.get("Avg_BPM"))
                bpm_rest = to_float(row.get("Resting_BPM"))
                duration_min = hours_to_minutes(row.get("Session_Duration (hours)"))
                calories = to_float(row.get("Calories_Burned"))
                fat_percentage = to_float(row.get("Fat_Percentage"))
                water_l = to_float(row.get("Water_Intake (liters)"))
                freq_week = to_float(row.get("Workout_Frequency (days/week)"))
                bmi = to_float(row.get("BMI"))
                workout_type = as_text(row.get("Workout_Type"))
                experience = as_text(row.get("Experience_Level"))
                genre_fr = normalize_gender_fr(row.get("Gender"))

                normalized = {
                    "age_source": age,
                    "genre_source": genre_fr,
                    "poids_kg": weight_kg,
                    "taille_cm": height_cm,
                    "imc": bmi,
                    "taux_masse_grasse": fat_percentage,
                    "bpm_repos": bpm_rest,
                    "bpm_moyen": bpm_avg,
                    "bpm_max": bpm_max,
                    "eau_l": water_l,
                    "type_entrainement": workout_type,
                    "duree_seance_min": duration_min,
                    "calories_brulees_total": calories,
                    "frequence_entrainement_j_sem": freq_week,
                    "niveau_experience": experience,
                }

                parseable = True
                status = "VALIDE"
                reject_code = None
                corrected = 0

                if weight_kg is None or not (20 <= weight_kg <= 350):
                    parseable = False
                    status = "REJETE"
                    reject_code = "GYM_WEIGHT_RANGE"
                    anomalies.append(build_anomaly(execution_id, lot_id, rule_ids.get("GYM_WEIGHT_RANGE"), "ERREUR", "gym", ref_line, "Weight (kg)", "GYM_WEIGHT_RANGE", f"Poids invalide ou hors plage: {row.get('Weight (kg)')}", row.get("Weight (kg)")))

                if height_m is None or not (0.8 <= height_m <= 2.5):
                    parseable = False
                    status = "REJETE"
                    reject_code = "GYM_HEIGHT_RANGE"
                    anomalies.append(build_anomaly(execution_id, lot_id, rule_ids.get("GYM_HEIGHT_RANGE"), "ERREUR", "gym", ref_line, "Height (m)", "GYM_HEIGHT_RANGE", f"Taille invalide ou hors plage: {row.get('Height (m)')}", row.get("Height (m)")))

                if bpm_max is not None and bpm_avg is not None and bpm_rest is not None and not (bpm_max >= bpm_avg >= bpm_rest):
                    parseable = False
                    status = "REJETE"
                    reject_code = "GYM_BPM_ORDER"
                    anomalies.append(build_anomaly(execution_id, lot_id, rule_ids.get("GYM_BPM_ORDER"), "ERREUR", "gym", ref_line, "BPM", "GYM_BPM_ORDER", f"Ordre BPM incoherent: max={bpm_max}, avg={bpm_avg}, rest={bpm_rest}"))

                if weight_kg is not None and height_m is not None and bmi is not None:
                    recomputed_bmi = round(weight_kg / (height_m * height_m), 2)
                    if abs(recomputed_bmi - bmi) > 1.0:
                        anomalies.append(build_anomaly(execution_id, lot_id, rule_ids.get("GYM_IMC_COH"), "AVERT", "gym", ref_line, "BMI", "GYM_IMC_COH", f"IMC dataset={bmi} different du recalcul={recomputed_bmi}", bmi))
                        if status == "VALIDE":
                            status = "AVERTISSEMENT"
                        normalized["imc"] = recomputed_bmi
                        corrected += 1

                if water_l is None:
                    normalized["eau_l"] = 0.0
                    corrected += 1

                gym_external_id = f"GYM_MEMBER_{row_idx:06d}"
                stg_records.append({
                    "lot_id": lot_id,
                    "entite": "gym",
                    "ref_externe": gym_external_id,
                    "source_payload_json": safe_json_dumps(row),
                    "payload_normalise_json": safe_json_dumps(normalized),
                    "est_parseable": 1 if parseable else 0,
                    "statut_validation": status,
                    "code_rejet_potentiel": reject_code,
                })

                if status == "REJETE":
                    stats.lignes_invalides += 1
                    stats.nb_rejets += 1
                    rejects.append(build_reject(execution_id, lot_id, "gym", gym_external_id, row, reject_code or "GYM_REJECT", "Ligne gym rejetee pendant validation"))
                    continue

                utilisateur_id = ensure_user_by_source_identity(
                    conn,
                    source_id,
                    gym_external_id,
                    f"@gym.member.{row_idx:06d}",
                    organisation_id=rng.choice(organisation_ids) if organisation_ids else 1,
                    defaults={
                        "genre": genre_fr,
                        "taille_cm": height_cm,
                        "date_naissance": birthdate_from_age(int(age)) if age is not None else None,
                        "role": "UTILISATEUR",
                        "statut": "ACTIF",
                    },
                )

                conn.execute(
                    text(
                        """
                        UPDATE utilisateur
                           SET genre = COALESCE(NULLIF(genre, 'Inconnu'), :genre, genre),
                               taille_cm = COALESCE(taille_cm, :taille_cm),
                               date_naissance = COALESCE(date_naissance, :date_naissance),
                               modifie_le = NOW()
                         WHERE utilisateur_id = :utilisateur_id
                        """
                    ),
                    {
                        "utilisateur_id": utilisateur_id,
                        "genre": genre_fr,
                        "taille_cm": height_cm,
                        "date_naissance": birthdate_from_age(int(age)) if age is not None else None,
                    },
                )

                measure_dt = build_demo_datetime(session_date, 18, row_idx)
                existing_measure = conn.execute(text("SELECT mesure_id FROM mesure_biometrique WHERE utilisateur_id = :uid AND mesure_le = :mesure_le LIMIT 1"), {"uid": utilisateur_id, "mesure_le": measure_dt}).mappings().first()
                if not existing_measure:
                    conn.execute(
                        text(
                            """
                            INSERT INTO mesure_biometrique (
                              utilisateur_id, source_id, lot_id, mesure_le, age_source, genre_source,
                              poids_kg, taille_cm, imc, taux_masse_grasse,
                              bpm_repos, bpm_moyen, bpm_max, eau_l, cree_le
                            ) VALUES (
                              :utilisateur_id, :source_id, :lot_id, :mesure_le, :age_source, :genre_source,
                              :poids_kg, :taille_cm, :imc, :taux_masse_grasse,
                              :bpm_repos, :bpm_moyen, :bpm_max, :eau_l, NOW()
                            )
                            """
                        ),
                        {
                            "utilisateur_id": utilisateur_id,
                            "source_id": source_id,
                            "lot_id": lot_id,
                            "mesure_le": measure_dt,
                            "age_source": int(age) if age is not None else None,
                            "genre_source": genre_fr,
                            "poids_kg": weight_kg,
                            "taille_cm": height_cm,
                            "imc": normalized["imc"],
                            "taux_masse_grasse": fat_percentage,
                            "bpm_repos": int(bpm_rest) if bpm_rest is not None else None,
                            "bpm_moyen": int(bpm_avg) if bpm_avg is not None else None,
                            "bpm_max": int(bpm_max) if bpm_max is not None else None,
                            "eau_l": normalized["eau_l"],
                        },
                    )

                existing_session = conn.execute(
                    text(
                        """
                        SELECT seance_id
                          FROM seance_entrainement
                         WHERE utilisateur_id = :uid
                           AND date_seance = :date_seance
                           AND type_entrainement = :type_entrainement
                         LIMIT 1
                        """
                    ),
                    {"uid": utilisateur_id, "date_seance": measure_dt, "type_entrainement": workout_type or "AUTRE"},
                ).mappings().first()
                if existing_session:
                    seance_id = int(existing_session["seance_id"])
                else:
                    session_insert = conn.execute(
                        text(
                            """
                            INSERT INTO seance_entrainement (
                              utilisateur_id, source_id, lot_id, date_seance, type_entrainement,
                              duree_seance_min, calories_brulees_total, frequence_entrainement_j_sem,
                              niveau_experience, eau_l, cree_le
                            ) VALUES (
                              :utilisateur_id, :source_id, :lot_id, :date_seance, :type_entrainement,
                              :duree_seance_min, :calories_brulees_total, :frequence_entrainement_j_sem,
                              :niveau_experience, :eau_l, NOW()
                            )
                            """
                        ),
                        {
                            "utilisateur_id": utilisateur_id,
                            "source_id": source_id,
                            "lot_id": lot_id,
                            "date_seance": measure_dt,
                            "type_entrainement": workout_type or "AUTRE",
                            "duree_seance_min": duration_min,
                            "calories_brulees_total": calories,
                            "frequence_entrainement_j_sem": freq_week,
                            "niveau_experience": experience,
                            "eau_l": normalized["eau_l"],
                        },
                    )
                    seance_id = int(session_insert.lastrowid)

                exercise_ids = pick_demo_exercises(conn, workout_type or "")
                if exercise_ids:
                    calories_parts = split_total(calories, len(exercise_ids))
                    duree_parts = split_total(float(duration_min) if duration_min is not None else None, len(exercise_ids))
                    for order_idx, exercice_id in enumerate(exercise_ids, start=1):
                        exists_ex = conn.execute(
                            text(
                                """
                                SELECT seance_exercice_id
                                  FROM seance_exercice
                                 WHERE seance_id = :seance_id
                                   AND ordre_exercice = :ordre_exercice
                                 LIMIT 1
                                """
                            ),
                            {"seance_id": seance_id, "ordre_exercice": order_idx},
                        ).mappings().first()
                        if exists_ex:
                            continue
                        conn.execute(
                            text(
                                """
                                INSERT INTO seance_exercice (
                                  seance_id, exercice_id, ordre_exercice, series_nb, repetitions_nb,
                                  charge_kg, duree_min, calories_brulees_estimees, commentaire, cree_le
                                ) VALUES (
                                  :seance_id, :exercice_id, :ordre_exercice, :series_nb, :repetitions_nb,
                                  :charge_kg, :duree_min, :calories_brulees_estimees, :commentaire, NOW()
                                )
                                """
                            ),
                            {
                                "seance_id": seance_id,
                                "exercice_id": exercice_id,
                                "ordre_exercice": order_idx,
                                "series_nb": rng.randint(2, 5),
                                "repetitions_nb": rng.randint(1, 5),
                                "charge_kg": round((weight_kg or 40.0) * rng.uniform(0.12, 0.35), 2),
                                "duree_min": duree_parts[order_idx - 1],
                                "calories_brulees_estimees": calories_parts[order_idx - 1],
                                "commentaire": random_comment(rng),
                            },
                        )

                stats.nb_valeurs_corrigees += corrected
                stats.lignes_valides += 1

            insert_stg_records(conn, stg_records)
            insert_anomalies(conn, anomalies)
            insert_rejects(conn, rejects)
            set_lot_status(conn, lot_id, "NETTOYE", commentaire="ETL gym termine")

        with engine.begin() as conn:
            finish_execution(conn, execution_id, "SUCCES", stats, message="ETL gym termine")

        print(f"[GYM] OK - lues={stats.lignes_lues} valides={stats.lignes_valides} invalides={stats.lignes_invalides} doublons={stats.nb_doublons_supprimes}")
    except Exception as exc:
        with engine.begin() as conn:
            finish_execution(conn, execution_id, "ECHEC", stats, message=str(exc)[:500])
        raise


if __name__ == "__main__":
    main()
